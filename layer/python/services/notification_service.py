"""
ふれまーるちゃん通知サービス

変更依頼書_2 §3 準拠 — PWA通知の作成・管理
LINE PUSH は廃止し、PWA通知 + LINE会話連携に置き換え
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from services.dynamodb_service import DynamoDBService
from models.schemas import SK_PREFIX_NOTIFICATION
from utils.logger import get_logger

logger = get_logger(__name__)


def create_notification(
    user_id: str,
    ddb: DynamoDBService,
    *,
    notification_type: str,
    title: str,
    message_text: str,
    recommendation_id: Optional[str] = None,
    expires_hours: int = 72,
) -> dict:
    """
    通知レコードを作成する。

    Args:
        notification_type: RECOMMENDATION | CART_ADDED | LOCATION_RECOMMENDATION |
                          MONTHLY_REMAINING | SYSTEM | LOGIN_REQUIRED | PURCHASE_READY
    """
    pk = f"USER#{user_id}"
    notification_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=expires_hours)).isoformat()
    sk = f"{SK_PREFIX_NOTIFICATION}{notification_id}"

    data = {
        "notification_id": notification_id,
        "user_id": user_id,
        "recommendation_id": recommendation_id,
        "type": notification_type,
        "title": title,
        "message_text": message_text,
        "status": "CREATED",
        "createdAt": now.isoformat(),
        "expires_at": expires_at,
    }

    ddb.put_item(pk, sk, data)

    logger.info(
        "notification_created",
        notification_id=notification_id,
        type=notification_type,
        user_id=user_id,
    )

    return data


def get_notifications(
    user_id: str,
    ddb: DynamoDBService,
    *,
    limit: int = 20,
) -> list[dict]:
    """ユーザーの通知一覧を取得（新しい順）"""
    pk = f"USER#{user_id}"
    items = ddb.query_begins_with(pk=pk, sk_prefix=SK_PREFIX_NOTIFICATION)

    # 期限切れを除外
    now = datetime.now(timezone.utc).isoformat()
    valid = [
        i for i in items
        if not i.get("expires_at") or i.get("expires_at", "") > now
    ]

    # 新しい順
    valid.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return valid[:limit]


def get_latest_actionable_notification(
    user_id: str,
    ddb: DynamoDBService,
) -> Optional[dict]:
    """
    最新のアクション可能な通知を取得する。
    LINE「ふれまーるちゃんと話す」で会話開始時に使用。
    """
    notifications = get_notifications(user_id, ddb)

    actionable_types = {
        "RECOMMENDATION",
        "CART_ADDED",
        "LOCATION_RECOMMENDATION",
        "LOGIN_REQUIRED",
        "PURCHASE_READY",
    }
    actionable_statuses = {"CREATED", "SENT"}

    for notif in notifications:
        if (
            notif.get("type") in actionable_types
            and notif.get("status") in actionable_statuses
        ):
            return notif

    return None


def mark_notification_opened(
    user_id: str,
    notification_id: str,
    ddb: DynamoDBService,
) -> None:
    """通知を開封済みにする"""
    pk = f"USER#{user_id}"
    sk = f"{SK_PREFIX_NOTIFICATION}{notification_id}"
    ddb.update_item(pk, sk, {"status": "OPENED"})


def create_cart_added_notification(
    user_id: str,
    ddb: DynamoDBService,
    *,
    product_title: str,
    reason_text: str,
    recommendation_id: str,
) -> dict:
    """カート投入成功通知を作成"""
    message = (
        f"ほしい物リストで熟成していた {product_title}、\n"
        f"今のあなたにちょうどよさそうだったから、\n"
        f"買い物かごに入れておいたよ～！\n\n"
        f"{reason_text}\n\n"
        f"買うって言ったら買っちゃうけど、どうする？"
    )

    return create_notification(
        user_id,
        ddb,
        notification_type="CART_ADDED",
        title=f"🛒 {product_title} をカートに入れたよ",
        message_text=message,
        recommendation_id=recommendation_id,
    )


def create_login_required_notification(
    user_id: str,
    ddb: DynamoDBService,
    *,
    recommendation_id: str,
) -> dict:
    """ログイン要求通知を作成"""
    message = (
        "Amazonに入るところだけ、あなたの手が必要です。\n\n"
        "パスワードや認証コードは、ふれまーるちゃんには教えなくて大丈夫だよ。\n"
        "ログインできたら、買い物かごまで運ぶね。"
    )

    return create_notification(
        user_id,
        ddb,
        notification_type="LOGIN_REQUIRED",
        title="🔑 Amazonログインが必要です",
        message_text=message,
        recommendation_id=recommendation_id,
    )
