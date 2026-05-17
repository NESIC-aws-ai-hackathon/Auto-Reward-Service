"""
liff_api.py のユニットテスト（Unit 7）

テスト方針:
- 認証: ID Token のデコード・検証
- ルーティング: 各エンドポイントが正しくディスパッチされる
- レスポンス: CORS ヘッダー・JSON 構造
- 設定更新: バリデーション（tone, budget, carryover_rate 等）
- エラーハンドリング: 401, 400, 404, 500
"""
from __future__ import annotations

import base64
import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from handlers.liff_api import (
    _decimal_default,
    _extract_user_id,
    _make_response,
    handler,
)


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────

def _make_jwt(payload: dict) -> str:
    """テスト用 JWT を生成する（署名なし）"""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fake_signature").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


def _valid_token(user_id: str = "U123456") -> str:
    return _make_jwt({
        "sub": user_id,
        "aud": "1234567890",
        "exp": int(time.time()) + 3600,
    })


def _make_event(path: str, method: str = "GET", token: str = None, body: dict = None, query: dict = None) -> dict:
    """API Gateway HttpApi v2 イベントを構築する"""
    event = {
        "rawPath": path,
        "requestContext": {"http": {"method": method}},
        "headers": {},
        "queryStringParameters": query or {},
    }
    if token:
        event["headers"]["authorization"] = f"Bearer {token}"
    if body:
        event["body"] = json.dumps(body)
    return event


# ─────────────────────────────────────────
# _extract_user_id テスト
# ─────────────────────────────────────────

class TestExtractUserId:

    def test_有効なトークン_ユーザーID抽出(self):
        event = {"headers": {"authorization": f"Bearer {_valid_token('U999')}"}}
        assert _extract_user_id(event) == "U999"

    def test_トークンなし_Noneを返す(self):
        event = {"headers": {}}
        assert _extract_user_id(event) is None

    def test_空トークン_Noneを返す(self):
        event = {"headers": {"authorization": "Bearer "}}
        assert _extract_user_id(event) is None

    def test_無効なJWT_Noneを返す(self):
        event = {"headers": {"authorization": "Bearer invalid.token"}}
        assert _extract_user_id(event) is None

    def test_aud不一致_Noneを返す(self):
        token = _make_jwt({"sub": "U123", "aud": "wrong_channel", "exp": int(time.time()) + 3600})
        event = {"headers": {"authorization": f"Bearer {token}"}}
        assert _extract_user_id(event) is None

    def test_期限切れ_Noneを返す(self):
        token = _make_jwt({"sub": "U123", "aud": "1234567890", "exp": int(time.time()) - 100})
        event = {"headers": {"authorization": f"Bearer {token}"}}
        assert _extract_user_id(event) is None

    def test_headersなし_Noneを返す(self):
        event = {}
        assert _extract_user_id(event) is None


# ─────────────────────────────────────────
# _make_response テスト
# ─────────────────────────────────────────

class TestMakeResponse:

    def test_CORSヘッダー付き(self):
        resp = _make_response(200, {"ok": True})
        assert resp["statusCode"] == 200
        assert resp["headers"]["Access-Control-Allow-Origin"] == "https://liff.line.me"
        assert "Authorization" in resp["headers"]["Access-Control-Allow-Headers"]

    def test_Decimalシリアライズ(self):
        resp = _make_response(200, {"price": Decimal("1980")})
        body = json.loads(resp["body"])
        assert body["price"] == 1980


# ─────────────────────────────────────────
# _decimal_default テスト
# ─────────────────────────────────────────

class TestDecimalDefault:

    def test_整数Decimal_intに変換(self):
        assert _decimal_default(Decimal("100")) == 100

    def test_小数Decimal_floatに変換(self):
        assert _decimal_default(Decimal("3.14")) == 3.14

    def test_非Decimal_TypeErrorを送出(self):
        with pytest.raises(TypeError):
            _decimal_default(set())


# ─────────────────────────────────────────
# handler ルーティングテスト
# ─────────────────────────────────────────

class TestHandlerRouting:

    @patch("handlers.liff_api._get_ddb")
    def test_認証なし_401(self, mock_ddb):
        event = _make_event("/api/dashboard")
        resp = handler(event, None)
        assert resp["statusCode"] == 401

    @patch("handlers.liff_api._get_ddb")
    def test_未知ルート_404(self, mock_ddb):
        event = _make_event("/api/unknown", token=_valid_token())
        mock_ddb.return_value = MagicMock()
        resp = handler(event, None)
        assert resp["statusCode"] == 404

    @patch("handlers.liff_api._get_ddb")
    def test_OPTIONS_200(self, mock_ddb):
        event = _make_event("/api/dashboard", method="OPTIONS")
        resp = handler(event, None)
        assert resp["statusCode"] == 200

    @patch("handlers.liff_api._serve_liff_html")
    def test_LIFF_HTML配信(self, mock_serve):
        mock_serve.return_value = {"statusCode": 200, "body": "<html></html>"}
        event = _make_event("/liff")
        resp = handler(event, None)
        assert resp["statusCode"] == 200


# ─────────────────────────────────────────
# GET /api/dashboard テスト
# ─────────────────────────────────────────

class TestDashboard:

    @patch("handlers.liff_api._get_ddb")
    def test_正常系_ダッシュボード返却(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb
        ddb.get_item.side_effect = [
            # PROFILE#
            {"nickname": "テスト", "tone": "friendly"},
            # MONTHLY_SUMMARY#
            {"total_budget": 24000, "total_amount": Decimal("8000"), "carryover_amount": 4000, "expense_count": 5},
        ]
        ddb.query_by_pk.return_value = [
            {"item_name": "入浴剤", "price": Decimal("1980"), "proposed_at": "2026-05-16T10:00:00", "outcome": "bought"},
        ]

        event = _make_event("/api/dashboard", token=_valid_token())
        resp = handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["nickname"] == "テスト"
        assert body["monthly_summary"]["total_budget"] == 24000
        assert body["monthly_summary"]["remaining"] == 16000
        assert len(body["recent_suggestions"]) == 1

    @patch("handlers.liff_api._get_ddb")
    def test_サマリーなし_0を返す(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb
        ddb.get_item.side_effect = [
            {"tone": "friendly"},  # PROFILE#
            None,                   # MONTHLY_SUMMARY# なし
        ]
        ddb.query_by_pk.return_value = []

        event = _make_event("/api/dashboard", token=_valid_token())
        resp = handler(event, None)
        body = json.loads(resp["body"])
        assert body["monthly_summary"]["total_budget"] == 0
        assert body["monthly_summary"]["remaining"] == 0


# ─────────────────────────────────────────
# GET /api/expenses テスト
# ─────────────────────────────────────────

class TestExpenses:

    @patch("handlers.liff_api._get_ddb")
    def test_正常系_支出リスト返却(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb
        ddb.query_by_pk.return_value = [
            {"item_name": "プリン", "amount": Decimal("320"), "ars_category": "情緒安定費", "created_at": "2026-05-16T12:00:00"},
        ]

        event = _make_event("/api/expenses", token=_valid_token(), query={"month": "2026-05"})
        resp = handler(event, None)
        body = json.loads(resp["body"])
        assert body["month"] == "2026-05"
        assert len(body["expenses"]) == 1
        assert body["expenses"][0]["amount"] == 320


# ─────────────────────────────────────────
# GET /api/pool テスト
# ─────────────────────────────────────────

class TestPool:

    @patch("handlers.liff_api._get_ddb")
    def test_正常系_スコア降順(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb
        ddb.get_item.return_value = {
            "items": [
                {"name": "A", "price": Decimal("100"), "category": "x", "score": 0.3, "type": "product"},
                {"name": "B", "price": Decimal("200"), "category": "y", "score": 0.9, "type": "travel"},
            ]
        }

        event = _make_event("/api/pool", token=_valid_token())
        resp = handler(event, None)
        body = json.loads(resp["body"])
        assert body["items"][0]["name"] == "B"  # スコア高い方が先
        assert body["items"][0]["score"] == 0.9

    @patch("handlers.liff_api._get_ddb")
    def test_プールなし_空リスト(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb
        ddb.get_item.return_value = None

        event = _make_event("/api/pool", token=_valid_token())
        resp = handler(event, None)
        body = json.loads(resp["body"])
        assert body["items"] == []


# ─────────────────────────────────────────
# PUT /api/settings テスト
# ─────────────────────────────────────────

class TestUpdateSettings:

    @patch("handlers.liff_api._get_ddb")
    def test_正常系_tone更新(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb

        event = _make_event("/api/settings", method="PUT", token=_valid_token(), body={"tone": "devilish"})
        resp = handler(event, None)
        body = json.loads(resp["body"])
        assert body["updated"] is True
        ddb.update_item.assert_called_once()

    @patch("handlers.liff_api._get_ddb")
    def test_無効tone_400(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb

        event = _make_event("/api/settings", method="PUT", token=_valid_token(), body={"tone": "invalid"})
        resp = handler(event, None)
        assert resp["statusCode"] == 400

    @patch("handlers.liff_api._get_ddb")
    def test_reward_budget_0以下_400(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb

        event = _make_event("/api/settings", method="PUT", token=_valid_token(), body={"reward_budget_monthly": 0})
        resp = handler(event, None)
        assert resp["statusCode"] == 400

    @patch("handlers.liff_api._get_ddb")
    def test_carryover_rate_範囲外_400(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb

        event = _make_event("/api/settings", method="PUT", token=_valid_token(), body={"carryover_rate": 1.5})
        resp = handler(event, None)
        assert resp["statusCode"] == 400

    @patch("handlers.liff_api._get_ddb")
    def test_nickname_21文字_400(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb

        event = _make_event("/api/settings", method="PUT", token=_valid_token(), body={"nickname": "あ" * 21})
        resp = handler(event, None)
        assert resp["statusCode"] == 400

    @patch("handlers.liff_api._get_ddb")
    def test_空ボディ_400(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb

        event = _make_event("/api/settings", method="PUT", token=_valid_token(), body={})
        resp = handler(event, None)
        assert resp["statusCode"] == 400

    @patch("handlers.liff_api._get_ddb")
    def test_無効JSON_400(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb

        event = _make_event("/api/settings", method="PUT", token=_valid_token())
        event["body"] = "not json {"
        resp = handler(event, None)
        assert resp["statusCode"] == 400


# ─────────────────────────────────────────
# GET /api/calendar/status テスト
# ─────────────────────────────────────────

class TestCalendarStatus:

    @patch("handlers.liff_api._get_ddb")
    def test_連携済み(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb
        ddb.get_item.return_value = {"connected_at": "2026-05-10T09:00:00"}

        event = _make_event("/api/calendar/status", token=_valid_token())
        resp = handler(event, None)
        body = json.loads(resp["body"])
        assert body["connected"] is True

    @patch("handlers.liff_api._get_ddb")
    def test_未連携(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb
        ddb.get_item.return_value = None

        event = _make_event("/api/calendar/status", token=_valid_token())
        resp = handler(event, None)
        body = json.loads(resp["body"])
        assert body["connected"] is False


# ─────────────────────────────────────────
# POST /api/calendar/disconnect テスト
# ─────────────────────────────────────────

class TestCalendarDisconnect:

    @patch("handlers.liff_api._get_ddb")
    def test_正常系_連携解除(self, mock_get_ddb):
        ddb = MagicMock()
        mock_get_ddb.return_value = ddb

        event = _make_event("/api/calendar/disconnect", method="POST", token=_valid_token())
        resp = handler(event, None)
        body = json.loads(resp["body"])
        assert body["disconnected"] is True
        ddb.delete_item.assert_called_once()
