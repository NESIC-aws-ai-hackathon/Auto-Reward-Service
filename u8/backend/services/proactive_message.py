"""
ProactiveMessageService - Generates and sends friend-like messages throughout the day.
Runs on a schedule (10:00-21:00 JST) and creates chat messages + push notifications.
"""
import json
import random
from datetime import datetime, timezone, timedelta
from shared.data_access import DataAccess, SK_PROFILE, SK_PUSH_SUBSCRIPTION
from shared.config import get_config

JST = timezone(timedelta(hours=9))

# ── Time-based message templates (森ガール/ゆるふわ tone) ──

MORNING_MESSAGES = [
    "おはよ〜。今日もゆるっといこうね。窓の外、どんな天気かな？",
    "おはよ♪ よく眠れた？ 今日はどんな一日にしよっか。",
    "おはよ〜。朝の空気、深呼吸してみて。きもちいいよ♪",
    "おはよ。今日も{display_name}のそばにいるからね。ゆっくりね。",
]

MIDDAY_MESSAGES = [
    "お昼だよ〜。ちゃんとごはん食べた？ 木漏れ日みたいにぽかぽかな午後になるといいね♪",
    "ねえねえ、今日のお昼なに食べたの？ 教えて〜。",
    "午後もがんばってるかな。ちょっとだけ伸びしてみて。気持ちいいよ♪",
    "{display_name}、水分とってる？ お茶でもコーヒーでも、ひと息つこうね。",
]

AFTERNOON_MESSAGES = [
    "3時だよ〜。おやつタイムにしない？ 小さなご褒美って大事だよ♪",
    "今日はどんなことがあった？ よかったら話してね。",
    "ふぅ……午後って眠くならない？ わたしはなる。えへへ。",
    "そろそろ疲れてきてない？ 無理しないでね。{display_name}のペースでいいんだよ。",
]

EVENING_MESSAGES = [
    "おつかれさま〜。今日もよくがんばったね。えらいえらい♪",
    "夜だね。今日一日、{display_name}はどうだった？ 話したいことあったら聞くよ。",
    "今日もおつかれさま。ゆっくり過ごしてね。明日のことは明日の{display_name}に任せよう♪",
    "夜ごはんは食べた？ あったかいもの食べると、心もほっとするよね。",
]

# ── Contextual triggers ──

STRESS_CHECK_MESSAGES = [
    "ねえ、最近ちょっと疲れてない？ 話すだけでも楽になることあるよ♪",
    "なんとなく気になって……。{display_name}、元気？ 無理してない？",
]

NO_TALK_MESSAGES = [
    "ひさしぶり〜！ 元気にしてた？ またお話しよ♪",
    "最近お話できてなくてさみしかったな……。今日はどんな感じ？",
]

STREAK_MESSAGES = [
    "すごい！{streak_days}日連続で記録してるんだね。{display_name}、コツコツ型だ♪",
    "{streak_days}日連続！ 習慣になってきたね。えらいなぁ。",
]


class ProactiveMessageService:
    def __init__(self, da: DataAccess = None):
        self.da = da or DataAccess()
        self.config = get_config()

    def run_scheduled(self) -> dict:
        """Main entry: check all users with push subscriptions and send contextual messages."""
        now_jst = datetime.now(JST)
        hour = now_jst.hour

        # Only send between 10:00-21:00 JST
        if hour < 10 or hour >= 21:
            return {"sent": 0, "reason": "outside_hours"}

        # Get all users with push subscriptions
        # (In production, use a GSI. For MVP, scan is acceptable)
        users = self._get_notifiable_users()

        sent_count = 0
        for user_id in users:
            try:
                if self._should_send_message(user_id, hour):
                    message = self._generate_message(user_id, hour)
                    if message:
                        self._save_and_notify(user_id, message)
                        sent_count += 1
            except Exception:
                continue

        return {"sent": sent_count, "hour": hour}

    def _get_notifiable_users(self) -> list[str]:
        """Get user IDs that have push subscriptions and notifications enabled."""
        # For MVP: scan for PUSH_SUBSCRIPTION items
        import boto3
        from boto3.dynamodb.conditions import Attr

        table = self.da._table
        resp = table.scan(
            FilterExpression=Attr("SK").eq(SK_PUSH_SUBSCRIPTION),
            ProjectionExpression="PK",
        )

        user_ids = []
        for item in resp.get("Items", []):
            pk = item.get("PK", "")
            if pk.startswith("USER#"):
                user_id = pk[5:]
                # Check notification_enabled
                profile = self.da.get_item(f"USER#{user_id}", SK_PROFILE)
                if profile and profile.get("notification_enabled", True):
                    user_ids.append(user_id)

        return user_ids

    def _should_send_message(self, user_id: str, hour: int) -> bool:
        """Determine if we should send a message now (max 3 per day, spaced 3+ hours apart)."""
        today = datetime.now(JST).strftime("%Y-%m-%d")
        prefix = f"PROACTIVE_MSG#{today}"

        existing = self.da.query_by_prefix(f"USER#{user_id}", prefix, limit=10)

        if len(existing) >= 3:
            return False

        # Check last message time
        if existing:
            last = existing[-1]
            last_hour = int(last.get("hour", 0))
            if abs(hour - last_hour) < 3:
                return False

        # Random chance (60%) to feel natural, not robotic
        return random.random() < 0.6

    def _generate_message(self, user_id: str, hour: int) -> str | None:
        """Generate a contextual message based on time and user state."""
        profile = self.da.get_or_create_profile(user_id)
        display_name = profile.get("display_name", "あなた")

        # Check for special conditions
        message = self._check_special_conditions(user_id, display_name)
        if message:
            return message

        # Time-based message selection
        if 10 <= hour < 12:
            pool = MORNING_MESSAGES
        elif 12 <= hour < 14:
            pool = MIDDAY_MESSAGES
        elif 14 <= hour < 18:
            pool = AFTERNOON_MESSAGES
        else:
            pool = EVENING_MESSAGES

        template = random.choice(pool)
        return template.format(display_name=display_name)

    def _check_special_conditions(self, user_id: str, display_name: str) -> str | None:
        """Check for special conditions that warrant specific messages."""
        # Check if user hasn't talked in 2+ days
        from datetime import date
        today = date.today()
        two_days_ago = (today - timedelta(days=2)).isoformat()

        recent_turns = self.da.query_by_prefix(
            f"USER#{user_id}",
            f"CONVERSATION_TURN#{two_days_ago}",
            limit=1,
        )

        if not recent_turns:
            template = random.choice(NO_TALK_MESSAGES)
            return template.format(display_name=display_name)

        # Check streak
        streak = self.da.get_item(f"USER#{user_id}", "STREAK#")
        if streak:
            days = streak.get("current_streak", 0)
            if days >= 3 and days in [3, 7, 14, 30]:
                template = random.choice(STREAK_MESSAGES)
                return template.format(display_name=display_name, streak_days=days)

        return None

    def _save_and_notify(self, user_id: str, message: str) -> None:
        """Save the message as a conversation turn and send push notification."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        now_jst = now.astimezone(JST)
        timestamp = now.isoformat()

        # Save as conversation turn (appears in chat)
        self.da.put_item(f"USER#{user_id}", f"CONVERSATION_TURN#{timestamp}", {
            "session_id": "proactive",
            "role": "assistant",
            "content": message,
            "timestamp": timestamp,
            "turn_index": 0,
            "proactive": True,
        })

        # Save proactive message record (for rate limiting)
        today = now_jst.strftime("%Y-%m-%d")
        self.da.put_item(f"USER#{user_id}", f"PROACTIVE_MSG#{today}#{timestamp}", {
            "hour": now_jst.hour,
            "message": message,
            "timestamp": timestamp,
        })

        # Send push notification
        from services.push_service import PushService
        push = PushService(self.da)
        push.send_notification(
            user_id,
            "🎀 ふれまーるちゃん",
            message[:100],  # Truncate for notification
        )
