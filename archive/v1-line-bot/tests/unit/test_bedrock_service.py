"""bedrock_service.py のユニットテスト"""
import pytest
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError

from services.bedrock_service import BedrockService
from utils.exceptions import BedrockError


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "error"}}, "converse")


@pytest.fixture
def svc():
    return BedrockService()


class TestInvokeText:
    def test_success(self, svc):
        mock_response = {
            "output": {"message": {"content": [{"text": "おはよう！"}]}}
        }
        with patch.object(svc._client, "converse", return_value=mock_response) as m:
            result = svc.invoke_text("こんにちは")
        assert result == "おはよう！"
        m.assert_called_once()

    def test_uses_env_model_id(self, svc, monkeypatch):
        monkeypatch.setenv("BEDROCK_TEXT_MODEL_ID", "amazon.nova-micro-v1:0")
        svc2 = BedrockService()
        mock_response = {
            "output": {"message": {"content": [{"text": "ok"}]}}
        }
        with patch.object(svc2._client, "converse", return_value=mock_response) as m:
            svc2.invoke_text("hello")
        call_args = m.call_args
        assert call_args.kwargs["modelId"] == "amazon.nova-micro-v1:0"

    def test_explicit_model_id_override(self, svc):
        mock_response = {
            "output": {"message": {"content": [{"text": "ok"}]}}
        }
        with patch.object(svc._client, "converse", return_value=mock_response) as m:
            svc.invoke_text("hello", model_id="anthropic.claude-3-haiku-20240307-v1:0")
        assert m.call_args.kwargs["modelId"] == "anthropic.claude-3-haiku-20240307-v1:0"

    def test_retry_on_throttling(self, svc):
        throttle = _make_client_error("ThrottlingException")
        success = {"output": {"message": {"content": [{"text": "ok"}]}}}
        with patch.object(svc._client, "converse", side_effect=[throttle, success]) as m:
            with patch("services.bedrock_service.time.sleep") as sleep_mock:
                result = svc.invoke_text("hello")
        assert result == "ok"
        assert m.call_count == 2
        sleep_mock.assert_called_once_with(0.5)

    def test_raises_after_max_retries(self, svc):
        throttle = _make_client_error("ThrottlingException")
        with patch.object(svc._client, "converse", side_effect=[throttle, throttle, throttle]):
            with patch("services.bedrock_service.time.sleep"):
                with pytest.raises(BedrockError):
                    svc.invoke_text("hello")

    def test_non_retryable_error_raises_immediately(self, svc):
        err = _make_client_error("ValidationException")
        with patch.object(svc._client, "converse", side_effect=err):
            with pytest.raises(BedrockError) as exc_info:
                svc.invoke_text("hello")
        assert "ValidationException" in str(exc_info.value)


class TestInvokeImage:
    def test_success(self, svc):
        mock_response = {
            "output": {"message": {"content": [{"text": "1000円"}]}}
        }
        with patch.object(svc._client, "converse", return_value=mock_response):
            result = svc.invoke_image("レシートを解析してください", b"fake_image")
        assert result == "1000円"
