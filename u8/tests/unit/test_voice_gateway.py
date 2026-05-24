"""
Unit tests for Voice Gateway Lambda handler.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
import os

os.environ["TABLE_NAME"] = "ArsTable"
os.environ["AWS_REGION"] = "ap-northeast-1"
os.environ["ENV"] = "test"
os.environ["ANALYSIS_QUEUE_URL"] = "https://sqs.ap-northeast-1.amazonaws.com/123/test-queue"
os.environ["NOVA_SONIC_MODEL_ID"] = "amazon.nova-sonic-v1:0"
os.environ["WEBSOCKET_API_ENDPOINT"] = "https://test.execute-api.ap-northeast-1.amazonaws.com/dev"


@pytest.fixture
def mock_table():
    with patch("shared.data_access.boto3") as mock_boto:
        mock_tbl = MagicMock()
        mock_resource = MagicMock()
        mock_resource.Table.return_value = mock_tbl
        mock_boto.resource.return_value = mock_resource
        # Also patch the module-level da in voice_gateway
        from shared.data_access import DataAccess
        da = DataAccess()
        with patch("handlers.voice_gateway.da", da):
            yield mock_tbl


@pytest.fixture
def mock_apigw_management():
    with patch("handlers.voice_gateway.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        yield mock_client


def _ws_event(route_key: str, connection_id: str = "conn-123", body: dict = None):
    """Helper to create WebSocket API Gateway event."""
    event = {
        "requestContext": {
            "routeKey": route_key,
            "connectionId": connection_id,
        },
    }
    if body:
        event["body"] = json.dumps(body)
    return event


class TestConnect:
    def test_connect_with_valid_token(self, mock_table, mock_apigw_management):
        """$connect with valid token stores connection."""
        mock_table.put_item.return_value = None

        with patch("shared.auth.validate_jwt_token", return_value="user-001"):
            from handlers.voice_gateway import lambda_handler

            event = _ws_event("$connect", "conn-abc")
            event["queryStringParameters"] = {"token": "valid-jwt-token"}

            result = lambda_handler(event, None)
            assert result["statusCode"] == 200
            assert mock_table.put_item.called

    def test_connect_without_token(self, mock_table, mock_apigw_management):
        """$connect without token returns 401."""
        from handlers.voice_gateway import lambda_handler

        event = _ws_event("$connect", "conn-abc")
        event["queryStringParameters"] = {}

        result = lambda_handler(event, None)
        assert result["statusCode"] == 401

    def test_connect_with_invalid_token(self, mock_table, mock_apigw_management):
        """$connect with invalid token returns 401."""
        with patch("shared.auth.validate_jwt_token", return_value=None):
            from handlers.voice_gateway import lambda_handler

            event = _ws_event("$connect", "conn-abc")
            event["queryStringParameters"] = {"token": "invalid-token"}

            result = lambda_handler(event, None)
            assert result["statusCode"] == 401


class TestDisconnect:
    def test_disconnect_cleans_up(self, mock_table, mock_apigw_management):
        """$disconnect removes connection record."""
        mock_table.get_item.return_value = {"Item": {
            "PK": "WS_CONNECTION#conn-xyz",
            "SK": "META#",
            "connection_id": "conn-xyz",
            "user_id": "user-001",
            "active_session_id": "",
        }}
        mock_table.delete_item.return_value = None

        from handlers.voice_gateway import lambda_handler

        event = _ws_event("$disconnect", "conn-xyz")
        result = lambda_handler(event, None)
        assert result["statusCode"] == 200


class TestStartSession:
    def test_start_session_creates_session(self, mock_table, mock_apigw_management):
        """startSession creates a new Nova Sonic session."""
        # Connection exists
        mock_table.get_item.return_value = {"Item": {
            "PK": "WS_CONNECTION#conn-001",
            "SK": "META#",
            "connection_id": "conn-001",
            "user_id": "user-001",
        }}
        mock_table.query.return_value = {"Items": []}
        mock_table.put_item.return_value = None
        mock_table.update_item.return_value = None

        from handlers.voice_gateway import lambda_handler

        event = _ws_event("startSession", "conn-001")
        result = lambda_handler(event, None)
        assert result["statusCode"] == 200

        # Verify send_to_client was called with sessionStarted
        mock_apigw_management.post_to_connection.assert_called()
        call_data = json.loads(
            mock_apigw_management.post_to_connection.call_args[1]["Data"].decode()
        )
        assert call_data["type"] == "sessionStarted"
        assert "session_id" in call_data

    def test_start_session_no_connection(self, mock_table, mock_apigw_management):
        """startSession returns 403 if connection not found."""
        mock_table.get_item.return_value = {}  # No "Item" key = not found

        from handlers.voice_gateway import lambda_handler

        event = _ws_event("startSession", "conn-unknown")
        result = lambda_handler(event, None)
        assert result["statusCode"] == 403


class TestEndSession:
    def test_end_session(self, mock_table, mock_apigw_management):
        """endSession completes session and sends conversationEnded."""
        # Use a function to handle multiple get_item calls
        def get_item_side_effect(**kwargs):
            key = kwargs.get("Key", {})
            pk = key.get("PK", "")
            if pk.startswith("WS_CONNECTION#"):
                return {"Item": {
                    "PK": "WS_CONNECTION#conn-001",
                    "SK": "META#",
                    "connection_id": "conn-001",
                    "user_id": "user-001",
                    "active_session_id": "sess-001",
                }}
            elif pk.startswith("USER#"):
                return {"Item": {
                    "PK": "USER#user-001",
                    "SK": "VOICE_SESSION#sess-001",
                    "status": "active",
                    "started_at": "2026-05-24T10:00:00+00:00",
                    "turn_count": 3,
                }}
            return {}

        mock_table.get_item.side_effect = get_item_side_effect
        mock_table.put_item.return_value = None
        mock_table.update_item.return_value = None

        with patch("services.sonic_voice_session.boto3.client") as mock_svc_boto:
            mock_sqs = MagicMock()
            mock_svc_boto.return_value = mock_sqs

            from handlers.voice_gateway import lambda_handler

            event = _ws_event("endSession", "conn-001")
            result = lambda_handler(event, None)
            assert result["statusCode"] == 200
