"""
rakuten_service ユニットテスト

楽天 API HTTP 呼び出しを requests.get のモックで代替してテストする。
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# サービスモジュール import
import services.rakuten_service as rs_mod
from services.rakuten_service import (
    RakutenAPIError,
    RakutenHotel,
    RakutenProduct,
    _parse_response,
    _parse_hotel_response,
    search_products,
    search_hotels,
)


# ─────────────────────────────────────────
# フィクスチャ
# ─────────────────────────────────────────
MOCK_RAKUTEN_RESPONSE = {
    "Items": [
        {
            "itemCode": "shop:item001",
            "itemName": "おいしいプリン 3個セット",
            "itemPrice": 980,
            "genreName": "スイーツ・お菓子",
            "itemUrl": "https://item.rakuten.co.jp/shop/item001/",
            "mediumImageUrls": [{"imageUrl": "https://thumbnail.image.rakuten.co.jp/item001.jpg"}],
            "shopName": "スイーツショップ",
            "reviewAverage": 4.5,
            "reviewCount": 120,
        },
        {
            "itemCode": "shop:item002",
            "itemName": "リラックスバスソルト",
            "itemPrice": 1500,
            "genreName": "コスメ",
            "itemUrl": "https://item.rakuten.co.jp/shop/item002/",
            "mediumImageUrls": [],
            "shopName": "コスメショップ",
            "reviewAverage": 3.8,
            "reviewCount": 5,
        },
    ]
}


@pytest.fixture(autouse=True)
def reset_app_id_cache():
    """各テスト前後で AppID キャッシュをリセットする"""
    rs_mod._cached_app_id = None
    yield
    rs_mod._cached_app_id = None


# ─────────────────────────────────────────
# _parse_response テスト
# ─────────────────────────────────────────
class TestParseResponse:
    def test_正常系_2件パース(self):
        products = _parse_response(MOCK_RAKUTEN_RESPONSE)
        assert len(products) == 2

    def test_商品名が100文字にトリムされる(self):
        long_name = "あ" * 150
        data = {"Items": [{"itemCode": "x:001", "itemName": long_name, "itemPrice": 1000, "genreName": "", "itemUrl": "", "mediumImageUrls": [], "shopName": "", "reviewAverage": 0.0, "reviewCount": 0}]}
        products = _parse_response(data)
        assert len(products[0].name) == 100

    def test_画像URLあり(self):
        products = _parse_response(MOCK_RAKUTEN_RESPONSE)
        assert products[0].image_url == "https://thumbnail.image.rakuten.co.jp/item001.jpg"

    def test_画像URLなし(self):
        products = _parse_response(MOCK_RAKUTEN_RESPONSE)
        assert products[1].image_url is None

    def test_priceがDecimal(self):
        products = _parse_response(MOCK_RAKUTEN_RESPONSE)
        assert isinstance(products[0].price, Decimal)
        assert products[0].price == Decimal("980")

    def test_空レスポンス(self):
        products = _parse_response({"Items": []})
        assert products == []

    def test_不正アイテムはスキップ(self):
        data = {"Items": [{"itemPrice": "not_a_number"}]}
        # 例外は発生せず空リストを返す
        products = _parse_response(data)
        assert products == []


# ─────────────────────────────────────────
# search_products テスト
# ─────────────────────────────────────────
class TestSearchProducts:
    @patch("services.rakuten_service.time.sleep", return_value=None)
    @patch("services.rakuten_service.requests.get")
    @patch("services.rakuten_service._get_credentials", return_value=("TEST_APP_ID", "TEST_ACCESS_KEY"))
    def test_正常系_商品リストを返す(self, mock_creds, mock_get, mock_sleep):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_RAKUTEN_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        products = search_products("スイーツ", hits=2)

        assert len(products) == 2
        mock_get.assert_called_once()
        mock_sleep.assert_called_once_with(rs_mod.RATE_LIMIT_SLEEP)

    @patch("services.rakuten_service.time.sleep", return_value=None)
    @patch("services.rakuten_service.requests.get")
    @patch("services.rakuten_service._get_credentials", return_value=("TEST_APP_ID", "TEST_ACCESS_KEY"))
    def test_リトライ3回失敗でRakutenAPIError(self, mock_creds, mock_get, mock_sleep):
        from requests.exceptions import ConnectionError as RequestsConnectionError
        mock_get.side_effect = RequestsConnectionError("接続失敗")

        with pytest.raises(RakutenAPIError) as exc_info:
            search_products("スイーツ")

        assert mock_get.call_count == rs_mod.MAX_RETRIES
        assert "リトライ失敗" in str(exc_info.value)

    @patch("services.rakuten_service.time.sleep", return_value=None)
    @patch("services.rakuten_service.requests.get")
    @patch("services.rakuten_service._get_credentials", return_value=("TEST_APP_ID", "TEST_ACCESS_KEY"))
    def test_1回失敗後2回目成功(self, mock_creds, mock_get, mock_sleep):
        from requests.exceptions import Timeout
        success_response = MagicMock()
        success_response.json.return_value = MOCK_RAKUTEN_RESPONSE
        success_response.raise_for_status.return_value = None

        mock_get.side_effect = [Timeout("タイムアウト"), success_response]

        products = search_products("スイーツ")

        assert len(products) == 2
        assert mock_get.call_count == 2

    @patch("services.rakuten_service.time.sleep", return_value=None)
    @patch("services.rakuten_service.requests.get")
    @patch("services.rakuten_service._get_credentials", return_value=("TEST_APP_ID", "TEST_ACCESS_KEY"))
    def test_価格パラメータが送信される(self, mock_creds, mock_get, mock_sleep):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        search_products("スイーツ", hits=5, min_price=500, max_price=10000)

        call_kwargs = mock_get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        assert params["minPrice"] == 500
        assert params["maxPrice"] == 10000


# ─────────────────────────────────────────
# search_hotels テスト
# ─────────────────────────────────────────
MOCK_HOTEL_RESPONSE = {
    "hotels": [
        {
            "hotelBasicInfo": {
                "hotelNo": 12345,
                "hotelName": "東京ビジネスホテル",
                "hotelMinCharge": 8000,
                "areaName": "東京",
                "hotelInformationUrl": "https://travel.rakuten.co.jp/hotel/12345/",
                "hotelImageUrl": "https://img.travel.rakuten.co.jp/hotel12345.jpg",
                "reviewAverage": 4.2,
                "reviewCount": 58,
            }
        },
        {
            "hotelBasicInfo": {
                "hotelNo": 99999,
                "hotelName": "山之温泉旅館",
                "hotelMinCharge": 15000,
                "areaName": "笥山",
                "hotelInformationUrl": "https://travel.rakuten.co.jp/hotel/99999/",
                "hotelImageUrl": None,
                "reviewAverage": 4.8,
                "reviewCount": 200,
            }
        },
    ]
}

MOCK_HOTEL_RESPONSE_NESTED = {
    "hotels": [
        [
            {
                "hotelBasicInfo": {
                    "hotelNo": 11111,
                    "hotelName": "ネストフォーマットホテル",
                    "hotelMinCharge": 5000,
                    "areaName": "大阪",
                    "hotelInformationUrl": "https://travel.rakuten.co.jp/hotel/11111/",
                    "hotelImageUrl": "https://img.com/11111.jpg",
                    "reviewAverage": 3.5,
                    "reviewCount": 12,
                }
            },
            {"hotelRatingInfo": {}},
        ]
    ]
}


class TestParseHotelResponse:
    def test_formatVersion2あり_フラット(self):
        hotels = _parse_hotel_response(MOCK_HOTEL_RESPONSE)
        assert len(hotels) == 2
        assert hotels[0].hotel_no == "12345"
        assert hotels[0].name == "東京ビジネスホテル"
        assert hotels[0].price == Decimal("8000")
        assert hotels[0].location == "東京"
        assert hotels[0].review_average == 4.2

    def test_ネスト配列形式(self):
        hotels = _parse_hotel_response(MOCK_HOTEL_RESPONSE_NESTED)
        assert len(hotels) == 1
        assert hotels[0].hotel_no == "11111"
        assert hotels[0].name == "ネストフォーマットホテル"

    def test_画像URLなしはデフォルトNone(self):
        hotels = _parse_hotel_response(MOCK_HOTEL_RESPONSE)
        assert hotels[1].image_url is None

    def test_空レスポンス(self):
        assert _parse_hotel_response({}) == []


class TestSearchHotels:
    @patch("services.rakuten_service.time.sleep", return_value=None)
    @patch("services.rakuten_service.requests.get")
    @patch("services.rakuten_service._get_credentials", return_value=("TEST_APP_ID", "TEST_ACCESS_KEY"))
    def test_正常系_ホテルリストを返す(self, mock_creds, mock_get, mock_sleep):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_HOTEL_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        hotels = search_hotels("旅行", hits=3)

        assert len(hotels) == 2
        assert isinstance(hotels[0], RakutenHotel)
        call_params = mock_get.call_args[1].get("params") or mock_get.call_args[0][1]
        assert call_params["keyword"] == "旅行"
        assert call_params["hits"] == 3

    @patch("services.rakuten_service.time.sleep", return_value=None)
    @patch("services.rakuten_service.requests.get")
    @patch("services.rakuten_service._get_credentials", return_value=("TEST_APP_ID", "TEST_ACCESS_KEY"))
    def test_全失敗_RakutenAPIError(self, mock_creds, mock_get, mock_sleep):
        from requests.exceptions import ConnectionError
        mock_get.side_effect = ConnectionError("接続失敗")

        with pytest.raises(RakutenAPIError):
            search_hotels("ホテル")
