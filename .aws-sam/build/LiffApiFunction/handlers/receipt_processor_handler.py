"""
SQS トリガー: レシート画像の非同期解析（Unit 3 スライス 3-6）

Webhook から SQS に投げられたメッセージを受け取り、
レシート解析 → 支出保存 → PWA通知の流れを実行する。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

from services.line_service import get_line_service
from services.dynamodb_service import DynamoDBService
from utils.logger import get_logger
import handlers.receipt_analyzer as receipt_analyzer

logger = get_logger(__name__)

_ddb = None


def _get_ddb() -> DynamoDBService:
    global _ddb
    if _ddb is None:
        _ddb = DynamoDBService()
    return _ddb


def handler(event, context):
    """SQS イベントハンドラー"""
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            user_id = body.get("user_id", "")
            message_id = body.get("message_id", "")
            if not user_id or not message_id:
                logger.warning("receipt_processor_missing_fields", body=body)
                continue
            _process_receipt(user_id, message_id)
        except Exception as e:
            logger.exception("receipt_processor_error", record=record, error=str(e))
            raise  # SQS の可視性タイムアウト後にリトライさせる


def _process_receipt(user_id: str, message_id: str) -> None:
    """レシート画像を解析して支出を保存しPWA通知する"""
    ddb = _get_ddb()
    line = get_line_service()

    try:
        image_bytes = line.get_message_content(message_id)
    except Exception as e:
        logger.warning("receipt_get_content_failed", user_id=user_id, error=str(e))
        from services.notification_service import create_notification
        create_notification(
            user_id, ddb,
            notification_type="SYSTEM",
            title="レシート読み取り失敗",
            message_text="レシートの読み込みに失敗しちゃった😅 もう一度送ってみてね～",
        )
        return

    reply_text, items_to_save = receipt_analyzer.analyze(
        image_bytes=image_bytes,
        content_type="image/jpeg",
        user_id=user_id,
        ddb=ddb,
    )

    # 支出保存
    if items_to_save:
        pk = f"USER#{user_id}"
        now = datetime.now(timezone.utc)
        ts = now.isoformat()
        month_sk = f"MONTHLY_SUMMARY#{now.strftime('%Y-%m')}"
        profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
        reward_budget = int(profile.get("reward_budget_monthly", 30_000))
        for item in items_to_save:
            expense_sk = f"EXPENSE#{ts}_{id(item)}"
            ddb.put_item(pk, expense_sk, {
                "entityType": "EXPENSE",
                "item_name": item.get("item_name"),
                "amount": item.get("amount", 0),
                "store_name": item.get("store_name"),
                "ars_category": item.get("category"),
                "source": "receipt_async",
                "confidence": item.get("confidence", 1.0),
                "created_at": ts,
            })
            amount = int(item.get("amount") or 0)
            if amount > 0:
                ddb.add_to_monthly_summary(
                    pk=pk,
                    month_sk=month_sk,
                    amount=amount,
                    reward_budget=reward_budget,
                    updated_at=ts,
                )

    # PWA 通知で結果を通知
    from services.notification_service import create_notification
    create_notification(
        user_id, ddb,
        notification_type="SYSTEM",
        title="レシート解析完了",
        message_text=reply_text,
    )
    logger.info("receipt_processed", user_id=user_id, items_count=len(items_to_save))
