"""secrets.py のユニットテスト"""
import json

import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from utils.secrets import get_secret, get_line_secrets, clear_cache
from utils.exceptions import SecretsError


@pytest.fixture(autouse=True)
def clear_secrets_cache():
    """テスト間でキャッシュをクリア"""
    clear_cache()
    yield
    clear_cache()


class TestGetSecret:
    def test_fetches_and_caches(self, monkeypatch):
        mock_value = {"LINE_CHANNEL_SECRET": "sec", "LINE_ACCESS_TOKEN": "tok"}

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(mock_value)
        }

        with patch("utils.secrets.boto3.client", return_value=mock_client):
            result1 = get_secret("ars/line")
            result2 = get_secret("ars/line")

        assert result1 == mock_value
        assert result2 == mock_value
        # キャッシュにより 2 回目は API 呼び出しなし
        mock_client.get_secret_value.assert_called_once()

    def test_raises_on_client_error(self, monkeypatch):
        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
            "GetSecretValue",
        )

        with patch("utils.secrets.boto3.client", return_value=mock_client):
            with pytest.raises(SecretsError):
                get_secret("ars/nonexistent")


class TestGetLineSecrets:
    def test_uses_env_var(self, monkeypatch):
        monkeypatch.setenv("LINE_SECRET_NAME", "ars/line")
        mock_value = {"LINE_CHANNEL_SECRET": "sec", "LINE_ACCESS_TOKEN": "tok"}

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(mock_value)
        }

        with patch("utils.secrets.boto3.client", return_value=mock_client):
            result = get_line_secrets()

        assert result["LINE_CHANNEL_SECRET"] == "sec"
        mock_client.get_secret_value.assert_called_once_with(SecretId="ars/line")
