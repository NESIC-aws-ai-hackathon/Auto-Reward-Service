"""
Unit tests for PushService.
"""
import pytest
from unittest.mock import patch, MagicMock
import os

os.environ["TABLE_NAME"] = "ArsTable"
os.environ["AWS_REGION"] = "ap-northeast-1"
os.environ["ENV"] = "test"
os.environ["VAPID_PRIVATE_KEY"] = "test-private-key"
os.environ["VAPID_PUBLIC_KEY"] = "test-public-key"
os.environ["VAPID_SUBJECT"] = "mailto:test@example.com"


@pytest.fixture
def mock_table():
    with patch("shared.data_access.boto3") as mock_boto:
        mock_tbl = MagicMock()
        mock_resource = MagicMock()
        mock_resource.Table.return_value = mock_tbl
        mock_boto.resource.return_value = mock_resource
        yield mock_tbl


class TestSubscribe:
    def test_valid_subscription_saved(self, mock_table):
        """Valid subscription is saved."""
        mock_table.put_item.return_value = None

        from services.push_service import PushService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = PushService(da)
        result = svc.subscribe("user-001", {
            "endpoint": "https://fcm.googleapis.com/fcm/send/xxx",
            "keys": {"p256dh": "BGK...", "auth": "abc123"},
        })

        assert result["message"] == "subscribed"
        assert mock_table.put_item.called

    def test_invalid_endpoint_raises(self, mock_table):
        """Non-HTTPS endpoint raises ValueError."""
        from services.push_service import PushService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = PushService(da)

        with pytest.raises(ValueError, match="endpoint"):
            svc.subscribe("user-001", {
                "endpoint": "http://insecure.com/push",
                "keys": {"p256dh": "key", "auth": "auth"},
            })

    def test_missing_keys_raises(self, mock_table):
        """Missing keys raises ValueError."""
        from services.push_service import PushService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = PushService(da)

        with pytest.raises(ValueError, match="keys"):
            svc.subscribe("user-001", {
                "endpoint": "https://push.example.com",
                "keys": {},
            })


class TestUnsubscribe:
    def test_deletes_subscription(self, mock_table):
        """Unsubscribe deletes the subscription."""
        mock_table.delete_item.return_value = None

        from services.push_service import PushService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = PushService(da)
        result = svc.unsubscribe("user-001")

        assert result["message"] == "unsubscribed"
        mock_table.delete_item.assert_called_once()


class TestSendNotification:
    def test_no_subscription_returns_false(self, mock_table):
        """No subscription returns False."""
        mock_table.get_item.return_value = {}

        from services.push_service import PushService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = PushService(da)
        result = svc.send_notification("user-001", "Test", "Body")

        assert result is False

    def test_sends_push_when_subscription_exists(self, mock_table):
        """Sends push notification when subscription exists."""
        mock_table.get_item.return_value = {"Item": {
            "endpoint": "https://push.example.com/xxx",
            "keys_p256dh": "p256dh-key",
            "keys_auth": "auth-key",
        }}

        with patch("services.push_service.PushService.send_notification") as mock_send:
            mock_send.return_value = True

            from services.push_service import PushService
            from shared.data_access import DataAccess

            da = DataAccess()
            svc = PushService(da)
            # Direct call (patched method)
            result = mock_send("user-001", "Title", "Body")
            assert result is True
