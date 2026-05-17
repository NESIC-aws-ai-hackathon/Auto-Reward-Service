"""schemas.py のユニットテスト"""
from decimal import Decimal

import pytest

from models.schemas import (
    ChatLog,
    Expense,
    FixedCostItem,
    FixedCosts,
    GoogleOAuth,
    LifeLog,
    PendingExpense,
    PrefItem,
    PrefMemory,
    RewardPool,
    RewardPoolItem,
    RewardSuggestion,
    UserProfile,
)


class TestUserProfile:
    def test_defaults(self):
        profile = UserProfile(
            pk="USER#U123", created_at="2026-01-01T00:00:00+09:00", updated_at="2026-01-01T00:00:00+09:00"
        )
        assert profile.sk == "PROFILE#"
        assert profile.entity_type == "PROFILE"
        assert profile.status == "ACTIVE"
        assert profile.tone == "friendly"
        assert profile.push_count_this_month == 0

    def test_extra_fields_ignored(self):
        profile = UserProfile(
            pk="USER#U123",
            created_at="2026-01-01T00:00:00+09:00",
            updated_at="2026-01-01T00:00:00+09:00",
            unknown_field="should_be_ignored",
        )
        assert not hasattr(profile, "unknown_field")

    def test_decimal_fields(self):
        profile = UserProfile(
            pk="USER#U123",
            created_at="2026-01-01T00:00:00+09:00",
            updated_at="2026-01-01T00:00:00+09:00",
            monthly_income=Decimal("300000"),
            reward_budget_monthly=Decimal("5000"),
        )
        assert profile.monthly_income == Decimal("300000")


class TestChatLog:
    def test_ttl_optional(self):
        log = ChatLog(
            pk="USER#U123",
            sk="CHAT#2026-01-01T00:00:00",
            role="user",
            message="テストメッセージ",
            created_at="2026-01-01T00:00:00+09:00",
        )
        assert log.ttl is None
        assert log.intent is None

    def test_with_ttl(self):
        log = ChatLog(
            pk="USER#U123",
            sk="CHAT#2026-01-01T00:00:00",
            role="assistant",
            message="リワードちゃんです",
            ttl=1753862400,
            created_at="2026-01-01T00:00:00+09:00",
        )
        assert log.ttl == 1753862400


class TestLifeLog:
    def test_ttl_optional(self):
        log = LifeLog(
            pk="USER#U123",
            sk="LIFELOG#2026-01-01T00:00:00",
            created_at="2026-01-01T00:00:00+09:00",
        )
        assert log.ttl is None
        assert log.emotion is None
        assert log.fatigue_level is None


class TestPendingExpense:
    def test_ttl_optional(self):
        expense = PendingExpense(
            pk="USER#U123",
            extracted={"amount": 500, "item_name": "コーヒー"},
            confidence=0.9,
            expires_at="2026-01-02T00:00:00+09:00",
            created_at="2026-01-01T00:00:00+09:00",
            raw_text="コーヒー500円",
        )
        assert expense.sk == "PENDING_EXPENSE#"
        assert expense.ttl is None


class TestPrefMemory:
    def test_entity_type(self):
        pref = PrefMemory(
            pk="USER#U123",
            updated_at="2026-01-01T00:00:00+09:00",
        )
        assert pref.entity_type == "PREF_MEMORY"
        assert pref.sk == "PREF_MEMORY#"
        assert pref.categories == []
        assert pref.items == []


class TestGoogleOAuth:
    def test_defaults(self):
        oauth = GoogleOAuth(
            pk="USER#U123",
            refresh_token="test_refresh_token",
            connected_at="2026-01-01T00:00:00+09:00",
            updated_at="2026-01-01T00:00:00+09:00",
        )
        assert oauth.sk == "GOOGLE_OAUTH#"
        assert oauth.scope == "calendar.events.readonly"
        assert oauth.email_hint is None
