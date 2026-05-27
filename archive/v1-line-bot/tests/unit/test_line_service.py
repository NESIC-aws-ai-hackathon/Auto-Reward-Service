"""line_service.py のユニットテスト"""
import hashlib
import hmac
import base64

import pytest
from unittest.mock import MagicMock, patch

from services.line_service import LineService
from utils.exceptions import LineServiceError


@pytest.fixture
def svc():
    return LineService(
        channel_secret="test_secret",
        channel_access_token="test_token",
    )


class TestVerifySignature:
    def test_valid_signature(self, svc):
        body = '{"events":[]}'
        digest = hmac.new(
            b"test_secret", body.encode("utf-8"), hashlib.sha256
        ).digest()
        signature = base64.b64encode(digest).decode("utf-8")
        assert svc.verify_signature(body, signature) is True

    def test_invalid_signature(self, svc):
        assert svc.verify_signature('{"events":[]}', "invalidsignature==") is False

    def test_tampered_body(self, svc):
        body = '{"events":[]}'
        digest = hmac.new(
            b"test_secret", body.encode("utf-8"), hashlib.sha256
        ).digest()
        signature = base64.b64encode(digest).decode("utf-8")
        tampered_body = '{"events":[], "extra": "tampered"}'
        assert svc.verify_signature(tampered_body, signature) is False


class TestReplyMessage:
    def test_reply_text_message(self, svc):
        with patch.object(svc._api, "reply_message") as mock_reply:
            svc.reply_message(
                reply_token="test_reply_token",
                messages=[{"type": "text", "text": "こんにちは！"}],
            )
        mock_reply.assert_called_once()

    def test_reply_raises_on_failure(self, svc):
        with patch.object(svc._api, "reply_message", side_effect=Exception("API error")):
            with pytest.raises(LineServiceError):
                svc.reply_message("token", [{"type": "text", "text": "test"}])

    def test_reply_no_retry_on_failure(self, svc):
        """LINE API はリトライしない"""
        with patch.object(svc._api, "reply_message", side_effect=Exception("error")) as m:
            with pytest.raises(LineServiceError):
                svc.reply_message("token", [{"type": "text", "text": "test"}])
        assert m.call_count == 1  # 1回のみ呼び出し


class TestPushMessage:
    def test_push_text_message(self, svc):
        with patch.object(svc._api, "push_message") as mock_push:
            svc.push_message(
                user_id="U1234567890abcdef",
                messages=[{"type": "text", "text": "お知らせです"}],
            )
        mock_push.assert_called_once()


class TestDictToMessage:
    def test_text_message(self, svc):
        from linebot.v3.messaging import TextMessage
        result = svc._dict_to_message({"type": "text", "text": "hello"})
        assert isinstance(result, TextMessage)
        assert result.text == "hello"

    def test_unknown_type_raises(self, svc):
        with pytest.raises(LineServiceError):
            svc._dict_to_message({"type": "unknown"})
