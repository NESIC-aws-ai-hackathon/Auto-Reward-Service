"""
hotpepper_service ユニットテスト
"""
import sys
import os

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

# パス設定（src/ と layer/python は conftest.py が追加済み）


class TestParseBudget:
    def test_円のみ(self):
        from services.hotpepper_service import _parse_budget
        assert _parse_budget("3000円") == Decimal("3000")

    def test_範囲表記_下限を返す(self):
        from services.hotpepper_service import _parse_budget
        assert _parse_budget("2001～3000円") == Decimal("2001")

    def test_チルダ表記(self):
        from services.hotpepper_service import _parse_budget
        assert _parse_budget("1000~2000円") == Decimal("1000")

    def test_空文字(self):
        from services.hotpepper_service import _parse_budget
        assert _parse_budget("") == Decimal("0")

    def test_不正文字(self):
        from services.hotpepper_service import _parse_budget
        assert _parse_budget("不明") == Decimal("0")

    def test_カンマ付き(self):
        from services.hotpepper_service import _parse_budget
        assert _parse_budget("1,500円") == Decimal("1500")


def _make_shop(shop_id="S001", name="テスト食堂", budget_avg="1500円",
               genre="和食", url="https://example.com", image="https://img.com/1.jpg",
               station="渋谷"):
    return {
        "id": shop_id,
        "name": name,
        "budget": {"average": budget_avg},
        "genre": {"name": genre},
        "urls": {"pc": url},
        "photo": {"pc": {"m": image}},
        "station_name": station,
    }


class TestParseResponse:
    def test_正常系_1件パース(self):
        from services.hotpepper_service import _parse_response
        data = {"results": {"shop": [_make_shop()]}}
        result = _parse_response(data)
        assert len(result) == 1
        assert result[0].shop_id == "S001"
        assert result[0].name == "テスト食堂"
        assert result[0].price == Decimal("1500")
        assert result[0].genre_name == "和食"

    def test_画像なし(self):
        from services.hotpepper_service import _parse_response
        shop = _make_shop()
        shop["photo"] = {}
        data = {"results": {"shop": [shop]}}
        result = _parse_response(data)
        assert result[0].image_url is None

    def test_空レスポンス(self):
        from services.hotpepper_service import _parse_response
        assert _parse_response({}) == []
        assert _parse_response({"results": {}}) == []

    def test_不正アイテムはスキップ(self):
        from services.hotpepper_service import _parse_response
        # 正常なアイテムと不正なアイテム（budget が None）を混在
        shops = [
            _make_shop("S001"),
            None,  # 不正アイテム → スキップされる
            _make_shop("S002"),
        ]
        data = {"results": {"shop": [s for s in shops if s]}}  # None 除外してテスト
        result = _parse_response(data)
        assert len(result) == 2

    def test_商品名100文字トリム(self):
        from services.hotpepper_service import _parse_response
        long_name = "あ" * 120
        data = {"results": {"shop": [_make_shop(name=long_name)]}}
        result = _parse_response(data)
        assert len(result[0].name) == 100


class TestSearchRestaurants:
    @patch("services.hotpepper_service._get_api_key")
    @patch("services.hotpepper_service._call_with_retry")
    def test_正常系_レストランリストを返す(self, mock_call, mock_key):
        from services.hotpepper_service import search_restaurants
        mock_key.return_value = "test_key"
        mock_call.return_value = {"results": {"shop": [_make_shop()]}}

        result = search_restaurants("和食", count=3)

        assert len(result) == 1
        mock_call.assert_called_once()
        call_params = mock_call.call_args[0][1]
        assert call_params["keyword"] == "和食"
        assert call_params["count"] == 3
        assert call_params["format"] == "json"

    @patch("services.hotpepper_service._get_api_key")
    @patch("services.hotpepper_service._call_with_retry")
    def test_リトライ全失敗_HotPepperAPIError(self, mock_call, mock_key):
        from services.hotpepper_service import search_restaurants, HotPepperAPIError
        mock_key.return_value = "test_key"
        mock_call.side_effect = HotPepperAPIError("失敗")

        with pytest.raises(HotPepperAPIError):
            search_restaurants("失敗テスト")


class TestGetApiKey:
    def test_シークレットなし_HotPepperAPIError(self, monkeypatch):
        from services.hotpepper_service import _get_api_key
        import services.hotpepper_service as mod
        mod._cached_api_key = None  # キャッシュリセット

        with patch("services.hotpepper_service.get_secret") as mock_sec:
            mock_sec.return_value = {}  # HOTPEPPER_API_KEY なし
            with pytest.raises(Exception):
                _get_api_key()
        mod._cached_api_key = None  # クリーンアップ
