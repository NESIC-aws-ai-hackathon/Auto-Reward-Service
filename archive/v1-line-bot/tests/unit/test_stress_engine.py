"""
stress_engine のユニットテスト

スコア計算・クールダウン・Bedrock呼び出し・総合判定を検証する。
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

# テスト対象
from services.stress_engine import (
    should_suggest_detour,
    _is_in_cooldown,
    _calc_time_score,
    _calc_expense_score,
    _calc_chat_stress_score,
    COOLDOWN_HOURS,
    SUGGEST_THRESHOLD,
)

_JST = timezone(timedelta(hours=9))


# ─────────────────────────────────────────
# _is_in_cooldown
# ─────────────────────────────────────────

class TestIsInCooldown:
    def _ddb(self, sessions):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = sessions
        return ddb

    def test_no_sessions_returns_false(self):
        ddb = self._ddb([])
        assert _is_in_cooldown("user1", ddb) is False

    def test_old_session_returns_false(self):
        old_time = (datetime.now(_JST) - timedelta(hours=COOLDOWN_HOURS + 1)).isoformat()
        ddb = self._ddb([{"created_at": old_time}])
        assert _is_in_cooldown("user1", ddb) is False

    def test_recent_session_returns_true(self):
        recent_time = (datetime.now(_JST) - timedelta(hours=1)).isoformat()
        ddb = self._ddb([{"created_at": recent_time}])
        assert _is_in_cooldown("user1", ddb) is True

    def test_ddb_exception_returns_false(self):
        ddb = MagicMock()
        ddb.query_by_pk.side_effect = Exception("DDB error")
        assert _is_in_cooldown("user1", ddb) is False


# ─────────────────────────────────────────
# _calc_time_score
# ─────────────────────────────────────────

class TestCalcTimeScore:
    def _mock_now(self, hour, weekday):
        """datetime.now(_JST) をモックする用のコンテキスト。"""
        dt = MagicMock()
        dt.hour = hour
        dt.weekday.return_value = weekday  # 0=月〜4=金
        return dt

    @patch("services.stress_engine.datetime")
    def test_weekday_evening_is_max(self, mock_dt):
        mock_dt.now.return_value = self._mock_now(hour=19, weekday=2)  # 水曜19時
        score = _calc_time_score()
        assert score == 25  # 5(平日base) + 20(帰宅)

    @patch("services.stress_engine.datetime")
    def test_weekend_midday_is_low(self, mock_dt):
        mock_dt.now.return_value = self._mock_now(hour=12, weekday=5)  # 土曜昼
        score = _calc_time_score()
        assert score == 0  # 週末 base=0, 昼=+0

    @patch("services.stress_engine.datetime")
    def test_weekday_late_night(self, mock_dt):
        mock_dt.now.return_value = self._mock_now(hour=23, weekday=1)  # 火曜23時
        score = _calc_time_score()
        assert score == 15  # 5 + 10


# ─────────────────────────────────────────
# _calc_expense_score
# ─────────────────────────────────────────

class TestCalcExpenseScore:
    def test_no_recovery_expenses(self):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [{"ars_category": "食費"}, {"ars_category": "娯楽"}]
        assert _calc_expense_score("user1", ddb) == 0

    def test_some_recovery_expenses(self):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [
            {"ars_category": "回復費"},
            {"ars_category": "回復費"},
            {"ars_category": "情緒安定費"},
            {"ars_category": "食費"},
        ]
        score = _calc_expense_score("user1", ddb)
        assert score == 15  # 3件 × 5点

    def test_capped_at_25(self):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [{"ars_category": "回復費"}] * 20
        assert _calc_expense_score("user1", ddb) == 25

    def test_ddb_exception_returns_0(self):
        ddb = MagicMock()
        ddb.query_by_pk.side_effect = Exception("error")
        assert _calc_expense_score("user1", ddb) == 0


# ─────────────────────────────────────────
# _calc_chat_stress_score
# ─────────────────────────────────────────

class TestCalcChatStressScore:
    def test_no_stress_words(self):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [
            {"user_text": "今日は楽しかった"},
            {"user_text": "ランチ食べた"},
        ]
        assert _calc_chat_stress_score("user1", ddb) == 0

    def test_stress_words_detected(self):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [
            {"user_text": "疲れたよ"},
            {"user_text": "もう無理かも"},
            {"user_text": "しんどい"},
        ]
        score = _calc_chat_stress_score("user1", ddb)
        assert score == 15  # 3件 × 5点

    def test_capped_at_25(self):
        ddb = MagicMock()
        ddb.query_by_pk.return_value = [{"user_text": "疲れた"} for _ in range(10)]
        assert _calc_chat_stress_score("user1", ddb) == 25


# ─────────────────────────────────────────
# should_suggest_detour（統合）
# ─────────────────────────────────────────

class TestShouldSuggestDetour:
    def _make_ddb(self, sessions=None, expenses=None, chats=None):
        ddb = MagicMock()
        sessions = sessions or []
        expenses = expenses or []
        chats = chats or []

        def query_by_pk(pk, sk_prefix, limit=None, descending=None):
            if "TEMPTATION_SESSION" in sk_prefix:
                return sessions
            if "EXPENSE" in sk_prefix:
                return expenses
            if "CHAT" in sk_prefix:
                return chats
            return []

        ddb.query_by_pk.side_effect = query_by_pk
        return ddb

    def test_cooldown_blocks_suggestion(self):
        recent = (datetime.now(_JST) - timedelta(minutes=30)).isoformat()
        ddb = self._make_ddb(sessions=[{"created_at": recent}])
        result = should_suggest_detour("user1", "疲れた", ddb)
        assert result["suggest"] is False
        assert result["reason"] == "cooldown"

    @patch("services.stress_engine._assess_message_stress", return_value=(25, "強い疲労"))
    @patch("services.stress_engine._calc_time_score", return_value=25)
    def test_high_score_suggests_detour(self, mock_time, mock_bedrock):
        ddb = self._make_ddb(
            expenses=[{"ars_category": "回復費"}] * 5,  # 25点
            chats=[{"user_text": "疲れた"} for _ in range(5)],  # 25点
        )
        result = should_suggest_detour("user1", "今日は長かった", ddb)
        # time=25, expense=25, chat=25, message=25 → 100点 → suggest
        assert result["suggest"] is True
        assert result["score"] >= SUGGEST_THRESHOLD

    @patch("services.stress_engine._assess_message_stress", return_value=(0, ""))
    @patch("services.stress_engine._calc_time_score", return_value=5)
    def test_low_score_no_suggestion(self, mock_time, mock_bedrock):
        ddb = self._make_ddb()  # 支出・チャットなし
        result = should_suggest_detour("user1", "ありがとう", ddb)
        assert result["suggest"] is False

    @patch("services.stress_engine._assess_message_stress", return_value=(0, ""))
    @patch("services.stress_engine._calc_time_score", return_value=25)
    def test_threshold_boundary(self, mock_time, mock_bedrock):
        """スコアがちょうど閾値の場合に提案される。"""
        # time=25, expense=25(5件), chat=10(2件), message=0 → 60点 → suggest
        ddb = self._make_ddb(
            expenses=[{"ars_category": "回復費"}] * 5,
            chats=[{"user_text": "疲れた"}, {"user_text": "しんどい"}],
        )
        result = should_suggest_detour("user1", "こんにちは", ddb)
        assert result["score"] == SUGGEST_THRESHOLD
        assert result["suggest"] is True
