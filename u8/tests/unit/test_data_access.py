"""
Unit tests for DataAccess layer.
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


class TestResolveUserId:
    def test_existing_identity_returns_user_id(self, mock_table):
        """Existing cognito identity returns stored user_id."""
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "IDENTITY#COGNITO#sub-abc",
                "SK": "META#",
                "user_id": "existing-user-id",
            }
        }

        from shared.data_access import DataAccess
        da = DataAccess()
        user_id = da.resolve_user_id("sub-abc")

        assert user_id == "existing-user-id"
        mock_table.get_item.assert_called_once_with(
            Key={"PK": "IDENTITY#COGNITO#sub-abc", "SK": "META#"}
        )

    def test_new_identity_creates_user(self, mock_table):
        """New cognito identity creates user and returns new user_id."""
        mock_table.get_item.return_value = {}  # Not found
        mock_table.put_item.return_value = None

        from shared.data_access import DataAccess
        da = DataAccess()
        user_id = da.resolve_user_id("new-sub")

        assert user_id is not None
        assert len(user_id) == 36  # UUID format
        # Should create identity + profile (2 put_item calls)
        assert mock_table.put_item.call_count == 2


class TestGetOrCreateProfile:
    def test_existing_profile_returned(self, mock_table):
        """Returns existing profile without creating."""
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "USER#user-1",
                "SK": "PROFILE#",
                "display_name": "太郎",
                "diary_time": "22:00",
                "notification_enabled": True,
                "monthly_surplus": 3000,
            }
        }

        from shared.data_access import DataAccess
        da = DataAccess()
        profile = da.get_or_create_profile("user-1")

        assert profile["display_name"] == "太郎"
        assert profile["monthly_surplus"] == 3000
        mock_table.put_item.assert_not_called()

    def test_missing_profile_creates_default(self, mock_table):
        """Creates default profile if not found."""
        mock_table.get_item.return_value = {}  # Not found
        mock_table.put_item.return_value = None

        from shared.data_access import DataAccess
        da = DataAccess()
        profile = da.get_or_create_profile("user-2")

        assert profile["display_name"] == ""
        assert profile["diary_time"] == "22:00"
        assert profile["notification_enabled"] is True
        assert profile["monthly_surplus"] == 0


class TestUpdateProfile:
    def test_update_adds_updated_at(self, mock_table):
        """update_profile always sets updated_at."""
        mock_table.update_item.return_value = None

        from shared.data_access import DataAccess
        da = DataAccess()
        da.update_profile("user-1", {"display_name": "新名前"})

        call_args = mock_table.update_item.call_args
        assert call_args is not None
        # Check that updated_at was included
        expr_values = call_args.kwargs.get("ExpressionAttributeValues", {})
        values_list = list(expr_values.values())
        # One should be display_name, one should be updated_at (ISO format)
        has_iso_date = any(isinstance(v, str) and "T" in v for v in values_list)
        assert has_iso_date


class TestSKConstants:
    def test_sk_constants_defined(self):
        """All SK constants are properly defined."""
        from shared.data_access import (
            SK_PROFILE,
            SK_VOICE_SESSION,
            SK_ANALYSIS_JOB_META,
            SK_CONVERSATION_TURN,
            SK_LIFE_LOG,
            SK_DAILY_FUREMARU_SUMMARY,
            SK_STRESS_SUMMARY,
            SK_EXPENSE,
            SK_REWARD_PERMIT,
            SK_REWARD_SKIP,
            SK_MONTHLY_SUMMARY,
            SK_PUSH_SUBSCRIPTION,
        )

        assert SK_PROFILE == "PROFILE#"
        assert "session_id" in SK_VOICE_SESSION
        assert SK_ANALYSIS_JOB_META == "META#"
        assert "timestamp" in SK_CONVERSATION_TURN
        assert "date" in SK_LIFE_LOG
        assert "date" in SK_DAILY_FUREMARU_SUMMARY
        assert "date" in SK_STRESS_SUMMARY
        assert "timestamp" in SK_EXPENSE
        assert "timestamp" in SK_REWARD_PERMIT
        assert "timestamp" in SK_REWARD_SKIP
        assert "yyyy_mm" in SK_MONTHLY_SUMMARY
        assert SK_PUSH_SUBSCRIPTION == "PUSH_SUBSCRIPTION#"
