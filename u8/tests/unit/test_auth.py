"""
Unit tests for auth module.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
import os

os.environ["TABLE_NAME"] = "ArsTable"
os.environ["AWS_REGION"] = "ap-northeast-1"
os.environ["ENV"] = "test"


class TestResolveUserFromEvent:
    def test_valid_jwt_resolves_user(self):
        """Valid JWT claims resolve to user_id."""
        from shared.auth import resolve_user_from_event

        mock_da = MagicMock()
        mock_da.resolve_user_id.return_value = "user-resolved-123"

        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "cognito-sub-abc",
                        }
                    }
                }
            }
        }

        user_id, error = resolve_user_from_event(event, mock_da)

        assert user_id == "user-resolved-123"
        assert error is None
        mock_da.resolve_user_id.assert_called_once_with("cognito-sub-abc")

    def test_missing_sub_returns_401(self):
        """Missing sub claim returns unauthorized error."""
        from shared.auth import resolve_user_from_event

        mock_da = MagicMock()

        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {}  # No sub
                    }
                }
            }
        }

        user_id, error = resolve_user_from_event(event, mock_da)

        assert user_id is None
        assert error is not None
        assert error["statusCode"] == 401

    def test_missing_authorizer_returns_401(self):
        """Missing authorizer context returns unauthorized error."""
        from shared.auth import resolve_user_from_event

        mock_da = MagicMock()

        event = {
            "requestContext": {}
        }

        user_id, error = resolve_user_from_event(event, mock_da)

        assert user_id is None
        assert error is not None
        assert error["statusCode"] == 401

    def test_empty_event_returns_401(self):
        """Completely empty event returns unauthorized error."""
        from shared.auth import resolve_user_from_event

        mock_da = MagicMock()
        event = {}

        user_id, error = resolve_user_from_event(event, mock_da)

        assert user_id is None
        assert error is not None
        assert error["statusCode"] == 401

    def test_da_exception_returns_401(self):
        """DataAccess exception returns unauthorized."""
        from shared.auth import resolve_user_from_event

        mock_da = MagicMock()
        mock_da.resolve_user_id.side_effect = Exception("DDB error")

        event = {
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {"sub": "some-sub"}
                    }
                }
            }
        }

        user_id, error = resolve_user_from_event(event, mock_da)

        assert user_id is None
        assert error is not None
        assert error["statusCode"] == 401
