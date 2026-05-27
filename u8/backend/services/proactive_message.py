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

# 月初メッセージ — 新しい月のはじまり、リセット感
MONTH_START_MESSAGES = [
    "今日から新しい月だね♪ 先月もお疲れさま！ 今月も{display_name}のペースで一緒にやってこ〜。",
    "新しい月のはじまりだよ〜。先月はがんばったね。今月はどんなご褒美を計画しよっか？",
]

# 月末メッセージ — 振り返り誘導
MONTH_END_MESSAGES = [
    "今月もあとちょっとだね。よくがんばった月だったよ。ダッシュボードで振り返ってみる？",
    "もう月末だね〜！ {display_name}、今月の自分にちゃんと「えらい」って言ってあげて♪",
]

# 購入後フォローアップ — 「あれどうだった？」
PURCHASE_FOLLOWUP_MESSAGES = [
    "ねえ、昨日の{item}、どうだった？ 気分上がった？",
    "{item}買ったの覚えてるよ〜。使ってみてどんな感じ？",
    "昨日の{item}、よかった？ ご褒美って大事だよね♪",
]

# 思い出して話しかける — 過去のLIFE_LOGトピックを参照
MEMORY_CALLBACK_MESSAGES = [
    "そういえば最近、{topic}の話してたよね。あれからどう？",
    "{topic}のこと、ふと思い出した♪ いまも楽しんでる？",
    "ねえ、{topic}って言ってたじゃない？ あれからなにか進展あった？",
]

# ご褒美提案メッセージ — ほしいものリスト/ユーザーの興味から
REWARD_SUGGESTION_MESSAGES = [
    "ねえねえ、{item}ってまだ気になってる？ 自分へのご褒美にいいかも♪",
    "そういえば{item}が気になってたよね。今月いけそうじゃない？えへへ。",
    "{item}、チェックしてみた？ たまには自分を甘やかしてもいいと思うな〜♪",
]

# 興味ベースの提案
INTEREST_NUDGE_MESSAGES = [
    "{display_name}、{interest}好きだったよね。なにか新しいの見つけた？",
    "最近{interest}のことあんまり話してないけど、忙しかったのかな？",
    "ねえ、{interest}関連でなにかほしいものある？ 一緒に探そっか♪",
]

# 天気・季節の雑談（バリエーション増）
WEATHER_CHAT_MESSAGES = [
    "今日はなんだかぽかぽかだね〜。お散歩日和かも♪",
    "雨の日は家でゆっくりする口実ができるよね。えへへ。",
    "風が気持ちいい日だね。深呼吸してみて〜♪",
]

# 応援・肯定メッセージ
ENCOURAGEMENT_MESSAGES = [
    "{display_name}、最近ちゃんとがんばってるの知ってるよ。えらいなぁ♪",
    "なんとなくだけど、{display_name}って真面目だよね。たまには手抜きしていいんだよ〜。",
    "今日も{display_name}は{display_name}のままでいいんだよ。そのままが素敵♪",
    "ねえ知ってる？ がんばらない日も大事なんだって。今日はゆるっとね。",
]

# 小さな問いかけ（会話のきっかけ）
TINY_QUESTION_MESSAGES = [
    "ねえ、最近なにかいいことあった？ 小さいことでもいいよ♪",
    "今ハマってるものある？ なんでも聞きたい〜。",
    "今日のごはん何にする？ 決まってなかったら一緒に考えよ♪",
    "週末なにするの？ ……って聞いてみたかっただけ。えへへ。",
    "なんか最近気になってることある？ なんでも話してね〜。",
    "ねえねえ、好きな季節っていつ？ ……急にごめんね、ふと気になって♪",
]


class ProactiveMessageService:
    def __init__(self, da: DataAccess = None):
        self.da = da or DataAccess()
        self.config = get_config()

    def run_scheduled(self) -> dict:
        """Main entry: check all users with push subscriptions and send contextual messages."""
        now_jst = datetime.now(JST)
        hour = now_jst.hour

        # Send between 8:00-23:00 JST (友達感覚で頻度up)
        if hour < 8 or hour >= 23:
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
        """友達感覚: 1日5回まで、1.5時間以上の間隔、75%確率。"""
        today = datetime.now(JST).strftime("%Y-%m-%d")
        prefix = f"PROACTIVE_MSG#{today}"

        existing = self.da.query_by_prefix(f"USER#{user_id}", prefix, limit=10)

        if len(existing) >= 5:
            return False

        # Check last message time (1.5時間 ≒ 2時間粒度で hour 差1以下は弾く)
        if existing:
            last = existing[-1]
            last_hour = int(last.get("hour", 0))
            if hour - last_hour < 2:
                return False

        # Random chance to feel natural
        return random.random() < 0.75

    def _generate_message(self, user_id: str, hour: int) -> str | None:
        """Generate a contextual message based on time and user state."""
        profile = self.da.get_or_create_profile(user_id)
        display_name = profile.get("display_name", "あなた")

        # Check for special conditions (30% chance to skip and use variety pool instead)
        if random.random() < 0.70:
            message = self._check_special_conditions(user_id, display_name)
            if message:
                return message

        # Variety pool: 40% time-based, 20% reward/interest, 20% encouragement, 20% questions
        roll = random.random()

        if roll < 0.20:
            # ご褒美/興味ベースの提案
            msg = self._generate_reward_nudge(user_id, display_name)
            if msg:
                return msg

        if roll < 0.40:
            # 応援・肯定
            template = random.choice(ENCOURAGEMENT_MESSAGES)
            return template.format(display_name=display_name)

        if roll < 0.55:
            # 小さな問いかけ
            return random.choice(TINY_QUESTION_MESSAGES)

        if roll < 0.65:
            # 天気・季節の雑談
            return random.choice(WEATHER_CHAT_MESSAGES)

        # Time-based message selection (残りの35%)
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

    def _generate_reward_nudge(self, user_id: str, display_name: str) -> str | None:
        """ほしいものリストやユーザーの興味に基づいてご褒美を提案する。"""
        # 1. ほしいものリストから提案
        try:
            wishlist_items = self.da.query_by_prefix(
                f"USER#{user_id}", "WISHLIST_ITEM#", limit=10,
            ) or []
            if wishlist_items and random.random() < 0.6:
                item = random.choice(wishlist_items)
                item_name = (item.get("name") or "").strip()
                if item_name:
                    template = random.choice(REWARD_SUGGESTION_MESSAGES)
                    return template.format(item=item_name[:20])
        except Exception:
            pass

        # 2. ユーザーの興味から提案
        try:
            interests_data = self.da.get_item(f"USER#{user_id}", "USER_INTERESTS#")
            if interests_data:
                interests = interests_data.get("interests", [])
                if interests:
                    top = sorted(interests, key=lambda x: x.get("score", 0), reverse=True)[:5]
                    chosen = random.choice(top)
                    interest_name = chosen.get("category", "")
                    if interest_name:
                        template = random.choice(INTEREST_NUDGE_MESSAGES)
                        return template.format(display_name=display_name, interest=interest_name)
        except Exception:
            pass

        return None

    def _check_special_conditions(self, user_id: str, display_name: str) -> str | None:
        """Check for special conditions that warrant specific messages."""
        from datetime import date
        from calendar import monthrange
        today = date.today()

        # 1. 月初 (1日) — 朝の時間帯のみ
        if today.day == 1 and 8 <= datetime.now(JST).hour < 12:
            return random.choice(MONTH_START_MESSAGES).format(display_name=display_name)

        # 2. 月末 (月の最終日) — 夕方以降のみ
        last_day = monthrange(today.year, today.month)[1]
        if today.day == last_day and datetime.now(JST).hour >= 17:
            return random.choice(MONTH_END_MESSAGES).format(display_name=display_name)

        # 3. 購入フォローアップ — 直近1日以内の支出があれば30%で言及
        if random.random() < 0.30:
            yesterday = (today - timedelta(days=1)).isoformat()
            recent_expenses = self.da.query_by_prefix(
                f"USER#{user_id}", f"EXPENSE#{yesterday}", limit=3,
            ) or []
            if recent_expenses:
                last = recent_expenses[-1]
                item = (last.get("item") or "").strip()
                # 食品でない＆少し贅沢っぽい支出を優先（食費は日常）
                category = (last.get("category") or "")
                if item and category not in ["食費", "交通費", "光熱費"]:
                    return random.choice(PURCHASE_FOLLOWUP_MESSAGES).format(item=item[:20])

        # 4. 思い出して話しかける — LIFE_LOGからトピックを引用 20%
        if random.random() < 0.20:
            life_logs = self.da.query_by_prefix_latest(
                f"USER#{user_id}", "LIFE_LOG#", limit=30,
            ) or []
            topics = [log.get("topic", "").strip() for log in life_logs if log.get("topic")]
            topics = [t for t in topics if t and 2 <= len(t) <= 20]
            if topics:
                topic = random.choice(topics)
                return random.choice(MEMORY_CALLBACK_MESSAGES).format(topic=topic)

        # 5. 久しぶり (2日以上沈黙)
        two_days_ago = (today - timedelta(days=2)).isoformat()
        recent_chats = self.da.query_by_prefix(
            f"USER#{user_id}",
            f"CHAT#{two_days_ago}",
            limit=1,
        )

        if not recent_chats:
            template = random.choice(NO_TALK_MESSAGES)
            return template.format(display_name=display_name)

        # 6. ストリーク
        streak = self.da.get_item(f"USER#{user_id}", "STREAK#")
        if streak:
            days = streak.get("current_streak", 0)
            if days >= 3 and days in [3, 7, 14, 30]:
                template = random.choice(STREAK_MESSAGES)
                return template.format(display_name=display_name, streak_days=days)

        return None

    def _save_and_notify(self, user_id: str, message: str) -> None:
        """CHAT#として保存することでチャット履歴に表示され、そこから会話を続けられる。"""
        from datetime import datetime, timezone
        now_jst = datetime.now(JST)
        timestamp = now_jst.isoformat()

        # CHAT# プレフィクスで保存（ChatPageで通常の会話として表示される）
        self.da.put_item(f"USER#{user_id}", f"CHAT#{timestamp}", {
            "role": "assistant",
            "text": message,
            "timestamp": timestamp,
            "proactive": True,
        })

        # 履歴互換のため CONVERSATION_TURN# にも残す（既存UIが参照していた場合に備える）
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
