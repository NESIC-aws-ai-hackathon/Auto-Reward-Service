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

def _get_user_id_from_access_token(token: str) -> Optional[str]:
    """LINE アクセストークンから userId を取得（LINE Profile API 呼び出し）"""
    import urllib.request as _ureq
    import urllib.error as _uerr
    try:
        req = _ureq.Request(
            "https://api.line.me/v2/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        with _ureq.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            user_id = data.get("userId")
            if user_id:
                logger.info("access_token_auth_ok", user_id=user_id[:8] + "***")
            return user_id
    except _uerr.HTTPError as e:
        # 401/403 = トークン無効 → None (認証失敗)
        if e.code in (401, 403):
            logger.warning("access_token_invalid", status=e.code)
            return None
        # 5xx = LINE API 一時障害 → "LINE_API_ERROR" を返してフロントが区別可能にする
        logger.warning("line_api_error", status=e.code, error=str(e))
        return "__LINE_API_ERROR__"
    except Exception as e:
        # タイムアウト等のネットワークエラー → API 障害扱い
        logger.warning("access_token_network_error", error=str(e))
        return "__LINE_API_ERROR__"


def _extract_user_id(event: dict) -> Optional[str]:
    """
    Authorization ヘッダーのトークンから LINE ユーザー ID を抽出する。

    優先順位:
    1. Authorization: Bearer <token> → LINE Profile API / JWT 検証
    2. X-ARS-User-Id: <userId> → PWA キャッシュフォールバック（ハッカソン用）
    """
    headers = event.get("headers") or {}
    auth = headers.get("authorization", headers.get("Authorization", ""))
    token = auth.replace("Bearer ", "").strip()

    # Bearer トークンがある場合 → 通常の認証フロー
    if token:
        # JWT でない場合（"." が2つない）→ LINE アクセストークン
        if token.count(".") != 2:
            result = _get_user_id_from_access_token(token)
            if result and result != "__LINE_API_ERROR__":
                return result
            if result == "__LINE_API_ERROR__":
                return "__LINE_API_ERROR__"
            # トークン無効 → フォールバックへ
        else:
            # JWT（LIFF ID Token）のデコード
            try:
                parts = token.split(".")
                payload_b64 = parts[1]
                padding = 4 - len(payload_b64) % 4
                if padding != 4:
                    payload_b64 += "=" * padding
                payload_bytes = base64.urlsafe_b64decode(payload_b64)
                payload = json.loads(payload_bytes)

                # aud 検証（LIFF Channel ID と一致すること）
                channel_id = os.environ.get("LIFF_CHANNEL_ID", "") or LIFF_CHANNEL_ID
                if channel_id and payload.get("aud") != channel_id:
                    logger.warning("liff_token_aud_mismatch", aud=payload.get("aud"))
                else:
                    # exp 検証（24時間の猶予: ハッカソンスコープ）
                    exp = payload.get("exp", 0)
                    if exp + 86400 < time.time():
                        logger.warning("liff_token_very_expired", exp=exp)
                    else:
                        sub = payload.get("sub")
                        if sub:
                            return sub
            except Exception as e:
                logger.warning("liff_token_decode_failed", error=str(e))

    # フォールバック: X-ARS-User-Id ヘッダー（PWA キャッシュ認証）
    cached_uid = headers.get("x-ars-user-id", headers.get("X-ARS-User-Id", "")).strip()
    if cached_uid and cached_uid.startswith("U") and len(cached_uid) > 10:
        logger.info("auth_fallback_cached_uid", user_id=cached_uid[:8] + "***")
        return cached_uid

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
        "push_cooldown_hours": int(profile.get("push_cooldown_hours", 1)),
        "push_suggest_threshold": int(profile.get("push_suggest_threshold", 40)),
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

    if "push_cooldown_hours" in body:
        try:
            val = int(body["push_cooldown_hours"])
            if not (0 <= val <= 24):
                return _make_response(400, {"error": "push_cooldown_hours は 0〜24 の範囲で指定してください"})
            updates["push_cooldown_hours"] = val
        except (ValueError, TypeError):
            return _make_response(400, {"error": "push_cooldown_hours は数値を指定してください"})

    if "push_suggest_threshold" in body:
        try:
            val = int(body["push_suggest_threshold"])
            if not (0 <= val <= 100):
                return _make_response(400, {"error": "push_suggest_threshold は 0〜100 の範囲で指定してください"})
            updates["push_suggest_threshold"] = val
        except (ValueError, TypeError):
            return _make_response(400, {"error": "push_suggest_threshold は数値を指定してください"})

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


def _serve_temptation_html() -> dict:
    """寄り道レーンの HTML を配信する"""
    html_path = Path(__file__).parent / "liff" / "temptation.html"
    if not html_path.exists():
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/plain"},
            "body": "Temptation page not found",
        }
    html = html_path.read_text(encoding="utf-8")
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
        },
        "body": html,
    }


def _serve_service_worker() -> dict:
    """PWA Service Worker を配信する (要件整理.md §7)"""
    sw = """// Auto-Reward-Service PWA Service Worker (auto-generated)
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data ? event.data.text() : '' }; }
  const title = data.title || 'ふれまーるちゃん🌿';
  const options = {
    body: data.body || 'ちょっと話したいことがあるよ〜',
    icon: data.icon || '/liff/icon-192.png',
    badge: data.badge || '/liff/badge-72.png',
    data: { url: data.url || '/liff' },
    tag: data.type || 'ars-notification',
    renotify: true,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data && event.notification.data.url ? event.notification.data.url : '/liff';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      for (const client of clientList) {
        if (client.url.includes('/liff') && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
"""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/javascript; charset=utf-8",
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache",
        },
        "body": sw,
    }


def _serve_manifest() -> dict:
    """PWA manifest.json を配信する"""
    manifest = {
        "id": "/liff",
        "name": "Auto Reward Service",
        "short_name": "ARS",
        "start_url": "/liff",
        "scope": "/",
        "display": "standalone",
        "theme_color": "#7BAF6E",
        "background_color": "#ffffff",
        "icons": [
            {"src": "/liff/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/liff/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/manifest+json; charset=utf-8"},
        "body": json.dumps(manifest, ensure_ascii=False),
    }


def _handle_temptation_start(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/temptation/start — 寄り道レーン生成"""
    from services.temptation_engine import build_lanes

    lat = body.get("lat")
    lng = body.get("lng")
    message = body.get("message", "寄り道したい")
    genre = body.get("genre", "")

    if lat is None or lng is None:
        return _make_response(400, {"error": "lat, lng は必須です"})

    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return _make_response(400, {"error": "lat, lng は数値で指定してください"})

    result = build_lanes(user_id, lat, lng, message, ddb, genre=genre)
    return _make_response(200, result)


def _handle_temptation_accept(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/temptation/accept — レーン選択確定"""
    from services.temptation_engine import accept_lane

    session_id = body.get("session_id", "")
    lane_id = body.get("lane_id", "")

    if not session_id or not lane_id:
        return _make_response(400, {"error": "session_id, lane_id は必須です"})

    result = accept_lane(user_id, session_id, lane_id, ddb)
    return _make_response(200, result)


def _handle_temptation_history(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/temptation/history — 寄り道履歴"""
    from services.temptation_engine import get_temptation_history

    result = get_temptation_history(user_id, ddb)
    return _make_response(200, result)


def _handle_temptation_complete(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/temptation/complete — ワンタップ支出記録"""
    from services.temptation_engine import complete_temptation

    session_id = body.get("session_id", "")
    lane_id = body.get("lane_id", "")
    amount = body.get("amount")
    item_name = body.get("item_name", "")
    place_name = body.get("place_name", "")
    reward_id = body.get("reward_id")

    if not session_id or not lane_id or amount is None or not item_name:
        return _make_response(400, {"error": "session_id, lane_id, amount, item_name are required"})

    try:
        amount = int(amount)
    except (ValueError, TypeError):
        return _make_response(400, {"error": "invalid amount"})

    if amount <= 0 or amount > 1_000_000:
        return _make_response(400, {"error": "amount out of range"})

    result = complete_temptation(
        user_id=user_id,
        session_id=session_id,
        lane_id=lane_id,
        amount=amount,
        item_name=item_name,
        place_name=place_name,
        reward_id=reward_id,
        ddb=ddb,
    )
    return _make_response(200, result)


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

    # /liff/temptation → 寄り道レーン HTML
    if raw_path == "/liff/temptation":
        return _serve_temptation_html()

    # /liff/amazon-login → Amazon 連携ページ（ECS 不要デモ版）
    if raw_path == "/liff/amazon-login":
        return _serve_amazon_login_html(event)

    # PWA: Service Worker / manifest (要件整理.md §7) — 認証不要
    if raw_path == "/service-worker.js":
        return _serve_service_worker()
    if raw_path == "/manifest.json" or raw_path == "/liff/manifest.json":
        return _serve_manifest()

    # VAPID 公開鍵は公開情報 — 認証不要
    if raw_path == "/api/webpush/vapid-public-key" and http_method == "GET":
        return _handle_webpush_vapid_key()

    # /api/* → 認証必須
    user_id = _extract_user_id(event)
    if user_id == "__LINE_API_ERROR__":
        return _make_response(503, {"error": "LINE API一時障害です。少し待ってから再試行してください。"})
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
        elif raw_path == "/api/temptation/start" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_temptation_start(user_id, ddb, body)
        elif raw_path == "/api/temptation/accept" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_temptation_accept(user_id, ddb, body)
        elif raw_path == "/api/temptation/history" and http_method == "GET":
            return _handle_temptation_history(user_id, ddb)
        elif raw_path == "/api/temptation/complete" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_temptation_complete(user_id, ddb, body)
        # ─── 欲望在庫 (Wishlist) ───
        elif raw_path == "/api/wishlist/public-url" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_wishlist_register(user_id, ddb, body)
        elif raw_path == "/api/wishlist/items" and http_method == "GET":
            return _handle_wishlist_items(user_id, ddb)
        # ─── レコメンド ───
        elif raw_path == "/api/recommendations/generate" and http_method == "POST":
            return _handle_recommendation_generate(user_id, ddb)
        elif raw_path == "/api/recommendations" and http_method == "GET":
            return _handle_recommendations_list(user_id, ddb)
        elif raw_path == "/api/recommendations/active" and http_method == "GET":
            return _handle_recommendation_active(user_id, ddb)
        elif raw_path.startswith("/api/recommendations/") and raw_path.endswith("/cart") and http_method == "POST":
            rec_id = raw_path.split("/")[3]
            return _handle_recommendation_cart(user_id, ddb, rec_id)
        elif raw_path.startswith("/api/recommendations/") and raw_path.endswith("/decline") and http_method == "POST":
            rec_id = raw_path.split("/")[3]
            return _handle_recommendation_decline(user_id, ddb, rec_id)
        elif raw_path.startswith("/api/recommendations/") and raw_path.endswith("/purchase") and http_method == "POST":
            rec_id = raw_path.split("/")[3]
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_recommendation_purchase(user_id, ddb, rec_id, body)
        # ─── 通知 ───
        elif raw_path == "/api/notifications" and http_method == "GET":
            return _handle_notifications_list(user_id, ddb)
        elif raw_path == "/api/notifications/latest-actionable" and http_method == "GET":
            return _handle_notification_latest(user_id, ddb)
        # ─── PWA Web Push ───
        elif raw_path == "/api/webpush/vapid-public-key" and http_method == "GET":
            return _handle_webpush_vapid_key()
        elif raw_path == "/api/webpush/subscribe" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            ua = (event.get("headers") or {}).get("user-agent", "")
            return _handle_webpush_subscribe(user_id, ddb, body, ua)
        elif raw_path == "/api/webpush/unsubscribe" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_webpush_unsubscribe(user_id, ddb, body)
        elif raw_path == "/api/webpush/test" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                body = {}
            return _handle_webpush_test(user_id, ddb, body)
        elif raw_path == "/api/webpush/status" and http_method == "GET":
            return _handle_webpush_status(user_id, ddb)
        # ─── Nova Act 検証導線 ───
        elif raw_path == "/api/nova-act/smoke" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                body = {}
            return _handle_nova_act_smoke(user_id, ddb, body)
        # ─── Amazon 連携 ───
        elif raw_path == "/api/amazon/status" and http_method == "GET":
            return _handle_amazon_status(user_id, ddb)
        elif raw_path == "/api/amazon/login-url" and http_method == "GET":
            return _handle_amazon_login_url(user_id, ddb)
        elif raw_path == "/api/amazon/confirm" and http_method == "POST":
            return _handle_amazon_confirm(user_id, ddb)
        elif raw_path == "/api/amazon/unlink" and http_method == "POST":
            return _handle_amazon_unlink(user_id, ddb)
        elif raw_path == "/api/amazon/add-to-cart" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_amazon_add_to_cart(user_id, ddb, body)
        elif raw_path == "/api/amazon/purchase" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_amazon_purchase(user_id, ddb, body)
        # ─── 定期 Push 手動トリガー ───
        elif raw_path == "/api/push/trigger" and http_method == "POST":
            return _handle_push_trigger(user_id, ddb)
        else:
            return _make_response(404, {"error": "Not Found"})
    except Exception as e:
        logger.error("liff_api_error", error=str(e), path=raw_path)
        return _make_response(500, {"error": "内部エラーが発生しました"})


# ─────────────────────────────────────────
# 欲望在庫 (Wishlist) ハンドラ
# ─────────────────────────────────────────
def _handle_wishlist_register(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/wishlist/public-url — 公開ほしい物リストURL登録"""
    from services.wishlist_service import register_wishlist_url

    wishlist_url = body.get("wishlistUrl", "").strip()
    display_name = body.get("displayName")
    source_type = body.get("sourceType", "AMAZON_PUBLIC_WISHLIST")

    if not wishlist_url:
        return _make_response(400, {"error": "wishlistUrl は必須です"})

    result = register_wishlist_url(
        user_id, wishlist_url, ddb,
        display_name=display_name,
        source_type=source_type,
    )
    status_code = 200 if result.get("success") else 400
    return _make_response(status_code, result)


def _handle_wishlist_items(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/wishlist/items — 欲望在庫一覧"""
    from services.wishlist_service import get_wishlist_items

    items = get_wishlist_items(user_id, ddb)
    return _make_response(200, {"items": items})


# ─────────────────────────────────────────
# レコメンドハンドラ
# ─────────────────────────────────────────
def _handle_recommendation_generate(user_id: str, ddb: DynamoDBService) -> dict:
    """POST /api/recommendations/generate — レコメンド生成"""
    from services.recommendation_engine import generate_recommendation

    rec = generate_recommendation(user_id, ddb)
    if rec:
        return _make_response(200, rec)
    return _make_response(200, {"message": "現在おすすめできる商品がありません"})


def _handle_recommendations_list(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/recommendations — レコメンド一覧"""
    from models.schemas import SK_PREFIX_RECOMMENDATION

    pk = f"USER#{user_id}"
    recs = ddb.query_by_pk(pk=pk, sk_prefix=SK_PREFIX_RECOMMENDATION)
    recs.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return _make_response(200, {"recommendations": recs[:20]})


def _handle_recommendation_active(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/recommendations/active — アクティブなレコメンド"""
    from services.recommendation_engine import get_active_recommendation

    rec = get_active_recommendation(user_id, ddb)
    if rec:
        return _make_response(200, rec)
    return _make_response(200, {"message": "アクティブなレコメンドはありません"})


def _handle_recommendation_cart(user_id: str, ddb: DynamoDBService, rec_id: str) -> dict:
    """POST /api/recommendations/{id}/cart — カート投入"""
    from services.cart_job_service import create_cart_job
    from services.recommendation_engine import update_recommendation_status
    from models.schemas import SK_PREFIX_RECOMMENDATION

    pk = f"USER#{user_id}"
    rec = ddb.get_item(pk=pk, sk=f"{SK_PREFIX_RECOMMENDATION}{rec_id}")
    if not rec:
        return _make_response(404, {"error": "レコメンドが見つかりません"})

    update_recommendation_status(user_id, rec_id, "CART_ADDING", ddb)

    result = create_cart_job(
        user_id, rec_id, "ADD_TO_CART", ddb,
        product_url=rec.get("product_url"),
        expected_product_title=rec.get("title"),
        expected_price=rec.get("price"),
    )
    return _make_response(200, result)


def _handle_recommendation_decline(user_id: str, ddb: DynamoDBService, rec_id: str) -> dict:
    """POST /api/recommendations/{id}/decline — 拒否"""
    from services.recommendation_engine import update_recommendation_status

    update_recommendation_status(user_id, rec_id, "DECLINED", ddb)
    return _make_response(200, {"status": "DECLINED", "message": "わかりました。欲望熟成庫に戻しておきます。"})


def _handle_recommendation_purchase(user_id: str, ddb: DynamoDBService, rec_id: str, body: dict) -> dict:
    """POST /api/recommendations/{id}/purchase — 購入リクエスト"""
    from services.purchase_intent import classify_purchase_intent
    from services.recommendation_engine import update_recommendation_status
    from services.cart_job_service import create_cart_job
    from models.schemas import SK_PREFIX_RECOMMENDATION

    pk = f"USER#{user_id}"
    rec = ddb.get_item(pk=pk, sk=f"{SK_PREFIX_RECOMMENDATION}{rec_id}")
    if not rec:
        return _make_response(404, {"error": "レコメンドが見つかりません"})

    approval_text = body.get("approvalText", "")
    intent = classify_purchase_intent(approval_text, rec.get("title"))

    if intent == "EXPLICIT_PURCHASE":
        update_recommendation_status(user_id, rec_id, "PURCHASE_APPROVED", ddb)
        result = create_cart_job(
            user_id, rec_id, "PURCHASE", ddb,
            product_url=rec.get("product_url"),
            expected_product_title=rec.get("title"),
            expected_price=rec.get("price"),
            explicit_approval_text=approval_text,
        )
        return _make_response(200, result)
    elif intent == "AMBIGUOUS_BUY":
        update_recommendation_status(user_id, rec_id, "PURCHASE_CONFIRMATION_REQUIRED", ddb)
        return _make_response(200, {
            "status": "PURCHASE_CONFIRMATION_REQUIRED",
            "message": "買いたい気持ちはわかったよ！\n「この商品を購入して」と送ってくれたら、買ってくるよ～～",
        })
    elif intent == "DECLINE":
        update_recommendation_status(user_id, rec_id, "DECLINED", ddb)
        return _make_response(200, {"status": "DECLINED", "message": "わかりました。戻しておくね。"})
    else:
        return _make_response(400, {"error": "購入意思を確認できませんでした"})


# ─────────────────────────────────────────
# 通知ハンドラ
# ─────────────────────────────────────────
def _handle_notifications_list(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/notifications — 通知一覧"""
    from services.notification_service import get_notifications

    notifications = get_notifications(user_id, ddb)
    return _make_response(200, {"notifications": notifications})


def _handle_notification_latest(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/notifications/latest-actionable — 最新アクション可能通知"""
    from services.notification_service import get_latest_actionable_notification

    notif = get_latest_actionable_notification(user_id, ddb)
    if notif:
        return _make_response(200, notif)
    return _make_response(200, {"message": "アクション可能な通知はありません"})


# ─────────────────────────────────────────
# PWA Web Push ハンドラ (要件整理.md §7)
# ─────────────────────────────────────────
def _handle_webpush_vapid_key() -> dict:
    """GET /api/webpush/vapid-public-key — ブラウザ用 applicationServerKey"""
    from services.webpush_service import get_public_key

    key = get_public_key()
    if not key:
        return _make_response(500, {"error": "VAPID key not configured"})
    return _make_response(200, {"publicKey": key})


def _handle_webpush_subscribe(user_id: str, ddb: DynamoDBService, body: dict, user_agent: str) -> dict:
    """POST /api/webpush/subscribe — PushSubscription を保存"""
    from services.webpush_service import save_subscription

    subscription = body.get("subscription") or body
    try:
        sk = save_subscription(user_id, subscription, ddb, user_agent=user_agent)
    except ValueError as e:
        return _make_response(400, {"error": f"無効な subscription: {e}"})
    except Exception as e:
        logger.error("webpush_subscribe_failed", error=str(e))
        return _make_response(500, {"error": "subscription 保存失敗"})
    return _make_response(200, {"subscribed": True, "sk": sk})


def _handle_webpush_unsubscribe(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/webpush/unsubscribe — PushSubscription を削除"""
    from services.webpush_service import delete_subscription

    endpoint = body.get("endpoint", "")
    if not endpoint:
        return _make_response(400, {"error": "endpoint は必須です"})
    ok = delete_subscription(user_id, endpoint, ddb)
    return _make_response(200, {"unsubscribed": ok})


def _handle_webpush_test(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/webpush/test — テスト通知を即時送信"""
    from services.webpush_service import send_webpush

    payload = {
        "title": body.get("title") or "ふれまーるちゃん🌿",
        "body": body.get("body") or "テスト通知だよ〜。ちゃんと届いてるかなぁ？",
        "url": body.get("url") or "/liff",
    }
    result = send_webpush(user_id, payload, ddb)
    status = 200 if result.get("sent", 0) > 0 else 500
    return _make_response(status, result)


def _handle_webpush_status(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/webpush/status — 購読状況"""
    from services.webpush_service import list_subscriptions, get_public_key

    subs = list_subscriptions(user_id, ddb)
    return _make_response(200, {
        "subscribed": len(subs) > 0,
        "subscriptionCount": len(subs),
        "vapidPublicKey": get_public_key(),
        "subscriptions": [{
            "endpoint_hash": s.get("endpoint", "")[:80] + "…" if len(s.get("endpoint", "")) > 80 else s.get("endpoint", ""),
            "userAgent": s.get("userAgent", ""),
            "createdAt": s.get("created_at", ""),
        } for s in subs],
    })


# ─────────────────────────────────────────
# Nova Act 検証導線 (要件整理.md §10)
# ─────────────────────────────────────────
def _handle_nova_act_smoke(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/nova-act/smoke — Nova Act 動作確認/候補取得テスト

    Body: {"query": "抹茶 プリン", "max_results": 3}
    """
    import os as _os
    enabled = _os.environ.get("ENABLE_NOVA_ACT_SMOKE", "true").lower() == "true"
    if not enabled:
        return _make_response(403, {"error": "Nova Act smoke is disabled"})

    query = (body.get("query") or "").strip()
    if not query:
        return _make_response(400, {"error": "query は必須です"})
    max_results = min(int(body.get("max_results", 3)), 10)

    try:
        from services.reward_candidate_provider import run_nova_act_smoke
        candidates, meta = run_nova_act_smoke(query=query, max_results=max_results)
    except Exception as e:
        logger.error("nova_act_smoke_failed", error=str(e))
        return _make_response(500, {
            "error": "Nova Act smoke failed",
            "detail": str(e)[:200],
        })

    # 結果をDynamoDBに監査ログとして保存
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        ddb.put_item(f"USER#{user_id}", f"NOVA_ACT_LOG#{ts}", {
            "entityType": "NOVA_ACT_LOG",
            "query": query,
            "result_count": len(candidates),
            "status": meta.get("status", "unknown"),
            "provider": meta.get("provider", ""),
            "duration_ms": meta.get("duration_ms", 0),
            "failure_reason": meta.get("failure_reason"),
            "created_at": ts,
        })
    except Exception as e:
        logger.warning("nova_act_log_save_failed", error=str(e))

    return _make_response(200, {
        "query": query,
        "candidates": candidates,
        "meta": meta,
    })


# ─────────────────────────────────────────
# Amazon 連携ハンドラ
# ─────────────────────────────────────────
# ECS ログインサーバーの URL（環境変数 or ハードコード）
_ECS_LOGIN_BASE_URL = os.environ.get("ECS_LOGIN_SERVER_URL", "")


def _handle_amazon_status(user_id: str, ddb) -> dict:
    """GET /api/amazon/status — Amazon 連携状態を確認"""
    try:
        item = ddb.get_item(f"USER#{user_id}", "AMAZON_SESSION")
        linked = item.get("amazon_linked", False) if item else False
        return _make_response(200, {
            "amazon_linked": linked,
            "updated_at": item.get("updated_at") if item else None,
        })
    except Exception as e:
        logger.warning("amazon_status_check_failed", error=str(e))
        return _make_response(200, {"amazon_linked": False})


def _handle_amazon_login_url(user_id: str, ddb) -> dict:
    """GET /api/amazon/login-url — Amazon ログインページの URL を返す"""
    base_url = _ECS_LOGIN_BASE_URL
    if base_url:
        # ECS デプロイ済みの場合
        login_url = f"{base_url}/login/{user_id}"
    else:
        # ECS 未デプロイ → Lambda 提供のデモログインページ
        login_url = f"/liff/amazon-login?uid={user_id}"
    return _make_response(200, {"login_url": login_url})


def _handle_amazon_confirm(user_id: str, ddb) -> dict:
    """POST /api/amazon/confirm — Amazon 連携を確認済みにマーク"""
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        ddb.put_item(f"USER#{user_id}", "AMAZON_SESSION", {
            "entityType": "AMAZON_SESSION",
            "amazon_linked": True,
            "updated_at": ts,
            "linked_at": ts,
        })
        return _make_response(200, {"success": True, "amazon_linked": True})
    except Exception as e:
        logger.error("amazon_confirm_failed", error=str(e))
        return _make_response(500, {"error": "連携確認に失敗しました"})


def _serve_amazon_login_html(event: dict) -> dict:
    """Amazon 連携ページ（URL方式 — ユーザーが自分のブラウザでログイン確認）"""
    qs = event.get("queryStringParameters") or {}
    uid = qs.get("uid", "")
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Amazon 連携 - ふれまーるちゃん</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
.container {{ max-width: 400px; width: 90%; padding: 24px; }}
.card {{ background: #fff; border-radius: 16px; padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 16px; }}
h1 {{ font-size: 20px; text-align: center; margin-bottom: 16px; color: #2d5016; }}
.desc {{ font-size: 14px; color: #555; line-height: 1.6; margin-bottom: 20px; text-align: center; }}
.steps-list {{ list-style: none; padding: 0; margin-bottom: 20px; }}
.steps-list li {{ font-size: 14px; color: #333; padding: 10px 0; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 10px; }}
.steps-list li .num {{ width: 24px; height: 24px; background: #ff9900; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold; flex-shrink: 0; }}
.btn {{ width: 100%; padding: 14px; border: none; border-radius: 10px; font-size: 16px; font-weight: bold; cursor: pointer; margin-bottom: 10px; }}
.btn-amazon {{ background: #ff9900; color: #111; }}
.btn-amazon:hover {{ background: #e88a00; }}
.btn-confirm {{ background: #2d5016; color: #fff; }}
.btn-confirm:hover {{ background: #1d3a0e; }}
.btn-confirm:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.btn-back {{ background: #e8e8e8; color: #333; }}
.success {{ display: none; text-align: center; }}
.success .icon {{ font-size: 48px; margin-bottom: 12px; }}
.success .msg {{ font-size: 16px; color: #155724; margin-bottom: 16px; }}
.note {{ font-size: 11px; color: #888; text-align: center; margin-top: 12px; }}
.error {{ color: #dc3545; font-size: 13px; text-align: center; margin-bottom: 10px; display: none; }}
.step {{ display: none; }}
.step.active {{ display: block; }}
.check-area {{ text-align: center; margin: 16px 0; }}
.check-area label {{ font-size: 14px; color: #333; cursor: pointer; }}
.check-area input {{ margin-right: 6px; transform: scale(1.2); }}
</style>
</head>
<body>
<div class="container">
<div class="card">
<h1>🛒 Amazon アカウント連携</h1>

<div id="step-login" class="step active">
<p class="desc">Amazonアカウントを連携すると、ふれまーるちゃんがおすすめのご褒美をワンタップでカートに追加できます。</p>

<ul class="steps-list">
  <li><span class="num">1</span>下のボタンでAmazon.co.jpを開いてログインしてください</li>
  <li><span class="num">2</span>ログイン完了後、このページに戻ってください</li>
  <li><span class="num">3</span>「連携完了」ボタンを押してください</li>
</ul>

<button class="btn btn-amazon" onclick="openAmazon()">🔗 Amazon.co.jp を開く</button>

<div id="error-msg" class="error"></div>

<div class="check-area">
  <label><input type="checkbox" id="chk-logged-in" onchange="toggleConfirm()"> Amazonにログイン済みです</label>
</div>

<button class="btn btn-confirm" id="btn-confirm" disabled onclick="doConfirm()">✅ 連携完了</button>
<button class="btn btn-back" onclick="goBack()">キャンセル</button>

<p class="note">※ Amazonの認証情報はサーバーに送信されません。<br>ご褒美のカート追加時はAmazonのページが開きます。</p>
</div>

<div id="step-success" class="step">
<div class="success" style="display:block;">
  <div class="icon">✅</div>
  <div class="msg">Amazon 連携完了！</div>
  <p class="desc">ふれまーるちゃんがあなたのご褒美をワンタップでカートに追加できるようになりました 🌿</p>
  <button class="btn btn-back" onclick="goBack()">LIFFに戻る</button>
</div>
</div>

</div>
</div>
<script>
const USER_ID = "{uid}";

function openAmazon() {{
  window.open('https://www.amazon.co.jp/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.co.jp%2F&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=jpflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0', '_blank');
}}

function toggleConfirm() {{
  document.getElementById('btn-confirm').disabled = !document.getElementById('chk-logged-in').checked;
}}

async function doConfirm() {{
  const errEl = document.getElementById('error-msg');
  errEl.style.display = 'none';
  const btn = document.getElementById('btn-confirm');
  btn.disabled = true;
  btn.textContent = '連携中...';

  try {{
    const headers = {{}};
    const cachedUid = localStorage.getItem('ars_user_id');
    if (cachedUid) headers['X-ARS-User-Id'] = cachedUid;
    headers['Content-Type'] = 'application/json';

    const res = await fetch('/api/amazon/confirm', {{
      method: 'POST',
      headers: headers,
      body: JSON.stringify({{ amazon_linked: true }})
    }});
    const data = await res.json();
    if (data.success) {{
      document.getElementById('step-login').classList.remove('active');
      document.getElementById('step-success').classList.add('active');
    }} else {{
      errEl.textContent = data.error || '連携に失敗しました';
      errEl.style.display = 'block';
    }}
  }} catch (e) {{
    errEl.textContent = 'エラー: ' + e.message;
    errEl.style.display = 'block';
  }} finally {{
    btn.disabled = false;
    btn.textContent = '✅ 連携完了';
  }}
}}

function goBack() {{
  if (window.opener) {{ window.close(); }}
  else {{ location.href = '/liff'; }}
}}
</script>
</body>
</html>"""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": html,
    }


def _handle_amazon_add_to_cart(user_id: str, ddb, body: dict) -> dict:
    """POST /api/amazon/add-to-cart — Amazon カートに商品を追加（URL方式）"""
    from services.amazon_cart_service import (
        build_cart_urls, get_amazon_product_for_category,
        generate_add_to_cart_url, generate_add_and_checkout_url, extract_asin,
    )

    product_url = body.get("product_url", "")
    asin = body.get("asin", "")
    category = body.get("category", "おまかせ")
    max_price = int(body.get("max_price", 5000))

    # ASIN が直接指定されている場合
    if asin:
        cart_url = generate_add_to_cart_url(asin)
        checkout_url = generate_add_and_checkout_url(asin)
        return _make_response(200, {
            "success": True,
            "asin": asin,
            "cart_url": cart_url,
            "checkout_url": checkout_url,
            "message": "カートに追加するURLを生成しました。タップしてAmazonカートに追加してください。",
        })

    # 商品URLが指定されている場合 → ASIN抽出
    if product_url:
        urls = build_cart_urls(product_url)
        if urls:
            return _make_response(200, {
                "success": True,
                "asin": urls["asin"],
                "cart_url": urls["add_to_cart_url"],
                "checkout_url": urls["checkout_url"],
                "message": "カートに追加するURLを生成しました。",
            })
        # Amazon以外のURL → そのまま返す
        return _make_response(200, {
            "success": True,
            "cart_url": product_url,
            "checkout_url": product_url,
            "message": "商品ページを開きます。",
        })

    # カテゴリから商品を選択
    product = get_amazon_product_for_category(category, max_price)
    if product:
        # DynamoDB に記録
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        ddb.put_item(f"USER#{user_id}", "AMAZON_CART_LAST", {
            "asin": product["asin"],
            "title": product["title"],
            "price": product["price"],
            "cart_url": product["add_to_cart_url"],
            "checkout_url": product["checkout_url"],
            "created_at": ts,
        })
        return _make_response(200, {
            "success": True,
            "product": product,
            "message": f"「{product['title']}」をカートに追加します。",
        })

    return _make_response(404, {"error": "条件に合うAmazon商品が見つかりませんでした"})


def _handle_amazon_purchase(user_id: str, ddb, body: dict) -> dict:
    """POST /api/amazon/purchase — Amazon で購入（チェックアウトページへ誘導）"""
    from services.amazon_cart_service import (
        generate_add_and_checkout_url, generate_checkout_url, extract_asin,
    )

    asin = body.get("asin", "")
    product_url = body.get("product_url", "")

    # ASIN or URL から購入URL生成
    if not asin and product_url:
        asin = extract_asin(product_url)

    if not asin:
        # DynamoDB から直前のカート追加情報を取得
        last_cart = ddb.get_item(pk=f"USER#{user_id}", sk="AMAZON_CART_LAST")
        if last_cart:
            asin = last_cart.get("asin", "")

    if asin:
        checkout_url = generate_add_and_checkout_url(asin)
        # 購入記録
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        ddb.put_item(f"USER#{user_id}", "AMAZON_PURCHASE_LOG#" + ts, {
            "asin": asin,
            "action": "PURCHASE_INITIATED",
            "created_at": ts,
        })
        return _make_response(200, {
            "success": True,
            "asin": asin,
            "checkout_url": checkout_url,
            "cart_view_url": generate_checkout_url(),
            "message": "購入ページを開きます。「注文を確定する」をタップして購入を完了してください。",
        })

    return _make_response(400, {"error": "購入する商品が指定されていません。先にカートに追加してください。"})


def _handle_amazon_unlink(user_id: str, ddb) -> dict:
    """POST /api/amazon/unlink — Amazon 連携を解除"""
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        ddb.put_item(f"USER#{user_id}", "AMAZON_SESSION", {
            "entityType": "AMAZON_SESSION",
            "amazon_linked": False,
            "updated_at": ts,
            "unlinked_at": ts,
        })
        return _make_response(200, {"success": True})
    except Exception as e:
        logger.error("amazon_unlink_failed", error=str(e))
        return _make_response(500, {"error": "解除に失敗しました"})


def _handle_push_trigger(user_id: str, ddb) -> dict:
    """POST /api/push/trigger — 手動で定期Push通知を自分に送る（テスト用）"""
    import random
    from services.notification_service import create_notification

    messages = [
        {"title": "今日もお疲れさまっ🌿", "body": "頑張った自分にちょっとしたご褒美、どうかなぁ？ ふれまーるちゃんが探しとくね～"},
        {"title": "ご褒美タイムだよ～🍵", "body": "毎日えらいっ！今日は何か自分に優しくしてあげよ？"},
        {"title": "のんびりしよっ🛁", "body": "今日も1日おつかれさま。ちょっとだけ自分を甘やかす時間にしない？"},
    ]
    msg = random.choice(messages)

    try:
        result = create_notification(
            user_id=user_id,
            ddb=ddb,
            notification_type="SCHEDULED_REWARD_REMIND",
            title=msg["title"],
            message_text=msg["body"],
        )
        return _make_response(200, {
            "success": True,
            "notification_id": result.get("notification_id"),
            "title": msg["title"],
            "message": msg["body"],
        })
    except Exception as e:
        logger.error("push_trigger_failed", error=str(e))
        return _make_response(500, {"error": f"Push送信失敗: {str(e)[:100]}"})
