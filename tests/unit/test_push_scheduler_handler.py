"""
push_scheduler_handler のユニットテスト
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import push_scheduler_handler


class TestPushSchedulerHandler:
    @patch("push_scheduler_handler.get_dynamodb_service")
    def test_warmup_returns_200(self, mock_get_ddb):
        result = push_scheduler_handler.handler({"source": "warmup"}, None)
        assert result["statusCode"] == 200
        assert result["body"] == "warm"
        mock_get_ddb.assert_not_called()

    @patch("push_scheduler_handler.get_dynamodb_service")
    def test_schedules_active_users(self, mock_get_ddb):
        ddb = MagicMock()
        ddb.query_by_gsi.return_value = [
            {"PK": "USER#U001", "SK": "PROFILE#", "status": "ACTIVE"},
            {"PK": "USER#U002", "SK": "PROFILE#", "status": "ACTIVE"},
        ]
        ddb.get_item.return_value = None  # No PUSH_SETTINGS
        mock_get_ddb.return_value = ddb

        result = push_scheduler_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        assert ddb.put_item.call_count == 2

    @patch("push_scheduler_handler.get_dynamodb_service")
    def test_skips_disabled_push_users(self, mock_get_ddb):
        ddb = MagicMock()
        ddb.query_by_gsi.return_value = [
            {"PK": "USER#U001", "SK": "PROFILE#", "status": "ACTIVE"},
        ]
        ddb.get_item.return_value = {"all_enabled": False}
        mock_get_ddb.return_value = ddb

        result = push_scheduler_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        assert "Skipped: 1" in result["body"]
        ddb.put_item.assert_not_called()

    @patch("push_scheduler_handler.get_dynamodb_service")
    def test_handles_gsi_error(self, mock_get_ddb):
        ddb = MagicMock()
        ddb.query_by_gsi.side_effect = Exception("GSI error")
        mock_get_ddb.return_value = ddb

        result = push_scheduler_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 500

    @patch("push_scheduler_handler.get_dynamodb_service")
    def test_put_item_error_continues(self, mock_get_ddb):
        ddb = MagicMock()
        ddb.query_by_gsi.return_value = [
            {"PK": "USER#U001", "SK": "PROFILE#", "status": "ACTIVE"},
            {"PK": "USER#U002", "SK": "PROFILE#", "status": "ACTIVE"},
        ]
        ddb.get_item.return_value = None
        # 1回目失敗、2回目成功
        ddb.put_item.side_effect = [Exception("DDB error"), None]
        mock_get_ddb.return_value = ddb

        result = push_scheduler_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        assert "Scheduled: 1" in result["body"]

    @patch("push_scheduler_handler.get_dynamodb_service")
    def test_custom_time_range(self, mock_get_ddb):
        ddb = MagicMock()
        ddb.query_by_gsi.return_value = [
            {"PK": "USER#U001", "SK": "PROFILE#", "status": "ACTIVE"},
        ]
        ddb.get_item.return_value = {
            "all_enabled": True,
            "daily_message": True,
            "push_time_start": "12:00",
            "push_time_end": "18:00",
        }
        mock_get_ddb.return_value = ddb

        result = push_scheduler_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        assert ddb.put_item.call_count == 1

    @patch("push_scheduler_handler.get_dynamodb_service")
    def test_skips_non_user_pk(self, mock_get_ddb):
        ddb = MagicMock()
        ddb.query_by_gsi.return_value = [
            {"PK": "SYSTEM#config", "SK": "PROFILE#", "status": "ACTIVE"},
        ]
        mock_get_ddb.return_value = ddb

        result = push_scheduler_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        ddb.put_item.assert_not_called()


class TestRandomTimeInRange:
    def test_time_within_range(self):
        base = datetime(2026, 5, 17, 10, 0, tzinfo=timezone(timedelta(hours=9)))
        for _ in range(20):
            result = push_scheduler_handler._random_time_in_range(base, "10:00", "21:00")
            assert 10 <= result.hour <= 21
            assert result.date() == base.date()

    def test_same_start_end(self):
        base = datetime(2026, 5, 17, 10, 0, tzinfo=timezone(timedelta(hours=9)))
        result = push_scheduler_handler._random_time_in_range(base, "12:00", "12:00")
        assert result.hour == 12
        assert result.minute == 0
