"""
Unit tests for RecoveryService.
"""
import pytest
from unittest.mock import patch, MagicMock
import os
import json

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


class TestGetRecovery:
    def test_no_stress_summary_returns_empty(self, mock_table, mock_bedrock):
        """No stress summary returns placeholder message."""
        mock_table.get_item.return_value = {}

        from services.recovery import RecoveryService
        from shared.data_access import DataAccess
        from shared.bedrock_client import BedrockClient

        da = DataAccess()
        bedrock = BedrockClient()
        svc = RecoveryService(da, bedrock)
        result = svc.get_recovery("user-001")

        assert result["stress_level"] is None
        assert "話しかけてね" in result["message"]
        assert result["free_recovery"] == []

    def test_stress_level_3_returns_moderate_options(self, mock_table, mock_bedrock):
        """Stress level 3 returns moderate recovery options."""
        # First call: get stress summary, second: get profile
        mock_table.get_item.side_effect = [
            {"Item": {"stress_level": 3, "mood": "疲れ"}},
            {"Item": {"display_name": "太郎", "monthly_surplus": 3000}},
        ]

        # Bedrock voice conversion
        mock_bedrock.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({
                "content": [{"text": "[]"}]
            }).encode()))
        }

        from services.recovery import RecoveryService
        from shared.data_access import DataAccess
        from shared.bedrock_client import BedrockClient

        da = DataAccess()
        bedrock = BedrockClient()
        svc = RecoveryService(da, bedrock)
        result = svc.get_recovery("user-001")

        assert result["stress_level"] == 3
        assert len(result["free_recovery"]) == 3
        assert "疲れ" in result["mood"]

    def test_no_surplus_skips_paid_options(self, mock_table, mock_bedrock):
        """No monthly surplus means no paid options."""
        mock_table.get_item.side_effect = [
            {"Item": {"stress_level": 4, "mood": "つらい"}},
            {"Item": {"display_name": "花子", "monthly_surplus": 0}},
        ]

        mock_bedrock.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({
                "content": [{"text": "[]"}]
            }).encode()))
        }

        from services.recovery import RecoveryService
        from shared.data_access import DataAccess
        from shared.bedrock_client import BedrockClient

        da = DataAccess()
        bedrock = BedrockClient()
        svc = RecoveryService(da, bedrock)
        result = svc.get_recovery("user-001")

        assert result["paid_recovery"] == []
        assert len(result["free_recovery"]) == 3


class TestRecordPermit:
    def test_records_permit(self, mock_table, mock_bedrock):
        """Records a permit action."""
        mock_table.put_item.return_value = None

        from services.recovery import RecoveryService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = RecoveryService(da)
        result = svc.record_permit("user-001", "fr-001", "free")

        assert result["message"] == "recorded"
        assert mock_table.put_item.called


class TestRecordSkip:
    def test_records_skip(self, mock_table, mock_bedrock):
        """Records a skip action."""
        mock_table.put_item.return_value = None

        from services.recovery import RecoveryService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = RecoveryService(da)
        result = svc.record_skip("user-001", "もう寝る")

        assert result["message"] == "recorded"
        assert mock_table.put_item.called


class TestAssessStress:
    def test_assesses_stress_from_conversation(self, mock_table, mock_bedrock):
        """Extracts stress level from conversation."""
        mock_table.query.return_value = {"Items": [
            {"PK": "USER#u1", "SK": "CONVERSATION_TURN#2026-05-24T10:00:00Z",
             "session_id": "sess-1", "role": "user", "content": "今日は仕事が大変だった…"},
            {"PK": "USER#u1", "SK": "CONVERSATION_TURN#2026-05-24T10:00:01Z",
             "session_id": "sess-1", "role": "assistant", "content": "大変だったね…"},
        ]}
        mock_table.put_item.return_value = None

        mock_bedrock.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=json.dumps({
                "content": [{"text": json.dumps({
                    "stress_level": 4,
                    "factors": ["仕事が大変"],
                    "positive_factors": [],
                    "mood": "疲労"
                })}]
            }).encode()))
        }

        from services.analysis import AnalysisService
        from shared.data_access import DataAccess
        from shared.bedrock_client import BedrockClient

        da = DataAccess()
        bedrock = BedrockClient()
        svc = AnalysisService(da, bedrock)
        result = svc.assess_stress("u1", "sess-1")

        assert result["stress_level"] == 4
        assert "仕事が大変" in result["factors"]
        assert mock_table.put_item.called

    def test_empty_session_returns_default(self, mock_table, mock_bedrock):
        """Empty session returns default stress level 2."""
        mock_table.query.return_value = {"Items": []}

        from services.analysis import AnalysisService
        from shared.data_access import DataAccess
        from shared.bedrock_client import BedrockClient

        da = DataAccess()
        bedrock = BedrockClient()
        svc = AnalysisService(da, bedrock)
        result = svc.assess_stress("u1", "sess-empty")

        assert result["stress_level"] == 2
        mock_bedrock.invoke_model.assert_not_called()
