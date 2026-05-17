"""
おすすめフロー — カテゴリ → 予算 → Bedrock 生成

状態管理: DynamoDB RECOMMEND_STATE# に step を保持（TTL: 10分）
全応答は Reply で返す（Push 通数ゼロ）
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional

from services.bedrock_service import BedrockService
from services.dynamodb_service import DynamoDBService
from services.finance_engine import calculate_slack
from utils.logger import get_logger

logger = get_logger(__name__)

_bedrock = BedrockService()

CATEGORIES = {
    "グルメ": ["グルメ", "食べ物", "スイーツ", "ごはん", "食事"],
    "エンタメ": ["エンタメ", "趣味", "ゲーム", "映画", "音楽"],
    "リラックス": ["リラックス", "美容", "癒し", "温泉", "マッサージ"],
    "ギフト": ["プレゼント", "ギフト", "お土産"],
    "おまかせ": ["おまかせ", "なんでも", "任せる", "わからない"],
}

BUDGET_OPTIONS = {
    "1000": 1000,
    "3000": 3000,
    "5000": 5000,
    "おまかせ": None,
}

SK_RECOMMEND_STATE = "RECOMMEND_STATE#"


def start_recommend(user_id: str, ddb: DynamoDBService) -> list[dict]:
    """おすすめフロー開始 — カテゴリ質問を返す"""
    pk = f"USER#{user_id}"
    ttl = int(time.time()) + 600  # 10分

    ddb.put_item(pk, SK_RECOMMEND_STATE, {
        "step": "WAITING_CATEGORY",
        "ttl": ttl,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    text = (
        "おすすめタイムだね！🎁\n"
        "何のおすすめがほしい？\n\n"
        "🍽️ グルメ・スイーツ\n"
        "🎮 エンタメ・趣味\n"
        "💆 リラックス・美容\n"
        "🎁 プレゼント・ギフト\n"
        "🤷 なんでもいい！おまかせ"
    )
    return [{"type": "text", "text": text}]


def handle_recommend_reply(
    user_id: str, text: str, state: dict, ddb: DynamoDBService
) -> list[dict]:
    """おすすめフローの中間状態を処理する"""
    step = state.get("step", "")
    pk = f"USER#{user_id}"

    if step == "WAITING_CATEGORY":
        category = _match_category(text)
        ttl = int(time.time()) + 600
        ddb.put_item(pk, SK_RECOMMEND_STATE, {
            "step": "WAITING_BUDGET",
            "category": category,
            "ttl": ttl,
            "created_at": state.get("created_at", ""),
        })
        reply = (
            "予算はどのくらい？\n\n"
            "💰 〜1,000円\n"
            "💰 〜3,000円\n"
            "💰 〜5,000円\n"
            "🤷 おまかせ"
        )
        return [{"type": "text", "text": reply}]

    elif step == "WAITING_BUDGET":
        category = state.get("category", "おまかせ")
        budget = _match_budget(text, user_id, ddb)
        # 状態クリア
        ddb.delete_item(pk, SK_RECOMMEND_STATE)
        # Bedrock でおすすめ生成（Flex Message 返却）
        return _generate_recommendation(user_id, category, budget, ddb)

    else:
        # 不明な状態 → クリア
        ddb.delete_item(pk, SK_RECOMMEND_STATE)
        return [{"type": "text", "text": "ごめん、最初からやり直してね🎀"}]


def _match_category(text: str) -> str:
    """ユーザー入力からカテゴリを判定"""
    text_lower = text.strip()
    for cat, keywords in CATEGORIES.items():
        if any(kw in text_lower for kw in keywords):
            return cat
    return "おまかせ"


def _match_budget(text: str, user_id: str, ddb: DynamoDBService) -> int:
    """ユーザー入力から予算を判定"""
    text = text.strip().replace(",", "").replace("，", "").replace("円", "")
    for key, val in BUDGET_OPTIONS.items():
        if key in text:
            if val is None:
                return _get_remaining_budget(user_id, ddb)
            return val
    # 数値抽出を試みる
    try:
        amount = int("".join(c for c in text if c.isdigit()))
        if amount > 0:
            return amount
    except (ValueError, TypeError):
        pass
    return _get_remaining_budget(user_id, ddb)


def _get_remaining_budget(user_id: str, ddb: DynamoDBService) -> int:
    """残予算を取得"""
    try:
        slack = calculate_slack(user_id, ddb)
        return max(int(slack), 1000)
    except Exception:
        return 3000


def _generate_recommendation(
    user_id: str, category: str, budget: int, ddb: DynamoDBService
) -> list[dict]:
    """Bedrock でおすすめを生成し Flex Message で返す"""
    pk = f"USER#{user_id}"

    # 嗜好情報を取得
    pref = ddb.get_item(pk=pk, sk="PREF_MEMORY#") or {}
    pref_categories = pref.get("categories", [])

    prompt = (
        f"あなたは「リワードちゃん」という可愛い女の子キャラクターです。\n"
        f"ユーザーに予算{budget}円以内で「{category}」カテゴリのご褒美を3つおすすめしてください。\n\n"
        f"ユーザーの好み: {', '.join(pref_categories) if pref_categories else '特になし'}\n\n"
        f"条件:\n"
        f"- 各おすすめは①②③の番号付きで\n"
        f"- 各アイテムに商品名、価格目安、一言コメントを含める\n"
        f"- リワードちゃんの口調（タメ口、可愛い、絵文字使用）で\n"
        f"- 最後に「気になるのあった？😊」で締める\n"
        f"- 200文字以内で簡潔に"
    )

    try:
        result_text = _bedrock.invoke_text(
            prompt=prompt,
            system_prompt="あなたはリワードちゃんです。可愛くフレンドリーにおすすめを紹介します。",
            max_tokens=400,
            temperature=0.9,
        )
        body_text = result_text.strip()
    except Exception as e:
        logger.warning("recommend_bedrock_error", error=str(e))
        body_text = (
            f"{category}で{budget}円くらいだと…🎀\n\n"
            f"① ちょっといいスイーツ 🍰\n"
            f"② 入浴剤セット 🛁\n"
            f"③ お気に入りのカフェでゆっくり ☕\n\n"
            f"気になるのあった？😊"
        )

    # Flex Message Bubble（テキスト本文 + アクションボタン）
    flex_message = {
        "type": "flex",
        "altText": f"🎁 {category}のおすすめを届けたよ〜！",
        "contents": {
            "type": "bubble",
            "styles": {
                "header": {"backgroundColor": "#FF6B9D"},
            },
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"🎁 {category}のおすすめ",
                        "color": "#FFFFFF",
                        "weight": "bold",
                        "size": "md",
                    }
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": body_text,
                        "wrap": True,
                        "size": "sm",
                        "color": "#333333",
                    }
                ],
            },
            "footer": {
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#FF6B9D",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "気になる！🎀",
                            "data": f"action=interested&item={category}",
                        },
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "もう一度",
                            "data": "action=start_recommend",
                        },
                    },
                ],
            },
        },
    }
    return [flex_message]
