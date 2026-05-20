"""
公開ほしい物リスト連携 / 欲望在庫サービス

変更依頼書_2 §5 準拠 — Provider パターンで差し替え可能な設計
"""
from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from services.dynamodb_service import DynamoDBService
from models.schemas import SK_PREFIX_WISHLIST_SOURCE, SK_PREFIX_WISHLIST_ITEM
from utils.logger import get_logger

logger = get_logger(__name__)

# URL バリデーション
AMAZON_WISHLIST_URL_PATTERN = re.compile(
    r"^https?://(www\.)?amazon\.(co\.jp|com|co\.uk|de|fr|it|es|ca)/.*"
)


# ─────────────────────────────────────────
# Provider Interface
# ─────────────────────────────────────────
class ProductProvider(ABC):
    """ほしい物リストから商品を取得するプロバイダ"""

    @abstractmethod
    def sync_wishlist(self, wishlist_url: str) -> list[dict]:
        """
        公開ほしい物リストURLから商品一覧を取得する。

        Returns:
            list of {product_title, product_url, product_image_url?, price?, category?}
        """
        ...


# ─────────────────────────────────────────
# Demo Provider
# ─────────────────────────────────────────
class DemoProductProvider(ProductProvider):
    """デモ/テスト用: 固定の商品リストを返す"""

    DEMO_ITEMS = [
        {
            "product_title": "BARTH プレミアム入浴剤 30錠",
            "product_url": "https://www.amazon.co.jp/dp/B08EXAMPLE1",
            "product_image_url": "https://m.media-amazon.com/images/example1.jpg",
            "price": 2750,
            "category": "バス用品",
        },
        {
            "product_title": "無印良品 アロマディフューザー",
            "product_url": "https://www.amazon.co.jp/dp/B08EXAMPLE2",
            "product_image_url": "https://m.media-amazon.com/images/example2.jpg",
            "price": 4900,
            "category": "インテリア",
        },
        {
            "product_title": "ルイボスティー ティーバッグ 100包",
            "product_url": "https://www.amazon.co.jp/dp/B08EXAMPLE3",
            "product_image_url": "https://m.media-amazon.com/images/example3.jpg",
            "price": 1280,
            "category": "食品・飲料",
        },
        {
            "product_title": "Anker モバイルバッテリー 10000mAh",
            "product_url": "https://www.amazon.co.jp/dp/B08EXAMPLE4",
            "product_image_url": "https://m.media-amazon.com/images/example4.jpg",
            "price": 3490,
            "category": "モバイルアクセサリー",
        },
        {
            "product_title": "今治タオル バスタオル 2枚セット",
            "product_url": "https://www.amazon.co.jp/dp/B08EXAMPLE5",
            "product_image_url": "https://m.media-amazon.com/images/example5.jpg",
            "price": 3980,
            "category": "日用品",
        },
    ]

    def sync_wishlist(self, wishlist_url: str) -> list[dict]:
        return self.DEMO_ITEMS


# ─────────────────────────────────────────
# Manual Provider
# ─────────────────────────────────────────
class ManualProductProvider(ProductProvider):
    """手動登録用: 空リストを返す(API側で手動追加する前提)"""

    def sync_wishlist(self, wishlist_url: str) -> list[dict]:
        return []


# ─────────────────────────────────────────
# Amazon Public Wishlist Provider (Placeholder)
# ─────────────────────────────────────────
class AmazonPublicWishlistProvider(ProductProvider):
    """
    Amazon公開ほしい物リストのHTMLスクレイピングプロバイダ

    NOTE: Amazon の HTML 構造は頻繁に変わるため不安定。
    取得失敗時は DemoProductProvider にフォールバックする運用を推奨。
    """

    def sync_wishlist(self, wishlist_url: str) -> list[dict]:
        # TODO: requests / BeautifulSoup で公開ページを取得・パース
        # 現段階では Demo にフォールバック
        logger.warning("amazon_public_wishlist_not_implemented_fallback_to_demo")
        return DemoProductProvider().sync_wishlist(wishlist_url)


# ─────────────────────────────────────────
# Service Layer
# ─────────────────────────────────────────
def _get_provider(source_type: str = "AMAZON_PUBLIC_WISHLIST") -> ProductProvider:
    """Provider を取得する"""
    if source_type == "DEMO":
        return DemoProductProvider()
    elif source_type == "MANUAL":
        return ManualProductProvider()
    else:
        return AmazonPublicWishlistProvider()


def register_wishlist_url(
    user_id: str,
    wishlist_url: str,
    ddb: DynamoDBService,
    *,
    display_name: Optional[str] = None,
    source_type: str = "AMAZON_PUBLIC_WISHLIST",
) -> dict:
    """
    公開ほしい物リストURLを登録し、商品を同期する。

    Returns:
        {"success": bool, "source_id": str, "items_count": int, "error"?: str}
    """
    # URL 検証
    if source_type == "AMAZON_PUBLIC_WISHLIST":
        if not AMAZON_WISHLIST_URL_PATTERN.match(wishlist_url):
            return {"success": False, "error": "不正なAmazon URLです"}

    pk = f"USER#{user_id}"
    source_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # WishlistSource 保存
    source_sk = f"{SK_PREFIX_WISHLIST_SOURCE}{source_id}"
    ddb.put_item(pk, source_sk, {
        "wishlist_source_id": source_id,
        "user_id": user_id,
        "source_type": source_type,
        "wishlist_url": wishlist_url,
        "display_name": display_name or "",
        "status": "ACTIVE",
        "last_synced_at": now,
        "createdAt": now,
        "updatedAt": now,
    })

    # 商品同期
    try:
        provider = _get_provider(source_type)
        items = provider.sync_wishlist(wishlist_url)
    except Exception as e:
        logger.error("wishlist_sync_failed", error=str(e))
        ddb.update_item(pk, source_sk, {"status": "SYNC_FAILED", "updatedAt": now})
        return {"success": False, "source_id": source_id, "error": str(e)}

    # 重複チェックしながら商品保存
    saved_count = 0
    for item_data in items:
        item_id = str(uuid.uuid4())
        item_sk = f"{SK_PREFIX_WISHLIST_ITEM}{item_id}"

        # 同一商品の重複チェック (product_url で判定)
        existing = _find_existing_item(pk, item_data.get("product_url", ""), ddb)
        if existing:
            # last_seen_at を更新
            ddb.update_item(pk, existing["SK"], {
                "last_seen_at": now,
                "updatedAt": now,
            })
            continue

        ddb.put_item(pk, item_sk, {
            "wishlist_item_id": item_id,
            "wishlist_source_id": source_id,
            "user_id": user_id,
            "product_title": item_data.get("product_title", ""),
            "product_url": item_data.get("product_url", ""),
            "product_image_url": item_data.get("product_image_url"),
            "price": item_data.get("price"),
            "currency": "JPY",
            "category": item_data.get("category"),
            "first_seen_at": now,
            "last_seen_at": now,
            "desire_aging_days": 0,
            "status": "ACTIVE",
            "createdAt": now,
            "updatedAt": now,
        })
        saved_count += 1

    return {"success": True, "source_id": source_id, "items_count": saved_count}


def get_wishlist_items(
    user_id: str,
    ddb: DynamoDBService,
    *,
    status_filter: Optional[str] = None,
) -> list[dict]:
    """ユーザーの欲望在庫を取得する"""
    pk = f"USER#{user_id}"
    items = ddb.query_begins_with(pk=pk, sk_prefix=SK_PREFIX_WISHLIST_ITEM)

    if status_filter:
        items = [i for i in items if i.get("status") == status_filter]

    # desire_aging_days を再計算
    now = datetime.now(timezone.utc)
    for item in items:
        first_seen = item.get("first_seen_at", "")
        if first_seen:
            try:
                first_dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
                item["desire_aging_days"] = (now - first_dt).days
            except (ValueError, TypeError):
                pass

    return items


def get_active_items_for_recommendation(
    user_id: str,
    ddb: DynamoDBService,
    *,
    max_price: Optional[float] = None,
) -> list[dict]:
    """レコメンド対象のACTIVEアイテムを取得（熟成日数の長い順）"""
    items = get_wishlist_items(user_id, ddb, status_filter="ACTIVE")

    if max_price is not None:
        items = [
            i for i in items
            if i.get("price") is None or float(i.get("price", 0)) <= max_price
        ]

    # 熟成日数の長い順にソート
    items.sort(key=lambda x: x.get("desire_aging_days", 0), reverse=True)
    return items


def _find_existing_item(pk: str, product_url: str, ddb: DynamoDBService) -> Optional[dict]:
    """同じ product_url を持つ既存アイテムを探す"""
    if not product_url:
        return None
    items = ddb.query_begins_with(pk=pk, sk_prefix=SK_PREFIX_WISHLIST_ITEM)
    for item in items:
        if item.get("product_url") == product_url:
            return item
    return None
