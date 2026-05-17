"""
連続記録（ストリーク）管理

支出記録時に呼ばれ、ストリークを更新。
マイルストーン到達時にお祝いメッセージを返す。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from services.dynamodb_service import DynamoDBService
from utils.logger import get_logger

logger = get_logger(__name__)

SK_STREAK = "STREAK#"

MILESTONES = {
    3: "3日連続で記録してくれてる！えらい〜✨",
    7: "1週間連続！！すごくない？🎉\nちょっと自分にごほうびしてもいいかもね😏",
    14: "2週間連続！もう習慣になってるね✨",
    30: "1ヶ月連続記録達成〜〜！！🏆🎊\nもうプロだね笑 何か欲しいものリストから選んじゃう？🎁",
}


def update_streak(user_id: str, ddb: DynamoDBService) -> Optional[str]:
    """ストリークを更新し、マイルストーンメッセージがあれば返す"""
    pk = f"USER#{user_id}"
    today_str = str(date.today())

    try:
        streak_item = ddb.get_item(pk=pk, sk=SK_STREAK)
        if not streak_item:
            streak_item = {"current_streak": 0, "longest_streak": 0, "last_record_date": ""}

        last_date = streak_item.get("last_record_date", "")

        # 今日既に記録済み → 何もしない
        if last_date == today_str:
            return None

        yesterday = str(date.today() - timedelta(days=1))
        current = int(streak_item.get("current_streak", 0))

        if last_date == yesterday:
            current += 1
        else:
            current = 1

        longest = max(int(streak_item.get("longest_streak", 0)), current)

        ddb.put_item(pk, SK_STREAK, {
            "current_streak": current,
            "longest_streak": longest,
            "last_record_date": today_str,
        })

        return MILESTONES.get(current)

    except Exception as e:
        logger.warning("streak_update_failed", error=str(e))
        return None


def get_streak(user_id: str, ddb: DynamoDBService) -> dict:
    """現在のストリーク情報を取得"""
    pk = f"USER#{user_id}"
    try:
        item = ddb.get_item(pk=pk, sk=SK_STREAK) or {}
        return {
            "current_streak": int(item.get("current_streak", 0)),
            "longest_streak": int(item.get("longest_streak", 0)),
            "last_record_date": item.get("last_record_date", ""),
        }
    except Exception:
        return {"current_streak": 0, "longest_streak": 0, "last_record_date": ""}
