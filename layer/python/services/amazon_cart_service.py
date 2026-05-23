"""
Amazon カート操作サービス（ECS不要・URL方式）

仕組み:
  - Amazon の公開 URL スキーム を利用
  - Add to Cart: https://www.amazon.co.jp/gp/aws/cart/add.html?ASIN.1={ASIN}&Quantity.1=1
  - Checkout: 上記 URL に &submit.add-to-cart=Submit を追加後リダイレクト
  - ASIN は商品 URL or DynamoDB レコードから抽出
  - 実際のカート追加・購入はユーザーのブラウザで完結（サーバー側自動操作不要）

設計:
  - Lambda で URL を生成 → フロントでユーザーのブラウザを開く
  - ユーザーは自分の Amazon にログイン済み → 自動でカートに入る
  - 購入: カート追加後チェックアウトページへリダイレクト
"""
from __future__ import annotations

import re
import hashlib
from typing import Optional
from urllib.parse import quote, urlencode

from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
AMAZON_JP_BASE = "https://www.amazon.co.jp"
CART_ADD_URL = f"{AMAZON_JP_BASE}/gp/aws/cart/add.html"
CHECKOUT_URL = f"{AMAZON_JP_BASE}/gp/buy/spc/handlers/display.html"
CART_VIEW_URL = f"{AMAZON_JP_BASE}/gp/cart/view.html"

# ASIN パターン (10 桁英数字, B で始まるか数字10桁)
ASIN_PATTERN = re.compile(r"\b([A-Z0-9]{10})\b")
AMAZON_URL_ASIN_PATTERN = re.compile(r"/(?:dp|gp/product|ASIN)/([A-Z0-9]{10})")


def extract_asin(url_or_text: str) -> Optional[str]:
    """URL またはテキストから Amazon ASIN を抽出する"""
    if not url_or_text:
        return None
    # URL パターンから抽出
    m = AMAZON_URL_ASIN_PATTERN.search(url_or_text)
    if m:
        return m.group(1)
    # テキストから ASIN パターン抽出 (B で始まる10桁)
    for match in ASIN_PATTERN.finditer(url_or_text):
        candidate = match.group(1)
        if candidate.startswith("B") or candidate[0].isdigit():
            return candidate
    return None


def generate_add_to_cart_url(asin: str, quantity: int = 1) -> str:
    """Amazon 「カートに追加」URL を生成する
    
    Amazon の公開 Add-to-Cart URL スキーム:
    ユーザーのブラウザでこのURLを開くと、ログイン済みの場合
    自動的にカートに商品が追加される。
    """
    params = {
        "ASIN.1": asin,
        "Quantity.1": str(quantity),
    }
    return f"{CART_ADD_URL}?{urlencode(params)}"


def generate_add_and_checkout_url(asin: str, quantity: int = 1) -> str:
    """Amazon 「カートに追加してレジに進む」URL を生成する
    
    Add-to-Cart 後に自動でチェックアウトへ遷移する。
    """
    params = {
        "ASIN.1": asin,
        "Quantity.1": str(quantity),
        "submit.add-to-cart": "1",
    }
    return f"{CART_ADD_URL}?{urlencode(params)}"


def generate_checkout_url() -> str:
    """Amazon チェックアウトページの URL を返す"""
    return f"{CART_VIEW_URL}?ref_=nav_cart&proceedToRetailCheckout=1"


def generate_product_url(asin: str) -> str:
    """Amazon 商品ページ URL を生成する"""
    return f"{AMAZON_JP_BASE}/dp/{asin}"


def search_amazon_keyword_url(keyword: str) -> str:
    """Amazon の検索結果 URL を生成する（参考用）"""
    return f"{AMAZON_JP_BASE}/s?k={quote(keyword)}"


# ─────────────────────────────────────────
# 商品 ASIN マスター（ハッカソン用デモデータ）
# カテゴリ → ASIN リスト
# 実運用では PA-API 5.0 or DynamoDB に商品マスタを持つ
# ─────────────────────────────────────────
DEMO_PRODUCTS = {
    "リラックス": [
        {"asin": "B07PFFMP9P", "title": "めぐりズム 蒸気でホットアイマスク 無香料 12枚入", "price": 1100},
        {"asin": "B01EL5LQY2", "title": "バブ 6つの香りお楽しみBOX 48錠", "price": 1280},
        {"asin": "B07D7JNBPG", "title": "小林製薬 あずきのチカラ 目もと用", "price": 880},
    ],
    "スイーツ": [
        {"asin": "B086W2B937", "title": "キットカット ミニ オトナの甘さ 13枚", "price": 298},
        {"asin": "B0184OZMDS", "title": "明治 チョコレート効果カカオ72% 大袋", "price": 780},
        {"asin": "B07GXMJXHP", "title": "ハリボー ゴールドベア 250g", "price": 310},
    ],
    "エンタメ": [
        {"asin": "B09B8V1LZ3", "title": "Fire TV Stick 4K Max", "price": 3980},
        {"asin": "B09B9B61VZ", "title": "Echo Dot 第5世代 チャコール", "price": 3480},
        {"asin": "B08N5WRWNW", "title": "Kindle Paperwhite 第11世代", "price": 4980},
    ],
    "ギフト": [
        {"asin": "B004N3APGO", "title": "Amazonギフトカード Eメールタイプ", "price": 1000},
        {"asin": "B004N3APGO", "title": "Amazonギフトカード Eメールタイプ", "price": 2000},
        {"asin": "B004N3APGO", "title": "Amazonギフトカード Eメールタイプ", "price": 3000},
    ],
    "ビューティー": [
        {"asin": "B000FQNIX0", "title": "ニベア クリーム 大缶 169g", "price": 498},
        {"asin": "B01N4G3JRQ", "title": "TSUBAKI プレミアムモイスト シャンプー 490ml", "price": 798},
        {"asin": "B07GV3GFLF", "title": "ボタニスト ボタニカルシャンプー モイスト 490ml", "price": 1540},
    ],
}


def get_amazon_product_for_category(category: str, max_price: int = 5000) -> Optional[dict]:
    """カテゴリに応じた Amazon 商品を返す（デモ用）"""
    import random

    # カテゴリマッピング
    cat_map = {
        "グルメ": "スイーツ",
        "エンタメ": "エンタメ",
        "リラックス": "リラックス",
        "ギフト": "ギフト",
        "おまかせ": random.choice(list(DEMO_PRODUCTS.keys())),
        "美容": "ビューティー",
    }

    key = cat_map.get(category, random.choice(list(DEMO_PRODUCTS.keys())))
    products = DEMO_PRODUCTS.get(key, [])

    # 予算内の商品をフィルタ
    affordable = [p for p in products if p["price"] <= max_price]
    if not affordable:
        # 全カテゴリから予算内を探す
        all_products = [p for ps in DEMO_PRODUCTS.values() for p in ps]
        affordable = [p for p in all_products if p["price"] <= max_price]

    if not affordable:
        return None

    product = random.choice(affordable)
    return {
        "asin": product["asin"],
        "title": product["title"],
        "price": product["price"],
        "product_url": generate_product_url(product["asin"]),
        "add_to_cart_url": generate_add_to_cart_url(product["asin"]),
        "checkout_url": generate_add_and_checkout_url(product["asin"]),
    }


def build_cart_urls(product_url: str) -> Optional[dict]:
    """
    商品 URL から各種 Amazon カート URL を構築する。
    楽天の URL 等の場合は None を返す。
    """
    asin = extract_asin(product_url or "")
    if not asin:
        return None

    return {
        "asin": asin,
        "product_url": generate_product_url(asin),
        "add_to_cart_url": generate_add_to_cart_url(asin),
        "checkout_url": generate_add_and_checkout_url(asin),
        "cart_view_url": CART_VIEW_URL,
    }
