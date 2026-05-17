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
            "Access-Control-Allow-Methods": "GET,PUT,OPTIONS",
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
                "item_name": item.get("item_name"),
                "amount": int(item.get("amount", 0)),
                "ars_category": item.get("ars_category"),
                "created_at": item.get("created_at"),
            }
            for item in items
        ],
    })


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
    """GET /api/settings — 設定取得"""
    pk = f"USER#{user_id}"
    profile = ddb.get_item(pk=pk, sk=SK_PROFILE) or {}

    return _make_response(200, {
        "tone": profile.get("tone", "friendly"),
        "reward_budget_monthly": int(profile.get("reward_budget_monthly", 0)),
        "bonus_months": profile.get("bonus_months") or [],
        "bonus_amount": int(profile.get("bonus_amount", 0)),
        "carryover_rate": float(profile.get("carryover_rate", 0.5)),
        "nickname": profile.get("nickname"),
    })


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


def _handle_calendar_status(user_id: str, ddb: DynamoDBService) -> dict:
    """GET /api/calendar/status — カレンダー連携状態"""
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
        else:
            return _make_response(404, {"error": "Not Found"})
    except Exception as e:
        logger.error("liff_api_error", error=str(e), path=raw_path)
        return _make_response(500, {"error": "内部エラーが発生しました"})
