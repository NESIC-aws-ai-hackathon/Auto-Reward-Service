"""
LIFF オンボーディングフォーム API ハンドラー

POST /api/onboarding — フォームデータを受け取り DynamoDB に保存
- PROFILE# 更新（monthly_income, reward_budget_monthly, bonus_months, bonus_amount）
- FIXED_COSTS# 作成
- ANNIVERSARY# 作成
- ご褒美枠計算
- 完了通知 Push（初回1回のみ）
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from services.dynamodb_service import DynamoDBService
from services.line_service import get_line_service
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))
LIFF_CHANNEL_ID = os.environ.get("LIFF_CHANNEL_ID", "")

_ddb = None


def _get_ddb():
    global _ddb
    if _ddb is None:
        _ddb = DynamoDBService()
    return _ddb


def handler(event, context):
    """API Gateway HttpApi v2 → Lambda ハンドラー"""
    method = (event.get("requestContext", {}).get("http", {}).get("method", "")).upper()
    raw_path = event.get("rawPath", "")

    # CORS preflight
    if method == "OPTIONS":
        return _make_response(200, {})

    # 認証
    user_id = _extract_user_id(event)
    if not user_id:
        return _make_response(401, {"error": "Unauthorized"})

    if method == "POST" and "/api/onboarding" in raw_path:
        return _handle_onboarding(user_id, event)

    return _make_response(404, {"error": "Not Found"})


def _handle_onboarding(user_id: str, event: dict) -> dict:
    """オンボーディングフォームデータを処理"""
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return _make_response(400, {"error": "Invalid JSON"})

    # バリデーション
    monthly_income = body.get("monthly_income")
    if not monthly_income or int(monthly_income) <= 0:
        return _make_response(400, {"error": "monthly_income は1以上の数値が必要です"})

    monthly_income = int(monthly_income)
    ddb = _get_ddb()
    pk = f"USER#{user_id}"
    now = datetime.now(timezone.utc).isoformat()

    # 固定費計算
    fixed_costs = body.get("fixed_costs", [])
    subscriptions = body.get("subscriptions", [])
    other_fixed = body.get("other_fixed_costs", [])

    all_fixed: list[dict] = []
    total_fixed = 0

    for item in fixed_costs:
        name = item.get("name", "")
        amount = int(item.get("amount", 0))
        if name and amount > 0:
            all_fixed.append({"name": name, "amount": amount})
            total_fixed += amount

    for item in subscriptions:
        name = item.get("name", "")
        amount = int(item.get("amount", 0))
        if name and amount > 0:
            all_fixed.append({"name": name, "amount": amount})
            total_fixed += amount

    for item in other_fixed:
        name = item.get("name", "")
        amount = int(item.get("amount", 0))
        if name and amount > 0:
            all_fixed.append({"name": name, "amount": amount})
            total_fixed += amount

    # ご褒美枠計算: max(3000, min((月収 - 固定費) * 0.15, 30000))
    disposable = monthly_income - total_fixed
    reward_budget = max(3000, min(int(disposable * 0.15), 30000))

    # ボーナス
    bonus_months = body.get("bonus_months", [])
    bonus_amount = int(body.get("bonus_amount", 0))

    # 記念日
    anniversaries = body.get("anniversaries", [])
    valid_anniversaries = []
    for ann in anniversaries:
        name = ann.get("name", "")
        date_str = ann.get("date", "")
        if name and date_str:
            valid_anniversaries.append({"name": name, "date": date_str})

    # DynamoDB 保存
    # PROFILE# 更新
    profile_updates = {
        "monthly_income": monthly_income,
        "reward_budget_monthly": reward_budget,
        "status": "ACTIVE",
        "updatedAt": now,
    }
    if bonus_months:
        profile_updates["bonus_months"] = bonus_months
    if bonus_amount > 0:
        profile_updates["bonus_amount"] = bonus_amount
    if valid_anniversaries:
        profile_updates["anniversaries"] = valid_anniversaries
    nickname = body.get("nickname", "")
    if nickname:
        profile_updates["nickname"] = nickname[:20]

    ddb.update_item(pk=pk, sk="PROFILE#", updates=profile_updates)

    # FIXED_COSTS# 保存
    if all_fixed:
        ddb.put_item(pk, "FIXED_COSTS#", {
            "entityType": "FIXED_COSTS",
            "items": all_fixed,
            "total": total_fixed,
            "updatedAt": now,
        })

    # ONBOARDING_STATE# を COMPLETED に
    ddb.put_item(pk, "ONBOARDING_STATE#", {
        "step": "COMPLETED",
        "monthly_income": monthly_income,
        "fixed_costs_total": total_fixed,
        "reward_budget": reward_budget,
        "updatedAt": now,
    })

    # Push 通知（初回完了通知）
    income_man = monthly_income // 10000
    fixed_man = total_fixed // 10000
    budget_man = reward_budget // 10000
    push_text = (
        f"おっけー！覚えた〜🎀\n"
        f"月収{income_man}万、固定費{fixed_man}万だから…\n"
        f"ごほうび枠は {budget_man}万円くらいから始めよっか！\n\n"
        f"いつでもメニューからダッシュボード見れるからね✨"
    )
    try:
        get_line_service().push_message(user_id, [{"type": "text", "text": push_text}])
    except Exception as e:
        logger.warning("onboarding_push_failed", error=str(e))

    return _make_response(200, {
        "success": True,
        "reward_budget": reward_budget,
        "monthly_income": monthly_income,
        "fixed_costs_total": total_fixed,
    })


def _extract_user_id(event: dict) -> str | None:
    """Bearer token から LINE user ID を取得（liff_api.py と同じロジック）"""
    import base64
    headers = event.get("headers") or {}
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
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
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)
        channel_id = os.environ.get("LIFF_CHANNEL_ID", "") or LIFF_CHANNEL_ID
        if channel_id and payload.get("aud") != channel_id:
            return None
        exp = payload.get("exp", 0)
        if exp < time.time():
            return None
        return payload.get("sub")
    except Exception:
        return None


def _make_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "https://liff.line.me",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Methods": "GET, POST, PUT, OPTIONS",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }
