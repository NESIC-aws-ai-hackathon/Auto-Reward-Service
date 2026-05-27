"""
pwa_temptation.py のユニットテスト

認証・入力バリデーション・ルーティングのテスト。
DynamoDB / Bedrock への実接続は行わない。
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ─── layer/python のインポート問題を回避 ───
# services/__init__.py が line_service をインポートし、
# そこから linebot → pydantic_core のネイティブモジュールが必要になる。
# conftest.py で sys.path 末尾に追加して system pydantic を使えるようにするが、
# layer/python/services/__init__.py が先に読まれてしまう。
# 回避策: services パッケージを丸ごとモックし、必要な部分だけ復元する。

# temptation_engine の関数モック
_mock_build_lanes = MagicMock(return_value={"session_id": "test", "lanes": []})
_mock_accept_lane = MagicMock(return_value={"accepted": True})
_mock_get_history = MagicMock(return_value={"this_month": {}})
_mock_complete = MagicMock(return_value={"expense_id": "exp1", "budget_remaining": 5000, "message": "ok"})

# DynamoDBService モック
_MockDDB = MagicMock()

# pwa_temptation が from ... import するモジュールをモック注入
_te_mock = MagicMock()
_te_mock.build_lanes = _mock_build_lanes
_te_mock.accept_lane = _mock_accept_lane
_te_mock.get_temptation_history = _mock_get_history
_te_mock.complete_temptation = _mock_complete

_ddb_mock = MagicMock()
_ddb_mock.DynamoDBService = _MockDDB

_logger_mock = MagicMock()
_logger_mock.get_logger = MagicMock(return_value=MagicMock())

# sys.modules にモックを仕込んでインポートチェーンを断ち切る
_location_mock = MagicMock()
_location_mock.geocode_text = MagicMock(return_value={"lat": 35.0, "lng": 139.0})

sys.modules["services"] = MagicMock()
sys.modules["services.temptation_engine"] = _te_mock
sys.modules["services.dynamodb_service"] = _ddb_mock
sys.modules["services.location_service"] = _location_mock
sys.modules["utils"] = MagicMock()
sys.modules["utils.logger"] = _logger_mock

import handlers.pwa_temptation as _mod

# インポート後にfrom ... importで取得した関数を上書き
_mod.build_lanes = _mock_build_lanes
_mod.accept_lane = _mock_accept_lane
_mod.get_temptation_history = _mock_get_history
_mod.complete_temptation = _mock_complete
_mod.DynamoDBService = _MockDDB

handler = _mod.handler
_authenticate = _mod._authenticate
_parse_body = _mod._parse_body


class TestAuthenticate:
    """LINE access_token 認証のテスト"""

    def test_no_auth_header(self):
        event = {"headers": {}}
        assert _authenticate(event) is None

    def test_invalid_bearer(self):
        event = {"headers": {"authorization": "Basic abc"}}
        assert _authenticate(event) is None

    def test_empty_token(self):
        event = {"headers": {"authorization": "Bearer "}}
        assert _authenticate(event) is None

    @patch.dict(os.environ, {"LIFF_CHANNEL_ID": "test_channel"})
    def test_valid_token(self):
        """JWT形式のLIFF ID Tokenからsub(user_id)を取得できること"""
        import base64 as b64
        import time as t
        header = b64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).rstrip(b"=").decode()
        payload = b64.urlsafe_b64encode(json.dumps({
            "sub": "U123",
            "aud": "test_channel",
            "exp": int(t.time()) + 3600,
        }).encode()).rstrip(b"=").decode()
        token = f"{header}.{payload}.fake_signature"

        event = {"headers": {"authorization": f"Bearer {token}"}}
        assert _authenticate(event) == "U123"


class TestParseBody:
    """リクエストボディパースのテスト"""

    def test_empty_body(self):
        assert _parse_body({"body": ""}) == {}

    def test_valid_json(self):
        body = json.dumps({"lat": 35.68, "lng": 139.76})
        assert _parse_body({"body": body}) == {"lat": 35.68, "lng": 139.76}

    def test_invalid_json(self):
        assert _parse_body({"body": "not json"}) == {}


class TestHandler:
    """handler のルーティングテスト"""

    @patch("handlers.pwa_temptation._authenticate", return_value=None)
    def test_unauthorized(self, _):
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "rawPath": "/api/temptation/start",
            "headers": {},
        }
        result = handler(event, None)
        assert result["statusCode"] == 401

    @patch("handlers.pwa_temptation._authenticate", return_value="U123")
    def test_not_found(self, _):
        event = {
            "requestContext": {"http": {"method": "GET"}},
            "rawPath": "/api/unknown",
            "headers": {},
        }
        result = handler(event, None)
        assert result["statusCode"] == 404

    @patch("handlers.pwa_temptation._authenticate", return_value="U123")
    def test_start_missing_lat_lng(self, _):
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "rawPath": "/api/temptation/start",
            "headers": {},
            "body": json.dumps({"message": "疲れた"}),
        }
        result = handler(event, None)
        assert result["statusCode"] == 400

    @patch("handlers.pwa_temptation._authenticate", return_value="U123")
    def test_complete_missing_fields(self, _):
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "rawPath": "/api/temptation/complete",
            "headers": {},
            "body": json.dumps({"session_id": "abc"}),
        }
        result = handler(event, None)
        assert result["statusCode"] == 400

    @patch("handlers.pwa_temptation._authenticate", return_value="U123")
    def test_complete_invalid_amount(self, _):
        event = {
            "requestContext": {"http": {"method": "POST"}},
            "rawPath": "/api/temptation/complete",
            "headers": {},
            "body": json.dumps({
                "session_id": "abc", "lane_id": "lane1",
                "amount": -100, "item_name": "test",
            }),
        }
        result = handler(event, None)
        assert result["statusCode"] == 400

    def test_options_cors(self):
        event = {
            "requestContext": {"http": {"method": "OPTIONS"}},
            "rawPath": "/api/temptation/start",
            "headers": {},
        }
        result = handler(event, None)
        assert result["statusCode"] == 204
        assert "Access-Control-Allow-Origin" in result["headers"]
