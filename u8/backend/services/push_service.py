"""
PushService - Web Push notification management.
Uses pywebpush for VAPID-based push notifications.
"""
import json
from shared.data_access import DataAccess, SK_PUSH_SUBSCRIPTION
from shared.config import get_config


class PushService:
    def __init__(self, da: DataAccess = None):
        self.da = da or DataAccess()
        self.config = get_config()

    def subscribe(self, user_id: str, subscription: dict) -> dict:
        """Save a push subscription for the user."""
        endpoint = subscription.get("endpoint", "")
        keys = subscription.get("keys", {})

        if not endpoint or not endpoint.startswith("https://"):
            raise ValueError("endpoint must be a valid HTTPS URL")
        if not keys.get("p256dh") or not keys.get("auth"):
            raise ValueError("keys.p256dh and keys.auth are required")

        self.da.put_item(f"USER#{user_id}", SK_PUSH_SUBSCRIPTION, {
            "endpoint": endpoint,
            "keys_p256dh": keys["p256dh"],
            "keys_auth": keys["auth"],
            "subscribed_at": self._now(),
        })

        return {"message": "subscribed"}

    def unsubscribe(self, user_id: str) -> dict:
        """Remove push subscription for the user."""
        self.da.delete_item(f"USER#{user_id}", SK_PUSH_SUBSCRIPTION)
        return {"message": "unsubscribed"}

    def send_notification(self, user_id: str, title: str, body: str) -> bool:
        """Send a push notification to the user. Returns True if successful."""
        sub = self.da.get_item(f"USER#{user_id}", SK_PUSH_SUBSCRIPTION)
        if not sub:
            return False

        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": {
                "p256dh": sub["keys_p256dh"],
                "auth": sub["keys_auth"],
            },
        }

        vapid_private_key = self.config.get("vapid_private_key", "")
        vapid_subject = self.config.get("vapid_subject", "mailto:admin@example.com")

        if not vapid_private_key:
            return False

        try:
            from pywebpush import webpush, WebPushException

            webpush(
                subscription_info=subscription_info,
                data=json.dumps({"title": title, "body": body}, ensure_ascii=False),
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": vapid_subject},
            )
            return True

        except Exception as e:
            # 410 Gone = subscription expired, delete it
            if "410" in str(e):
                self.da.delete_item(f"USER#{user_id}", SK_PUSH_SUBSCRIPTION)
            return False

    def _now(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
