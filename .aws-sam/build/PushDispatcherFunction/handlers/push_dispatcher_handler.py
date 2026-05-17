"""
Push ディスパッチャーハンドラー — 10 分おきに起動

責務:
  1. PUSH_QUEUE#{today} から scheduled_at <= now AND status = "pending" を取得
  2. daily_push.generate_daily_push() でメッセージ生成
  3. push_manager.send_push() で送信
  4. status を "sent" に更新
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.daily_push import generate_daily_push
from services.dynamodb_service import get_dynamodb_service
from services.push_manager import send_push
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))


def handler(event: dict, context) -> dict:
    """EventBridge から 10 分おきに起動される"""
    # ウォームアップ
    if event.get("source") == "warmup":
        return {"statusCode": 200, "body": "warm"}

    logger.info("push_dispatcher_start")
    ddb = get_dynamodb_service()
    now_jst = datetime.now(_JST)
    today_str = now_jst.strftime("%Y-%m-%d")
    now_str = now_jst.strftime("%Y-%m-%dT%H:%M:%S")
    queue_pk = f"PUSH_QUEUE#{today_str}"

    # PUSH_QUEUE から pending を取得
    try:
        queue_items = ddb.query_by_pk(pk=queue_pk, sk_prefix="USER#")
    except Exception as e:
        logger.error("push_dispatcher_query_failed", error=str(e))
        return {"statusCode": 500, "body": "Queue query failed"}

    # 予定時刻到達 + pending のものを処理
    pending_items = [
        item for item in queue_items
        if item.get("status") == "pending"
        and item.get("scheduled_at", "9999") <= now_str
    ]

    sent_count = 0
    failed_count = 0

    for item in pending_items:
        sk = item.get("SK", "")
        if not sk.startswith("USER#"):
            continue
        user_id = sk.replace("USER#", "")

        # メッセージ生成
        try:
            push_msg = generate_daily_push(user_id, ddb)
        except Exception as e:
            logger.warning(
                "push_message_generation_failed",
                error=str(e),
                user_id_prefix=user_id[:6],
            )
            _update_queue_status(ddb, queue_pk, sk, "failed")
            failed_count += 1
            continue

        if push_msg is None:
            _update_queue_status(ddb, queue_pk, sk, "skipped")
            continue

        # Push 送信
        category = push_msg.pop("category", "")
        template_id = push_msg.pop("template_id", "")

        success = send_push(
            user_id=user_id,
            message=push_msg,
            ddb=ddb,
            category=category,
            template_id=template_id,
        )

        if success:
            _update_queue_status(ddb, queue_pk, sk, "sent", category=category)
            sent_count += 1
        else:
            _update_queue_status(ddb, queue_pk, sk, "failed")
            failed_count += 1

    logger.info(
        "push_dispatcher_complete",
        pending=len(pending_items),
        sent=sent_count,
        failed=failed_count,
    )

    return {
        "statusCode": 200,
        "body": f"Sent: {sent_count}, Failed: {failed_count}",
    }


def _update_queue_status(
    ddb, queue_pk: str, sk: str, status: str, category: str = ""
) -> None:
    """PUSH_QUEUE のステータスを更新する"""
    try:
        updates = {"status": status}
        if category:
            updates["category"] = category
        ddb.update_item(pk=queue_pk, sk=sk, updates=updates)
    except Exception as e:
        logger.warning("push_queue_update_failed", error=str(e))
