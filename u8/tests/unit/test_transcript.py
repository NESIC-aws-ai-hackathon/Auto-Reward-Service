"""
Unit tests for TranscriptService.
"""
import pytest
from unittest.mock import patch, MagicMock
import os

os.environ["TABLE_NAME"] = "ArsTable"
os.environ["AWS_REGION"] = "ap-northeast-1"
os.environ["ENV"] = "test"


@pytest.fixture
def mock_table():
    with patch("shared.data_access.boto3") as mock_boto:
        mock_tbl = MagicMock()
        mock_resource = MagicMock()
        mock_resource.Table.return_value = mock_tbl
        mock_boto.resource.return_value = mock_resource
        yield mock_tbl


class TestSaveTurn:
    def test_valid_turn_saved(self, mock_table):
        """Valid turn is saved to DynamoDB."""
        mock_table.put_item.return_value = None

        from services.transcript import TranscriptService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = TranscriptService(da)
        result = svc.save_turn("user-001", "sess-001", {
            "role": "user",
            "content": "今日は疲れた",
            "timestamp": "2026-05-24T10:30:00.000Z",
        })

        assert "turn_id" in result
        assert mock_table.put_item.called

    def test_invalid_role_raises(self, mock_table):
        """Invalid role raises ValueError."""
        from services.transcript import TranscriptService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = TranscriptService(da)

        with pytest.raises(ValueError, match="role"):
            svc.save_turn("user-001", "sess-001", {
                "role": "system",
                "content": "test",
                "timestamp": "2026-05-24T10:30:00.000Z",
            })

    def test_empty_content_raises(self, mock_table):
        """Empty content raises ValueError."""
        from services.transcript import TranscriptService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = TranscriptService(da)

        with pytest.raises(ValueError, match="content"):
            svc.save_turn("user-001", "sess-001", {
                "role": "user",
                "content": "",
                "timestamp": "2026-05-24T10:30:00.000Z",
            })

    def test_content_too_long_raises(self, mock_table):
        """Content > 10000 chars raises ValueError."""
        from services.transcript import TranscriptService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = TranscriptService(da)

        with pytest.raises(ValueError, match="10000"):
            svc.save_turn("user-001", "sess-001", {
                "role": "user",
                "content": "x" * 10001,
                "timestamp": "2026-05-24T10:30:00.000Z",
            })

    def test_missing_timestamp_raises(self, mock_table):
        """Missing timestamp raises ValueError."""
        from services.transcript import TranscriptService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = TranscriptService(da)

        with pytest.raises(ValueError, match="timestamp"):
            svc.save_turn("user-001", "sess-001", {
                "role": "user",
                "content": "hello",
                "timestamp": "",
            })


class TestSaveBulk:
    def test_bulk_saves_multiple_turns(self, mock_table):
        """Bulk save writes all turns and updates turn_count."""
        mock_table.get_item.return_value = {"Item": {
            "PK": "USER#user-001",
            "SK": "VOICE_SESSION#sess-001",
            "turn_count": 3,
        }}
        mock_table.update_item.return_value = None
        mock_batch = MagicMock()
        mock_batch.__enter__ = MagicMock(return_value=mock_batch)
        mock_batch.__exit__ = MagicMock(return_value=False)
        mock_table.batch_writer.return_value = mock_batch

        from services.transcript import TranscriptService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = TranscriptService(da)
        turns = [
            {"role": "user", "content": "こんにちは", "timestamp": "2026-05-24T10:00:00Z"},
            {"role": "assistant", "content": "やっほー！", "timestamp": "2026-05-24T10:00:01Z"},
        ]
        result = svc.save_bulk("user-001", "sess-001", turns)

        assert result["saved_count"] == 2

    def test_empty_turns_returns_zero(self, mock_table):
        """Empty turns list returns saved_count 0."""
        from services.transcript import TranscriptService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = TranscriptService(da)
        result = svc.save_bulk("user-001", "sess-001", [])

        assert result["saved_count"] == 0

    def test_over_100_turns_raises(self, mock_table):
        """More than 100 turns raises ValueError."""
        from services.transcript import TranscriptService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = TranscriptService(da)
        turns = [
            {"role": "user", "content": f"msg{i}", "timestamp": f"2026-05-24T10:00:{i:02d}Z"}
            for i in range(101)
        ]

        with pytest.raises(ValueError, match="100"):
            svc.save_bulk("user-001", "sess-001", turns)

    def test_invalid_turn_in_bulk_raises(self, mock_table):
        """Invalid turn in bulk raises ValueError."""
        from services.transcript import TranscriptService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = TranscriptService(da)
        turns = [
            {"role": "invalid", "content": "test", "timestamp": "2026-05-24T10:00:00Z"},
        ]

        with pytest.raises(ValueError, match="role"):
            svc.save_bulk("user-001", "sess-001", turns)
