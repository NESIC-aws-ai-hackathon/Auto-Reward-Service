"""
ご褒美マッチャー（Reward Matcher）

寄り道レーンに合うご褒美候補を REWARD_POOL + Bedrock 生成で提案する。
"""
from __future__ import annotations

import json
import re
from typing import Optional

from services.dynamodb_service import DynamoDBService
from services.bedrock_service import BedrockService
from utils.logger import get_logger

logger = get_logger(__name__)
_bedrock = BedrockService()

# lane_type → REWARD_POOL のカテゴリ対応
_LANE_TO_REWARD_CATEGORIES: dict[str, list[str]] = {
    "CAFE_REBOOT": ["情緒安定費", "趣味費"],
    "CONVENIENCE_RECOVERY": ["回復費"],
    "SELF_COOKING_ESCAPE": ["グルメ費"],
    "LOW_COST_RECOVERY": ["回復費", "緊急回復費"],
    "RICHER_ESCAPE": ["グルメ費", "美容費"],
}

# lane_type → デフォルトのご褒美候補（Bedrock 失敗時のフォールバック）
_DEFAULT_REWARDS: dict[str, list[dict]] = {
    "CAFE_REBOOT": [
        {"name": "季節限定フラペチーノ", "price": 680, "emoji": "🥤", "source": "default"},
        {"name": "濃厚チーズケーキ", "price": 520, "emoji": "🍰", "source": "default"},
    ],
    "CONVENIENCE_RECOVERY": [
        {"name": "プレミアムプリン", "price": 298, "emoji": "🍮", "source": "default"},
        {"name": "ハーゲンダッツ", "price": 351, "emoji": "🍨", "source": "default"},
    ],
    "SELF_COOKING_ESCAPE": [
        {"name": "替玉＋トッピング", "price": 300, "emoji": "🍜", "source": "default"},
        {"name": "サイドメニュー追加", "price": 400, "emoji": "🥟", "source": "default"},
    ],
    "LOW_COST_RECOVERY": [
        {"name": "栄養ドリンク", "price": 200, "emoji": "💊", "source": "default"},
        {"name": "入浴剤", "price": 350, "emoji": "🛁", "source": "default"},
    ],
    "RICHER_ESCAPE": [
        {"name": "デザートセット", "price": 800, "emoji": "🍰", "source": "default"},
        {"name": "グラスワイン", "price": 600, "emoji": "🍷", "source": "default"},
    ],
}


def match_rewards_to_lane(
    user_id: str,
    lane_type: str,
    places: list[dict],
    budget_remaining: int,
    ddb: DynamoDBService,
) -> list[dict]:
    """レーンに合うご褒美候補を2〜3件返す。"""
    pk = f"USER#{user_id}"

    # 嗜好データ
    pref = ddb.get_item(pk=pk, sk="PREF_MEMORY#") or {}
    food_likes = pref.get("food", {}).get("likes", []) if isinstance(pref.get("food"), dict) else []

    # REWARD_POOL からカテゴリマッチする候補を取得
    categories = _LANE_TO_REWARD_CATEGORIES.get(lane_type, ["回復費"])
    pool_items = _get_pool_rewards(pk, categories, budget_remaining, ddb)

    # Bedrock でパーソナライズ候補を生成
    generated = _generate_personalized_rewards(
        lane_type, places, food_likes, budget_remaining,
    )

    # 統合してスコア順
    all_rewards = pool_items + generated
    all_rewards.sort(key=lambda x: x.get("score", 0), reverse=True)

    result = all_rewards[:3]
    if not result:
        result = _DEFAULT_REWARDS.get(lane_type, [])[:2]

    # reward_id を付与
    for i, r in enumerate(result):
        if "reward_id" not in r:
            r["reward_id"] = f"rw_{lane_type.lower()}_{i:03d}"

    return result


def _get_pool_rewards(
    pk: str, categories: list[str], budget: int, ddb: DynamoDBService
) -> list[dict]:
    """REWARD_POOL# からカテゴリに合う候補を取得。"""
    try:
        pools = ddb.query_by_pk(pk=pk, sk_prefix="REWARD_POOL#", limit=50)
        matched = []
        for item in pools:
            cat = item.get("category", "")
            price = int(item.get("price", 0) or 0)
            if cat in categories and 0 < price <= budget:
                matched.append({
                    "name": item.get("name", ""),
                    "price": price,
                    "emoji": item.get("emoji", "🎁"),
                    "source": "reward_pool",
                    "match_reason": f"{cat}カテゴリからのおすすめ",
                    "score": 60,
                    "url": item.get("url", ""),
                })
        return matched[:5]
    except Exception as e:
        logger.warning("reward_pool_query_failed", error=str(e))
        return []


def _generate_personalized_rewards(
    lane_type: str,
    places: list[dict],
    food_likes: list,
    budget: int,
) -> list[dict]:
    """Bedrock でパーソナライズしたご褒美候補を生成。"""
    place_names = ", ".join(p.get("name", "") for p in places[:2])
    likes_str = ", ".join(str(l) for l in food_likes[:5]) if food_likes else "まだわからない"

    prompt = (
        f"あなたはふれまーるちゃんのアシスタントAIです。\n"
        f"ユーザーの好み: {likes_str}\n"
        f"予算残り: {budget}円\n"
        f"寄り道先: {place_names}\n"
        f"レーンタイプ: {lane_type}\n\n"
        f"この寄り道先で買えそうなおすすめ商品・メニューを2つ提案してください。\n"
        f"以下のJSON配列形式で返してください（それ以外のテキストは不要）:\n"
        f'[{{"name": "商品名", "price": 金額, "emoji": "絵文字1個", "reason": "おすすめ理由(20文字以内)"}}]'
    )

    try:
        raw = _bedrock.invoke_text(prompt, max_tokens=300, temperature=0.7)
        return _parse_reward_json(raw)
    except Exception as e:
        logger.warning("reward_generation_failed", error=str(e))
        return []


def _parse_reward_json(raw: str) -> list[dict]:
    """Bedrock の返答からJSON配列を抽出してパースする。"""
    # JSON配列部分を抽出
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []

    try:
        items = json.loads(match.group())
        result = []
        for item in items:
            if isinstance(item, dict) and "name" in item:
                result.append({
                    "name": item["name"],
                    "price": int(item.get("price", 0)),
                    "emoji": item.get("emoji", "🎁"),
                    "source": "bedrock_generated",
                    "match_reason": item.get("reason", ""),
                    "score": 70,
                })
        return result
    except (json.JSONDecodeError, ValueError):
        return []
