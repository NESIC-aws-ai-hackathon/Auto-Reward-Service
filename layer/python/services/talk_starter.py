"""
リワードちゃん「話す」機能 — 話しかけパターン選択

postback action=start_talk で呼ばれ、ランダムに話しかけメッセージを生成する。
記念日が近い場合はリマインダーメッセージを優先する。
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Optional

from services.dynamodb_service import DynamoDBService
from utils.logger import get_logger

logger = get_logger(__name__)

TALK_STARTERS_MOOD = [
    "ねーねー、最近なんかいいことあった？😊",
    "今日はどんな気分〜？🎵",
    "お疲れさま〜！今週がんばったね✨",
    "ねぇねぇ、最近どう？🎀",
    "なんか楽しいことあった？教えて〜😆",
]

TALK_STARTERS_PREFERENCE = [
    "最近ハマってるものとかある？🤔",
    "休みの日って何してることが多い？",
    "好きな食べ物ベスト3教えて〜🍽️",
    "最近読んだ本とか観た映画ある？📚🎬",
    "今欲しいものとかある？教えて〜🎁",
]

TALK_STARTERS_SEASONAL = [
    "今月も残り少しだね〜✨ 何かご褒美考えてる？",
    "週末だね〜！何か予定ある？😊",
]


def generate_talk_starter(user_id: str, ddb: DynamoDBService) -> list[dict]:
    """話しかけメッセージを生成して LINE messages 形式で返す"""
    pk = f"USER#{user_id}"

    # 記念日チェック
    anniversary_msg = _check_upcoming_anniversary(pk, ddb)
    if anniversary_msg:
        return [{"type": "text", "text": anniversary_msg}]

    # ランダムカテゴリ選択
    category = random.choice(["mood", "preference", "seasonal"])
    if category == "mood":
        text = random.choice(TALK_STARTERS_MOOD)
    elif category == "preference":
        text = random.choice(TALK_STARTERS_PREFERENCE)
    else:
        text = random.choice(TALK_STARTERS_SEASONAL)

    return [{"type": "text", "text": text}]


def _check_upcoming_anniversary(pk: str, ddb: DynamoDBService) -> Optional[str]:
    """7日以内の記念日があればリマインダーメッセージを返す"""
    try:
        profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
        anniversaries = profile.get("anniversaries") or []
        if not anniversaries:
            return None

        today = date.today()
        for ann in anniversaries:
            ann_date_str = ann.get("date", "")
            name = ann.get("name", "記念日")
            if not ann_date_str:
                continue
            try:
                month, day = ann_date_str.split("-") if "-" in ann_date_str else ann_date_str.split("/")
                ann_date = today.replace(month=int(month), day=int(day))
                if ann_date < today:
                    ann_date = ann_date.replace(year=today.year + 1)
                days_until = (ann_date - today).days
                if 0 < days_until <= 7:
                    return f"{name}まであと{days_until}日だよ〜🎂\n何か準備する？"
            except (ValueError, TypeError):
                continue
        return None
    except Exception as e:
        logger.warning("anniversary_check_failed", error=str(e))
        return None
