"""
RecoveryProvider - Generates recovery suggestions based on stress level.
Prioritizes free (0-yen) recovery options.
"""
import random
from datetime import datetime, timezone, timedelta

from shared.data_access import (
    DataAccess,
    SK_STRESS_SUMMARY,
    SK_REWARD_PERMIT,
    SK_REWARD_SKIP,
)
from shared.bedrock_client import BedrockClient


FREE_RECOVERY_OPTIONS = {
    "light": [
        "好きな音楽を1曲聴く",
        "窓を開けて深呼吸する",
        "5分だけ外を散歩する",
        "軽いストレッチをする",
        "好きな香りを嗅ぐ",
        "空を見上げてぼーっとする",
    ],
    "moderate": [
        "5分間の深呼吸エクササイズ",
        "温かい飲み物をゆっくり飲む",
        "3分間の瞑想",
        "好きな動画を1本見る",
        "明日やることを3つだけ書き出す",
        "好きな写真を眺める",
    ],
    "strong": [
        "ゆっくりお風呂に浸かる",
        "今日は早めに寝る",
        "信頼できる人に少し話す",
        "好きな場所の写真を眺める",
        "何もしない10分を作る",
        "横になって目を閉じる",
    ],
}

PAID_RECOVERY_OPTIONS = [
    {"text": "コンビニで好きなスイーツを1個買う", "category": "sweets", "budget_hint": "〜500円"},
    {"text": "カフェでお気に入りの一杯を注文する", "category": "cafe", "budget_hint": "〜800円"},
    {"text": "好きなお菓子をお取り寄せする", "category": "sweets", "budget_hint": "〜1500円"},
    {"text": "好きな入浴剤を使う", "category": "self_care", "budget_hint": "〜500円"},
    {"text": "好きなアロマキャンドルを灯す", "category": "self_care", "budget_hint": "〜1000円"},
]

RECOVERY_VOICE_SYSTEM = """あなたは「ふれまーるちゃん」です。森に住む妖精のような女の子。
回復案のテキストを、ゆるふわ森ガール口調に変換してください。
- 語尾: 「〜だよ」「〜してみて♪」「〜かもね」「〜かな」
- 押しつけがましくなく、友達が提案するような自然さで
- 語尾に♪や……をたまに入れる
- 1文〜2文で短く"""

RECOVERY_VOICE_PROMPT = """以下の回復案を、ふれまーるちゃんの口調で表現してください。
ユーザー名: {display_name}

回復案:
{items}

JSON配列で出力してください:
[{{"original": "元のテキスト", "voiced": "ふれまーるちゃん口調のテキスト"}}]"""

EMPATHY_MESSAGES = {
    1: "今日はリラックスできてるみたいだね。いい感じ♪ 木漏れ日が気持ちいい日だね。",
    2: "ちょっとお疲れかな？ でも大丈夫、{display_name}はよくがんばってるよ♪",
    3: "今日は少しお疲れみたいだね……。無理しないでね。わたしがそばにいるから。",
    4: "かなり疲れてるみたい……。{display_name}、ちょっと休もう？ 深呼吸してみて♪",
    5: "今日はとっても大変だったんだね……。{display_name}のそばにいるからね。ゆっくりでいいんだよ。",
}


class RecoveryService:
    def __init__(self, da: DataAccess = None, bedrock: BedrockClient = None):
        self.da = da or DataAccess()
        self.bedrock = bedrock or BedrockClient()

    def get_recovery(self, user_id: str) -> dict:
        """Get recovery suggestions for the user based on today's stress."""
        jst = timezone(timedelta(hours=9))
        today = datetime.now(jst).strftime("%Y-%m-%d")

        # Get stress summary
        sk = SK_STRESS_SUMMARY.format(date=today)
        stress = self.da.get_item(f"USER#{user_id}", sk)

        if not stress:
            return {
                "stress_level": None,
                "mood": None,
                "free_recovery": [],
                "paid_recovery": [],
                "message": "まだ今日の判定がないよ。話しかけてね♪",
            }

        stress_level = stress.get("stress_level", 2)
        mood = stress.get("mood", "")

        # Get user profile
        profile = self.da.get_or_create_profile(user_id)
        display_name = profile.get("display_name", "") or "あなた"
        monthly_surplus = profile.get("monthly_surplus", 0)

        # Generate free recovery options
        free_options = self._select_free_options(stress_level)

        # Generate paid recovery (only if surplus > 0)
        paid_options = self._select_paid_options(monthly_surplus) if monthly_surplus > 0 else []

        # Voice conversion
        all_texts = [o["text"] for o in free_options] + [o["text"] for o in paid_options]
        voiced = self._voice_convert(display_name, all_texts)

        # Apply voiced text
        for i, opt in enumerate(free_options):
            opt["text"] = voiced.get(opt["text"], opt["text"])
        for i, opt in enumerate(paid_options):
            opt["text"] = voiced.get(opt["text"], opt["text"])

        # Empathy message
        message = EMPATHY_MESSAGES.get(stress_level, EMPATHY_MESSAGES[2]).format(
            display_name=display_name
        )

        return {
            "stress_level": stress_level,
            "mood": mood,
            "free_recovery": free_options,
            "paid_recovery": paid_options,
            "message": message,
        }

    def record_permit(self, user_id: str, recovery_id: str, recovery_type: str) -> dict:
        """Record that user chose to try a recovery option."""
        now = datetime.now(timezone.utc).isoformat()
        sk = SK_REWARD_PERMIT.format(timestamp=now)
        self.da.put_item(f"USER#{user_id}", sk, {
            "recovery_id": recovery_id,
            "type": recovery_type,
            "created_at": now,
        })
        return {"message": "recorded", "reward_permit_id": sk}

    def record_skip(self, user_id: str, reason: str = "") -> dict:
        """Record that user skipped recovery for today."""
        now = datetime.now(timezone.utc).isoformat()
        sk = SK_REWARD_SKIP.format(timestamp=now)
        self.da.put_item(f"USER#{user_id}", sk, {
            "reason": reason,
            "created_at": now,
        })
        return {"message": "recorded"}

    def _select_free_options(self, stress_level: int) -> list[dict]:
        """Select free recovery options based on stress level."""
        if stress_level <= 2:
            pool = FREE_RECOVERY_OPTIONS["light"]
            count = 2
        elif stress_level == 3:
            pool = FREE_RECOVERY_OPTIONS["moderate"]
            count = 3
        else:
            pool = FREE_RECOVERY_OPTIONS["strong"]
            count = 3

        selected = random.sample(pool, min(count, len(pool)))
        return [
            {"id": f"fr-{i:03d}", "text": text, "category": "free"}
            for i, text in enumerate(selected)
        ]

    def _select_paid_options(self, monthly_surplus: int) -> list[dict]:
        """Select paid recovery options within budget."""
        options = []
        for opt in PAID_RECOVERY_OPTIONS:
            # Parse budget hint to rough number
            hint = opt["budget_hint"]
            try:
                max_price = int(hint.replace("〜", "").replace("円", ""))
            except ValueError:
                max_price = 500

            if max_price <= monthly_surplus:
                options.append(opt)

        selected = random.sample(options, min(2, len(options))) if options else []
        return [
            {
                "id": f"pr-{i:03d}",
                "text": opt["text"],
                "category": opt["category"],
                "budget_hint": opt["budget_hint"],
            }
            for i, opt in enumerate(selected)
        ]

    def _voice_convert(self, display_name: str, texts: list[str]) -> dict:
        """Convert recovery texts to furemaru-chan voice using Bedrock."""
        if not texts:
            return {}

        items_text = "\n".join(f"- {t}" for t in texts)
        prompt = RECOVERY_VOICE_PROMPT.format(display_name=display_name, items=items_text)

        try:
            result = self.bedrock.invoke_json(prompt, system=RECOVERY_VOICE_SYSTEM, temperature=0.7)
            if isinstance(result, list):
                return {item["original"]: item["voiced"] for item in result if "original" in item and "voiced" in item}
        except Exception:
            pass
        return {}
