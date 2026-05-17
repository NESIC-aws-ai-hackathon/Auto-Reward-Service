"""
LIFF ダッシュボード API ハンドラー（Unit 7）

設計方針:
- LIFF ID Token から LINE ユーザー ID を抽出（簡易検証）
- /api/{path} をルーティングし各ハンドラーに振り分け
- /liff で HTML を直接配信（ハッカソンスコープ: S3不要）
- 全レスポンスに CORS ヘッダーを付与
- DynamoDB Decimal → int 変換で JSON 互換性を担保
"""
from __future__ import annotations

import base64
import json
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from models.schemas import (
    SK_GOOGLE_OAUTH,
    SK_PREFIX_EXPENSE,
    SK_PREFIX_REWARD_POOL,
    SK_PREFIX_REWARD_SUGGESTION,
    SK_PREFIX_MONTHLY_SUMMARY,
    SK_PROFILE,
)
from services.dynamodb_service import DynamoDBService
from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
_JST = timezone(timedelta(hours=9))
LIFF_CHANNEL_ID = os.environ.get("LIFF_CHANNEL_ID", "")
ALLOWED_ORIGINS = ["https://liff.line.me"]
VALID_TONES = {"friendly", "polite", "devilish"}
MAX_EXPENSES = 50
MAX_SUGGESTIONS = 20
# 設定更新で許可するフィールド
ALLOWED_SETTINGS_FIELDS = {
    "tone", "reward_budget_monthly", "carryover_rate",
    "nickname", "bonus_months", "bonus_amount",
}


# ─────────────────────────────────────────
# JSON シリアライズ
# ─────────────────────────────────────────

def _decimal_default(obj: Any) -> Any:
    """Decimal → int/float 変換（json.dumps の default 引数用）"""
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ─────────────────────────────────────────
# レスポンスヘルパー
# ─────────────────────────────────────────

def _make_response(status: int, body: dict) -> dict:
    """CORS ヘッダー付き JSON レスポンスを構築する"""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "https://liff.line.me",
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
            "Access-Control-Allow-Methods": "GET,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body, ensure_ascii=False, default=_decimal_default),
    }


# ─────────────────────────────────────────
# 認証
# ─────────────────────────────────────────

def _extract_user_id(event: dict) -> Optional[str]:
    """
    LIFF ID Token（JWT）から LINE ユーザー ID を抽出する。

    ハッカソンスコープ: 署名検証なし（aud + exp チェックのみ）。
    本番環境では LINE の公開鍵による署名検証が必要。
    """
    headers = event.get("headers") or {}
    auth = headers.get("authorization", headers.get("Authorization", ""))
    token = auth.replace("Bearer ", "").strip()
    if not token:
        return None

    try:
        # JWT ペイロード部分をデコード（header.payload.signature の 2 番目）
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # パディング補完
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)

        # aud 検証（LIFF Channel ID と一致すること）
        channel_id = os.environ.get("LIFF_CHANNEL_ID", "") or LIFF_CHANNEL_ID
        if channel_id and payload.get("aud") != channel_id:
            logger.warning("liff_token_aud_mismatch", aud=payload.get("aud"))
            return None

        # exp 検証
        exp = payload.get("exp", 0)
        if exp < time.time():
            logger.warning("liff_token_expired")
            return None

        return payload.get("sub")  # LINE ユーザー ID
    except Exception as e:
        logger.warning("liff_token_decode_failed", error=str(e))
        return None


# ─────────────────────────────────────────
# API ハンドラー
# ─────────────────────────────────────────

def _handle_dashboard(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/dashboard — ダッシュボード統合情報"""
    pk = f"USER#{user_id}"

    # プロファイル
    profile = ddb.get_item(pk=pk, sk=SK_PROFILE) or {}

    # 今月サマリー
    now = datetime.now(_JST)
    month_str = now.strftime("%Y-%m")
    summary_sk = f"{SK_PREFIX_MONTHLY_SUMMARY}{month_str}"
    summary = ddb.get_item(pk=pk, sk=summary_sk) or {}

    # 最新提案（3件）
    suggestions = ddb.query_by_pk(
        pk=pk,
        sk_prefix=SK_PREFIX_REWARD_SUGGESTION,
        limit=3,
        descending=True,
    )

    return _make_response(200, {
        "nickname": profile.get("nickname"),
        "tone": profile.get("tone", "friendly"),
        "monthly_summary": {
            "total_budget": int(summary.get("total_budget", 0)),
            "total_spent": int(summary.get("total_amount", 0)),
            "remaining": int(summary.get("total_budget", 0)) - int(summary.get("total_amount", 0)),
            "carryover_amount": int(summary.get("carryover_amount", 0)),
            "expense_count": int(summary.get("expense_count", 0)),
        },
        "recent_suggestions": [
            {
                "item_name": s.get("item_name"),
                "price": int(s["price"]) if s.get("price") is not None else None,
                "proposed_at": s.get("proposed_at"),
                "outcome": s.get("outcome"),
            }
            for s in suggestions
        ],
    })


def _handle_expenses(user_id: str, ddb: DynamoDBService, query: dict) -> dict:
    """GET /api/expenses — 支出履歴"""
    pk = f"USER#{user_id}"
    month = query.get("month") or datetime.now(_JST).strftime("%Y-%m")
    sk_prefix = f"{SK_PREFIX_EXPENSE}{month}"

    items = ddb.query_by_pk(pk=pk, sk_prefix=sk_prefix, limit=MAX_EXPENSES, descending=True)

    return _make_response(200, {
        "month": month,
        "expenses": [
            {
                "sk": item.get("SK", ""),
                "item_name": item.get("item_name"),
                "amount": int(item.get("amount", 0)),
                "ars_category": item.get("ars_category"),
                "created_at": item.get("created_at"),
            }
            for item in items
        ],
    })


def _handle_update_expense(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """PUT /api/expenses — 支出金額・品名の手動修正"""
    pk = f"USER#{user_id}"
    sk = body.get("sk", "").strip()
    if not sk.startswith(SK_PREFIX_EXPENSE):
        return _make_response(400, {"error": "無効な支出IDです"})

    # 既存アイテム取得
    existing = ddb.get_item(pk=pk, sk=sk)
    if not existing:
        return _make_response(404, {"error": "支出が見つかりません"})

    updates: dict[str, Any] = {}
    old_amount = int(existing.get("amount", 0))
    new_amount = old_amount

    if "amount" in body:
        try:
            new_amount = int(body["amount"])
            if not (1 <= new_amount <= 9_999_999):
                return _make_response(400, {"error": "金額は 1〜9,999,999 円で指定してください"})
            updates["amount"] = new_amount
        except (ValueError, TypeError):
            return _make_response(400, {"error": "amount は整数を指定してください"})

    if "item_name" in body:
        name = str(body["item_name"]).strip()
        if not (1 <= len(name) <= 100):
            return _make_response(400, {"error": "品名は 1〜100 文字で指定してください"})
        updates["item_name"] = name

    if not updates:
        return _make_response(400, {"error": "更新するフィールドがありません"})

    updates["updated_at"] = datetime.now(_JST).isoformat()
    updates["corrected"] = True
    ddb.update_item(pk=pk, sk=sk, updates=updates)

    # 月次サマリーの total_amount を差分調整
    delta = new_amount - old_amount
    if delta != 0:
        try:
            prefix_len = len(SK_PREFIX_EXPENSE)
            expense_month = sk[prefix_len:prefix_len + 7]  # "YYYY-MM"
            month_sk = f"{SK_PREFIX_MONTHLY_SUMMARY}{expense_month}"
            monthly = ddb.get_item(pk=pk, sk=month_sk)
            if monthly:
                current_total = int(monthly.get("total_amount", 0))
                ddb.update_item(
                    pk=pk,
                    sk=month_sk,
                    updates={"total_amount": max(0, current_total + delta)},
                )
        except Exception as e:
            logger.warning("liff_expense_monthly_adjust_failed", error=str(e))

    return _make_response(200, {"updated": True, "delta": delta})


def _handle_monthly_chart(user_id: str, ddb: DynamoDBService, query: dict) -> dict:
    """GET /api/monthly-chart — 過去N月分の支出グラフデータ"""
    pk = f"USER#{user_id}"
    try:
        months_count = min(int(query.get("months", 6)), 12)
    except (ValueError, TypeError):
        months_count = 6

    # 過去 N 月分の "YYYY-MM" リストを昇順で生成
    now = datetime.now(_JST)
    month_list: list[str] = []
    year, month = now.year, now.month
    for _ in range(months_count):
        month_list.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    month_list.reverse()

    # DynamoDB から月次サマリーを取得
    items = ddb.query_by_pk(
        pk=pk,
        sk_prefix=SK_PREFIX_MONTHLY_SUMMARY,
        limit=months_count + 2,
        descending=True,
    )
    summary_map = {
        item.get("SK", "").replace(SK_PREFIX_MONTHLY_SUMMARY, ""): item
        for item in items
    }

    data = []
    for m in month_list:
        s = summary_map.get(m, {})
        budget = int(s.get("reward_budget", s.get("total_budget", 0)))
        data.append({
            "month": m,
            "total_spent": int(s.get("total_amount", 0)),
            "budget": budget,
        })

    return _make_response(200, {"data": data})


def _handle_history(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/history — ご褒美提案履歴"""
    pk = f"USER#{user_id}"
    items = ddb.query_by_pk(
        pk=pk,
        sk_prefix=SK_PREFIX_REWARD_SUGGESTION,
        limit=MAX_SUGGESTIONS,
        descending=True,
    )

    return _make_response(200, {
        "suggestions": [
            {
                "item_name": item.get("item_name"),
                "price": int(item["price"]) if item.get("price") is not None else None,
                "proposed_at": item.get("proposed_at"),
                "outcome": item.get("outcome"),
            }
            for item in items
        ],
    })


def _handle_pool(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/pool — ご褒美候補一覧"""
    pk = f"USER#{user_id}"
    pool_item = ddb.get_item(pk=pk, sk=SK_PREFIX_REWARD_POOL) or {}
    raw_items = pool_item.get("items") or []

    # スコア降順ソート
    sorted_items = sorted(raw_items, key=lambda x: float(x.get("score", 0)), reverse=True)

    return _make_response(200, {
        "items": [
            {
                "name": item.get("name"),
                "price": int(item.get("price", 0)),
                "category": item.get("category"),
                "score": float(item.get("score", 0)),
                "type": item.get("type", "product"),
                "image_url": item.get("image_url"),
                "source_url": item.get("source_url"),
            }
            for item in sorted_items
        ],
    })


def _handle_get_settings(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/settings — 設定取得（固定費・記念日含む）"""
    pk = f"USER#{user_id}"
    profile = ddb.get_item(pk=pk, sk=SK_PROFILE) or {}
    fixed_costs_item = ddb.get_item(pk=pk, sk="FIXED_COSTS#") or {}

    return _make_response(200, {
        "tone": profile.get("tone", "friendly"),
        "reward_budget_monthly": int(profile.get("reward_budget_monthly", 0)),
        "monthly_income": int(profile.get("monthly_income", 0)),
        "bonus_months": profile.get("bonus_months") or [],
        "bonus_amount": int(profile.get("bonus_amount", 0)),
        "carryover_rate": float(profile.get("carryover_rate", 0.5)),
        "nickname": profile.get("nickname"),
        "fixed_costs": fixed_costs_item.get("items") or [],
        "anniversaries": profile.get("anniversaries") or [],
    })


def _handle_delete_expense(user_id: str, ddb: DynamoDBService, query: dict) -> dict:
    """DELETE /api/expenses?sk=EXPENSE#... — 支出削除"""
    pk = f"USER#{user_id}"
    sk = query.get("sk", "").strip()
    if not sk.startswith(SK_PREFIX_EXPENSE):
        return _make_response(400, {"error": "無効な支出IDです"})

    existing = ddb.get_item(pk=pk, sk=sk)
    if not existing:
        return _make_response(404, {"error": "支出が見つかりません"})

    amount = int(existing.get("amount", 0))
    ddb.delete_item(pk=pk, sk=sk)

    # 月次サマリーを差分調整
    try:
        prefix_len = len(SK_PREFIX_EXPENSE)
        expense_month = sk[prefix_len:prefix_len + 7]  # "YYYY-MM"
        month_sk = f"{SK_PREFIX_MONTHLY_SUMMARY}{expense_month}"
        monthly = ddb.get_item(pk=pk, sk=month_sk)
        if monthly:
            current_total = int(monthly.get("total_amount", 0))
            current_count = int(monthly.get("expense_count", 0))
            ddb.update_item(
                pk=pk,
                sk=month_sk,
                updates={
                    "total_amount": max(0, current_total - amount),
                    "expense_count": max(0, current_count - 1),
                },
            )
    except Exception as e:
        logger.warning("liff_expense_delete_monthly_adjust_failed", error=str(e))

    return _make_response(200, {"deleted": True})


def _handle_update_settings(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """PUT /api/settings — 設定更新"""
    pk = f"USER#{user_id}"
    updates: dict[str, Any] = {}

    # ホワイトリスト方式: 許可フィールドのみ処理
    if "tone" in body:
        if body["tone"] not in VALID_TONES:
            return _make_response(400, {"error": f"tone は {VALID_TONES} のいずれかを指定してください"})
        updates["tone"] = body["tone"]

    if "reward_budget_monthly" in body:
        try:
            val = int(body["reward_budget_monthly"])
            if val <= 0:
                return _make_response(400, {"error": "reward_budget_monthly は正の整数を指定してください"})
            updates["reward_budget_monthly"] = Decimal(str(val))
        except (ValueError, TypeError):
            return _make_response(400, {"error": "reward_budget_monthly は数値を指定してください"})

    if "carryover_rate" in body:
        try:
            rate = float(body["carryover_rate"])
            if not (0.0 <= rate <= 1.0):
                return _make_response(400, {"error": "carryover_rate は 0.0〜1.0 の範囲で指定してください"})
            updates["carryover_rate"] = Decimal(str(rate))
        except (ValueError, TypeError):
            return _make_response(400, {"error": "carryover_rate は数値を指定してください"})

    if "nickname" in body:
        nick = str(body["nickname"]).strip()
        if not (1 <= len(nick) <= 20):
            return _make_response(400, {"error": "nickname は 1〜20 文字で指定してください"})
        updates["nickname"] = nick

    if "bonus_months" in body:
        bm = body["bonus_months"]
        if isinstance(bm, list) and all(isinstance(m, int) and 1 <= m <= 12 for m in bm):
            updates["bonus_months"] = bm
        else:
            return _make_response(400, {"error": "bonus_months は 1〜12 の整数リストを指定してください"})

    if "bonus_amount" in body:
        try:
            val = int(body["bonus_amount"])
            if val < 0:
                return _make_response(400, {"error": "bonus_amount は 0 以上を指定してください"})
            updates["bonus_amount"] = val
        except (ValueError, TypeError):
            return _make_response(400, {"error": "bonus_amount は数値を指定してください"})

    if not updates:
        return _make_response(400, {"error": "更新するフィールドがありません"})

    updates["updated_at"] = datetime.now(_JST).isoformat()
    ddb.update_item(pk=pk, sk=SK_PROFILE, updates=updates)

    return _make_response(200, {"updated": True})


def _handle_calendar_auth(user_id: str) -> dict:
    """GET /api/calendar/auth — Google OAuth 認証 URL を返す"""
    try:
        from utils.secrets import get_google_secrets
        secrets = get_google_secrets()
        client_id = secrets.get("client_id", "")
        redirect_uri = secrets.get("redirect_uri", "")
    except Exception:
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "")

    if not client_id or not redirect_uri:
        return _make_response(503, {"error": "Google Calendar 連携はまだ設定されていません"})

    import urllib.parse
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar.events.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": user_id,  # CSRF 対策: user_id をステートに埋め込む
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return _make_response(200, {"auth_url": auth_url})


def _handle_calendar_callback(user_id: str, ddb: DynamoDBService, query: dict) -> dict:
    """GET /api/calendar/callback — Google OAuth コールバック処理"""
    code = query.get("code", "")
    state = query.get("state", "")

    # state 検証（CSRF 対策）
    if state != user_id:
        return _make_response(400, {"error": "不正なリクエストです"})

    if not code:
        return _make_response(400, {"error": "認証コードが見つかりません"})

    try:
        from utils.secrets import get_google_secrets
        secrets = get_google_secrets()
        client_id = secrets.get("client_id", "")
        client_secret = secrets.get("client_secret", "")
        redirect_uri = secrets.get("redirect_uri", "")
    except Exception as e:
        logger.warning("google_secrets_failed", error=str(e))
        return _make_response(500, {"error": "認証設定の読み込みに失敗しました"})

    # authorization_code → tokens 交換
    import requests as req
    try:
        token_resp = req.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()
    except Exception as e:
        logger.warning("google_token_exchange_failed", error=str(e))
        return _make_response(500, {"error": "トークン取得に失敗しました"})

    refresh_token = tokens.get("refresh_token", "")
    if not refresh_token:
        return _make_response(400, {"error": "refresh_token が取得できませんでした。再度連携してください"})

    # DynamoDB に保存（refresh_token は機密情報）
    pk = f"USER#{user_id}"
    now = datetime.now(_JST).isoformat()
    ddb.put_item(pk, SK_GOOGLE_OAUTH, {
        "entityType": "GOOGLE_OAUTH",
        "refresh_token": refresh_token,
        "connected_at": now,
    })
    logger.info("google_calendar_connected", user_id=user_id)

    # LIFF ダッシュボードにリダイレクト
    api_base = os.environ.get("LIFF_URL", "")
    redirect_url = f"{api_base}/liff" if api_base else "/liff"
    return {
        "statusCode": 302,
        "headers": {
            "Location": redirect_url,
            "Access-Control-Allow-Origin": "https://liff.line.me",
        },
        "body": "",
    }


def _handle_calendar_status(user_id: str, ddb: DynamoDBService) -> dict:
    pk = f"USER#{user_id}"
    oauth = ddb.get_item(pk=pk, sk=SK_GOOGLE_OAUTH)

    return _make_response(200, {
        "connected": oauth is not None,
        "connected_at": oauth.get("connected_at") if oauth else None,
    })


def _handle_calendar_disconnect(user_id: str, ddb: DynamoDBService) -> dict:
    """POST /api/calendar/disconnect — カレンダー連携解除"""
    pk = f"USER#{user_id}"

    # Google Token Revoke は best-effort（省略: ハッカソンスコープ）
    try:
        ddb.delete_item(pk=pk, sk=SK_GOOGLE_OAUTH)
    except Exception as e:
        logger.warning("calendar_disconnect_failed", error=str(e))
        return _make_response(500, {"error": "連携解除に失敗しました"})

    return _make_response(200, {"disconnected": True})


# ─────────────────────────────────────────
# LIFF HTML 配信
# ─────────────────────────────────────────

def _serve_liff_html() -> dict:
    """LIFF ダッシュボードの HTML を直接配信する"""
    html_path = Path(__file__).parent / "liff" / "index.html"
    if not html_path.exists():
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/plain"},
            "body": "LIFF page not found",
        }
    html = html_path.read_text(encoding="utf-8")
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
        },
        "body": html,
    }


def _serve_onboarding_html() -> dict:
    """オンボーディングフォームの HTML を配信する"""
    html_path = Path(__file__).parent / "liff" / "onboarding.html"
    if not html_path.exists():
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/plain"},
            "body": "Onboarding page not found",
        }
    html = html_path.read_text(encoding="utf-8")
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
        },
        "body": html,
    }


def _handle_streak(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/streak — ストリーク情報"""
    pk = f"USER#{user_id}"
    streak = ddb.get_item(pk=pk, sk="STREAK#") or {}
    return _make_response(200, {
        "current_streak": int(streak.get("current_streak", 0)),
        "longest_streak": int(streak.get("longest_streak", 0)),
        "last_record_date": streak.get("last_record_date", ""),
    })


# ─────────────────────────────────────────
# メインルーター
# ─────────────────────────────────────────

# DynamoDB シングルトン
_ddb: Optional[DynamoDBService] = None


def _get_ddb() -> DynamoDBService:
    global _ddb
    if _ddb is None:
        _ddb = DynamoDBService()
    return _ddb


def handler(event: dict, context: Any) -> dict:
    """Lambda ハンドラー（API Gateway HttpApi v2 payload format 2.0）"""
    logger.info("liff_api_request", path=event.get("rawPath"), method=event.get("requestContext", {}).get("http", {}).get("method"))

    # LIFF ページ配信
    raw_path = event.get("rawPath", "")
    http_method = (event.get("requestContext", {}).get("http", {}).get("method", "GET")).upper()

    # OPTIONS（CORS プリフライト）
    if http_method == "OPTIONS":
        return _make_response(200, {})

    # /liff → HTML 配信
    if raw_path == "/liff":
        return _serve_liff_html()

    # /liff/onboarding → オンボーディングフォーム HTML
    if raw_path == "/liff/onboarding":
        return _serve_onboarding_html()

    # /api/* → 認証必須
    user_id = _extract_user_id(event)
    if not user_id:
        return _make_response(401, {"error": "認証が必要です"})

    ddb = _get_ddb()
    query = event.get("queryStringParameters") or {}

    try:
        # ルーティング
        if raw_path == "/api/dashboard" and http_method == "GET":
            return _handle_dashboard(user_id, ddb)
        elif raw_path == "/api/expenses" and http_method == "GET":
            return _handle_expenses(user_id, ddb, query)
        elif raw_path == "/api/expenses" and http_method == "PUT":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_update_expense(user_id, ddb, body)
        elif raw_path == "/api/expenses" and http_method == "DELETE":
            return _handle_delete_expense(user_id, ddb, query)
        elif raw_path == "/api/monthly-chart" and http_method == "GET":
            return _handle_monthly_chart(user_id, ddb, query)
        elif raw_path == "/api/history" and http_method == "GET":
            return _handle_history(user_id, ddb)
        elif raw_path == "/api/pool" and http_method == "GET":
            return _handle_pool(user_id, ddb)
        elif raw_path == "/api/settings" and http_method == "GET":
            return _handle_get_settings(user_id, ddb)
        elif raw_path == "/api/settings" and http_method == "PUT":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_update_settings(user_id, ddb, body)
        elif raw_path == "/api/calendar/status" and http_method == "GET":
            return _handle_calendar_status(user_id, ddb)
        elif raw_path == "/api/calendar/disconnect" and http_method == "POST":
            return _handle_calendar_disconnect(user_id, ddb)
        elif raw_path == "/api/calendar/auth" and http_method == "GET":
            return _handle_calendar_auth(user_id)
        elif raw_path == "/api/calendar/callback" and http_method == "GET":
            return _handle_calendar_callback(user_id, ddb, query)
        elif raw_path == "/api/onboarding" and http_method == "POST":
            from handlers.liff_onboarding import _handle_onboarding
            return _handle_onboarding(user_id, event)
        elif raw_path == "/api/streak" and http_method == "GET":
            return _handle_streak(user_id, ddb)
        else:
            return _make_response(404, {"error": "Not Found"})
    except Exception as e:
        logger.error("liff_api_error", error=str(e), path=raw_path)
        return _make_response(500, {"error": "内部エラーが発生しました"})
