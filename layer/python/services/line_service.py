"""
LINE サービス — line-bot-sdk v3 の薄いラッパー

設計方針:
- 公開メソッドは 4 つのみ（verify_signature / reply_message / push_message / get_message_content）
- reply_message / push_message は冪等性なし → リトライなし・失敗時は即 LineServiceError
- user_id は PII — ログに出力しない
"""
from __future__ import annotations

import hashlib
import hmac
import base64
import os
from typing import Optional

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexMessage,
    MessagingApi,
    MessagingApiBlob,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)

from utils.exceptions import LineServiceError
from utils.logger import get_logger
from utils.secrets import get_line_secrets

logger = get_logger(__name__)


class LineService:
    """LINE Messaging API の薄いラッパー"""

    def __init__(self, channel_secret: str, channel_access_token: str) -> None:
        self._channel_secret = channel_secret
        configuration = Configuration(access_token=channel_access_token)
        self._api_client = ApiClient(configuration)
        self._api = MessagingApi(self._api_client)
        self._blob_api = MessagingApiBlob(self._api_client)

    # ─────────────────────────────────────────
    # 公開メソッド（4つのみ）
    # ─────────────────────────────────────────

    def verify_signature(self, body: str, signature: str) -> bool:
        """
        X-Line-Signature を検証する

        Args:
            body: リクエストボディ（文字列）
            signature: X-Line-Signature ヘッダーの値

        Returns:
            True: 検証成功 / False: 検証失敗
        """
        channel_secret_bytes = self._channel_secret.encode("utf-8")
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body
        digest = hmac.new(channel_secret_bytes, body_bytes, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def reply_message(self, reply_token: str, messages: list[dict]) -> None:
        """
        Reply API でメッセージを送信する（最大 5 メッセージ）

        Args:
            reply_token: LINE Reply Token
            messages: メッセージ dict のリスト

        Raises:
            LineServiceError: 送信失敗時（リトライなし）
        """
        line_messages = [self._dict_to_message(m) for m in messages]
        request = ReplyMessageRequest(
            reply_token=reply_token, messages=line_messages
        )
        try:
            self._api.reply_message(reply_message_request=request)
            logger.info("reply_message success", message_count=len(messages))
        except Exception as e:
            raise LineServiceError(f"reply_message 失敗: {e}", e) from e

    def push_message(self, user_id: str, messages: list[dict]) -> None:
        """
        Push API でメッセージを送信する

        Args:
            user_id: LINE ユーザー ID（PII — ログ禁止）
            messages: メッセージ dict のリスト

        Raises:
            LineServiceError: 送信失敗時（リトライなし）
        """
        line_messages = [self._dict_to_message(m) for m in messages]
        request = PushMessageRequest(to=user_id, messages=line_messages)
        try:
            self._api.push_message(push_message_request=request)
            logger.info("push_message success", message_count=len(messages))
        except Exception as e:
            raise LineServiceError(f"push_message 失敗: {e}", e) from e

    def get_message_content(self, message_id: str) -> bytes:
        """
        メッセージコンテンツ（画像等）を取得する

        Args:
            message_id: LINE メッセージ ID

        Returns:
            コンテンツのバイナリデータ

        Raises:
            LineServiceError: 取得失敗時
        """
        try:
            response = self._blob_api.get_message_content(message_id=message_id)
            # LINE Bot SDK v3 は bytearray を直接返す（.read() 不要）
            return bytes(response)
        except Exception as e:
            raise LineServiceError(f"get_message_content 失敗: {e}", e) from e

    # ─────────────────────────────────────────
    # 内部メソッド
    # ─────────────────────────────────────────

    def _dict_to_message(self, msg: dict):
        """
        dict 形式のメッセージを LINE SDK のメッセージオブジェクトに変換する

        対応形式:
          {"type": "text", "text": "メッセージ本文"}
          {"type": "flex", "altText": "代替テキスト", "contents": {...}}
        """
        msg_type = msg.get("type", "text")
        if msg_type == "text":
            return TextMessage(type="text", text=msg["text"])
        elif msg_type == "flex":
            return FlexMessage(
                type="flex",
                alt_text=msg.get("altText", ""),
                contents=msg["contents"],
            )
        else:
            raise LineServiceError(f"未対応のメッセージタイプ: {msg_type}")


# ─────────────────────────────────────────
# モジュールレベルシングルトン
# ─────────────────────────────────────────
_instance: Optional[LineService] = None


def get_line_service() -> LineService:
    """LineService シングルトンを返す（コールドスタート時に Secrets を取得・キャッシュ）"""
    global _instance
    if _instance is None:
        secrets = get_line_secrets()
        _instance = LineService(
            channel_secret=secrets["LINE_CHANNEL_SECRET"],
            channel_access_token=secrets["LINE_ACCESS_TOKEN"],
        )
    return _instance
