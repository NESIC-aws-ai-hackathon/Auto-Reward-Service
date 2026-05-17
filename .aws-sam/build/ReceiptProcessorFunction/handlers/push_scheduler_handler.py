"""
Push スケジューラーハンドラー — 毎朝 JST 10:00 起動

責務:
  1. entityType-index GSI で全 ACTIVE ユーザーを取得
  2. 各ユーザーの PUSH_SETTINGS を確認
  3. 10:00〜21:00 のランダム時刻を生成
  4. PUSH_QUEUE#{date} に書き込み
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from models.schemas import ENTITY_PROFILE, SK_PUSH_SETTINGS
from services.dynamodb_service import get_dynamodb_service
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))


def handler(event: dict, context) -> dict:
    """EventBridge から毎朝 10:00 JST に起動される"""
    # ウォームアップ
    if event.get("source") == "warmup":
        return {"statusCode": 200, "body": "warm"}

    logger.info("push_scheduler_start")
    ddb = get_dynamodb_service()
    now_jst = datetime.now(_JST)
    today_str = now_jst.strftime("%Y-%m-%d")
    queue_pk = f"PUSH_QUEUE#{today_str}"

    # 全 ACTIVE ユーザーを取得
    try:
        profiles = ddb.query_by_gsi(entity_type=ENTITY_PROFILE, filter_expr={"status": "ACTIVE"})
    except Exception as e:
        logger.error("push_scheduler_gsi_query_failed", error=str(e))
        return {"statusCode": 500, "body": "GSI query failed"}

    scheduled_count = 0
    skipped_count = 0

    for profile in profiles:
        user_pk = profile.get("PK", "")
        if not user_pk.startswith("USER#"):
            continue

        user_id = user_pk.replace("USER#", "")

        # PUSH_SETTINGS チェック
        settings = ddb.get_item(pk=user_pk, sk=SK_PUSH_SETTINGS) or {}
        if not settings.get("all_enabled", True):
            skipped_count += 1
            continue
        if not settings.get("daily_message", True):
            skipped_count += 1
            continue

        # 配信時間帯
        time_start = settings.get("push_time_start", "10:00")
        time_end = settings.get("push_time_end", "21:00")

        # ランダム時刻生成
        scheduled_time = _random_time_in_range(now_jst, time_start, time_end)
        scheduled_at = scheduled_time.strftime("%Y-%m-%dT%H:%M:%S")

        # TTL: 翌日 00:00 JST
        tomorrow_midnight = (now_jst + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        ttl = int(tomorrow_midnight.timestamp())

        # PUSH_QUEUE 書き込み
        try:
            ddb.put_item(
                pk=queue_pk,
                sk=f"USER#{user_id}",
                item={
                    "scheduled_at": scheduled_at,
                    "status": "pending",
                    "ttl": ttl,
                },
            )
            scheduled_count += 1
        except Exception as e:
            logger.warning(
                "push_queue_write_failed",
                error=str(e),
                user_id_prefix=user_id[:6],
            )

    logger.info(
        "push_scheduler_complete",
        scheduled=scheduled_count,
        skipped=skipped_count,
        total=len(profiles),
    )

    return {
        "statusCode": 200,
        "body": f"Scheduled: {scheduled_count}, Skipped: {skipped_count}",
    }


def _random_time_in_range(base_date: datetime, start: str, end: str) -> datetime:
    """指定した時間帯内のランダム時刻を生成する"""
    start_parts = start.split(":")
    end_parts = end.split(":")
    start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
    end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])

    random_minutes = random.randint(start_minutes, end_minutes)
    hour = random_minutes // 60
    minute = random_minutes % 60

    return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
