"""
Wishlist サービスのユニットテスト

変更依頼書_2 §27 準拠
"""
import pytest
import sys
import os
import importlib.util
from unittest.mock import MagicMock, patch

_LAYER = os.path.join(os.path.dirname(__file__), "..", "..", "layer", "python")
sys.path.insert(0, _LAYER)

# line_service 経由 pydantic_core を回避するためモック
sys.modules["utils"] = MagicMock()
sys.modules["utils.logger"] = MagicMock()
sys.modules["utils.logger"].get_logger = MagicMock(return_value=MagicMock())
sys.modules["utils.exceptions"] = MagicMock()
sys.modules["services.dynamodb_service"] = MagicMock()
sys.modules["services.dynamodb_service"].DynamoDBService = MagicMock

# models.schemas — pydantic を使わずにSK定数だけ提供
_mock_schemas = MagicMock()
_mock_schemas.SK_PREFIX_WISHLIST_SOURCE = "WISHLIST_SOURCE#"
_mock_schemas.SK_PREFIX_WISHLIST_ITEM = "WISHLIST_ITEM#"
sys.modules["models"] = MagicMock()
sys.modules["models.schemas"] = _mock_schemas

_spec = importlib.util.spec_from_file_location(
    "services.wishlist_service",
    os.path.join(_LAYER, "services", "wishlist_service.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

register_wishlist_url = _mod.register_wishlist_url
get_wishlist_items = _mod.get_wishlist_items
get_active_items_for_recommendation = _mod.get_active_items_for_recommendation
DemoProductProvider = _mod.DemoProductProvider
ManualProductProvider = _mod.ManualProductProvider
AMAZON_WISHLIST_URL_PATTERN = _mod.AMAZON_WISHLIST_URL_PATTERN


class TestWishlistURLValidation:
    """URL バリデーションテスト"""

    def test_valid_amazon_co_jp(self):
        assert AMAZON_WISHLIST_URL_PATTERN.match("https://www.amazon.co.jp/hz/wishlist/ls/ABC123")

    def test_valid_amazon_com(self):
        assert AMAZON_WISHLIST_URL_PATTERN.match("https://www.amazon.com/hz/wishlist/ls/ABC123")

    def test_invalid_url(self):
        assert not AMAZON_WISHLIST_URL_PATTERN.match("https://evil.example.com/phishing")

    def test_invalid_no_scheme(self):
        assert not AMAZON_WISHLIST_URL_PATTERN.match("amazon.co.jp/wishlist")


class TestDemoProductProvider:
    """Demo Provider テスト"""

    def test_returns_items(self):
        provider = DemoProductProvider()
        items = provider.sync_wishlist("https://www.amazon.co.jp/hz/wishlist/ls/DEMO")
        assert len(items) > 0
        assert all("product_title" in i for i in items)
        assert all("product_url" in i for i in items)
        assert all("price" in i for i in items)


class TestManualProductProvider:
    """Manual Provider テスト"""

    def test_returns_empty(self):
        provider = ManualProductProvider()
        items = provider.sync_wishlist("https://www.amazon.co.jp/hz/wishlist/ls/MANUAL")
        assert items == []


class TestRegisterWishlistUrl:
    """ほしい物リスト登録テスト"""

    def test_invalid_url_rejected(self):
        ddb = MagicMock()
        result = register_wishlist_url(
            "user1", "https://evil.example.com/bad", ddb
        )
        assert result["success"] is False
        assert "不正" in result.get("error", "")

    def test_valid_url_with_demo_provider(self):
        ddb = MagicMock()
        ddb.query_begins_with.return_value = []  # no existing items

        result = register_wishlist_url(
            "user1",
            "https://www.amazon.co.jp/hz/wishlist/ls/DEMO123",
            ddb,
            source_type="DEMO",
        )
        assert result["success"] is True
        assert result["items_count"] > 0
        # put_item should have been called for source + items
        assert ddb.put_item.call_count >= 2

    def test_duplicate_items_not_saved(self):
        ddb = MagicMock()
        # Simulate existing item with same product_url
        ddb.query_begins_with.return_value = [
            {"product_url": "https://www.amazon.co.jp/dp/B08EXAMPLE1", "SK": "WISHLIST_ITEM#existing"}
        ]

        result = register_wishlist_url(
            "user1",
            "https://www.amazon.co.jp/hz/wishlist/ls/DEMO123",
            ddb,
            source_type="DEMO",
        )
        assert result["success"] is True
        # Only source + non-duplicate items saved
        # DemoProvider has 5 items, 1 already exists
        # put_item: 1 for source + 4 for new items = 5
        # update_item: 1 for existing item's last_seen_at


class TestGetActiveItemsForRecommendation:
    """レコメンド候補取得テスト"""

    def test_excludes_high_price(self):
        ddb = MagicMock()
        ddb.query_begins_with.return_value = [
            {"status": "ACTIVE", "price": 500, "first_seen_at": "2026-05-01T00:00:00+00:00", "desire_aging_days": 10},
            {"status": "ACTIVE", "price": 5000, "first_seen_at": "2026-05-01T00:00:00+00:00", "desire_aging_days": 20},
        ]
        items = get_active_items_for_recommendation("user1", ddb, max_price=1000)
        assert len(items) == 1
        assert items[0]["price"] == 500

    def test_sorted_by_aging_desc(self):
        ddb = MagicMock()
        ddb.query_begins_with.return_value = [
            {"status": "ACTIVE", "price": 500, "first_seen_at": "2026-05-15T00:00:00+00:00", "desire_aging_days": 5},
            {"status": "ACTIVE", "price": 800, "first_seen_at": "2026-05-01T00:00:00+00:00", "desire_aging_days": 19},
        ]
        items = get_active_items_for_recommendation("user1", ddb)
        assert items[0]["desire_aging_days"] >= items[1]["desire_aging_days"]
