"""
Google Calendar サービス — OAuth 2.0 token 管理 + イベント取得

設計方針 (SEC-08, SEC-09):
- access_token は毎回 refresh_token から取得（キャッシュしない）
- refresh_token は DynamoDB GOOGLE_OAUTH# SK に保管（KMS 暗号化）
- カレンダーイベントのタイトル/内容はログ・DynamoDB に一切保存しない
- 非連携ユーザーへの呼び出しは空リストを返す（エラーにしない）
- Google Calendar API: 固定インターバルリトライ（1秒, 最大 2 回）
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from services.dynamodb_service import get_dynamodb_service
from utils.exceptions import GoogleCalendarError
from utils.logger import get_logger
from utils.secrets import get_google_secrets

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_CALENDAR_URL = (
    "https://www.googleapis.com/calendar/v3/calendars/primary/events"
)
_GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

_SK_GOOGLE_OAUTH = "GOOGLE_OAUTH#"

_RETRY_COUNT = 2
_RETRY_DELAY = 1.0  # 秒（固定）
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_JST = timezone(timedelta(hours=9))


class GoogleCalendarService:
    """Google Calendar OAuth + イベント取得サービス"""

    # ─────────────────────────────────────────
    # 公開メソッド
    # ─────────────────────────────────────────

    def is_connected(self, user_id: str) -> bool:
        """
        ユーザーが Google Calendar と連携済みかを確認する

        Args:
            user_id: LINE ユーザー ID（PII）

        Returns:
            True: 連携済み / False: 未連携
        """
        pk = f"USER#{user_id}"
        item = get_dynamodb_service().get_item(pk=pk, sk=_SK_GOOGLE_OAUTH)
        return item is not None

    def save_refresh_token(
        self,
        user_id: str,
        refresh_token: str,
        email_hint: str = None,
    ) -> None:
        """
        refresh_token を DynamoDB に保存する

        Args:
            user_id: LINE ユーザー ID（PII）
            refresh_token: Google OAuth refresh_token（PII）
            email_hint: マスク済みメール表示用（例: "u***@gmail.com"）
        """
        pk = f"USER#{user_id}"
        now = datetime.now(_JST).isoformat()
        item = {
            "PK": pk,
            "SK": _SK_GOOGLE_OAUTH,
            "refresh_token": refresh_token,  # DynamoDB SSE で暗号化
            "scope": "calendar.events.readonly",
            "connected_at": now,
            "updated_at": now,
        }
        if email_hint:
            item["email_hint"] = email_hint

        get_dynamodb_service().put_item(pk=pk, sk=_SK_GOOGLE_OAUTH, item=item)
        logger.info("Google Calendar 連携を保存しました")

    def revoke_and_delete(self, user_id: str) -> None:
        """
        Google に revoke を送信し、DynamoDB から削除する

        Args:
            user_id: LINE ユーザー ID（PII）
        """
        refresh_token = self._get_refresh_token(user_id)
        if refresh_token:
            try:
                requests.post(
                    _GOOGLE_REVOKE_URL,
                    params={"token": refresh_token},
                    timeout=10,
                )
                logger.info("Google OAuth revoke 送信完了")
            except Exception as e:
                logger.warning("Google OAuth revoke 失敗（削除は継続）", error=str(e))

        pk = f"USER#{user_id}"
        get_dynamodb_service().delete_item(pk=pk, sk=_SK_GOOGLE_OAUTH)
        logger.info("Google Calendar 連携を削除しました")

    def get_today_events(self, user_id: str) -> list[dict]:
        """
        今日と明日のカレンダーイベントを取得する

        非連携ユーザーの場合は空リストを返す。
        イベント内容はログ・DynamoDB に保存しない (SEC-08)。

        Args:
            user_id: LINE ユーザー ID（PII）

        Returns:
            イベントリスト（内容はログ禁止）

        Raises:
            GoogleCalendarError: API 呼び出し失敗時
        """
        if not self.is_connected(user_id):
            logger.info("Google Calendar 未連携のためスキップ")
            return []

        refresh_token = self._get_refresh_token(user_id)
        if not refresh_token:
            logger.warning("refresh_token が取得できませんでした")
            return []

        access_token = self._refresh_access_token(refresh_token)

        now_jst = datetime.now(_JST)
        time_min = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
        time_max = time_min + timedelta(days=2)

        params = {
            "timeMin": time_min.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "timeMax": time_max.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "maxResults": 20,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        response = self._request_with_retry(
            _GOOGLE_CALENDAR_URL, headers=headers, params=params
        )
        response.raise_for_status()
        data = response.json()
        events = data.get("items", [])

        # イベント件数のみログ（内容は禁止）
        logger.info("カレンダーイベント取得完了", event_count=len(events))
        return events

    def _build_calendar_context(self, events: list[dict]) -> str:
        """
        イベントリストを Bedrock プロンプト用の自然言語コンテキストに変換する

        イベントのタイトル・詳細はログ禁止 (SEC-08)。
        「今日 3 件の予定あり、明日は予定なし」のような件数・時間帯情報のみを返す。

        Args:
            events: get_today_events() の戻り値

        Returns:
            自然言語コンテキスト文字列（Bedrock プロンプトに埋め込む用）
        """
        if not events:
            return "今日・明日の予定はありません。"

        now_jst = datetime.now(_JST)
        today_str = now_jst.strftime("%Y-%m-%d")
        tomorrow_str = (now_jst + timedelta(days=1)).strftime("%Y-%m-%d")

        today_count = 0
        tomorrow_count = 0

        for event in events:
            start = event.get("start", {})
            start_date = start.get("dateTime", start.get("date", ""))[:10]
            if start_date == today_str:
                today_count += 1
            elif start_date == tomorrow_str:
                tomorrow_count += 1

        parts: list[str] = []
        if today_count > 0:
            parts.append(f"今日は {today_count} 件の予定があります")
        else:
            parts.append("今日は予定がありません")

        if tomorrow_count > 0:
            parts.append(f"明日は {tomorrow_count} 件の予定があります")
        else:
            parts.append("明日は予定がありません")

        return "。".join(parts) + "。"

    # ─────────────────────────────────────────
    # 内部メソッド
    # ─────────────────────────────────────────

    def _get_refresh_token(self, user_id: str) -> Optional[str]:
        """DynamoDB から refresh_token を取得する"""
        pk = f"USER#{user_id}"
        item = get_dynamodb_service().get_item(pk=pk, sk=_SK_GOOGLE_OAUTH)
        if not item:
            return None
        return item.get("refresh_token")

    def _refresh_access_token(self, refresh_token: str) -> str:
        """
        Google OAuth token endpoint へリフレッシュ要求を送り access_token を返す

        毎回リフレッシュ（access_token はキャッシュしない）(SEC-09)

        Raises:
            GoogleCalendarError: リフレッシュ失敗時
        """
        secrets = get_google_secrets()
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": secrets["GOOGLE_CLIENT_ID"],
            "client_secret": secrets["GOOGLE_CLIENT_SECRET"],
        }

        try:
            response = requests.post(_GOOGLE_TOKEN_URL, data=data, timeout=10)
            if response.status_code != 200:
                raise GoogleCalendarError(
                    f"access_token リフレッシュ失敗: HTTP {response.status_code}"
                )
            token_data = response.json()
            return token_data["access_token"]
        except GoogleCalendarError:
            raise
        except Exception as e:
            raise GoogleCalendarError(
                f"access_token リフレッシュ中に例外が発生: {e}", e
            ) from e

    def _request_with_retry(
        self,
        url: str,
        headers: dict,
        params: dict,
    ) -> requests.Response:
        """
        固定インターバルリトライ付き GET リクエスト（最大 2 回）

        リトライ対象: HTTP 429 / 5xx
        """
        last_response: Optional[requests.Response] = None

        for attempt in range(_RETRY_COUNT + 1):
            try:
                response = requests.get(
                    url, headers=headers, params=params, timeout=10
                )
                if response.status_code not in _RETRYABLE_STATUS:
                    return response
                last_response = response
                logger.warning(
                    "Google Calendar API リトライ",
                    attempt=attempt + 1,
                    status=response.status_code,
                )
                if attempt < _RETRY_COUNT:
                    time.sleep(_RETRY_DELAY)
            except requests.exceptions.RequestException as e:
                raise GoogleCalendarError(
                    f"Google Calendar API リクエスト例外: {e}", e
                ) from e

        raise GoogleCalendarError(
            f"Google Calendar API リトライ上限到達 (status={last_response.status_code if last_response else 'N/A'})"
        )


# ─────────────────────────────────────────
# モジュールレベルシングルトン
# ─────────────────────────────────────────
_instance: Optional[GoogleCalendarService] = None


def get_google_calendar_service() -> GoogleCalendarService:
    """GoogleCalendarService シングルトンを返す"""
    global _instance
    if _instance is None:
        _instance = GoogleCalendarService()
    return _instance
