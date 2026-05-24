"""
Unit tests for api_handler Lambda function.
Tests patch resolve_user_from_event and da at the handler module level.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

# Patch environment before import
import os
os.environ["TABLE_NAME"] = "ArsTable"
os.environ["AWS_REGION"] = "ap-northeast-1"
os.environ["ENV"] = "test"
os.environ["COGNITO_USER_POOL_ID"] = "ap-northeast-1_TestPool"
os.environ["COGNITO_CLIENT_ID"] = "test-client-id"


@pytest.fixture(autouse=True)
def mock_deps():
    """Patch the module-level da and resolve_user_from_event."""
    with patch("shared.data_access.boto3"):
        mock_da = MagicMock()
        mock_resolve = MagicMock()

        with patch("handlers.api_handler.da", mock_da), \
             patch("handlers.api_handler.resolve_user_from_event", mock_resolve):
            # Default: auth succeeds with user-123
            mock_resolve.return_value = ("user-123", None)
            yield {"da": mock_da, "resolve": mock_resolve}


@pytest.fixture
def make_event():
    """Factory for API Gateway HTTP API events."""
    def _make(method: str, path: str, body: dict | None = None, sub: str = "test-sub-123"):
        event = {
            "requestContext": {
                "http": {
                    "method": method,
                    "path": path,
                },
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": sub,
                        }
                    }
                }
            },
            "body": json.dumps(body) if body else None,
        }
        return event
    return _make


class TestGetSettings:
    def test_returns_defaults_for_new_user(self, make_event, mock_deps):
        """New user gets default settings."""
        mock_deps["da"].get_or_create_profile.return_value = {
            "display_name": "",
            "diary_time": "22:00",
            "notification_enabled": True,
            "monthly_surplus": 0,
        }

        from handlers.api_handler import lambda_handler

        event = make_event("GET", "/api/settings")
        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["diary_time"] == "22:00"
        assert body["notification_enabled"] is True
        assert body["monthly_surplus"] == 0

    def test_returns_existing_settings(self, make_event, mock_deps):
        """Returns stored settings for existing user."""
        mock_deps["da"].get_or_create_profile.return_value = {
            "display_name": "テスト太郎",
            "diary_time": "21:00",
            "notification_enabled": False,
            "monthly_surplus": 5000,
        }

        from handlers.api_handler import lambda_handler

        event = make_event("GET", "/api/settings")
        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["display_name"] == "テスト太郎"
        assert body["diary_time"] == "21:00"
        assert body["notification_enabled"] is False
        assert body["monthly_surplus"] == 5000


class TestPutSettings:
    def test_update_valid_settings(self, make_event, mock_deps):
        """Valid settings update returns success."""
        mock_deps["da"].update_profile.return_value = None

        from handlers.api_handler import lambda_handler

        event = make_event("PUT", "/api/settings", {
            "display_name": "新しい名前",
            "diary_time": "23:00",
        })
        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "display_name" in body["updated_fields"]
        assert "diary_time" in body["updated_fields"]

    def test_invalid_diary_time_format(self, make_event, mock_deps):
        """Invalid time format returns 400."""
        from handlers.api_handler import lambda_handler

        event = make_event("PUT", "/api/settings", {
            "diary_time": "25:00",
        })
        response = lambda_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"] == "validation_error"

    def test_invalid_monthly_surplus(self, make_event, mock_deps):
        """Negative or too-large monthly surplus returns 400."""
        from handlers.api_handler import lambda_handler

        event = make_event("PUT", "/api/settings", {
            "monthly_surplus": -1,
        })
        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    def test_display_name_too_long(self, make_event, mock_deps):
        """Display name > 30 chars returns 400."""
        from handlers.api_handler import lambda_handler

        event = make_event("PUT", "/api/settings", {
            "display_name": "あ" * 31,
        })
        response = lambda_handler(event, None)

        assert response["statusCode"] == 400

    def test_empty_body_returns_success(self, make_event, mock_deps):
        """Empty body means no update - returns success with empty list."""
        from handlers.api_handler import lambda_handler

        event = make_event("PUT", "/api/settings", {})
        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["updated_fields"] == []

    def test_ignores_unknown_fields(self, make_event, mock_deps):
        """Unknown fields in body are silently ignored."""
        mock_deps["da"].update_profile.return_value = None

        from handlers.api_handler import lambda_handler

        event = make_event("PUT", "/api/settings", {
            "display_name": "OK名前",
            "hacker_field": "should_be_ignored",
        })
        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "hacker_field" not in body["updated_fields"]
        assert "display_name" in body["updated_fields"]


class TestGetUser:
    def test_returns_user_info(self, make_event, mock_deps):
        """GET /api/user/me returns user_id and display_name."""
        mock_deps["resolve"].return_value = ("user-456", None)
        mock_deps["da"].get_or_create_profile.return_value = {
            "display_name": "花子",
        }

        from handlers.api_handler import lambda_handler

        event = make_event("GET", "/api/user/me")
        response = lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user_id"] == "user-456"
        assert body["display_name"] == "花子"


class TestAuth:
    def test_missing_sub_returns_401(self, make_event, mock_deps):
        """Missing JWT sub claim returns 401."""
        # Simulate auth failure
        mock_deps["resolve"].return_value = (None, {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"},
            "body": json.dumps({"error": "unauthorized", "message": "Missing authentication"}),
        })

        from handlers.api_handler import lambda_handler

        event = {
            "requestContext": {
                "http": {"method": "GET", "path": "/api/settings"},
                "authorizer": {"jwt": {"claims": {}}},
            },
            "body": None,
        }
        response = lambda_handler(event, None)
        assert response["statusCode"] == 401

    def test_missing_authorizer_returns_401(self, make_event, mock_deps):
        """Missing authorizer context returns 401."""
        mock_deps["resolve"].return_value = (None, {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "Content-Type,Authorization",
                        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"},
            "body": json.dumps({"error": "unauthorized", "message": "Authentication failed"}),
        })

        from handlers.api_handler import lambda_handler

        event = {
            "requestContext": {
                "http": {"method": "GET", "path": "/api/settings"},
            },
            "body": None,
        }
        response = lambda_handler(event, None)
        assert response["statusCode"] == 401


class TestRouting:
    def test_unknown_path_returns_404(self, make_event, mock_deps):
        """Unknown API path returns 404."""
        from handlers.api_handler import lambda_handler

        event = make_event("GET", "/api/unknown")
        response = lambda_handler(event, None)
        assert response["statusCode"] == 404

    def test_options_returns_cors(self, make_event, mock_deps):
        """OPTIONS returns CORS headers."""
        from handlers.api_handler import lambda_handler

        event = make_event("OPTIONS", "/api/settings")
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200
        assert "Access-Control-Allow-Origin" in response["headers"]
