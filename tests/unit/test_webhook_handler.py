"""webhook_handler.py のユニットテスト"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest

import webhook_handler
from webhook_handler import ERROR_REPLY, UNSUPPORTED_REPLIES, handler
from utils.exceptions import LineServiceError


# ─────────────────────────────────────────
# テストヘルパー
# ─────────────────────────────────────────

def _make_apigw_event(
    body: str,
    signature: str = "",
    base64_encoded: bool = False,
) -> dict:
    """API Gateway HTTP API v2 プロキシイベントを生成するヘルパー"""
    encoded_body = (
        base64.b64encode(body.encode("utf-8")).decode("utf-8")
        if base64_encoded
        else body
    )
    return {
        "headers": {
            "x-line-signature": signature,
            "content-type": "application/json",
        },
        "body": encoded_body,
        "isBase64Encoded": base64_encoded,
        "requestContext": {},
    }


def _make_line_text_event(
    user_id: str = "U123456789abcdef",
    reply_token: str = "reply_token_abc",
    text: str = "こんにちは",
) -> dict:
    """LINE テキストメッセージイベントを生成するヘルパー"""
    return {
        "type": "message",
        "replyToken": reply_token,
        "source": {"type": "user", "userId": user_id},
        "message": {"type": "text", "id": "msg001", "text": text},
        "timestamp": 1716000000000,
    }


def _make_line_image_event(
    user_id: str = "U123456789abcdef",
    reply_token: str = "reply_token_img",
    msg_id: str = "img001",
) -> dict:
    """LINE 画像メッセージイベントを生成するヘルパー"""
    return {
        "type": "message",
        "replyToken": reply_token,
        "source": {"type": "user", "userId": user_id},
        "message": {"type": "image", "id": msg_id},
        "timestamp": 1716000000000,
    }


def _make_line_sticker_event(
    user_id: str = "U123456789abcdef",
    reply_token: str = "reply_token_stk",
) -> dict:
    """LINE スタンプメッセージイベントを生成するヘルパー"""
    return {
        "type": "message",
        "replyToken": reply_token,
        "source": {"type": "user", "userId": user_id},
        "message": {"type": "sticker", "id": "stk001", "packageId": "1", "stickerId": "1"},
        "timestamp": 1716000000000,
    }


# ─────────────────────────────────────────
# フィクスチャ
# ─────────────────────────────────────────

@pytest.fixture
def mock_line_svc():
    """くれおくれおく get_line_service を mock LineService に差し替えるフィクスチャ"""
    mock_svc = MagicMock()
    mock_svc.verify_signature.return_value = True
    with patch("webhook_handler.get_line_service", return_value=mock_svc):
        yield mock_svc


@pytest.fixture
def mock_ddb():
    """
    DynamoDB モックフィクスチャ
    - PROFILE# は既存ユーザーを想定し ACTIVE プロフィールを返す（初回フォールバックをスキップ）
    - その他の get_item は None を返す（オンボーディングなし / デイリーカウント 0）
    - put_item / update_item / increment_atomic_counter は無応答
    """
    mock = MagicMock()
    mock.get_item.side_effect = lambda pk=None, sk=None: (
        {"entityType": "PROFILE", "status": "ACTIVE", "tone": "friendly"}
        if sk == "PROFILE#" else None
    )
    mock.put_item.return_value = None
    mock.update_item.return_value = None
    mock.increment_atomic_counter.return_value = 1
    with patch("webhook_handler._get_ddb", return_value=mock):
        yield mock


# ─────────────────────────────────────────
# TestWarmup
# ─────────────────────────────────────────

class TestWarmup:
    def test_warmup_returns_200(self):
        """ウォームアップイベントは即 200 を返す"""
        result = handler({"source": "warmup"}, None)
        assert result["statusCode"] == 200

    def test_warmup_body_is_warm(self):
        """ウォームアップレスポンスのボディ確認"""
        result = handler({"source": "warmup"}, None)
        assert result["body"] == "warm"

    def test_warmup_does_not_initialize_line_service(self):
        """ウォームアップ時は LineService を一切呼び出さない"""
        with patch("webhook_handler.get_line_service") as mock_get:
            handler({"source": "warmup"}, None)
        mock_get.assert_not_called()


# ─────────────────────────────────────────
# TestSignatureVerification
# ─────────────────────────────────────────

class TestSignatureVerification:
    def test_missing_signature_header_returns_403(self):
        """署名ヘッダーなしは 403"""
        event = {
            "headers": {},
            "body": '{"events":[]}',
            "isBase64Encoded": False,
        }
        with patch("webhook_handler.get_line_service") as mock_get:
            result = handler(event, None)
        assert result["statusCode"] == 403
        mock_get.assert_not_called()

    def test_invalid_signature_returns_403(self, mock_line_svc):
        """無効な署名は 403"""
        mock_line_svc.verify_signature.return_value = False
        event = _make_apigw_event('{"events":[]}', "invalid_sig==")
        result = handler(event, None)
        assert result["statusCode"] == 403

    def test_valid_signature_returns_200(self, mock_line_svc):
        """有効な署名は 200"""
        body = '{"events":[]}'
        event = _make_apigw_event(body, "valid_sig")
        result = handler(event, None)
        assert result["statusCode"] == 200

    def test_signature_passed_to_verify(self, mock_line_svc):
        """body と signature が verify_signature に正しく渡される"""
        body = '{"events":[]}'
        event = _make_apigw_event(body, "my_sig")
        handler(event, None)
        mock_line_svc.verify_signature.assert_called_once_with(body, "my_sig")


# ─────────────────────────────────────────
# TestBase64Body
# ─────────────────────────────────────────

class TestBase64Body:
    def test_base64_body_is_decoded_before_verify(self, mock_line_svc):
        """isBase64Encoded=True の場合、デコード済みの body で verify_signature を呼ぶ"""
        body = '{"events":[]}'
        event = _make_apigw_event(body, "sig", base64_encoded=True)
        handler(event, None)
        # デコード済みの文字列が verify_signature に渡ること
        mock_line_svc.verify_signature.assert_called_once_with(body, "sig")


# ─────────────────────────────────────────
# TestTextMessage
# ─────────────────────────────────────────

class TestTextMessage:
    def test_text_message_echo_reply(self, mock_line_svc, mock_ddb):
        """テキストメッセージ: キャラクター応答を Reply する"""
        line_event = _make_line_text_event(text="テスト送信")
        body = json.dumps({"events": [line_event]})
        event = _make_apigw_event(body, "sig")

        with patch("webhook_handler.classify_intent", return_value={"intent": "CHAT", "confidence": 0.8}), \
             patch("webhook_handler.generate_reply", return_value="やあ！どうぞ～"), \
             patch("webhook_handler._save_chat_log"), \
             patch("webhook_handler._update_daily_count"), \
             patch("webhook_handler._detect_preferences"):
            result = handler(event, None)

        assert result["statusCode"] == 200
        mock_line_svc.reply_message.assert_called_once()
        reply_text = mock_line_svc.reply_message.call_args[0][1][0]["text"]
        assert reply_text == "やあ！どうぞ～"

    def test_text_message_empty_text_echo(self, mock_line_svc, mock_ddb):
        """空テキストも処理できる"""
        line_event = _make_line_text_event(text="")
        body = json.dumps({"events": [line_event]})
        event = _make_apigw_event(body, "sig")

        with patch("webhook_handler.classify_intent", return_value={"intent": "CHAT", "confidence": 0.5}), \
             patch("webhook_handler.generate_reply", return_value="ん？"), \
             patch("webhook_handler._save_chat_log"), \
             patch("webhook_handler._update_daily_count"), \
             patch("webhook_handler._detect_preferences"):
            result = handler(event, None)

        assert result["statusCode"] == 200
        mock_line_svc.reply_message.assert_called_once()


# ─────────────────────────────────────────
# TestImageMessage
# ─────────────────────────────────────────

class TestImageMessage:
    def test_image_message_calls_receipt_analyzer(self, mock_line_svc, mock_ddb):
        """画像メッセージ: receipt_analyzer に委譲して返信する (Unit 3)"""
        line_event = _make_line_image_event()
        body = json.dumps({"events": [line_event]})
        event = _make_apigw_event(body, "sig")

        mock_line_svc.get_message_content.return_value = b"\xff\xd8\xff"

        with patch("handlers.receipt_analyzer.analyze", return_value=("レシート読んだよ📄", [])):
            result = handler(event, None)

        assert result["statusCode"] == 200
        mock_line_svc.reply_message.assert_called_once()
        reply_text = mock_line_svc.reply_message.call_args[0][1][0]["text"]
        assert reply_text == "レシート読んだよ📄"


# ─────────────────────────────────────────
# TestUnsupportedMessage
# ─────────────────────────────────────────

class TestUnsupportedMessage:
    def test_sticker_returns_unsupported_reply(self, mock_line_svc, mock_ddb):
        """スタンプ: UNSUPPORTED_REPLIES のいずれかを Reply する"""
        line_event = _make_line_sticker_event()
        body = json.dumps({"events": [line_event]})
        event = _make_apigw_event(body, "sig")

        result = handler(event, None)

        assert result["statusCode"] == 200
        mock_line_svc.reply_message.assert_called_once()
        reply_text = mock_line_svc.reply_message.call_args[0][1][0]["text"]
        assert reply_text in UNSUPPORTED_REPLIES

    def test_unsupported_reply_has_randomness(self, mock_line_svc, mock_ddb):
        """UNSUPPORTED_REPLIES から複数種が選ばれることを確認（50 回試行）"""
        results: set[str] = set()
        for _ in range(50):
            line_event = _make_line_sticker_event()
            body = json.dumps({"events": [line_event]})
            event = _make_apigw_event(body, "sig")
            handler(event, None)
            reply_text = mock_line_svc.reply_message.call_args[0][1][0]["text"]
            results.add(reply_text)
            mock_line_svc.reset_mock()
        assert len(results) > 1


# ─────────────────────────────────────────
# TestNonMessageEvents
# ─────────────────────────────────────────

class TestNonMessageEvents:
    def test_follow_event_starts_onboarding(self, mock_line_svc, mock_ddb):
        """follow イベント: オンボーディングを開始しウェルカム Reply を送る"""
        line_event = {
            "type": "follow",
            "replyToken": "reply_token_follow",
            "source": {"type": "user", "userId": "U123456789abcdef"},
            "timestamp": 1716000000000,
        }
        body = json.dumps({"events": [line_event]})
        event = _make_apigw_event(body, "sig")

        with patch("webhook_handler.handle_onboarding", return_value="はじめまして！"):
            result = handler(event, None)

        assert result["statusCode"] == 200
        mock_line_svc.reply_message.assert_called_once()
        reply_text = mock_line_svc.reply_message.call_args[0][1][0]["text"]
        assert "はじめまして" in reply_text

    def test_empty_events_returns_200(self, mock_line_svc):
        """events が空の場合でも 200 を返す"""
        body = json.dumps({"events": []})
        event = _make_apigw_event(body, "sig")
        result = handler(event, None)
        assert result["statusCode"] == 200


# ─────────────────────────────────────────
# TestErrorHandling
# ─────────────────────────────────────────

class TestErrorHandling:
    def test_reply_error_triggers_fallback_reply(self, mock_line_svc, mock_ddb):
        """reply_message 失敗時: ERROR_REPLY でフォールバック Reply"""
        mock_line_svc.reply_message.side_effect = [
            LineServiceError("エコー Reply 失敗"),  # 1 回目: 通常 Reply 失敗
            None,  # 2 回目: フォールバック Reply 成功
        ]
        line_event = _make_line_text_event(text="テスト")
        body = json.dumps({"events": [line_event]})
        event = _make_apigw_event(body, "sig")

        with patch("webhook_handler.classify_intent", return_value={"intent": "CHAT", "confidence": 0.5}), \
             patch("webhook_handler.generate_reply", return_value="やあ"):
            result = handler(event, None)

        assert result["statusCode"] == 200
        assert mock_line_svc.reply_message.call_count == 2
        fallback_text = mock_line_svc.reply_message.call_args_list[1][0][1][0]["text"]
        assert fallback_text == ERROR_REPLY

    def test_fallback_reply_failure_is_swallowed(self, mock_line_svc):
        """フォールバック Reply も失敗した場合: 200 を返す（二重障害防止）"""
        mock_line_svc.reply_message.side_effect = LineServiceError("全て失敗")

        line_event = _make_line_text_event(text="テスト")
        body = json.dumps({"events": [line_event]})
        event = _make_apigw_event(body, "sig")

        result = handler(event, None)
        assert result["statusCode"] == 200

    def test_invalid_json_body_returns_200(self, mock_line_svc):
        """不正 JSON ボディ: 200 を返す（LINE Platform へは常に 200）"""
        event = {
            "headers": {"x-line-signature": "sig"},
            "body": "not-valid-json{{",
            "isBase64Encoded": False,
        }
        result = handler(event, None)
        assert result["statusCode"] == 200

    def test_event_without_reply_token_skips_fallback(self, mock_line_svc):
        """replyToken なしのイベントでエラー発生: Reply を送らない"""
        mock_line_svc.reply_message.side_effect = LineServiceError("エラー")

        line_event = {
            "type": "message",
            "source": {"type": "user", "userId": "U123456789abcdef"},
            "message": {"type": "text", "text": "テスト"},
            "timestamp": 1716000000000,
            # replyToken 欠落
        }
        body = json.dumps({"events": [line_event]})
        event = _make_apigw_event(body, "sig")

        mock_ddb_inst = MagicMock()
        mock_ddb_inst.get_item.return_value = None
        with patch("webhook_handler._get_ddb", return_value=mock_ddb_inst), \
             patch("webhook_handler.classify_intent", return_value={"intent": "CHAT", "confidence": 0.5}), \
             patch("webhook_handler.generate_reply", return_value="やあ"):
            result = handler(event, None)

        assert result["statusCode"] == 200
        # フォールバック Reply は呼ばれない（replyToken がないため）
        assert mock_line_svc.reply_message.call_count == 1  # 最初の失敗のみ

    def test_null_body_does_not_crash(self, mock_line_svc):
        """body が null の場合でも 200 を返す"""
        event = {
            "headers": {"x-line-signature": "sig"},
            "body": None,
            "isBase64Encoded": False,
        }
        result = handler(event, None)
        # body が None の場合は verify_signature が空文字で呼ばれる
        assert result["statusCode"] in (200, 403)
