"""google_calendar_service.py のユニットテスト"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.google_calendar_service import GoogleCalendarService
from utils.exceptions import GoogleCalendarError


@pytest.fixture
def svc():
    return GoogleCalendarService()


class TestIsConnected:
    def test_connected(self, svc):
        with patch("services.google_calendar_service.get_dynamodb_service") as mock_ddb:
            mock_ddb.return_value.get_item.return_value = {
                "PK": "USER#U001",
                "SK": "GOOGLE_OAUTH#",
                "refresh_token": "token",
            }
            assert svc.is_connected("U001") is True

    def test_not_connected(self, svc):
        with patch("services.google_calendar_service.get_dynamodb_service") as mock_ddb:
            mock_ddb.return_value.get_item.return_value = None
            assert svc.is_connected("U001") is False


class TestGetTodayEvents:
    def test_not_connected_returns_empty(self, svc):
        with patch.object(svc, "is_connected", return_value=False):
            result = svc.get_today_events("U001")
        assert result == []

    def test_no_refresh_token_returns_empty(self, svc):
        with patch.object(svc, "is_connected", return_value=True):
            with patch.object(svc, "_get_refresh_token", return_value=None):
                result = svc.get_today_events("U001")
        assert result == []

    def test_success(self, svc):
        events = [
            {"summary": "会議", "start": {"dateTime": "2026-05-16T10:00:00+09:00"}}
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": events}
        mock_response.raise_for_status = MagicMock()

        with patch.object(svc, "is_connected", return_value=True):
            with patch.object(svc, "_get_refresh_token", return_value="refresh"):
                with patch.object(svc, "_refresh_access_token", return_value="access"):
                    with patch.object(svc, "_request_with_retry", return_value=mock_response):
                        result = svc.get_today_events("U001")

        assert len(result) == 1


class TestBuildCalendarContext:
    def test_empty_events(self, svc):
        result = svc._build_calendar_context([])
        assert "今日・明日の予定はありません" in result

    def test_counts_today_and_tomorrow(self, svc):
        _JST = timezone(timedelta(hours=9))
        now = datetime.now(_JST)
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        events = [
            {"start": {"dateTime": f"{today_str}T10:00:00+09:00"}},
            {"start": {"dateTime": f"{today_str}T14:00:00+09:00"}},
            {"start": {"date": tomorrow_str}},
        ]
        result = svc._build_calendar_context(events)
        assert "今日は 2 件" in result
        assert "明日は 1 件" in result


class TestRefreshAccessToken:
    def test_success(self, svc):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new_access_token"}

        with patch("services.google_calendar_service.requests.post", return_value=mock_response):
            with patch("services.google_calendar_service.get_google_secrets") as mock_secrets:
                mock_secrets.return_value = {
                    "GOOGLE_CLIENT_ID": "client_id",
                    "GOOGLE_CLIENT_SECRET": "client_secret",
                }
                result = svc._refresh_access_token("refresh_token")

        assert result == "new_access_token"

    def test_failure_raises(self, svc):
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("services.google_calendar_service.requests.post", return_value=mock_response):
            with patch("services.google_calendar_service.get_google_secrets") as mock_secrets:
                mock_secrets.return_value = {
                    "GOOGLE_CLIENT_ID": "id",
                    "GOOGLE_CLIENT_SECRET": "secret",
                }
                with pytest.raises(GoogleCalendarError):
                    svc._refresh_access_token("bad_token")


class TestRequestWithRetry:
    def test_retries_on_429(self, svc):
        r429 = MagicMock()
        r429.status_code = 429
        r200 = MagicMock()
        r200.status_code = 200

        with patch("services.google_calendar_service.requests.get", side_effect=[r429, r200]):
            with patch("services.google_calendar_service.time.sleep"):
                result = svc._request_with_retry("http://test", {}, {})
        assert result.status_code == 200

    def test_raises_after_max_retries(self, svc):
        r500 = MagicMock()
        r500.status_code = 500

        with patch("services.google_calendar_service.requests.get", return_value=r500):
            with patch("services.google_calendar_service.time.sleep"):
                with pytest.raises(GoogleCalendarError):
                    svc._request_with_retry("http://test", {}, {})
