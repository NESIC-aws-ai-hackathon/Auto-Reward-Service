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
            "Cache-Control": "no-cache, no-store, must-revalidate",
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

    # /liff/amazon-buy → 自動カート追加＋購入中間ページ
    if raw_path == "/liff/amazon-buy":
        return _serve_amazon_buy_html(event)

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
        # ─── ご褒美候補検索 (Provider ベース) ───
        elif raw_path == "/api/reward-candidates" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                body = {}
            return _handle_reward_candidates(user_id, ddb, body)
        # ─── Nova Act 検証導線 (後方互換) ───
        elif raw_path == "/api/nova-act/smoke" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                body = {}
            return _handle_nova_act_smoke(user_id, ddb, body)
        elif raw_path == "/api/nova-act/cart" and http_method == "POST":
            # 後方互換: 新APIにリダイレクト
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                body = {}
            return _handle_reward_candidates(user_id, ddb, body)
        elif raw_path == "/api/nova-act/create-job" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_nova_act_create_search_job(user_id, ddb, body)
        elif raw_path == "/api/nova-act/job-status" and http_method == "GET":
            qs = event.get("queryStringParameters") or {}
            return _handle_nova_act_search_job_status(user_id, ddb, qs)
        # ─── Amazon カートに追加 (ASIN解決) ───
        elif raw_path == "/api/amazon/add-to-cart" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                body = {}
            return _handle_amazon_add_to_cart(user_id, ddb, body)
        elif raw_path == "/api/amazon/resolve-cart" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                body = {}
            return _handle_amazon_resolve_cart(user_id, body)
        # ─── Amazon 連携 ───
        elif raw_path == "/api/amazon/status" and http_method == "GET":
            return _handle_amazon_status(user_id, ddb)
        elif raw_path == "/api/amazon/login-url" and http_method == "GET":
            return _handle_amazon_login_url(user_id, ddb)
        elif raw_path == "/api/amazon/confirm" and http_method == "POST":
            return _handle_amazon_confirm(user_id, ddb)
        elif raw_path == "/api/amazon/save-cookies" and http_method == "POST":
            try:
                body = json.loads(event.get("body") or "{}")
            except json.JSONDecodeError:
                return _make_response(400, {"error": "無効な JSON です"})
            return _handle_amazon_save_cookies(user_id, ddb, body)
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


def _handle_nova_act_cart(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/nova-act/cart — Nova Actが自動でカートに入れた商品を返す

    Nova Act体験のコア: ユーザーのほしいものリストから自動選択し、
    「もうカートに入れたよ」として表示する。
    """
    from services.wishlist_service import get_active_items_for_recommendation
    import random

    max_price = int(body.get("max_price", 5000))

    try:
        items = get_active_items_for_recommendation(user_id, ddb, max_price=max_price)
    except Exception as e:
        logger.error("nova_act_cart_items_failed", error=str(e))
        return _make_response(200, {"success": False, "error": "ほしいものリストの取得に失敗しました"})

    if not items:
        # ほしいものリスト未登録時はデモ商品でフォールバック
        from services.amazon_cart_service import get_amazon_product_for_category
        demo = get_amazon_product_for_category("おまかせ", max_price=max_price)
        if demo:
            items = [{
                "title": demo["title"],
                "price": demo["price"],
                "asin": demo["asin"],
                "url": demo.get("product_url", ""),
                "image_url": "",
            }]
        else:
            return _make_response(200, {
                "success": False,
                "error": "商品が見つかりませんでした🌿"
            })

    # Nova Actが「選んだ」商品 = ほしいものリストからランダムに1つ選択
    # 実際のNova Actではブラウザ操作で追加するが、ハッカソンではシミュレート
    selected = random.choice(items) if len(items) > 1 else items[0]

    # ほしい度が高いものを優先（desire_levelでソート済みの上位から選ぶ）
    high_desire = [it for it in items if it.get("desire_level", 0) >= 3]
    if high_desire:
        selected = random.choice(high_desire)

    # フィールド名の正規化（DynamoDB: product_title/product_url vs コード: title/url）
    if not selected.get("title") and selected.get("product_title"):
        selected["title"] = selected["product_title"]
    if not selected.get("url") and selected.get("product_url"):
        selected["url"] = selected["product_url"]
    if not selected.get("image_url") and selected.get("product_image_url"):
        selected["image_url"] = selected["product_image_url"]

    # ASIN抽出
    from services.amazon_cart_service import extract_asin, get_amazon_product_for_category as _get_demo
    asin = selected.get("asin") or ""
    if not asin and selected.get("url"):
        asin = extract_asin(selected["url"]) or ""

    # ASINが取れない場合はデモ商品にフォールバック
    if not asin:
        logger.warning("nova_act_no_asin_fallback", selected_title=selected.get("title"), selected_url=selected.get("url"))
        demo = _get_demo("おまかせ", max_price=max_price)
        if demo:
            selected = {
                "title": demo["title"],
                "price": demo["price"],
                "asin": demo["asin"],
                "url": demo.get("product_url", ""),
                "image_url": "",
            }
            asin = demo["asin"]

    # カート追加URL・チェックアウトURLを生成
    from services.amazon_cart_service import generate_add_to_cart_url, generate_checkout_url, generate_product_url
    add_to_cart_url = generate_add_to_cart_url(asin) if asin else ""
    checkout_url = generate_checkout_url()
    product_url = generate_product_url(asin) if asin else selected.get("url", "")

    product = {
        "title": selected.get("title", "不明な商品"),
        "price": selected.get("price"),
        "image_url": selected.get("image_url"),
        "asin": asin,
        "product_url": product_url,
        "add_to_cart_url": add_to_cart_url,
        "checkout_url": checkout_url,
    }

    # Nova Actがカートに入れた記録を保存
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        ddb.put_item(f"USER#{user_id}", f"NOVA_ACT_CART#{ts}", {
            "entityType": "NOVA_ACT_CART",
            "asin": asin,
            "title": product["title"],
            "price": product.get("price"),
            "status": "proposed",
            "created_at": ts,
        })
    except Exception as e:
        logger.warning("nova_act_cart_log_failed", error=str(e))

    reasons = [
        "あなたのほしいものリストから、今のあなたにぴったりだと思って選んだよ🌿",
        "最近頑張ってたから、これご褒美にどうかな？🌿",
        "ほしいものリストでずっと気になってたやつ、カートに入れちゃった🌿",
        "今日は自分にご褒美あげていい日だよ～🌿",
    ]

    return _make_response(200, {
        "success": True,
        "product": product,
        "reason": random.choice(reasons),
        "source": "nova_act_wishlist",
    })


def _handle_nova_act_approve(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/nova-act/approve — Nova Actがサーバーサイドでカートに追加

    Body: {"asin": "...", "title": "...", "price": 1234}

    フロー:
      1. ユーザーの保存済みAmazon Cookieを取得
      2. サーバーサイドからAmazonのカート追加エンドポイントにリクエスト
      3. ユーザーのAmazonカートに実際に商品が追加される
      4. 購入許可ログを記録
    """
    from services.nova_act_service import add_to_cart_server_side, get_amazon_cookies

    asin = body.get("asin", "")
    title = body.get("title", "")
    price = body.get("price")

    # 1. ユーザーのAmazon Cookieを取得
    cookies = get_amazon_cookies(user_id, ddb)
    if not cookies:
        logger.warning("nova_act_no_cookies", user_id=user_id[:8])
        return _make_response(400, {
            "success": False,
            "message": "Amazonセッションが保存されていません。設定画面から「Amazonにログインする」を実行してください。",
            "needs_login": True,
        })

    # 2. サーバーサイドでカートに追加（Nova Act）
    cart_result = add_to_cart_server_side(asin, cookies)
    logger.info("nova_act_cart_result", asin=asin, success=cart_result.get("success"))

    if not cart_result.get("success"):
        # セッション切れの場合
        if cart_result.get("needs_relogin"):
            return _make_response(401, {
                "success": False,
                "message": cart_result.get("message", "セッションが切れています"),
                "needs_login": True,
            })
        return _make_response(400, {
            "success": False,
            "message": cart_result.get("message", "カート追加に失敗しました"),
        })

    # 3. 購入許可ログを保存
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()

        ddb.put_item(f"USER#{user_id}", f"NOVA_ACT_PURCHASE#{ts}", {
            "entityType": "NOVA_ACT_PURCHASE",
            "asin": asin,
            "title": title,
            "price": int(price) if price else None,
            "status": "cart_added",
            "approved_at": ts,
        })

        # ご褒美支出としても記録
        ddb.put_item(f"USER#{user_id}", f"EXPENSE#REWARD#{ts}", {
            "entityType": "EXPENSE",
            "category": "reward",
            "description": f"🎁 {title}" if title else "🎁 ご褒美購入",
            "amount": int(price) if price else 0,
            "date": datetime.now(_JST).strftime("%Y-%m-%d"),
            "source": "nova_act",
            "created_at": ts,
        })

        logger.info("nova_act_purchase_approved", user_id=user_id[:8], asin=asin, price=price)
    except Exception as e:
        logger.error("nova_act_approve_log_failed", error=str(e))

    return _make_response(200, {
        "success": True,
        "message": "カートに追加しました！🛒 Amazonで注文を確定してね🌿",
        "cart_url": cart_result.get("cart_url", "https://www.amazon.co.jp/gp/cart/view.html"),
    })


# ─────────────────────────────────────────
# Amazon ASIN解決 → カートURL (商品名ベース)
# ─────────────────────────────────────────
def _handle_amazon_resolve_cart(user_id: str, body: dict) -> dict:
    """POST /api/amazon/resolve-cart — 商品名からASINを解決しカートURLを返す

    Body: {"product_name": "アロマキャンドル", "max_price": 3000}
    Returns: {"success": true, "asin": "B08...", "cart_url": "https://...", ...}
    """
    product_name = (body.get("product_name") or "").strip()
    if not product_name:
        return _make_response(400, {"success": False, "error": "product_name が必要です"})

    max_price = int(body.get("max_price", 5000))

    try:
        from services.reward_candidate_provider import resolve_amazon_asin
        result = resolve_amazon_asin(product_name, max_price=max_price)

        if result.get("asin"):
            return _make_response(200, {
                "success": True,
                "asin": result["asin"],
                "cart_url": result["cart_url"],
                "product_url": result.get("url", ""),
                "image_url": result.get("image_url", ""),
                "name": result.get("name", product_name),
            })
        else:
            return _make_response(200, {
                "success": False,
                "error": result.get("error", "ASINが見つかりませんでした"),
            })
    except Exception as e:
        logger.error("amazon_resolve_cart_failed", error=str(e))
        return _make_response(500, {
            "success": False,
            "error": "ASIN解決に失敗しました",
            "detail": str(e)[:200],
        })


# ─────────────────────────────────────────
# ご褒美候補検索 Provider API (新方式)
# ─────────────────────────────────────────
def _handle_reward_candidates(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/reward-candidates — Provider ベースでご褒美候補を検索

    Body: {"query": "プリン", "max_price": 3000}
    Returns: {"success": true, "candidates": [...]}
    """
    query = (body.get("query") or "").strip()
    max_price = int(body.get("max_price", 3000))

    try:
        from services.reward_candidate_provider import search_reward_candidates
        candidates = search_reward_candidates(
            query=query,
            max_price=max_price,
            user_context={"user_id": user_id, "ddb": ddb},
        )

        # candidates は既に list[dict] で返ってくる
        return _make_response(200, {
            "success": True,
            "candidates": candidates,
            "count": len(candidates),
        })
    except Exception as e:
        logger.error("reward_candidates_failed", error=str(e))
        return _make_response(500, {
            "success": False,
            "error": "候補検索に失敗しました",
            "detail": str(e)[:200],
        })


# ─────────────────────────────────────────
# Nova Act 検索ジョブ API (新方式: 検索のみ、カート操作なし)
# ─────────────────────────────────────────
_NOVA_ACT_SEARCH_JOB_PK_PREFIX = "NOVA_ACT_SEARCH_JOB#"


def _handle_nova_act_create_search_job(user_id: str, ddb: DynamoDBService, body: dict) -> dict:
    """POST /api/nova-act/create-job — Amazon 検索ジョブを作成（Worker が非同期処理）

    Body: {"query": "抹茶 プリン", "max_price": 3000}

    フロー:
      1. DynamoDB に queued ステータスの検索ジョブレコードを作成
      2. job_id を返す
      3. Nova Act Worker が queued ジョブを検出して Amazon 検索を実行
      4. LIFF がポーリングで進捗確認
    """
    import uuid as _uuid

    query = (body.get("query") or "").strip()
    max_price = int(body.get("max_price", 5000))

    if not query:
        return _make_response(400, {"error": "query は必須です"})

    job_id = str(_uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    pk = f"{_NOVA_ACT_SEARCH_JOB_PK_PREFIX}{job_id}"
    sk = "META#"

    job_data = {
        "entityType": "NOVA_ACT_SEARCH_JOB",
        "job_id": job_id,
        "userId": f"USER#{user_id}",
        "query": query,
        "max_price": max_price,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
    }

    ddb.put_item(pk, sk, job_data)
    logger.info("nova_act_search_job_created", job_id=job_id, user_id=user_id[:8], query=query)

    return _make_response(200, {
        "success": True,
        "job_id": job_id,
        "status": "queued",
        "message": "検索ジョブを作成しました！ふれまーるちゃんがAmazonを検索するよ🔍",
    })


def _handle_nova_act_search_job_status(user_id: str, ddb: DynamoDBService, qs: dict) -> dict:
    """GET /api/nova-act/job-status?job_id=xxx — 検索ジョブの進捗を返す"""
    job_id = qs.get("job_id", "")
    if not job_id:
        return _make_response(400, {"error": "job_id パラメータが必要です"})

    pk = f"{_NOVA_ACT_SEARCH_JOB_PK_PREFIX}{job_id}"
    sk = "META#"

    item = ddb.get_item(pk, sk)
    if not item:
        return _make_response(404, {"error": "ジョブが見つかりません"})

    # 完了時は結果件数も返す
    result = {
        "job_id": item.get("job_id"),
        "status": item.get("status", "unknown"),
        "query": item.get("query"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }

    if item.get("status") == "completed":
        result["candidate_count"] = item.get("candidate_count", 0)
    elif item.get("status") == "failed":
        result["error"] = item.get("error", "不明なエラー")

    return _make_response(200, result)


# ─────────────────────────────────────────
# Amazon 連携ハンドラ
# ─────────────────────────────────────────
# ECS ログインサーバーの URL（環境変数 or ハードコード）
_ECS_LOGIN_BASE_URL = os.environ.get("ECS_LOGIN_SERVER_URL", "")


def _handle_amazon_status(user_id: str, ddb) -> dict:
    """GET /api/amazon/status — Amazon 連携状態を確認（セッション有効期限含む）"""
    try:
        item = ddb.get_item(f"USER#{user_id}", "AMAZON_SESSION")
        linked = item.get("amazon_linked", False) if item else False
        linked_at = item.get("linked_at") if item else None
        return _make_response(200, {
            "amazon_linked": linked,
            "linked_at": linked_at,
            "updated_at": item.get("updated_at") if item else None,
        })
    except Exception as e:
        logger.warning("amazon_status_check_failed", error=str(e))
        return _make_response(200, {"amazon_linked": False})


def _handle_amazon_save_cookies(user_id: str, ddb, body: dict) -> dict:
    """POST /api/amazon/save-cookies — ユーザーのAmazon CookieをDynamoDBに保存

    Body: {"cookies": {"session-id": "...", "ubid-acbjp": "...", ...}}

    これにより、Nova Act がサーバーサイドからユーザーのAmazonセッションを使って
    カート操作等を行えるようになる。
    """
    cookies = body.get("cookies")
    if not cookies or not isinstance(cookies, dict):
        return _make_response(400, {"error": "cookies フィールドが必要です"})

    # 最低限必要なCookie
    required_keys = ["session-id"]
    if not any(k in cookies for k in required_keys):
        return _make_response(400, {"error": "session-id Cookie が必要です"})

    from services.nova_act_service import save_amazon_cookies
    success = save_amazon_cookies(user_id, cookies, ddb)
    if success:
        return _make_response(200, {
            "success": True,
            "message": "Amazonセッションを保存しました。ふれまーるちゃんが自動操作できるようになりました🌿",
        })
    return _make_response(500, {"error": "保存に失敗しました"})


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


def _serve_amazon_buy_html(event: dict) -> dict:
    """ふれまーるちゃんが自動でカートに追加する中間ページ。

    Amazon の公開 Add-to-Cart URL を使い、ユーザーのブラウザ(Cookie)で
    自動的にカートに追加する。ユーザーはカートに入った状態のAmazonを見る。
    """
    import html as html_mod
    qs = event.get("queryStringParameters") or {}
    asin = qs.get("asin", "")
    title = qs.get("title", "ご褒美アイテム")

    # Sanitize
    asin = html_mod.escape(asin)
    title = html_mod.escape(title)

    # Amazon カート追加URL（GETでカートに追加→カート確認ページ表示）
    cart_add_url = f"https://www.amazon.co.jp/gp/aws/cart/add.html?ASIN.1={asin}&Quantity.1=1"

    page_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ふれまーるちゃんがカートに追加中...</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(135deg, #f5f0e8 0%, #e8f5e9 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
.container {{ text-align: center; padding: 32px; max-width: 380px; }}
.mascot {{ font-size: 64px; animation: bounce 1s infinite; }}
@keyframes bounce {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-12px); }} }}
.msg {{ font-size: 18px; color: #2d5016; font-weight: bold; margin: 16px 0 8px; }}
.sub {{ font-size: 14px; color: #555; margin-bottom: 12px; }}
.product {{ background: #fff; border-radius: 12px; padding: 12px 16px; margin: 12px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.product-title {{ font-size: 13px; font-weight: bold; color: #333; }}
.progress {{ margin: 16px 0; }}
.progress-bar {{ height: 6px; background: #e0e0e0; border-radius: 3px; overflow: hidden; }}
.progress-fill {{ height: 100%; background: linear-gradient(90deg, #7BAF6E, #ff9900); border-radius: 3px; animation: fill 1.2s ease-in-out forwards; }}
@keyframes fill {{ from {{ width: 0%; }} to {{ width: 100%; }} }}
.status {{ font-size: 13px; color: #2e7d32; margin-top: 8px; font-weight: bold; }}
</style>
</head>
<body>
<div class="container">
  <div class="mascot">🌿🛒</div>
  <div class="msg">ふれまーるちゃんがカートに入れてるよ～</div>
  <div class="sub">{title}</div>
  <div class="progress">
    <div class="progress-bar"><div class="progress-fill"></div></div>
    <div class="status" id="st">Amazonのカートに追加中...</div>
  </div>
</div>
<script>
// 1.2秒の演出後にAmazonカート追加URLへ直接遷移
// ユーザーのブラウザCookieでログイン済みAmazonカートに自動追加される
setTimeout(function() {{
  document.getElementById('st').textContent = 'カートに追加完了！移動中...';
  window.location.href = '{cart_add_url}';
}}, 1200);
</script>
</body>
</html>"""

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-cache, no-store",
        },
        "body": page_html,
    }


def _serve_amazon_login_html(event: dict) -> dict:
    """Amazon 連携ページ — Cookie保存方式でNova Actがカート操作可能になる"""
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
.container {{ max-width: 420px; width: 92%; padding: 20px; }}
.card {{ background: #fff; border-radius: 16px; padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 16px; }}
h1 {{ font-size: 18px; text-align: center; margin-bottom: 16px; color: #2d5016; }}
.desc {{ font-size: 13px; color: #555; line-height: 1.6; margin-bottom: 16px; text-align: center; }}
.btn {{ width: 100%; padding: 14px; border: none; border-radius: 10px; font-size: 15px; font-weight: bold; cursor: pointer; margin-bottom: 10px; }}
.btn-amazon {{ background: #ff9900; color: #111; }}
.btn-confirm {{ background: #2d5016; color: #fff; }}
.btn-confirm:disabled {{ opacity: 0.5; cursor: not-allowed; }}
.btn-back {{ background: #e8e8e8; color: #333; }}
.success {{ text-align: center; }}
.success .icon {{ font-size: 48px; margin-bottom: 12px; }}
.success .msg {{ font-size: 16px; color: #155724; margin-bottom: 12px; }}
.step {{ display: none; }}
.step.active {{ display: block; }}
.cookie-area {{ margin: 16px 0; }}
.cookie-area textarea {{ width: 100%; height: 100px; border: 2px solid #ddd; border-radius: 8px; padding: 10px; font-size: 12px; font-family: monospace; resize: vertical; }}
.cookie-area textarea:focus {{ border-color: #ff9900; outline: none; }}
.cookie-help {{ font-size: 11px; color: #666; margin-top: 8px; line-height: 1.5; }}
.status-msg {{ font-size: 13px; text-align: center; margin: 10px 0; padding: 8px; border-radius: 8px; }}
.status-msg.error {{ background: #fde8e8; color: #c53030; }}
.status-msg.success {{ background: #e8f5e9; color: #155724; }}
.tab-btns {{ display: flex; gap: 8px; margin-bottom: 16px; }}
.tab-btn {{ flex: 1; padding: 10px; text-align: center; border: 2px solid #ddd; border-radius: 8px; font-size: 13px; cursor: pointer; font-weight: bold; }}
.tab-btn.active {{ border-color: #ff9900; background: #fff8e8; }}
</style>
</head>
<body>
<div class="container">
<div class="card">
<h1>🛒 Amazon セッション連携</h1>

<div id="step-login" class="step active">
<p class="desc">Amazonのセッション情報を連携すると、<br>ふれまーるちゃんが<strong>サーバーサイドで自動的にカートに追加</strong>できるようになります🌿</p>

<div class="tab-btns">
  <div class="tab-btn active" onclick="showTab('easy')">かんたん連携</div>
  <div class="tab-btn" onclick="showTab('manual')">手動Cookie入力</div>
</div>

<div id="tab-easy" class="tab-content">
  <p style="font-size:13px;color:#333;margin-bottom:12px;">
    <strong>手順:</strong><br>
    1. 下のボタンでAmazonにログイン<br>
    2. ログイン後このページに戻る<br>
    3. 「セッション取得」ボタンを押す
  </p>
  <button class="btn btn-amazon" onclick="openAmazon()">🔗 Amazon.co.jp にログインする</button>
  <button class="btn btn-confirm" id="btn-auto-capture" onclick="autoCaptureSession()">🔄 セッション取得（ログイン後に押す）</button>
</div>

<div id="tab-manual" class="tab-content" style="display:none;">
  <p style="font-size:12px;color:#333;margin-bottom:8px;">
    ブラウザのDevToolsからAmazon Cookieを貼り付けてください：<br>
    <small>DevTools → Application → Cookies → amazon.co.jp → 全てコピー</small>
  </p>
  <div class="cookie-area">
    <textarea id="cookie-input" placeholder="session-id=xxx-xxxxxxx-xxxxxxx; ubid-acbjp=xxx-xxxxxxx-xxxxxxx; ..."></textarea>
  </div>
  <button class="btn btn-confirm" onclick="saveCookiesManual()">💾 Cookie を保存</button>
  <p class="cookie-help">
    必要なCookie: <code>session-id</code>, <code>ubid-acbjp</code>, <code>session-id-time</code><br>
    これらがあればふれまーるちゃんがカート操作できます。
  </p>
</div>

<div id="status" class="status-msg" style="display:none;"></div>

<button class="btn btn-back" onclick="goBack()" style="margin-top:12px;">← 戻る</button>
</div>

<div id="step-success" class="step">
<div class="success">
  <div class="icon">✅</div>
  <div class="msg">セッション連携完了！</div>
  <p class="desc">ふれまーるちゃんがサーバーサイドで<br>自動カート追加できるようになりました🌿</p>
  <p style="font-size:12px;color:#666;margin-bottom:16px;">ほしいものリストの商品が自動でカートに入ります</p>
  <button class="btn btn-back" onclick="goBack()">LIFFに戻る</button>
</div>
</div>

</div>
</div>
<script>
const USER_ID = "{uid}";
const API_BASE = location.origin;

function showTab(tab) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
  if (tab === 'easy') {{
    document.querySelectorAll('.tab-btn')[0].classList.add('active');
    document.getElementById('tab-easy').style.display = 'block';
  }} else {{
    document.querySelectorAll('.tab-btn')[1].classList.add('active');
    document.getElementById('tab-manual').style.display = 'block';
  }}
}}

function showStatus(msg, type) {{
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = 'status-msg ' + type;
  el.style.display = 'block';
}}

function openAmazon() {{
  window.open('https://www.amazon.co.jp/', '_blank');
}}

async function autoCaptureSession() {{
  // ブラウザから直接Cookieは取れないため、プロキシ経由で確認を試みる
  // 実際にはユーザーのブラウザでAmazonにログイン済みなら、
  // 中間ページ経由でCookieを取得する方法を使う
  showStatus('セッション確認中...', '');
  try {{
    // confirmエンドポイントを呼んでセッション登録
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
      showStatus('連携登録完了！手動Cookie入力でセッションを保存してください。', 'success');
      // 自動でmanualタブに切り替え
      showTab('manual');
    }}
  }} catch(e) {{
    showStatus('エラー: ' + e.message, 'error');
  }}
}}

async function saveCookiesManual() {{
  const raw = document.getElementById('cookie-input').value.trim();
  if (!raw) {{
    showStatus('Cookie文字列を入力してください', 'error');
    return;
  }}

  // Cookie文字列をパース: "key=value; key2=value2" 形式
  const cookies = {{}};
  raw.split(/[;\\n]/).forEach(function(pair) {{
    pair = pair.trim();
    if (!pair) return;
    var eq = pair.indexOf('=');
    if (eq > 0) {{
      var key = pair.substring(0, eq).trim();
      var val = pair.substring(eq + 1).trim();
      cookies[key] = val;
    }}
  }});

  if (!cookies['session-id']) {{
    showStatus('session-id Cookie が見つかりません。正しい形式で入力してください。', 'error');
    return;
  }}

  showStatus('保存中...', '');
  try {{
    const headers = {{}};
    const cachedUid = localStorage.getItem('ars_user_id');
    if (cachedUid) headers['X-ARS-User-Id'] = cachedUid;
    headers['Content-Type'] = 'application/json';

    const res = await fetch('/api/amazon/save-cookies', {{
      method: 'POST',
      headers: headers,
      body: JSON.stringify({{ cookies: cookies }})
    }});
    const data = await res.json();
    if (data.success) {{
      document.getElementById('step-login').classList.remove('active');
      document.getElementById('step-success').classList.add('active');
    }} else {{
      showStatus(data.error || '保存に失敗しました', 'error');
    }}
  }} catch(e) {{
    showStatus('エラー: ' + e.message, 'error');
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
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-cache, no-store",
        },
        "body": html,
    }


def _handle_amazon_add_to_cart(user_id: str, ddb, body: dict) -> dict:
    """POST /api/amazon/add-to-cart — ほしいものリストから商品を選んでカートURL生成"""
    import random
    from services.amazon_cart_service import (
        generate_add_to_cart_url, generate_add_and_checkout_url, extract_asin,
    )
    from services.wishlist_service import get_active_items_for_recommendation

    max_price = int(body.get("max_price", 5000))

    # ユーザーのほしいものリストから商品を取得
    items = get_active_items_for_recommendation(user_id, ddb, max_price=max_price)

    if not items:
        return _make_response(404, {
            "error": "ほしいものリストに商品がありません。先にほしいものリストを登録してね🌿",
        })

    # ランダムに1つ選択
    item = random.choice(items)

    # ASIN を抽出
    product_url = item.get("product_url", "")
    asin = extract_asin(product_url)

    product = {
        "title": item.get("product_title", "商品"),
        "price": item.get("price"),
        "product_url": product_url,
        "image_url": item.get("product_image_url"),
        "asin": asin,
    }

    if asin:
        product["add_to_cart_url"] = generate_add_to_cart_url(asin)
        product["checkout_url"] = generate_add_and_checkout_url(asin)
    else:
        # ASIN 抽出不可 → 商品ページ直接リンク
        product["add_to_cart_url"] = product_url
        product["checkout_url"] = product_url

    # DynamoDB に記録
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    ddb.put_item(f"USER#{user_id}", "AMAZON_CART_LAST", {
        "asin": asin or "",
        "title": product["title"],
        "price": product.get("price"),
        "cart_url": product["add_to_cart_url"],
        "checkout_url": product["checkout_url"],
        "product_url": product_url,
        "created_at": ts,
    })

    return _make_response(200, {
        "success": True,
        "product": product,
        "message": f"「{product['title']}」を見つけました！",
    })


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
