"""
PWA 寄り道レーン API ハンドラー

POST /api/temptation/start   — 現在地からレーン生成
POST /api/temptation/accept  — レーン選択
GET  /api/temptation/history — 寄り道履歴
POST /api/temptation/complete — ワンタップ支出記録

認証: Authorization: Bearer {line_access_token} → LINE Profile API で user_id 取得
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from services.dynamodb_service import DynamoDBService
from services.temptation_engine import (
    build_lanes,
    accept_lane,
    get_temptation_history,
    complete_temptation,
)
from services.location_service import geocode_text
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))
LIFF_CHANNEL_ID = os.environ.get("LIFF_CHANNEL_ID", "2010106872")
_ddb: DynamoDBService | None = None

# CORS: PWA ドメイン
_ALLOWED_ORIGINS = [
    "https://liff.line.me",
    os.environ.get("PWA_ORIGIN", "https://localhost:3000"),
]


def _get_ddb() -> DynamoDBService:
    global _ddb
    if _ddb is None:
        _ddb = DynamoDBService()
    return _ddb


def handler(event: dict, context: Any) -> dict:
    """Lambda エントリポイント。"""
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path = event.get("rawPath", "")

    # CORS preflight
    if method == "OPTIONS":
        return _cors_response(204, "")

    # 認証
    user_id = _authenticate(event)
    if not user_id:
        return _cors_response(401, {"error": "unauthorized"})

    try:
        if path == "/api/temptation/start" and method == "POST":
            return _handle_start(event, user_id)
        elif path == "/api/temptation/accept" and method == "POST":
            return _handle_accept(event, user_id)
        elif path == "/api/temptation/history" and method == "GET":
            return _handle_history(user_id)
        elif path == "/api/temptation/complete" and method == "POST":
            return _handle_complete(event, user_id)
        elif path == "/api/temptation/geocode" and method == "POST":
            return _handle_geocode(event)
        else:
            return _cors_response(404, {"error": "not_found"})
    except Exception as e:
        logger.error("pwa_temptation_error", error=str(e), path=path)
        return _cors_response(500, {"error": "internal_server_error"})


def _handle_start(event: dict, user_id: str) -> dict:
    """POST /api/temptation/start"""
    body = _parse_body(event)
    lat = body.get("lat")
    lng = body.get("lng")
    message = body.get("message", "寄り道したい")
    genre = body.get("genre", "")

    if lat is None or lng is None:
        return _cors_response(400, {"error": "lat and lng are required"})

    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return _cors_response(400, {"error": "invalid lat/lng"})

    # 緯度経度の範囲チェック
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return _cors_response(400, {"error": "lat/lng out of range"})

    result = build_lanes(user_id, lat, lng, message, _get_ddb(), genre=genre)
    return _cors_response(200, result)


def _handle_accept(event: dict, user_id: str) -> dict:
    """POST /api/temptation/accept"""
    body = _parse_body(event)
    session_id = body.get("session_id", "")
    lane_id = body.get("lane_id", "")

    if not session_id or not lane_id:
        return _cors_response(400, {"error": "session_id and lane_id are required"})

    result = accept_lane(user_id, session_id, lane_id, _get_ddb())
    return _cors_response(200, result)


def _handle_history(user_id: str) -> dict:
    """GET /api/temptation/history"""
    result = get_temptation_history(user_id, _get_ddb())
    return _cors_response(200, result)


def _handle_complete(event: dict, user_id: str) -> dict:
    """POST /api/temptation/complete"""
    body = _parse_body(event)
    session_id = body.get("session_id", "")
    lane_id = body.get("lane_id", "")
    amount = body.get("amount")
    item_name = body.get("item_name", "")
    place_name = body.get("place_name", "")
    reward_id = body.get("reward_id")

    if not session_id or not lane_id or amount is None or not item_name:
        return _cors_response(400, {"error": "session_id, lane_id, amount, item_name are required"})

    try:
        amount = int(amount)
    except (ValueError, TypeError):
        return _cors_response(400, {"error": "invalid amount"})

    if amount <= 0 or amount > 1_000_000:
        return _cors_response(400, {"error": "amount out of range"})

    result = complete_temptation(
        user_id=user_id,
        session_id=session_id,
        lane_id=lane_id,
        amount=amount,
        item_name=item_name,
        place_name=place_name,
        reward_id=reward_id,
        ddb=_get_ddb(),
    )
    return _cors_response(200, result)


def _handle_geocode(event: dict) -> dict:
    """POST /api/temptation/geocode — テキストから緯度経度を取得（認証不要）"""
    body = _parse_body(event)
    query = body.get("query", "").strip()

    if not query:
        return _cors_response(400, {"error": "query is required"})
    if len(query) > 100:
        return _cors_response(400, {"error": "query too long"})

    result = geocode_text(query)
    if result is None:
        return _cors_response(404, {"error": "location_not_found", "query": query})

    return _cors_response(200, result)


# ─────────────────────────────────────────
# 認証
# ─────────────────────────────────────────
def _authenticate(event: dict) -> str | None:
    """
    LIFF ID Token（JWT）から LINE ユーザー ID を抽出する。
    liff_api.py と同じ方式（署名検証なし、aud+exp チェックのみ）。
    """
    headers = event.get("headers") or {}
    auth = headers.get("authorization", headers.get("Authorization", ""))
    token = auth.replace("Bearer ", "").strip()
    if not token:
        return None

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        channel_id = os.environ.get("LIFF_CHANNEL_ID", "") or LIFF_CHANNEL_ID
        if channel_id and payload.get("aud") != channel_id:
            logger.warning("liff_token_aud_mismatch", aud=payload.get("aud"))
            return None

        if payload.get("exp", 0) < time.time():
            logger.warning("liff_token_expired")
            return None

        return payload.get("sub")
    except Exception as e:
        logger.warning("liff_token_decode_failed", error=str(e))
        return None


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────
def _parse_body(event: dict) -> dict:
    """リクエストボディをJSONパースする。"""
    body = event.get("body", "")
    if not body:
        return {}
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def _decimal_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _cors_response(status: int, body: Any) -> dict:
    """CORS ヘッダー付きレスポンスを返す。"""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "86400",
        },
        "body": json.dumps(body, default=_decimal_default, ensure_ascii=False) if body else "",
    }
