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
SK_LAST_SUGGESTION = "LAST_SUGGESTION#"  # 直前のおすすめ候補（テキスト「買った」と紐付け用）


def _save_last_suggestion(user_id: str, candidates: list[dict], ddb: DynamoDBService, source: str = "rakuten") -> None:
    """直前のおすすめ候補を保存する。テキスト「買った/これにする」での購入確定に使用。

    candidates: [{"name": str, "price": int, "url": str, "source": str}, ...]
    TTL: 1 時間
    """
    if not candidates:
        return
    pk = f"USER#{user_id}"
    ttl = int(time.time()) + 3600  # 1 時間
    try:
        ddb.put_item(pk, SK_LAST_SUGGESTION, {
            "candidates": candidates,
            "source": source,
            "ttl": ttl,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning("save_last_suggestion_failed", error=str(e))


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
    candidates = []
    for r in restaurants[:3]:
        bubble = _build_restaurant_bubble(r, user_id)
        bubbles.append(bubble)
        candidates.append({
            "name": str(r.name)[:30],
            "price": int(r.price) if r.price else budget,
            "url": r.shop_url,
            "source": "hotpepper",
            "category": "ご褒美費",
        })

    carousel = {
        "type": "flex",
        "altText": f"🍽️ {category}のおすすめを見つけたよ〜🌿",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }

    _save_last_suggestion(user_id, candidates, ddb, source="hotpepper")

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
    candidates = []
    for p in products[:3]:
        bubble = _build_product_bubble(p, user_id)
        bubbles.append(bubble)
        candidates.append({
            "name": str(p.name)[:30],
            "price": int(p.price),
            "url": p.item_url,
            "source": "rakuten",
            "category": "ご褒美費",
        })

    carousel = {
        "type": "flex",
        "altText": f"🌿 {category}のおすすめを見つけたよ〜",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }

    _save_last_suggestion(user_id, candidates, ddb, source="rakuten")

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


# ─────────────────────────────────────────
# テキスト「買った/これにする/OK」と直前提案の紐付け
# ─────────────────────────────────────────
_PURCHASE_KEYWORDS = (
    "買った", "買いました", "購入した", "ポチった", "ぽちった",
    "これにする", "それにする", "これにした", "それにした",
    "決めた", "決めました", "ok", "OK", "了解", "いいね", "これ買う", "これ買います",
    "行った", "行きました", "行ってきた",
)


def try_handle_last_suggestion_purchase(
    user_id: str, text: str, ddb: DynamoDBService
) -> Optional[list[dict]]:
    """直前のおすすめ提案候補がある状態で「買った」系テキストが来た場合に処理する。

    - 候補が1件なら自動で支出記録
    - 複数候補なら Quick Reply で選択肢を提示
    - 候補無し or キーワード未一致なら None を返す

    Returns:
        list[dict] (LINE messages) または None
    """
    pk = f"USER#{user_id}"
    state = ddb.get_item(pk=pk, sk=SK_LAST_SUGGESTION)
    if not state:
        return None

    candidates = state.get("candidates") or []
    if not candidates:
        ddb.delete_item(pk, SK_LAST_SUGGESTION)
        return None

    text_lower = text.strip().lower()
    if not any(kw.lower() in text_lower for kw in _PURCHASE_KEYWORDS):
        return None

    # 「N番」「1番目」「最初」「2つ目」などの選択語を解釈
    selected_idx = _parse_selection_index(text, len(candidates))

    if selected_idx is not None:
        cand = candidates[selected_idx]
        _record_suggestion_purchase(user_id, cand, ddb)
        ddb.delete_item(pk, SK_LAST_SUGGESTION)
        return [{
            "type": "text",
            "text": (
                f"おっ、{cand.get('name', 'それ')} 買ったんだねぇ～🌿\n"
                f"ご褒美費 ¥{int(cand.get('price', 0)):,} で記録しといたよ〜✨\n"
                f"自分を甘やかせて、ふれまーるちゃんもうれしいなぁ🌱"
            ),
        }]

    # 候補が1件しかなければ即記録
    if len(candidates) == 1:
        cand = candidates[0]
        _record_suggestion_purchase(user_id, cand, ddb)
        ddb.delete_item(pk, SK_LAST_SUGGESTION)
        return [{
            "type": "text",
            "text": (
                f"おっ、{cand.get('name', 'それ')} 買ったんだねぇ～🌿\n"
                f"ご褒美費 ¥{int(cand.get('price', 0)):,} で記録しといたよ〜✨"
            ),
        }]

    # 複数候補 → Quick Reply で確認
    items = []
    for i, cand in enumerate(candidates[:3]):
        label = f"{i+1}番 {str(cand.get('name', ''))[:10]}"
        items.append({
            "type": "action",
            "action": {
                "type": "message",
                "label": label[:20],
                "text": f"{i+1}番 買った",
            },
        })
    items.append({
        "type": "action",
        "action": {"type": "message", "label": "違うやつ", "text": "違うやつ買った"},
    })

    return [{
        "type": "text",
        "text": "おっ、どれを買ったかなぁ～？🌿 教えてくれたら記録するねぇ〜",
        "quickReply": {"items": items},
    }]


def _parse_selection_index(text: str, max_count: int) -> Optional[int]:
    """「1番」「2つ目」「最初」などから候補インデックスを推測する。"""
    text = text.strip()
    if any(kw in text for kw in ("最初", "1番", "1つ目", "一番", "ひとつめ", "1番目")):
        return 0 if max_count >= 1 else None
    if any(kw in text for kw in ("2番", "2つ目", "二番", "ふたつめ", "2番目", "真ん中")):
        return 1 if max_count >= 2 else None
    if any(kw in text for kw in ("3番", "3つ目", "三番", "みっつめ", "3番目", "最後")):
        return 2 if max_count >= 3 else None
    m = re.match(r"^\s*([1-9])\s*[番つ]", text)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < max_count:
            return idx
    return None


def _record_suggestion_purchase(user_id: str, cand: dict, ddb: DynamoDBService) -> None:
    """選ばれた候補を ご褒美費 として支出記録する。"""
    try:
        from datetime import date
        import uuid
        pk = f"USER#{user_id}"
        now = datetime.now(timezone.utc).isoformat()
        today = date.today().strftime("%Y-%m-%d")
        expense_id = uuid.uuid4().hex[:8]
        ddb.put_item(pk, f"EXPENSE#{today}#{expense_id}", {
            "entityType": "EXPENSE",
            "item_name": cand.get("name", "ご褒美"),
            "amount": int(cand.get("price", 0)),
            "category": cand.get("category", "ご褒美費"),
            "source": "recommend",
            "url": cand.get("url", ""),
            "date": today,
            "createdAt": now,
        })
        # streak 更新
        try:
            from services.streak import update_streak
            update_streak(user_id, ddb)
        except Exception:
            pass
    except Exception as e:
        logger.warning("record_suggestion_purchase_failed", error=str(e))
