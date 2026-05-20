"""
temptation_engine ユニットテスト
"""
import pytest
from unittest.mock import MagicMock, patch, call
from decimal import Decimal


def _mock_ddb():
    ddb = MagicMock()
    ddb.get_item.return_value = {}
    ddb.query_by_pk.return_value = []
    return ddb


class TestEnrichWithHotpepper:
    """_enrich_with_hotpepper のテスト"""

    def test_キーワードなしのレーンはスキップ(self):
        from services.temptation_engine import _enrich_with_hotpepper
        places = [{"name": "セブンイレブン", "distance_m": 100}]
        result = _enrich_with_hotpepper(places, 35.0, 139.0, "CONVENIENCE_RECOVERY")
        assert result == places  # 変更なし

    @patch("services.temptation_engine.logger")
    def test_HotPepper例外時は元データを返す(self, mock_logger):
        from services.temptation_engine import _enrich_with_hotpepper
        with patch("services.hotpepper_service.search_nearby_restaurants", side_effect=Exception("API error")):
            places = [{"name": "スタバ", "distance_m": 200}]
            result = _enrich_with_hotpepper(places, 35.0, 139.0, "CAFE_REBOOT")
        assert result == places

    @patch("services.hotpepper_service._get_api_key", return_value="test")
    @patch("services.hotpepper_service._call_with_retry")
    def test_名前一致でURLが付与される(self, mock_call, mock_key):
        from services.temptation_engine import _enrich_with_hotpepper
        mock_call.return_value = {
            "results": {"shop": [{
                "id": "S001",
                "name": "スタバ",
                "budget": {"average": "500円"},
                "genre": {"name": "カフェ"},
                "urls": {"pc": "https://tabelog.com/starbucks"},
                "photo": {"pc": {"m": "https://img.com/starbucks.jpg"}},
                "station_name": "渋谷",
            }]}
        }
        places = [{"name": "スタバ", "distance_m": 200, "category": "cafe", "lat": 35.0, "lng": 139.0, "address": ""}]
        result = _enrich_with_hotpepper(places, 35.0, 139.0, "CAFE_REBOOT")
        assert result[0]["shop_url"] == "https://tabelog.com/starbucks"
        assert result[0]["genre"] == "カフェ"

    @patch("services.hotpepper_service._get_api_key", return_value="test")
    @patch("services.hotpepper_service._call_with_retry")
    def test_部分一致でマッチする(self, mock_call, mock_key):
        from services.temptation_engine import _enrich_with_hotpepper
        mock_call.return_value = {
            "results": {"shop": [{
                "id": "S001",
                "name": "タリーズコーヒー 渋谷店",
                "budget": {"average": "600円"},
                "genre": {"name": "カフェ"},
                "urls": {"pc": "https://example.com/tullys"},
                "photo": {"pc": {"m": ""}},
                "station_name": "渋谷",
            }]}
        }
        places = [{"name": "タリーズコーヒー", "distance_m": 300, "category": "cafe", "lat": 35.0, "lng": 139.0, "address": ""}]
        result = _enrich_with_hotpepper(places, 35.0, 139.0, "CAFE_REBOOT")
        assert result[0].get("shop_url") == "https://example.com/tullys"

    @patch("services.hotpepper_service._get_api_key", return_value="test")
    @patch("services.hotpepper_service._call_with_retry")
    def test_HotPepper結果が追加される(self, mock_call, mock_key):
        from services.temptation_engine import _enrich_with_hotpepper
        mock_call.return_value = {
            "results": {"shop": [
                {"id": "S001", "name": "一蘭 渋谷店", "budget": {"average": "900円"},
                 "genre": {"name": "ラーメン"}, "urls": {"pc": "https://example.com/ichiran"},
                 "photo": {"pc": {"m": ""}}, "station_name": "渋谷"},
                {"id": "S002", "name": "松屋 渋谷店", "budget": {"average": "500円"},
                 "genre": {"name": "定食"}, "urls": {"pc": "https://example.com/matsuya"},
                 "photo": {"pc": {"m": ""}}, "station_name": "渋谷"},
            ]}
        }
        # Overpass では別の店が見つかった場合 → HP の店も追加される
        places = [{"name": "丸亀製麺", "distance_m": 400, "category": "restaurant", "lat": 35.0, "lng": 139.0, "address": ""}]
        result = _enrich_with_hotpepper(places, 35.0, 139.0, "SELF_COOKING_ESCAPE")
        # 元の1件 + HP の2件 = 3件
        assert len(result) == 3
        names = [r["name"] for r in result]
        assert "一蘭 渋谷店" in names
        assert "松屋 渋谷店" in names


class TestAcceptLane:
    """accept_lane のテスト"""

    @patch("services.temptation_engine._push_lane_detail")
    def test_正常系_PushされてDDB更新(self, mock_push):
        from services.temptation_engine import accept_lane
        ddb = _mock_ddb()
        ddb.get_item.return_value = {
            "lanes": [
                {"lane_id": "lane_cafe_reboot_abc", "title": "カフェ再起動レーン ☕",
                 "places": [{"name": "スタバ", "distance_m": 200, "shop_url": "https://hp.example.com"}]},
            ]
        }

        result = accept_lane("U123", "sess1", "lane_cafe_reboot_abc", ddb)

        assert result["accepted"] is True
        ddb.update_item.assert_called_once()
        mock_push.assert_called_once_with("U123", ddb.get_item.return_value["lanes"][0])

    @patch("services.temptation_engine._push_lane_detail", side_effect=Exception("LINE error"))
    def test_Push失敗でもacceptは成功(self, mock_push):
        from services.temptation_engine import accept_lane
        ddb = _mock_ddb()
        ddb.get_item.return_value = {
            "lanes": [{"lane_id": "lane_x", "title": "テスト", "places": []}]
        }

        result = accept_lane("U123", "sess1", "lane_x", ddb)
        assert result["accepted"] is True

    def test_レーン不一致_Pushはスキップ(self):
        from services.temptation_engine import accept_lane
        ddb = _mock_ddb()
        ddb.get_item.return_value = {"lanes": [{"lane_id": "lane_other"}]}

        with patch("services.temptation_engine._push_lane_detail") as mock_push:
            result = accept_lane("U123", "sess1", "lane_nonexistent", ddb)
            mock_push.assert_not_called()
        assert result["accepted"] is True


class TestPushLaneDetail:
    """_push_lane_detail のテスト"""

    @patch("services.line_service.LineService")
    def test_スポット情報がPushされる(self, MockLS):
        from services.temptation_engine import _push_lane_detail
        mock_svc = MagicMock()
        MockLS.return_value = mock_svc

        lane = {
            "title": "カフェ再起動レーン ☕",
            "places": [
                {"name": "スタバ", "distance_m": 240, "genre": "カフェ", "budget_text": "¥500",
                 "shop_url": "https://hp.example.com", "category": "cafe"},
            ],
        }
        _push_lane_detail("U123", lane)

        mock_svc.push_message.assert_called_once()
        msg = mock_svc.push_message.call_args[0][1][0]
        assert "スタバ" in msg["text"]
        assert "https://hp.example.com" in msg["text"]
        assert "支出を教えてね" in msg["text"]

    @patch("services.line_service.LineService")
    def test_URL無しでも送信される(self, MockLS):
        from services.temptation_engine import _push_lane_detail
        mock_svc = MagicMock()
        MockLS.return_value = mock_svc

        lane = {
            "title": "コンビニ回復レーン 🏪",
            "places": [
                {"name": "ローソン", "distance_m": 80, "category": "convenience"},
            ],
        }
        _push_lane_detail("U123", lane)
        mock_svc.push_message.assert_called_once()
        msg = mock_svc.push_message.call_args[0][1][0]
        assert "ローソン" in msg["text"]

    @patch("services.line_service.LineService")
    def test_places空ならPushしない(self, MockLS):
        from services.temptation_engine import _push_lane_detail
        mock_svc = MagicMock()
        MockLS.return_value = mock_svc

        _push_lane_detail("U123", {"title": "テスト", "places": []})
        mock_svc.push_message.assert_not_called()


class TestSearchNearbyRestaurants:
    """hotpepper_service.search_nearby_restaurants のテスト"""

    @patch("services.hotpepper_service._get_api_key", return_value="test")
    @patch("services.hotpepper_service._call_with_retry")
    def test_位置情報パラメータが正しく渡される(self, mock_call, mock_key):
        from services.hotpepper_service import search_nearby_restaurants
        mock_call.return_value = {"results": {"shop": []}}

        search_nearby_restaurants(35.681, 139.767, keyword="カフェ", range_code=3, count=5)

        params = mock_call.call_args[0][1]
        assert params["lat"] == 35.681
        assert params["lng"] == 139.767
        assert params["keyword"] == "カフェ"
        assert params["range"] == 3
        assert params["order"] == 4

    @patch("services.hotpepper_service._get_api_key", return_value="test")
    @patch("services.hotpepper_service._call_with_retry")
    def test_キーワードなしでも検索可能(self, mock_call, mock_key):
        from services.hotpepper_service import search_nearby_restaurants
        mock_call.return_value = {"results": {"shop": []}}

        search_nearby_restaurants(35.0, 139.0)

        params = mock_call.call_args[0][1]
        assert "keyword" not in params
