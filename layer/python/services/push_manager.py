"""
Push 送信管理 — 通数カウント + ログ + LINE Push 送信

設計方針:
- 月間 190 通上限チェック（フリープラン 200 通、10 通バッファ）
- PUSH_LOG 書き込み（重複回避 + 分析用）
- PROFILE.push_count_this_month の更新
- 送信エラーは WARNING ログに留め、他ユーザーの処理を継続
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from models.schemas import SK_PREFIX_PUSH_LOG
from services.dynamodb_service import DynamoDBService
from services.line_service import get_line_service
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))
MONTHLY_PUSH_LIMIT = 190  # フリープラン 200 通 - 10 通バッファ
PUSH_LOG_TTL_DAYS = 30


def send_push(
    user_id: str,
    message: dict,
    ddb: DynamoDBService,
    category: str = "",
    template_id: str = "",
) -> bool:
    """Push メッセージを送信し、ログを記録する。

    Args:
        user_id: LINE ユーザー ID
        message: {"type": "text", "text": "..."} 形式
        ddb: DynamoDB サービス
        category: メッセージカテゴリ（ログ用）
        template_id: テンプレート ID（重複回避用）

    Returns:
        True: 送信成功 / False: スキップまたは失敗
    """
    pk = f"USER#{user_id}"

    # 月間通数チェック
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    push_count = int(profile.get("push_count_this_month", 0))
    if push_count >= MONTHLY_PUSH_LIMIT:
        logger.warning("monthly_push_limit_reached", user_id_prefix=user_id[:6])
        return False

    # Push 送信
    try:
        line_service = get_line_service()
        line_service.push_message(user_id=user_id, messages=[message])
    except Exception as e:
        logger.warning("push_send_failed", error=str(e), user_id_prefix=user_id[:6])
        return False

    # push_count_this_month を +1
    try:
        ddb.update_item(pk=pk, sk="PROFILE#", updates={
            "push_count_this_month": push_count + 1,
        })
    except Exception as e:
        logger.warning("push_count_update_failed", error=str(e))

    # PUSH_LOG 記録
    _log_push(pk, ddb, category, template_id, message.get("text", ""))

    return True


def reset_monthly_push_count(user_id: str, ddb: DynamoDBService) -> None:
    """月間 Push カウントをリセットする（月初レポートで呼ばれる）"""
    pk = f"USER#{user_id}"
    try:
        ddb.update_item(pk=pk, sk="PROFILE#", updates={"push_count_this_month": 0})
    except Exception as e:
        logger.warning("push_count_reset_failed", error=str(e))


def _log_push(pk: str, ddb: DynamoDBService, category: str, template_id: str, text: str) -> None:
    """PUSH_LOG を DynamoDB に記録する"""
    now = datetime.now(_JST)
    sk = f"{SK_PREFIX_PUSH_LOG}{now.strftime('%Y-%m-%dT%H:%M:%S')}"
    ttl = int((now + timedelta(days=PUSH_LOG_TTL_DAYS)).timestamp())

    try:
        ddb.put_item(pk=pk, sk=sk, item={
            "category": category,
            "template_id": template_id,
            "message_preview": text[:50] if text else "",
            "created_at": now.isoformat(),
            "ttl": ttl,
        })
    except Exception as e:
        logger.warning("push_log_write_failed", error=str(e))
