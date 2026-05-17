"""
daily_push サービスのユニットテスト
"""
import random
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.daily_push import (
    DAILY_CATEGORIES,
    _adjust_weights,
    _days_left_in_month,
    _default_settings,
    _fill_template,
    _find_upcoming_anniversary,
    _get_food_pref,
    _get_past_category,
    _get_past_item,
    _get_random_pref,
    _get_remaining_budget,
    _get_tone,
    _select_template,
    generate_daily_push,
)

_JST = timezone(timedelta(hours=9))


# ─────────────────────────────────────────
# _get_tone テスト
# ─────────────────────────────────────────
class TestGetTone:
    def test_morning_tone(self):
        tone = _get_tone(10)
        assert tone in ["ねね、", "そういえばさ、", "ちょっと聞きたいんだけど、"]

    def test_lunch_tone(self):
        tone = _get_tone(12)
        assert tone in ["お昼だ！", "ランチ中？", "ごはん食べた？"]

    def test_afternoon_tone(self):
        tone = _get_tone(15)
        assert tone in ["ちょっと聞いてよ〜", "ひまな時でいいんだけど、", "急にごめんね笑"]

    def test_evening_tone(self):
        tone = _get_tone(18)
        assert tone in ["おつかれ！", "仕事終わった？", "もう帰り？"]

    def test_night_tone(self):
        tone = _get_tone(20)
        assert tone in ["夜だけどさ、", "寝る前にちょっと！", "今日もおつかれ〜！"]


# ─────────────────────────────────────────
# _find_upcoming_anniversary テスト
# ─────────────────────────────────────────
class TestFindUpcomingAnniversary:
    def test_no_anniversaries(self):
        assert _find_upcoming_anniversary([], datetime.now(_JST)) is None

    def test_anniversary_7_days_ahead(self):
        now = datetime(2026, 5, 10, 12, 0, tzinfo=_JST)
        anns = [{"name": "結婚記念日", "date": "05-15"}]
        result = _find_upcoming_anniversary(anns, now)
        assert result is not None
        assert result["name"] == "結婚記念日"
        assert result["days"] == 5

    def test_anniversary_today(self):
        now = datetime(2026, 5, 15, 12, 0, tzinfo=_JST)
        anns = [{"name": "結婚記念日", "date": "05-15"}]
        result = _find_upcoming_anniversary(anns, now)
        assert result is not None
        assert result["days"] == 0

    def test_anniversary_too_far(self):
        now = datetime(2026, 5, 1, 12, 0, tzinfo=_JST)
        anns = [{"name": "結婚記念日", "date": "06-15"}]
        result = _find_upcoming_anniversary(anns, now)
        assert result is None

    def test_invalid_date_format(self):
        now = datetime(2026, 5, 10, 12, 0, tzinfo=_JST)
        anns = [{"name": "test", "date": "invalid"}]
        assert _find_upcoming_anniversary(anns, now) is None


# ─────────────────────────────────────────
# _adjust_weights テスト
# ─────────────────────────────────────────
class TestAdjustWeights:
    def test_anniversary_overrides(self):
        settings = _default_settings()
        weights = _adjust_weights(
            pref_count=0,
            has_recent_expenses=False,
            has_upcoming_anniversary=True,
            settings=settings,
        )
        assert weights == {"anniversary_approach": 10}

    def test_low_pref_count_boosts_deep_dive(self):
        settings = _default_settings()
        weights = _adjust_weights(
            pref_count=2,
            has_recent_expenses=True,
            has_upcoming_anniversary=False,
            settings=settings,
        )
        assert weights.get("deep_dive_preference") == 5
        assert weights.get("specific_recommendation") == 1

    def test_high_pref_count_boosts_recommendation(self):
        settings = _default_settings()
        weights = _adjust_weights(
            pref_count=10,
            has_recent_expenses=True,
            has_upcoming_anniversary=False,
            settings=settings,
        )
        assert weights.get("specific_recommendation") == 5
        assert weights.get("deep_dive_preference") == 1

    def test_no_expenses_removes_past_reference(self):
        settings = _default_settings()
        weights = _adjust_weights(
            pref_count=3,
            has_recent_expenses=False,
            has_upcoming_anniversary=False,
            settings=settings,
        )
        assert "past_reference" not in weights

    def test_disabled_settings_excluded(self):
        settings = _default_settings()
        settings["budget_nudge"] = False
        weights = _adjust_weights(
            pref_count=3,
            has_recent_expenses=True,
            has_upcoming_anniversary=False,
            settings=settings,
        )
        assert "budget_nudge" not in weights


# ─────────────────────────────────────────
# _select_template テスト
# ─────────────────────────────────────────
class TestSelectTemplate:
    def test_returns_valid_template(self):
        weights = {"either_or": 5}
        cat, template, template_id = _select_template(weights, set())
        assert cat == "either_or"
        assert template in DAILY_CATEGORIES["either_or"]["templates"]
        assert template_id.startswith("either_or:")

    def test_avoids_recent_templates(self):
        weights = {"either_or": 5}
        all_ids = {
            f"either_or:{i}"
            for i in range(len(DAILY_CATEGORIES["either_or"]["templates"]))
        }
        # 全テンプレートが recent → フォールバック
        cat, template, template_id = _select_template(weights, all_ids)
        assert cat == "either_or"
        assert template_id == "either_or:0"


# ─────────────────────────────────────────
# _fill_template テスト
# ─────────────────────────────────────────
class TestFillTemplate:
    def test_fills_variables(self):
        template = "{tone}今月まだ{remaining}円あるよ〜"
        result = _fill_template(template, {"tone": "ねね、", "remaining": "10,000"})
        assert result == "ねね、今月まだ10,000円あるよ〜"

    def test_missing_variable_left_as_is(self):
        template = "{tone}こんにちは{unknown}"
        result = _fill_template(template, {"tone": "ねね、"})
        assert "{unknown}" in result


# ─────────────────────────────────────────
# ヘルパーテスト
# ─────────────────────────────────────────
class TestHelpers:
    def test_days_left_in_month_mid_month(self):
        dt = datetime(2026, 5, 15, 12, 0, tzinfo=_JST)
        days = _days_left_in_month(dt)
        assert days == 17  # 5/15 → 6/1 = 17日

    def test_days_left_in_december(self):
        dt = datetime(2026, 12, 25, 12, 0, tzinfo=_JST)
        days = _days_left_in_month(dt)
        assert days == 7  # 12/25 → 1/1 = 7日

    def test_get_food_pref_with_food_item(self):
        items = [{"keyword": "豚骨ラーメン", "category": "food"}]
        assert _get_food_pref(items) == "豚骨ラーメン"

    def test_get_food_pref_no_food(self):
        items = [{"keyword": "映画", "category": "entertainment"}]
        assert _get_food_pref(items) == "おいしいもの"

    def test_get_random_pref_empty(self):
        assert _get_random_pref([]) == "気になるもの"

    def test_get_past_item_with_expenses(self):
        expenses = [{"item_name": "プリン", "amount": 200}]
        assert _get_past_item(expenses) == "プリン"

    def test_get_past_item_no_name(self):
        expenses = [{"amount": 200}]
        assert _get_past_item(expenses) == "いいもの"

    def test_get_past_category_empty(self):
        assert _get_past_category([]) == "お買い物"

    def test_default_settings(self):
        settings = _default_settings()
        assert settings["all_enabled"] is True
        assert settings["push_time_start"] == "10:00"
        assert settings["push_time_end"] == "21:00"


# ─────────────────────────────────────────
# generate_daily_push 統合テスト
# ─────────────────────────────────────────
class TestGenerateDailyPush:
    def _make_ddb_mock(self, profile=None, pref=None, settings=None, expenses=None, streak=None, push_logs=None):
        ddb = MagicMock()

        def get_item_side_effect(pk, sk):
            if sk == "PROFILE#":
                return profile or {"nickname": "テスト太郎"}
            if sk == "PREF_MEMORY#":
                return pref or {}
            if sk == "PUSH_SETTINGS#":
                return settings
            if sk == "STREAK#":
                return streak or {}
            return None

        ddb.get_item.side_effect = get_item_side_effect
        ddb.query_by_pk.return_value = expenses or []
        return ddb

    def test_all_enabled_false_returns_none(self):
        ddb = self._make_ddb_mock(settings={"all_enabled": False})
        result = generate_daily_push("U123", ddb)
        assert result is None

    def test_daily_message_false_returns_none(self):
        ddb = self._make_ddb_mock(settings={"all_enabled": True, "daily_message": False})
        result = generate_daily_push("U123", ddb)
        assert result is None

    def test_generates_message_with_default_settings(self):
        ddb = self._make_ddb_mock(
            profile={"nickname": "テスト太郎", "reward_budget_monthly": 20000},
        )
        result = generate_daily_push("U123", ddb)
        assert result is not None
        assert result["type"] == "text"
        assert len(result["text"]) > 0
        assert "category" in result
        assert "template_id" in result

    def test_with_pref_items(self):
        ddb = self._make_ddb_mock(
            profile={"nickname": "花子"},
            pref={"items": [
                {"keyword": "豚骨ラーメン", "category": "food"},
                {"keyword": "映画", "category": "entertainment"},
                {"keyword": "ユニクロ", "category": "fashion"},
                {"keyword": "カフェ巡り", "category": "lifestyle"},
                {"keyword": "温泉", "category": "place"},
            ]},
        )
        result = generate_daily_push("U456", ddb)
        assert result is not None

    def test_with_anniversary_upcoming(self):
        today = datetime.now(_JST)
        ann_date = (today + timedelta(days=3)).strftime("%m-%d")
        ddb = self._make_ddb_mock(
            profile={
                "nickname": "太郎",
                "anniversaries": [{"name": "結婚記念日", "date": ann_date}],
            },
        )
        result = generate_daily_push("U789", ddb)
        assert result is not None
        assert "結婚記念日" in result["text"]

    def test_with_recent_expenses(self):
        ddb = self._make_ddb_mock(
            profile={"nickname": "次郎"},
            expenses=[
                {"item_name": "スタバ", "ars_category": "情緒安定費", "amount": 500, "SK": "EXPENSE#2026-05-16T10:00:00"},
            ],
        )
        result = generate_daily_push("U111", ddb)
        assert result is not None

    def test_with_streak(self):
        ddb = self._make_ddb_mock(
            profile={"nickname": "三郎"},
            streak={"current_streak": 7},
        )
        result = generate_daily_push("U222", ddb)
        assert result is not None
