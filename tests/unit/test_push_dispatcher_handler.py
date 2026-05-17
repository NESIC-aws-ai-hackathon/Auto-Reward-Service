"""
push_dispatcher_handler のユニットテスト
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

import pytest

import push_dispatcher_handler


class TestPushDispatcherHandler:
    @patch("push_dispatcher_handler.get_dynamodb_service")
    def test_warmup_returns_200(self, mock_get_ddb):
        result = push_dispatcher_handler.handler({"source": "warmup"}, None)
        assert result["statusCode"] == 200
        mock_get_ddb.assert_not_called()

    @patch("push_dispatcher_handler.send_push")
    @patch("push_dispatcher_handler.generate_daily_push")
    @patch("push_dispatcher_handler.get_dynamodb_service")
    def test_dispatches_pending_items(self, mock_get_ddb, mock_generate, mock_send):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [
            {
                "PK": "PUSH_QUEUE#2026-05-17",
                "SK": "USER#U001",
                "scheduled_at": "2026-05-17T10:30:00",
                "status": "pending",
            },
        ]
        mock_get_ddb.return_value = ddb
        mock_generate.return_value = {
            "type": "text",
            "text": "テスト",
            "category": "either_or",
            "template_id": "either_or:0",
        }
        mock_send.return_value = True

        result = push_dispatcher_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        assert "Sent: 1" in result["body"]
        mock_send.assert_called_once()

    @patch("push_dispatcher_handler.send_push")
    @patch("push_dispatcher_handler.generate_daily_push")
    @patch("push_dispatcher_handler.get_dynamodb_service")
    def test_skips_future_scheduled(self, mock_get_ddb, mock_generate, mock_send):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [
            {
                "PK": "PUSH_QUEUE#2026-05-17",
                "SK": "USER#U001",
                "scheduled_at": "9999-12-31T23:59:59",  # 未来
                "status": "pending",
            },
        ]
        mock_get_ddb.return_value = ddb

        result = push_dispatcher_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        mock_generate.assert_not_called()

    @patch("push_dispatcher_handler.generate_daily_push")
    @patch("push_dispatcher_handler.get_dynamodb_service")
    def test_skips_already_sent(self, mock_get_ddb, mock_generate):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [
            {
                "PK": "PUSH_QUEUE#2026-05-17",
                "SK": "USER#U001",
                "scheduled_at": "2026-05-17T10:30:00",
                "status": "sent",  # 既に送信済み
            },
        ]
        mock_get_ddb.return_value = ddb

        result = push_dispatcher_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        mock_generate.assert_not_called()

    @patch("push_dispatcher_handler.generate_daily_push")
    @patch("push_dispatcher_handler.get_dynamodb_service")
    def test_message_generation_failure(self, mock_get_ddb, mock_generate):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [
            {
                "PK": "PUSH_QUEUE#2026-05-17",
                "SK": "USER#U001",
                "scheduled_at": "2026-05-17T10:30:00",
                "status": "pending",
            },
        ]
        mock_get_ddb.return_value = ddb
        mock_generate.side_effect = Exception("Generation error")

        result = push_dispatcher_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        assert "Failed: 1" in result["body"]
        # status が "failed" に更新される
        ddb.update_item.assert_called()

    @patch("push_dispatcher_handler.generate_daily_push")
    @patch("push_dispatcher_handler.get_dynamodb_service")
    def test_generate_returns_none_skips(self, mock_get_ddb, mock_generate):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [
            {
                "PK": "PUSH_QUEUE#2026-05-17",
                "SK": "USER#U001",
                "scheduled_at": "2026-05-17T10:30:00",
                "status": "pending",
            },
        ]
        mock_get_ddb.return_value = ddb
        mock_generate.return_value = None

        result = push_dispatcher_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 200
        # status が "skipped" に更新される
        update_calls = ddb.update_item.call_args_list
        assert any("skipped" in str(c) for c in update_calls)

    @patch("push_dispatcher_handler.get_dynamodb_service")
    def test_query_failure(self, mock_get_ddb):
        ddb = MagicMock()
        ddb.query_by_pk.side_effect = Exception("DDB error")
        mock_get_ddb.return_value = ddb

        result = push_dispatcher_handler.handler({"source": "scheduler"}, None)

        assert result["statusCode"] == 500


class TestUpdateQueueStatus:
    def test_updates_status(self):
        ddb = MagicMock()
        push_dispatcher_handler._update_queue_status(
            ddb, "PUSH_QUEUE#2026-05-17", "USER#U001", "sent", "food_discovery"
        )
        ddb.update_item.assert_called_once()

    def test_handles_error_gracefully(self):
        ddb = MagicMock()
        ddb.update_item.side_effect = Exception("error")
        # Should not raise
        push_dispatcher_handler._update_queue_status(
            ddb, "PUSH_QUEUE#2026-05-17", "USER#U001", "failed"
        )
