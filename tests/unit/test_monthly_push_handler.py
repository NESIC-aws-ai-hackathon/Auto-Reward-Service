"""
monthly_push_handler のユニットテスト
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

import monthly_push_handler
from monthly_push_handler import _build_monthly_report


class TestBuildMonthlyReport:
    def test_no_data_returns_greeting(self):
        msg = _build_monthly_report("太郎", 0, 0, 0, 0, 0)
        assert "太郎" in msg
        assert "よろしくね" in msg

    def test_with_carryover(self):
        msg = _build_monthly_report("花子", 24000, 16000, 8000, 4000, 28000)
        assert "花子" in msg
        assert "24,000" in msg
        assert "16,000" in msg
        assert "8,000" in msg
        assert "4,000" in msg
        assert "28,000" in msg
        assert "贅沢" in msg

    def test_no_carryover(self):
        msg = _build_monthly_report("次郎", 20000, 20000, 0, 0, 20000)
        assert "次郎" in msg
        assert "20,000" in msg

    def test_low_usage_comment(self):
        msg = _build_monthly_report("三郎", 20000, 5000, 15000, 7500, 27500)
        assert "セーブ" in msg

    def test_mid_usage_comment(self):
        msg = _build_monthly_report("四郎", 20000, 14000, 6000, 3000, 23000)
        assert "いい感じ" in msg

    def test_high_usage_comment(self):
        msg = _build_monthly_report("五郎", 20000, 19000, 1000, 500, 20500)
        assert "楽しんだ" in msg


class TestMonthlyPushHandler:
    @patch("monthly_push_handler.get_dynamodb_service")
    def test_warmup_returns_200(self, mock_get_ddb):
        result = monthly_push_handler.handler({"source": "warmup"}, None)
        assert result["statusCode"] == 200
        mock_get_ddb.assert_not_called()

    @patch("monthly_push_handler.reset_monthly_push_count")
    @patch("monthly_push_handler.send_push")
    @patch("monthly_push_handler.get_dynamodb_service")
    def test_sends_monthly_report(self, mock_get_ddb, mock_send, mock_reset):
        ddb = MagicMock()
        ddb.query_by_gsi.return_value = [
            {
                "PK": "USER#U001",
                "SK": "PROFILE#",
                "status": "ACTIVE",
                "nickname": "テスト太郎",
                "reward_budget_monthly": 20000,
                "carryover_rate": 0.5,
            },
        ]
        ddb.get_item.side_effect = lambda pk, sk: {
            "PUSH_SETTINGS#": None,
            f"MONTHLY_SUMMARY#": {
                "total_amount": 15000,
                "total_budget": 20000,
            },
        }.get(sk)
        mock_get_ddb.return_value = ddb
        mock_send.return_value = True

        result = monthly_push_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        mock_send.assert_called_once()
        mock_reset.assert_called()

    @patch("monthly_push_handler.reset_monthly_push_count")
    @patch("monthly_push_handler.send_push")
    @patch("monthly_push_handler.get_dynamodb_service")
    def test_skips_monthly_report_disabled(self, mock_get_ddb, mock_send, mock_reset):
        ddb = MagicMock()
        ddb.query_by_gsi.return_value = [
            {
                "PK": "USER#U001",
                "SK": "PROFILE#",
                "status": "ACTIVE",
                "nickname": "テスト太郎",
                "reward_budget_monthly": 20000,
            },
        ]
        ddb.get_item.side_effect = lambda pk, sk: {
            "PUSH_SETTINGS#": {"monthly_report": False},
        }.get(sk)
        mock_get_ddb.return_value = ddb

        result = monthly_push_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        mock_send.assert_not_called()
        # push_count リセットは実行される
        mock_reset.assert_called_once()

    @patch("monthly_push_handler.get_dynamodb_service")
    def test_gsi_error(self, mock_get_ddb):
        ddb = MagicMock()
        ddb.query_by_gsi.side_effect = Exception("GSI error")
        mock_get_ddb.return_value = ddb

        result = monthly_push_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 500
