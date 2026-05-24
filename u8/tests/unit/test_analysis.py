"""
Unit tests for AnalysisService.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
import os

os.environ["TABLE_NAME"] = "ArsTable"
os.environ["AWS_REGION"] = "ap-northeast-1"
os.environ["ENV"] = "test"
os.environ["BEDROCK_REGION"] = "us-east-1"
os.environ["BEDROCK_MODEL_ID"] = "anthropic.claude-3-5-sonnet-20241022-v2:0"


@pytest.fixture
def mock_table():
    with patch("shared.data_access.boto3") as mock_boto:
        mock_tbl = MagicMock()
        mock_resource = MagicMock()
        mock_resource.Table.return_value = mock_tbl
        mock_boto.resource.return_value = mock_resource
        yield mock_tbl


@pytest.fixture
def mock_bedrock():
    with patch("shared.bedrock_client.boto3") as mock_boto:
        mock_client = MagicMock()
        mock_boto.client.return_value = mock_client
        yield mock_client


class TestProcessConversation:
    def test_extracts_life_logs_from_turns(self, mock_table, mock_bedrock):
        """Processes conversation and saves extracted life logs."""
        # Setup: conversation turns
        mock_table.query.return_value = {"Items": [
            {"PK": "USER#u1", "SK": "CONVERSATION_TURN#2026-05-24T10:00:00Z",
             "session_id": "sess-1", "role": "user", "content": "今日はカフェでコーヒー飲んだよ。450円だった"},
            {"PK": "USER#u1", "SK": "CONVERSATION_TURN#2026-05-24T10:00:01Z",
             "session_id": "sess-1", "role": "assistant", "content": "カフェいいね！"},
        ]}
        mock_table.get_item.return_value = {"Item": {
            "PK": "ANALYSIS_JOB#job-1", "SK": "META#", "retry_count": 0
        }}
        mock_table.update_item.return_value = None
        mock_table.put_item.return_value = None

        # Bedrock returns life log JSON
        life_log_json = json.dumps([
            {"category": "支出", "content": "カフェでコーヒー", "confidence": 0.9,
             "timestamp_hint": "午前", "amount": 450},
            {"category": "場所", "content": "カフェ", "confidence": 0.8,
             "timestamp_hint": "午前", "amount": None},
        ])
        mock_bedrock.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({
                "content": [{"text": life_log_json}]
            }).encode()))
        }

        from services.analysis import AnalysisService
        from shared.data_access import DataAccess

        da = DataAccess()
        from shared.bedrock_client import BedrockClient
        bedrock = BedrockClient()
        svc = AnalysisService(da, bedrock)
        svc.process_conversation("job-1", "u1", "sess-1")

        # Should update job to completed
        update_calls = mock_table.update_item.call_args_list
        # At least processing + completed
        assert len(update_calls) >= 2

    def test_empty_session_completes_without_extraction(self, mock_table, mock_bedrock):
        """Empty session (no turns) completes without calling Bedrock."""
        mock_table.query.return_value = {"Items": []}
        mock_table.get_item.return_value = {"Item": {"retry_count": 0}}
        mock_table.update_item.return_value = None

        from services.analysis import AnalysisService
        from shared.data_access import DataAccess
        from shared.bedrock_client import BedrockClient

        da = DataAccess()
        bedrock = BedrockClient()
        svc = AnalysisService(da, bedrock)
        svc.process_conversation("job-2", "u1", "sess-empty")

        # Bedrock should NOT be called
        mock_bedrock.invoke_model.assert_not_called()


class TestGenerateDiarySummary:
    def test_generates_diary_from_life_logs(self, mock_table, mock_bedrock):
        """Generates diary text from life logs."""
        # Life logs exist
        mock_table.query.side_effect = [
            {"Items": [  # life logs
                {"category": "活動", "content": "仕事した"},
            ]},
            {"Items": []},  # expenses
        ]
        mock_table.get_item.return_value = {"Item": {
            "display_name": "太郎", "notification_enabled": True
        }}
        mock_table.put_item.return_value = None

        mock_bedrock.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({
                "content": [{"text": "今日の太郎はお仕事頑張ったんだね。お疲れ様♪明日もふれまーるちゃんが応援してるよ！"}]
            }).encode()))
        }

        from services.analysis import AnalysisService
        from shared.data_access import DataAccess
        from shared.bedrock_client import BedrockClient

        da = DataAccess()
        bedrock = BedrockClient()
        svc = AnalysisService(da, bedrock)
        result = svc.generate_diary_summary("u1", "2026-05-24")

        assert "太郎" in result
        assert mock_table.put_item.called

    def test_default_diary_when_no_logs(self, mock_table, mock_bedrock):
        """Returns default diary when no life logs exist."""
        mock_table.query.side_effect = [
            {"Items": []},  # no life logs
            {"Items": []},  # no expenses
        ]
        mock_table.get_item.return_value = {"Item": {"display_name": "花子"}}
        mock_table.put_item.return_value = None

        from services.analysis import AnalysisService
        from shared.data_access import DataAccess
        from shared.bedrock_client import BedrockClient

        da = DataAccess()
        bedrock = BedrockClient()
        svc = AnalysisService(da, bedrock)
        result = svc.generate_diary_summary("u1", "2026-05-24")

        assert "ゆっくり" in result
        mock_bedrock.invoke_model.assert_not_called()
