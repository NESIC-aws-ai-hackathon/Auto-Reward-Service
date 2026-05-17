"""
日次 Push メッセージ生成 — カテゴリ選択 + テンプレート変数埋め

設計方針:
- カテゴリは重み付きランダム選択（ユーザー状態で動的変更）
- テンプレートは具体的な話題 + 答えやすい問いかけで構成
- 過去 7 日の PUSH_LOG と照合し同テンプレ重複を回避
- 時間帯によるトーン切り替え
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from services.dynamodb_service import DynamoDBService
from services.finance_engine import get_reward_budget, get_monthly_spending
from models.schemas import SK_PREFIX_PUSH_LOG, SK_PUSH_SETTINGS, SK_PREFIX_EXPENSE, SK_PREF_MEMORY
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))

# ─────────────────────────────────────────
# 時間帯別トーン
# ─────────────────────────────────────────
_TONES: dict[str, list[str]] = {
    "morning": ["ねね、", "そういえばさ、", "ちょっと聞きたいんだけど、"],
    "lunch": ["お昼だ！", "ランチ中？", "ごはん食べた？"],
    "afternoon": ["ちょっと聞いてよ〜", "ひまな時でいいんだけど、", "急にごめんね笑"],
    "evening": ["おつかれ！", "仕事終わった？", "もう帰り？"],
    "night": ["夜だけどさ、", "寝る前にちょっと！", "今日もおつかれ〜！"],
}


def _get_tone(hour: int) -> str:
    if 10 <= hour < 12:
        return random.choice(_TONES["morning"])
    elif 12 <= hour < 14:
        return random.choice(_TONES["lunch"])
    elif 14 <= hour < 17:
        return random.choice(_TONES["afternoon"])
    elif 17 <= hour < 19:
        return random.choice(_TONES["evening"])
    else:
        return random.choice(_TONES["night"])


# ─────────────────────────────────────────
# メッセージカテゴリ & テンプレート
# ─────────────────────────────────────────
DAILY_CATEGORIES: dict[str, dict[str, Any]] = {
    "food_discovery": {
        "weight": 3,
        "setting_key": "recommendation",
        "templates": [
            "{tone}コンビニの新作スイーツ出てたよ！{name}好きそうだなと思って😋 気になる？",
            "{tone}駅前に新しいカフェできたらしいよ☕ 行ってみたいと思わない？",
            "{tone}今日のランチ何にする？最近{food_pref}系で気になるのある？🍽️",
            "{tone}ちょっと気になったんだけど、最後にちゃんとご褒美ごはん食べたのいつ？笑",
        ],
    },
    "budget_nudge": {
        "weight": 2,
        "setting_key": "budget_nudge",
        "templates": [
            "{tone}今月まだ{remaining}円あるよ〜 何か欲しいものリストにあったりする？🎁",
            "{tone}今月いい感じに節約できてるよ！我慢しすぎてない？たまには使っちゃおうよ😏",
            "{tone}あと{days_left}日で{remaining}円。1日{daily_budget}円使える計算💰 今日は何に使う？",
        ],
    },
    "specific_recommendation": {
        "weight": 3,
        "setting_key": "recommendation",
        "templates": [
            "{tone}{pref_item}好きだったよね？最近なんか新しいの試した？😊",
            "{tone}前に{pref_item}の話してたじゃん？また気になるのある？✨",
            "{tone}{pref_item}で最近のおすすめある？教えて〜🎵",
        ],
    },
    "either_or": {
        "weight": 2,
        "setting_key": "recommendation",
        "templates": [
            "{tone}ご褒美にするなら「食べる系🍰」と「体験する系♨️」どっちが好き？",
            "{tone}今週末どうする？おうちでまったり派？それともどっか行っちゃう派？☀️",
            "{tone}今日のご褒美、甘いもの🍰としょっぱいもの🍕どっちの気分？",
            "{tone}コーヒー☕と紅茶🫖だったらどっち派？おすすめ探してあげる！",
            "{tone}もし3,000円自由に使えるとしたら「食べる」「買う」「体験する」どれにする？",
        ],
    },
    "past_reference": {
        "weight": 2,
        "setting_key": "recommendation",
        "templates": [
            "{tone}最近{past_category}系の出費が多いね！ハマってる感じ？😊",
            "{tone}この前{past_item}って記録してたよね？よかった？また行く？",
        ],
    },
    "deep_dive_preference": {
        "weight": 3,
        "setting_key": "recommendation",
        "templates": [
            "{tone}最近なんか映画観た？🎬 おすすめあったら教えて！",
            "{tone}Netflix何か観てる？面白いのあった？📺",
            "{tone}突然だけどラーメンは何系が好き？🍜 味噌？醬油？豚骨？",
            "{tone}好きなコンビニスイーツある？最近のおすすめ知りたい🍮",
            "{tone}この前の休み何してた？😊",
            "{tone}休みの日ってインドア派🏠？アウトドア派☀️？",
            "{tone}最近なんか新しいこと始めた？or 始めたいことある？",
            "{tone}音楽って普段何聴くの？🎵 アーティスト教えて！",
            "{tone}最近買ってよかったものある？ジャンル問わず！",
            "{tone}最近なんか欲しいものってある？予算的にいけるか調べてあげるよ🎁",
        ],
    },
    "anniversary_approach": {
        "weight": 2,
        "setting_key": "anniversary",
        "templates": [
            "{tone}{ann_name}まであと{ann_days}日！何かプレゼント決めた？一緒に考えよっか🎁",
            "{tone}{ann_name}が近づいてるよ〜！何か計画してる？🎂",
        ],
    },
    "streak_challenge": {
        "weight": 1,
        "setting_key": "streak",
        "templates": [
            "{tone}今{streak_days}日連続記録中！すごくない？途切れさせる？😏",
            "{tone}{streak_days}日連続すごいね！今日も何か使ったら教えてね〜🔥",
        ],
    },
}

# ─────────────────────────────────────────
# 公開メソッド
# ─────────────────────────────────────────


def generate_daily_push(user_id: str, ddb: DynamoDBService) -> Optional[dict]:
    """日次 Push メッセージを生成する。送信不要の場合は None を返す。"""
    pk = f"USER#{user_id}"

    # 1. Push 設定チェック
    settings = ddb.get_item(pk=pk, sk=SK_PUSH_SETTINGS) or _default_settings()
    if not settings.get("all_enabled", True):
        return None
    if not settings.get("daily_message", True):
        return None

    # 2. ユーザー情報取得
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    pref_raw = ddb.get_item(pk=pk, sk=SK_PREF_MEMORY) or {}
    pref_items = pref_raw.get("items", [])

    # 3. 予算情報取得
    now_jst = datetime.now(_JST)
    remaining = _get_remaining_budget(user_id, ddb, profile)
    days_left = _days_left_in_month(now_jst)

    # 4. 最近の支出
    recent_expenses = ddb.query_by_pk(
        pk=pk, sk_prefix=SK_PREFIX_EXPENSE, limit=10, descending=True
    )

    # 5. ストリーク
    streak_item = ddb.get_item(pk=pk, sk="STREAK#") or {}
    streak_days = int(streak_item.get("current_streak", 0))

    # 6. 過去の PUSH_LOG（重複回避用）
    seven_days_ago = (now_jst - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    push_logs = ddb.query_by_pk(pk=pk, sk_prefix=SK_PREFIX_PUSH_LOG)
    recent_templates = {
        log.get("template_id", "") for log in push_logs
        if log.get("SK", "") > f"PUSH_LOG#{seven_days_ago}"
    }

    # 7. 記念日チェック
    anniversaries = profile.get("anniversaries") or []
    upcoming_ann = _find_upcoming_anniversary(anniversaries, now_jst)

    # 8. カテゴリ重み調整
    weights = _adjust_weights(
        pref_count=len(pref_items),
        has_recent_expenses=len(recent_expenses) > 0,
        has_upcoming_anniversary=upcoming_ann is not None,
        settings=settings,
    )

    # 9. カテゴリ選択 + テンプレート選択（重複回避）
    category, template, template_id = _select_template(weights, recent_templates)

    # 10. 変数埋め
    hour = now_jst.hour
    tone = _get_tone(hour)
    name = profile.get("nickname") or "きみ"
    food_pref = _get_food_pref(pref_items)
    pref_item = _get_random_pref(pref_items)
    past_item = _get_past_item(recent_expenses)
    past_category = _get_past_category(recent_expenses)
    daily_budget = remaining // max(days_left, 1)

    variables = {
        "tone": tone,
        "name": name,
        "food_pref": food_pref,
        "pref_item": pref_item,
        "remaining": f"{remaining:,}",
        "days_left": str(days_left),
        "daily_budget": f"{daily_budget:,}",
        "past_item": past_item,
        "past_category": past_category,
        "streak_days": str(streak_days),
        "ann_name": upcoming_ann["name"] if upcoming_ann else "",
        "ann_days": str(upcoming_ann["days"]) if upcoming_ann else "",
    }

    message = _fill_template(template, variables)

    return {
        "type": "text",
        "text": message,
        "category": category,
        "template_id": template_id,
    }


# ─────────────────────────────────────────
# 内部ヘルパー
# ─────────────────────────────────────────


def _default_settings() -> dict:
    return {
        "all_enabled": True,
        "daily_message": True,
        "push_time_start": "10:00",
        "push_time_end": "21:00",
        "budget_nudge": True,
        "recommendation": True,
        "anniversary": True,
        "monthly_report": True,
        "streak": True,
    }


def _get_remaining_budget(user_id: str, ddb: DynamoDBService, profile: dict = None) -> int:
    try:
        if profile is None:
            pk = f"USER#{user_id}"
            profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
        budget = int(get_reward_budget(profile))
        spent = int(get_monthly_spending(user_id, ddb))
        return max(budget - spent, 0)
    except Exception:
        return 0


def _days_left_in_month(now: datetime) -> int:
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    return (next_month - now).days


def _find_upcoming_anniversary(anniversaries: list[dict], now: datetime) -> Optional[dict]:
    today = now.date()
    for ann in anniversaries:
        ann_date_str = ann.get("date", "")
        if not ann_date_str or "-" not in ann_date_str:
            continue
        try:
            parts = ann_date_str.split("-")
            ann_date = today.replace(month=int(parts[0]), day=int(parts[1]))
            if ann_date < today:
                ann_date = ann_date.replace(year=today.year + 1)
            diff = (ann_date - today).days
            if 0 <= diff <= 7:
                return {"name": ann.get("name", "記念日"), "days": diff}
        except (ValueError, IndexError):
            continue
    return None


def _adjust_weights(
    pref_count: int,
    has_recent_expenses: bool,
    has_upcoming_anniversary: bool,
    settings: dict,
) -> dict[str, int]:
    weights = {}
    for cat, config in DAILY_CATEGORIES.items():
        setting_key = config.get("setting_key", "recommendation")
        if not settings.get(setting_key, True):
            continue
        weights[cat] = config["weight"]

    # 記念日優先
    if has_upcoming_anniversary and "anniversary_approach" in weights:
        return {"anniversary_approach": 10}

    # 嗜好データに応じた重み調整
    if pref_count < 5:
        if "deep_dive_preference" in weights:
            weights["deep_dive_preference"] = 5
        if "specific_recommendation" in weights:
            weights["specific_recommendation"] = 1
    else:
        if "specific_recommendation" in weights:
            weights["specific_recommendation"] = 5
        if "deep_dive_preference" in weights:
            weights["deep_dive_preference"] = 1

    # 支出なし → past_reference 無効
    if not has_recent_expenses:
        weights.pop("past_reference", None)

    return weights


def _select_template(
    weights: dict[str, int], recent_templates: set[str]
) -> tuple[str, str, str]:
    """重み付きランダムでカテゴリ→テンプレートを選択（重複回避）"""
    categories = list(weights.keys())
    w_list = [weights[c] for c in categories]

    for _ in range(10):  # 最大 10 回リトライ
        chosen_cat = random.choices(categories, weights=w_list, k=1)[0]
        templates = DAILY_CATEGORIES[chosen_cat]["templates"]
        template = random.choice(templates)
        template_id = f"{chosen_cat}:{templates.index(template)}"
        if template_id not in recent_templates:
            return chosen_cat, template, template_id

    # フォールバック: either_or の先頭テンプレート
    fallback = DAILY_CATEGORIES["either_or"]["templates"][0]
    return "either_or", fallback, "either_or:0"


def _fill_template(template: str, variables: dict[str, str]) -> str:
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", value)
    return result


def _get_food_pref(pref_items: list[dict]) -> str:
    for item in pref_items:
        cat = item.get("category", "")
        if cat == "food":
            return item.get("keyword", "食べ物")
    return "おいしいもの"


def _get_random_pref(pref_items: list[dict]) -> str:
    if not pref_items:
        return "気になるもの"
    item = random.choice(pref_items)
    return item.get("keyword", "気になるもの")


def _get_past_item(expenses: list[dict]) -> str:
    if not expenses:
        return "いいもの"
    expense = random.choice(expenses)
    return expense.get("item_name") or "いいもの"


def _get_past_category(expenses: list[dict]) -> str:
    if not expenses:
        return "お買い物"
    expense = random.choice(expenses)
    return expense.get("ars_category") or "お買い物"
