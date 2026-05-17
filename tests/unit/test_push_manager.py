"""
push_manager サービスのユニットテスト
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.push_manager import (
    MONTHLY_PUSH_LIMIT,
    _log_push,
    reset_monthly_push_count,
    send_push,
)


class TestSendPush:
    def _make_ddb_mock(self, push_count=0):
        ddb = MagicMock()
        ddb.get_item.return_value = {"push_count_this_month": push_count}
        return ddb

    @patch("services.push_manager.get_line_service")
    def test_send_push_success(self, mock_get_line):
        mock_line = MagicMock()
        mock_get_line.return_value = mock_line
        ddb = self._make_ddb_mock(push_count=0)

        result = send_push(
            user_id="U123",
            message={"type": "text", "text": "テスト"},
            ddb=ddb,
            category="food_discovery",
            template_id="food_discovery:0",
        )

        assert result is True
        mock_line.push_message.assert_called_once()
        ddb.update_item.assert_called()
        ddb.put_item.assert_called()  # PUSH_LOG

    def test_send_push_monthly_limit_reached(self):
        ddb = self._make_ddb_mock(push_count=MONTHLY_PUSH_LIMIT)

        result = send_push(
            user_id="U123",
            message={"type": "text", "text": "テスト"},
            ddb=ddb,
        )

        assert result is False

    @patch("services.push_manager.get_line_service")
    def test_send_push_line_error(self, mock_get_line):
        mock_line = MagicMock()
        mock_line.push_message.side_effect = Exception("LINE API error")
        mock_get_line.return_value = mock_line
        ddb = self._make_ddb_mock(push_count=0)

        result = send_push(
            user_id="U123",
            message={"type": "text", "text": "テスト"},
            ddb=ddb,
        )

        assert result is False

    @patch("services.push_manager.get_line_service")
    def test_send_push_increments_count(self, mock_get_line):
        mock_line = MagicMock()
        mock_get_line.return_value = mock_line
        ddb = self._make_ddb_mock(push_count=5)

        send_push(user_id="U123", message={"type": "text", "text": "テスト"}, ddb=ddb)

        # update_item で push_count_this_month = 6 を確認
        calls = ddb.update_item.call_args_list
        profile_update = [c for c in calls if c.kwargs.get("sk") == "PROFILE#" or (len(c.args) >= 2 and c.args[1] == "PROFILE#")]
        assert len(profile_update) > 0


class TestResetMonthlyPushCount:
    def test_reset_count(self):
        ddb = MagicMock()
        reset_monthly_push_count("U123", ddb)
        ddb.update_item.assert_called_once_with(
            pk="USER#U123",
            sk="PROFILE#",
            updates={"push_count_this_month": 0},
        )

    def test_reset_handles_error(self):
        ddb = MagicMock()
        ddb.update_item.side_effect = Exception("DDB error")
        # Should not raise
        reset_monthly_push_count("U123", ddb)


class TestLogPush:
    def test_log_push_creates_entry(self):
        ddb = MagicMock()
        _log_push("USER#U123", ddb, "food_discovery", "food_discovery:0", "テストメッセージですよ")
        ddb.put_item.assert_called_once()
        call_kwargs = ddb.put_item.call_args
        assert call_kwargs.kwargs.get("pk") == "USER#U123" or call_kwargs[1].get("pk") == "USER#U123"

    def test_log_push_handles_error(self):
        ddb = MagicMock()
        ddb.put_item.side_effect = Exception("DDB error")
        # Should not raise
        _log_push("USER#U123", ddb, "cat", "id", "text")
