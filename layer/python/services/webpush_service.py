"""
Web Push 通知サービス

要件整理.md §7 準拠:
- VAPID キーは Secrets Manager (`ars/webpush`) で管理
- PushSubscription は DynamoDB `WEB_PUSH_SUBSCRIPTION#{endpointHash}` に保存
- pywebpush で実配信

VAPID 構造 (Secrets Manager):
{
  "private_pem": "...",
  "public_b64url": "BJ6_...",
  "subject": "mailto:..."
}

PushSubscription DB 構造:
{
  "PK": "USER#{userId}",
  "SK": "WEB_PUSH_SUBSCRIPTION#{endpointHash}",
  "endpoint": "...",
  "keys": {"p256dh": "...", "auth": "..."},
  "userAgent": "...",
  "enabled": true,
  "created_at": "...",
  "updated_at": "..."
}
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from services.dynamodb_service import DynamoDBService
from utils.logger import get_logger

logger = get_logger(__name__)

# モジュールレベルキャッシュ
_vapid_cache: Optional[dict] = None
_secrets_client = None

VAPID_SECRET_ID = os.environ.get("VAPID_SECRET_ID", "ars/webpush")
SK_PREFIX = "WEB_PUSH_SUBSCRIPTION#"


def _get_secrets_client():
    global _secrets_client
    if _secrets_client is None:
        _secrets_client = boto3.client("secretsmanager")
    return _secrets_client


def get_vapid_config() -> dict:
    """Secrets Manager から VAPID 設定を取得（キャッシュあり）。

    Returns:
        {"private_pem": str, "public_b64url": str, "subject": str}
    """
    global _vapid_cache
    if _vapid_cache is not None:
        return _vapid_cache

    try:
        resp = _get_secrets_client().get_secret_value(SecretId=VAPID_SECRET_ID)
        _vapid_cache = json.loads(resp.get("SecretString", "{}"))
        return _vapid_cache
    except Exception as e:
        logger.error("vapid_config_fetch_failed", error=str(e))
        # フォールバック: 環境変数
        return {
            "private_pem": os.environ.get("VAPID_PRIVATE_PEM", ""),
            "public_b64url": os.environ.get("VAPID_PUBLIC_KEY", ""),
            "subject": os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com"),
        }


def get_public_key() -> str:
    """ブラウザ用 applicationServerKey (base64URL) を返す。"""
    config = get_vapid_config()
    return config.get("public_b64url", "")


def _endpoint_hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:16]


def save_subscription(
    user_id: str,
    subscription: dict,
    ddb: DynamoDBService,
    user_agent: str = "",
) -> str:
    """PushSubscription を DynamoDB に保存する。

    Args:
        subscription: {"endpoint": str, "keys": {"p256dh": str, "auth": str}}

    Returns:
        保存した SK
    """
    endpoint = subscription.get("endpoint", "")
    keys = subscription.get("keys", {})
    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        raise ValueError("invalid_subscription")

    sk = f"{SK_PREFIX}{_endpoint_hash(endpoint)}"
    now = datetime.now(timezone.utc).isoformat()
    pk = f"USER#{user_id}"

    existing = ddb.get_item(pk=pk, sk=sk)
    item = {
        "entityType": "WEB_PUSH_SUBSCRIPTION",
        "endpoint": endpoint,
        "keys": keys,
        "userAgent": user_agent[:200],
        "enabled": True,
        "created_at": (existing or {}).get("created_at", now),
        "updated_at": now,
    }
    ddb.put_item(pk, sk, item)
    logger.info("webpush_subscription_saved", user_id=user_id, endpoint_hash=_endpoint_hash(endpoint))
    return sk


def delete_subscription(user_id: str, endpoint: str, ddb: DynamoDBService) -> bool:
    """PushSubscription を削除する。"""
    pk = f"USER#{user_id}"
    sk = f"{SK_PREFIX}{_endpoint_hash(endpoint)}"
    try:
        ddb.delete_item(pk, sk)
        return True
    except Exception as e:
        logger.warning("webpush_delete_failed", error=str(e))
        return False


def list_subscriptions(user_id: str, ddb: DynamoDBService) -> list[dict]:
    """ユーザーの全 PushSubscription を取得する。"""
    pk = f"USER#{user_id}"
    items = ddb.query_by_pk(pk, sk_prefix=SK_PREFIX)
    return [i for i in items if i.get("enabled", True)]


def send_webpush(
    user_id: str,
    payload: dict,
    ddb: DynamoDBService,
    *,
    ttl_seconds: int = 86400,
) -> dict:
    """ユーザーの全有効 Subscription に Web Push を送信する。

    Args:
        payload: {"title": str, "body": str, "url": Optional[str], ...}

    Returns:
        {"sent": int, "failed": int, "details": [...]}
    """
    subs = list_subscriptions(user_id, ddb)
    if not subs:
        logger.info("webpush_no_subscriptions", user_id=user_id)
        return {"sent": 0, "failed": 0, "details": []}

    config = get_vapid_config()
    private_pem = config.get("private_pem", "")
    subject = config.get("subject", "mailto:admin@example.com")

    if not private_pem:
        logger.error("webpush_no_vapid_key")
        return {"sent": 0, "failed": len(subs), "details": [{"error": "no_vapid_key"}]}

    # PEM → DER → raw 32-byte private number (base64url)
    # py_vapid.from_string() は PEM を扱えないので変換が必要
    try:
        from cryptography.hazmat.primitives import serialization as _ser
        _key_obj = _ser.load_pem_private_key(private_pem.encode("utf-8"), password=None)
        _private_numbers = _key_obj.private_numbers()
        _raw_bytes = _private_numbers.private_value.to_bytes(32, byteorder="big")
        vapid_private_key_b64 = base64.urlsafe_b64encode(_raw_bytes).rstrip(b"=").decode("ascii")
    except Exception as e:
        logger.error("vapid_key_conversion_failed", error=str(e))
        return {"sent": 0, "failed": len(subs), "details": [{"error": "key_conversion_failed"}]}

    # 遅延 import (cold start 軽減 + ライブラリ依存をハンドラ層に閉じる)
    try:
        from pywebpush import webpush, WebPushException
    except Exception as e:
        logger.error("pywebpush_import_failed", error=str(e))
        return {"sent": 0, "failed": len(subs), "details": [{"error": "import_failed"}]}

    body_str = json.dumps(payload, ensure_ascii=False)
    vapid_claims = {"sub": subject}

    sent = 0
    failed = 0
    details = []

    for sub in subs:
        endpoint = sub.get("endpoint", "")
        keys = sub.get("keys", {})
        subscription_info = {"endpoint": endpoint, "keys": keys}
        try:
            webpush(
                subscription_info=subscription_info,
                data=body_str,
                vapid_private_key=vapid_private_key_b64,
                vapid_claims=dict(vapid_claims),
                ttl=ttl_seconds,
            )
            sent += 1
            details.append({"endpoint_hash": _endpoint_hash(endpoint), "status": "sent"})
            logger.info("webpush_sent", user_id=user_id, endpoint_hash=_endpoint_hash(endpoint))
        except WebPushException as e:
            failed += 1
            status_code = getattr(e.response, "status_code", None) if e.response is not None else None
            details.append({
                "endpoint_hash": _endpoint_hash(endpoint),
                "status": "failed",
                "code": status_code,
                "error": str(e)[:200],
            })
            logger.warning("webpush_failed", user_id=user_id, code=status_code, error=str(e)[:200])
            # 410 Gone / 404 → subscription 削除
            if status_code in (404, 410):
                try:
                    delete_subscription(user_id, endpoint, ddb)
                except Exception:
                    pass
        except Exception as e:
            failed += 1
            details.append({"endpoint_hash": _endpoint_hash(endpoint), "status": "failed", "error": str(e)[:200]})
            logger.warning("webpush_send_exception", error=str(e)[:200])

    return {"sent": sent, "failed": failed, "details": details}
