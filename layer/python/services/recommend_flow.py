"""
おすすめフロー — カテゴリ → 予算 → 実商品検索（楽天/ホットペッパー）

状態管理: DynamoDB RECOMMEND_STATE# に step を保持（TTL: 10分）
全応答は Reply で返す（Push 通数ゼロ）
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Optional

from services.dynamodb_service import DynamoDBService
from services.finance_engine import calculate_slack
from services.rakuten_service import search_products, RakutenProduct, RakutenAPIError
from services.hotpepper_service import search_restaurants, HotPepperRestaurant, HotPepperAPIError
from utils.logger import get_logger

logger = get_logger(__name__)

# カテゴリ設定
CATEGORIES = {
    "グルメ": {
        "keywords": ["グルメ", "食べ物", "スイーツ", "ごはん", "食事", "カフェ", "ランチ"],
        "source": "hotpepper",
        "search_terms": ["ご褒美 ランチ", "スイーツ カフェ", "人気 グルメ"],
    },
    "エンタメ": {
        "keywords": ["エンタメ", "趣味", "ゲーム", "映画", "音楽", "本"],
        "source": "rakuten",
        "search_terms": ["ゲーム 人気", "漫画 話題", "趣味 グッズ"],
    },
    "リラックス": {
        "keywords": ["リラックス", "美容", "癒し", "温泉", "マッサージ", "バス"],
        "source": "rakuten",
        "search_terms": ["入浴剤 ギフト", "アロマ リラックス", "美容 ご褒美"],
    },
    "ギフト": {
        "keywords": ["プレゼント", "ギフト", "お土産"],
        "source": "rakuten",
        "search_terms": ["ギフト 人気", "プレゼント おしゃれ", "お取り寄せ ギフト"],
    },
    "おまかせ": {
        "keywords": ["おまかせ", "なんでも", "任せる", "わからない"],
        "source": "rakuten",
        "search_terms": ["ご褒美 自分用", "癒し グッズ", "人気 ランキング"],
    },
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
        "おすすめタイムだねぇ～🌿\n"
        "何のおすすめがほしい？\n\n"
        "🍽️ グルメ・スイーツ\n"
        "🎮 エンタメ・趣味\n"
        "💆 リラックス・美容\n"
        "🎁 プレゼント・ギフト\n"
        "🤷 なんでもいい～おまかせ～"
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
            "予算はどのくらいがいいかなぁ～？\n\n"
            "💰 ～1,000円\n"
            "💰 ～3,000円\n"
            "💰 ～5,000円\n"
            "🤷 おまかせ～"
        )
        return [{"type": "text", "text": reply}]

    elif step == "WAITING_BUDGET":
        category = state.get("category", "おまかせ")
        budget = _match_budget(text, user_id, ddb)
        # 状態クリア
        ddb.delete_item(pk, SK_RECOMMEND_STATE)
        # 実商品検索（Flex Carousel 返却）
        return _generate_recommendation(user_id, category, budget, ddb)

    else:
        # 不明な状態 → クリア
        ddb.delete_item(pk, SK_RECOMMEND_STATE)
        return [{"type": "text", "text": "ごめんねぇ～、最初からやり直してみてね🌿"}]


def _match_category(text: str) -> str:
    """ユーザー入力からカテゴリを判定"""
    text_lower = text.strip()
    for cat, info in CATEGORIES.items():
        if any(kw in text_lower for kw in info["keywords"]):
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
    """実商品/飲食店を検索し Flex Carousel で返す"""
    cat_info = CATEGORIES.get(category, CATEGORIES["おまかせ"])
    source = cat_info.get("source", "rakuten")
    search_terms = cat_info.get("search_terms", [])

    if source == "hotpepper":
        return _search_hotpepper(user_id, category, budget, search_terms, ddb)
    else:
        return _search_rakuten(user_id, category, budget, search_terms, ddb)


def _search_hotpepper(
    user_id: str, category: str, budget: int, search_terms: list[str], ddb: DynamoDBService
) -> list[dict]:
    """ホットペッパーで飲食店を検索して Flex Carousel で返す"""
    keyword = random.choice(search_terms) if search_terms else "人気 グルメ"

    try:
        restaurants = search_restaurants(keyword=keyword, count=5)
    except HotPepperAPIError as e:
        logger.warning("recommend_hotpepper_error", error=str(e))
        return [{"type": "text", "text": "ごめんねぇ～、お店の検索がうまくいかなかったみたい🌿 もう一度試してみてね～"}]

    if not restaurants:
        return [{"type": "text", "text": f"うーん、{category}で見つからなかったかも…🌿 別のジャンルも試してみる？"}]

    # Flex Carousel 構築
    bubbles = []
    for r in restaurants[:3]:
        bubble = _build_restaurant_bubble(r, user_id)
        bubbles.append(bubble)

    carousel = {
        "type": "flex",
        "altText": f"🍽️ {category}のおすすめを見つけたよ〜🌿",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }

    intro_text = f"{category}で探してみたよぇ～🌿\n気になるお店があったら見てみてね〜"
    return [{"type": "text", "text": intro_text}, carousel]


def _search_rakuten(
    user_id: str, category: str, budget: int, search_terms: list[str], ddb: DynamoDBService
) -> list[dict]:
    """楽天市場で商品を検索して Flex Carousel で返す"""
    keyword = random.choice(search_terms) if search_terms else "ご褒美"

    try:
        products = search_products(
            keyword=keyword,
            hits=5,
            min_price=300,
            max_price=budget,
        )
    except RakutenAPIError as e:
        logger.warning("recommend_rakuten_error", error=str(e))
        return [{"type": "text", "text": "ごめんねぇ～、商品の検索がうまくいかなかったみたい🌿 もう一度試してみてね～"}]

    if not products:
        return [{"type": "text", "text": f"うーん、{category}で{budget}円以内だと見つからなかったかも…🌿 予算を上げてみる？"}]

    # Flex Carousel 構築
    bubbles = []
    for p in products[:3]:
        bubble = _build_product_bubble(p, user_id)
        bubbles.append(bubble)

    carousel = {
        "type": "flex",
        "altText": f"🌿 {category}のおすすめを見つけたよ〜",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }

    intro_text = f"{category}で{budget}円以内のおすすめを探してみたよぇ～🌿\n気になるのあったら商品ページ見てみてね〜"
    return [{"type": "text", "text": intro_text}, carousel]


def _build_product_bubble(product: RakutenProduct, user_id: str) -> dict:
    """楽天商品の Flex Bubble を構築"""
    price_str = f"¥{int(product.price):,}"
    name = str(product.name)[:40]

    body_contents = [
        {
            "type": "text",
            "text": name,
            "weight": "bold",
            "size": "sm",
            "wrap": True,
            "maxLines": 2,
        },
        {
            "type": "text",
            "text": price_str,
            "size": "lg",
            "color": "#7BAF6E",
            "weight": "bold",
            "margin": "sm",
        },
        {
            "type": "text",
            "text": product.shop_name,
            "size": "xs",
            "color": "#999999",
            "margin": "sm",
        },
    ]

    bubble: dict = {
        "type": "bubble",
        "size": "micro",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#7BAF6E",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "商品を見る🌿",
                        "uri": product.item_url,
                    },
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "買ったよ！",
                        "data": f"action=purchased&price={int(product.price)}&name={name[:20]}",
                    },
                },
            ],
        },
    }

    if product.image_url:
        bubble["hero"] = {
            "type": "image",
            "url": product.image_url.replace("http://", "https://"),
            "size": "full",
            "aspectRatio": "1:1",
            "aspectMode": "cover",
        }

    return bubble


def _build_restaurant_bubble(restaurant: HotPepperRestaurant, user_id: str) -> dict:
    """ホットペッパー飲食店の Flex Bubble を構築"""
    price_str = f"予算 ¥{int(restaurant.price):,}" if restaurant.price else "予算情報なし"
    name = str(restaurant.name)[:40]

    body_contents = [
        {
            "type": "text",
            "text": name,
            "weight": "bold",
            "size": "sm",
            "wrap": True,
            "maxLines": 2,
        },
        {
            "type": "text",
            "text": restaurant.genre_name,
            "size": "xs",
            "color": "#7BAF6E",
            "margin": "sm",
        },
        {
            "type": "text",
            "text": price_str,
            "size": "sm",
            "color": "#333333",
            "margin": "sm",
        },
    ]

    if restaurant.station_name:
        body_contents.append({
            "type": "text",
            "text": f"📍 {restaurant.station_name}",
            "size": "xs",
            "color": "#999999",
            "margin": "sm",
        })

    bubble: dict = {
        "type": "bubble",
        "size": "micro",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#7BAF6E",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "お店を見る🍽️",
                        "uri": restaurant.shop_url,
                    },
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "行ったよ！",
                        "data": f"action=purchased&price={int(restaurant.price)}&name={name[:20]}",
                    },
                },
            ],
        },
    }

    if restaurant.image_url:
        bubble["hero"] = {
            "type": "image",
            "url": restaurant.image_url.replace("http://", "https://"),
            "size": "full",
            "aspectRatio": "3:2",
            "aspectMode": "cover",
        }

    return bubble
