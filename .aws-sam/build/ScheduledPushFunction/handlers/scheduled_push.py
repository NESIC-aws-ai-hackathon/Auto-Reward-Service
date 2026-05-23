"""
定期 Push 通知スケジューラー

EventBridge (CloudWatch Scheduler) から定期的に呼び出され、
Web Push 登録済みのユーザーに対してプロアクティブな通知を送信する。

通知タイプ:
  - ご褒美リマインド: 「今日もお疲れ様！ご褒美はいかが？」
  - 月次予算リマインド: 「今月のご褒美枠、まだ余裕あるよ～」
  - 寄り道提案: ストレスエンジンの蓄積スコアベース

トリガータイミング:
  - 毎日 18:00 JST (帰宅時間帯)
  - 毎日 21:00 JST (リラックスタイム)

スパム防止:
  - 各ユーザーに対して PUSH_COOLDOWN_HOURS 以内の再送信を行わない
  - 1日1回まで（DAILY_PUSH_LIMIT）
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timezone, timedelta

from services.dynamodb_service import DynamoDBService
from services.notification_service import create_notification
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))
TABLE_NAME = os.environ.get("TABLE_NAME", "ArsTable")
DAILY_PUSH_LIMIT = int(os.environ.get("DAILY_PUSH_LIMIT", "2"))
PUSH_COOLDOWN_HOURS = int(os.environ.get("PUSH_COOLDOWN_HOURS", "1"))

# ご褒美提案メッセージ候補（ふれまーるちゃん口調）
_REWARD_MESSAGES = [
    {
        "title": "今日もお疲れさまっ🌿",
        "body": "頑張った自分にちょっとしたご褒美、どうかなぁ？ ふれまーるちゃんが探しとくね～",
    },
    {
        "title": "ご褒美タイムだよ～🍵",
        "body": "毎日えらいっ！今日は何か自分に優しくしてあげよ？",
    },
    {
        "title": "のんびりしよっ🛁",
        "body": "今日も1日おつかれさま。ちょっとだけ自分を甘やかす時間にしない？",
    },
    {
        "title": "ふれまーるちゃんからのお知らせ💝",
        "body": "あなたの頑張り、ちゃんと見てるよ。ご褒美候補、チェックしてみてね～",
    },
    {
        "title": "今週もがんばったね🌸",
        "body": "週末前のちょこっとご褒美、考えてみない？きっといい気分転換になるよ～",
    },
]

# 月次予算リマインドメッセージ
_BUDGET_MESSAGES = [
    {
        "title": "ご褒美枠、まだ余裕あるよ～✨",
        "body": "今月のご褒美予算、まだ使い切ってないみたい。自分へのご褒美、忘れてない？",
    },
    {
        "title": "月末だよ～！🎁",
        "body": "今月のご褒美枠が残ってるよ。月末までに使わないともったいないかも？",
    },
]


def handler(event, context):
    """Lambda ハンドラー: 定期 Push 通知を送信する"""
    logger.info("scheduled_push_start", event=json.dumps(event))
    ddb = DynamoDBService(TABLE_NAME)

    now_jst = datetime.now(_JST)
    hour = now_jst.hour
    logger.info("scheduled_push_time", hour_jst=hour, date=now_jst.strftime("%Y-%m-%d"))

    # 1. Web Push 登録済みユーザーを全取得
    subscribed_users = _get_subscribed_users(ddb)
    if not subscribed_users:
        logger.info("scheduled_push_no_users")
        return {"statusCode": 200, "body": json.dumps({"sent": 0, "reason": "no_subscribed_users"})}

    logger.info("scheduled_push_users_found", count=len(subscribed_users))

    sent_count = 0
    skipped_count = 0

    for user_id in subscribed_users:
        try:
            # クールダウンチェック
            if _is_push_cooldown(user_id, ddb):
                skipped_count += 1
                continue

            # 日次上限チェック
            if _is_daily_limit_reached(user_id, ddb, now_jst):
                skipped_count += 1
                continue

            # 通知メッセージ選択
            msg = _select_message(user_id, ddb, now_jst)

            # 通知作成 & 送信
            create_notification(
                user_id=user_id,
                ddb=ddb,
                notification_type="SCHEDULED_REWARD_REMIND",
                title=msg["title"],
                message_text=msg["body"],
            )

            # 最終送信時刻を記録
            _record_push_sent(user_id, ddb, now_jst)
            sent_count += 1
            logger.info("scheduled_push_sent", user_id=user_id, title=msg["title"])

        except Exception as e:
            logger.warning("scheduled_push_user_failed", user_id=user_id, error=str(e))

    result = {
        "sent": sent_count,
        "skipped": skipped_count,
        "total_users": len(subscribed_users),
    }
    logger.info("scheduled_push_complete", **result)
    return {"statusCode": 200, "body": json.dumps(result)}


def _get_subscribed_users(ddb: DynamoDBService) -> list[str]:
    """Web Push 登録済みの全ユーザー ID を取得"""
    try:
        items = ddb.query_by_gsi("WEB_PUSH_SUBSCRIPTION")
        # PK から user_id を抽出（PK = "USER#{user_id}"）
        user_ids = set()
        for item in items:
            pk = item.get("PK", "")
            if pk.startswith("USER#"):
                uid = pk[5:]
                if uid and item.get("enabled", True):
                    user_ids.add(uid)
        return list(user_ids)
    except Exception as e:
        logger.error("get_subscribed_users_failed", error=str(e))
        return []


def _is_push_cooldown(user_id: str, ddb: DynamoDBService) -> bool:
    """直近 PUSH_COOLDOWN_HOURS 以内に Push 送信済みならTrue"""
    if PUSH_COOLDOWN_HOURS <= 0:
        return False
    try:
        pk = f"USER#{user_id}"
        item = ddb.get_item(pk, "PUSH_LAST_SENT")
        if not item:
            return False
        last_sent = item.get("sent_at", "")
        if not last_sent:
            return False
        dt = datetime.fromisoformat(last_sent)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_JST)
        cutoff = datetime.now(_JST) - timedelta(hours=PUSH_COOLDOWN_HOURS)
        return dt > cutoff
    except Exception:
        return False


def _is_daily_limit_reached(user_id: str, ddb: DynamoDBService, now: datetime) -> bool:
    """今日の Push 送信回数が上限に達しているか"""
    try:
        pk = f"USER#{user_id}"
        today = now.strftime("%Y-%m-%d")
        item = ddb.get_item(pk, f"PUSH_DAILY#{today}")
        if not item:
            return False
        count = int(item.get("count", 0))
        return count >= DAILY_PUSH_LIMIT
    except Exception:
        return False


def _select_message(user_id: str, ddb: DynamoDBService, now: datetime) -> dict:
    """ユーザーの状況に応じたメッセージを選択"""
    # 月末 (25日以降) で予算に余裕がある場合は予算リマインド
    if now.day >= 25:
        try:
            pk = f"USER#{user_id}"
            month_sk = f"MONTHLY#{now.strftime('%Y-%m')}"
            summary = ddb.get_item(pk, month_sk)
            if summary:
                spent = int(summary.get("total_amount", 0))
                budget = int(summary.get("reward_budget", 20000))
                remaining = budget - spent
                if remaining > budget * 0.3:
                    return random.choice(_BUDGET_MESSAGES)
        except Exception:
            pass

    # 通常のご褒美提案
    return random.choice(_REWARD_MESSAGES)


def _record_push_sent(user_id: str, ddb: DynamoDBService, now: datetime):
    """Push 送信記録を保存"""
    pk = f"USER#{user_id}"
    today = now.strftime("%Y-%m-%d")
    ts = now.isoformat()

    # 最終送信時刻を更新
    ddb.put_item(pk, "PUSH_LAST_SENT", {
        "entityType": "PUSH_LAST_SENT",
        "sent_at": ts,
    })

    # 日次カウンタをインクリメント
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    ttl = int(tomorrow.timestamp())
    ddb.increment_atomic_counter(pk, f"PUSH_DAILY#{today}", attribute="count", ttl=ttl)
