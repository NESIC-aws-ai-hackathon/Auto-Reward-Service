"""
Unit tests for SonicVoiceSessionService.
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
        yield mock_tbl


class TestStartSession:
    def test_creates_session(self, mock_table):
        """start_session returns session_id and model_id."""
        mock_table.query.return_value = {"Items": []}
        mock_table.put_item.return_value = None

        from services.sonic_voice_session import SonicVoiceSessionService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = SonicVoiceSessionService(da)
        result = svc.start_session("user-001", "conn-001")

        assert "session_id" in result
        assert result["model_id"] == "amazon.nova-sonic-v1:0"
        assert mock_table.put_item.called

        # Verify the put_item was called with correct attributes
        call_args = mock_table.put_item.call_args
        item = call_args[1]["Item"] if "Item" in call_args[1] else call_args[0][0]
        if isinstance(item, dict):
            assert item.get("voice_provider") == "bedrock_nova_sonic"
            assert item.get("connection_type") == "backend_websocket"

    def test_closes_active_sessions(self, mock_table):
        """Existing active sessions are aborted before starting new one."""
        mock_table.query.return_value = {"Items": [
            {"PK": "USER#user-001", "SK": "VOICE_SESSION#old-id", "status": "active"}
        ]}
        mock_table.put_item.return_value = None
        mock_table.update_item.return_value = None

        from services.sonic_voice_session import SonicVoiceSessionService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = SonicVoiceSessionService(da)
        svc.start_session("user-001", "conn-001")

        # Should have called update_item to abort old session
        assert mock_table.update_item.called


class TestEndSession:
    def test_completes_session_and_creates_job(self, mock_table):
        """end_session marks completed and creates analysis job when turns > 0."""
        mock_table.get_item.return_value = {"Item": {
            "PK": "USER#user-001",
            "SK": "VOICE_SESSION#sess-001",
            "status": "active",
            "started_at": "2026-05-24T10:00:00+00:00",
            "turn_count": 5,
        }}
        mock_table.put_item.return_value = None
        mock_table.update_item.return_value = None

        with patch("boto3.client") as mock_boto3_client:
            mock_sqs = MagicMock()
            mock_boto3_client.return_value = mock_sqs

            from services.sonic_voice_session import SonicVoiceSessionService
            from shared.data_access import DataAccess

            da = DataAccess()
            svc = SonicVoiceSessionService(da)
            result = svc.end_session("user-001", "sess-001")

            assert result["analysis_job_id"] is not None
            assert result["turn_count"] == 5
            mock_sqs.send_message.assert_called_once()

    def test_no_job_for_empty_session(self, mock_table):
        """No analysis job is created if turn_count is 0."""
        mock_table.get_item.return_value = {"Item": {
            "PK": "USER#user-001",
            "SK": "VOICE_SESSION#sess-002",
            "status": "active",
            "started_at": "2026-05-24T10:00:00+00:00",
            "turn_count": 0,
        }}
        mock_table.update_item.return_value = None

        from services.sonic_voice_session import SonicVoiceSessionService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = SonicVoiceSessionService(da)
        result = svc.end_session("user-001", "sess-002")

        assert result["analysis_job_id"] is None

    def test_session_not_found_raises(self, mock_table):
        """Raises ValueError if session doesn't exist."""
        mock_table.get_item.return_value = {}

        from services.sonic_voice_session import SonicVoiceSessionService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = SonicVoiceSessionService(da)

        with pytest.raises(ValueError, match="Session not found"):
            svc.end_session("user-001", "nonexistent")


class TestAbortSession:
    def test_abort_active_session(self, mock_table):
        """abort_session marks session as aborted."""
        mock_table.get_item.return_value = {"Item": {
            "PK": "USER#user-001",
            "SK": "VOICE_SESSION#sess-003",
            "status": "active",
            "turn_count": 3,
        }}
        mock_table.put_item.return_value = None
        mock_table.update_item.return_value = None

        with patch("boto3.client") as mock_boto3_client:
            mock_sqs = MagicMock()
            mock_boto3_client.return_value = mock_sqs

            from services.sonic_voice_session import SonicVoiceSessionService
            from shared.data_access import DataAccess

            da = DataAccess()
            svc = SonicVoiceSessionService(da)
            svc.abort_session("user-001", "sess-003")

            # Should update status to aborted
            assert mock_table.update_item.called


class TestProcessTextTurn:
    def test_text_turn_saves_and_responds(self, mock_table):
        """process_text_turn saves user turn and generates response."""
        mock_table.put_item.return_value = None
        mock_table.query.return_value = {"Items": []}
        mock_table.get_item.return_value = {"Item": {
            "PK": "USER#user-001",
            "SK": "VOICE_SESSION#sess-004",
            "status": "active",
            "turn_count": 0,
        }}
        mock_table.update_item.return_value = None

        with patch("services.sonic_voice_session.SonicVoiceSessionService._invoke_claude_text") as mock_claude, \
             patch("services.sonic_voice_session.SonicVoiceSessionService._send_to_client") as mock_send:
            mock_claude.return_value = "うんうん、わかるよ！"

            from services.sonic_voice_session import SonicVoiceSessionService
            from shared.data_access import DataAccess

            da = DataAccess()
            svc = SonicVoiceSessionService(da)
            svc.process_text_turn("user-001", "sess-004", "conn-001", "疲れた")

            # Should save user turn and assistant turn
            assert mock_table.put_item.call_count >= 2
            # Should send transcript to client
            mock_send.assert_called()

    def test_end_keyword_triggers_end_request(self, mock_table):
        """End keywords trigger conversationEndRequested."""
        mock_table.put_item.return_value = None
        mock_table.query.return_value = {"Items": []}
        mock_table.get_item.return_value = {"Item": {
            "PK": "USER#user-001",
            "SK": "VOICE_SESSION#sess-005",
            "status": "active",
            "turn_count": 2,
        }}
        mock_table.update_item.return_value = None

        with patch("services.sonic_voice_session.SonicVoiceSessionService._invoke_claude_text") as mock_claude, \
             patch("services.sonic_voice_session.SonicVoiceSessionService._send_to_client") as mock_send:
            mock_claude.return_value = "またね！"

            from services.sonic_voice_session import SonicVoiceSessionService
            from shared.data_access import DataAccess

            da = DataAccess()
            svc = SonicVoiceSessionService(da)
            svc.process_text_turn("user-001", "sess-005", "conn-001", "バイバイ")

            # Should send conversationEndRequested
            calls = [c[0][1] for c in mock_send.call_args_list]
            end_calls = [c for c in calls if c.get("type") == "conversationEndRequested"]
            assert len(end_calls) > 0
