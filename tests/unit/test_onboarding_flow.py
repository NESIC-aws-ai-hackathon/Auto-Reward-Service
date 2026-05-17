"""
tests/unit/test_onboarding_flow.py

オンボーディングフロー（状態機械）のユニットテスト
- 金額抽出（extract_amount）
- 状態遷移
- ご褒美枠算出
- 誕生日抽出
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from onboarding_flow import (
    extract_amount,
    _extract_birthday,
    _calc_reward_budget,
    _is_affirmative,
    _is_skip,
    handle_onboarding,
    start_onboarding,
    STEP_WAITING_INCOME,
    STEP_WAITING_FIXED_COSTS,
    STEP_CONFIRM_REWARD_BUDGET,
    STEP_WAITING_BONUS,
    STEP_WAITING_BIRTHDAY,
    STEP_COMPLETED,
)


# ─────────────────────────────────────────
# extract_amount テスト
# ─────────────────────────────────────────

class TestExtractAmount:
    def test_man_format(self):
        assert extract_amount("25万") == 250000

    def test_man_format_with_decimal(self):
        assert extract_amount("2.5万") == 25000

    def test_raw_yen(self):
        assert extract_amount("300000円") == 300000

    def test_multiple_man_sums(self):
        # 「8万、1万、5000」は万パターンが優先される（8万 + 1万 = 9万）
        result = extract_amount("家賃8万スマホ1万")
        assert result == 90000

    def test_returns_none_for_no_amount(self):
        assert extract_amount("今日はいい天気") is None

    def test_short_digits_ignored(self):
        # 3桁以下は無視
        result = extract_amount("123")
        assert result is None

    def test_four_digit_number(self):
        result = extract_amount("5000円くらい")
        assert result == 5000


# ─────────────────────────────────────────
# _extract_birthday テスト
# ─────────────────────────────────────────

class TestExtractBirthday:
    def test_japanese_format(self):
        assert _extract_birthday("8月20日") == "08-20"

    def test_slash_format(self):
        assert _extract_birthday("8/20") == "08-20"

    def test_hyphen_format(self):
        assert _extract_birthday("08-20") == "08-20"

    def test_with_surrounding_text(self):
        assert _extract_birthday("誕生日は3月15日です") == "03-15"

    def test_invalid_returns_none(self):
        assert _extract_birthday("誕生日なし") is None

    def test_month_out_of_range_returns_none(self):
        assert _extract_birthday("13月5日") is None


# ─────────────────────────────────────────
# _calc_reward_budget テスト
# ─────────────────────────────────────────

class TestCalcRewardBudget:
    def test_normal_case(self):
        # (300000 - 150000) * 0.15 = 22500 → 22500 (min:3000 max:30000 内)
        assert _calc_reward_budget(300000, 150000) == 22500

    def test_minimum_3000(self):
        # 余剰が少ない場合は 3000 円が下限
        assert _calc_reward_budget(200000, 195000) == 3000

    def test_maximum_30000(self):
        # 余剰が多い場合は 30000 円が上限
        assert _calc_reward_budget(1000000, 100000) == 30000

    def test_negative_surplus_returns_minimum(self):
        # 固定費 > 収入の場合も 3000 円を返す
        assert _calc_reward_budget(100000, 200000) == 3000


# ─────────────────────────────────────────
# _is_affirmative / _is_skip テスト
# ─────────────────────────────────────────

class TestHelperFunctions:
    def test_affirmative_hai(self):
        assert _is_affirmative("はい") is True

    def test_affirmative_ok(self):
        assert _is_affirmative("OK") is True

    def test_affirmative_un(self):
        assert _is_affirmative("うん") is True

    def test_not_affirmative(self):
        assert _is_affirmative("違います") is False

    def test_skip_nashi(self):
        assert _is_skip("なし") is True

    def test_skip_skip(self):
        assert _is_skip("スキップ") is True

    def test_not_skip(self):
        assert _is_skip("あります") is False


# ─────────────────────────────────────────
# start_onboarding テスト
# ─────────────────────────────────────────

class TestStartOnboarding:
    def test_creates_onboarding_state(self):
        mock_ddb = MagicMock()
        mock_ddb.put_item.return_value = None

        result = start_onboarding("user123", mock_ddb)

        # put_item が呼ばれること
        mock_ddb.put_item.assert_called_once()
        # 呼び出し引数（第3引数 = item dict）に step が含まれること
        call_arg = mock_ddb.put_item.call_args[0][2]
        assert call_arg["step"] == STEP_WAITING_INCOME

        # ウェルカムメッセージが返ること
        assert "はじめまして" in result or "リワードちゃん" in result


# ─────────────────────────────────────────
# handle_onboarding 状態遷移テスト
# ─────────────────────────────────────────

def _make_ddb(step: str, extra: dict = None) -> MagicMock:
    """オンボーディング状態を持つ mock DynamoDB を作成"""
    mock_ddb = MagicMock()
    state = {"step": step}
    if extra:
        state.update(extra)
    mock_ddb.get_item.return_value = state
    mock_ddb.put_item.return_value = None
    return mock_ddb


class TestHandleOnboarding:
    def test_waiting_income_valid_amount(self):
        mock_ddb = _make_ddb(STEP_WAITING_INCOME)
        result = handle_onboarding("u1", "25万", mock_ddb)
        # 次の質問（固定費）が返ること
        assert "固定費" in result
        # 状態が更新されること
        mock_ddb.put_item.assert_called()

    def test_waiting_income_invalid_amount(self):
        mock_ddb = _make_ddb(STEP_WAITING_INCOME)
        result = handle_onboarding("u1", "わからない", mock_ddb)
        assert "金額" in result or "読み取れ" in result

    def test_waiting_income_too_small_amount(self):
        mock_ddb = _make_ddb(STEP_WAITING_INCOME)
        result = handle_onboarding("u1", "1000円", mock_ddb)
        # 5万未満は誤入力
        assert "金額" in result or "読み取れ" in result

    def test_waiting_fixed_costs_valid(self):
        mock_ddb = _make_ddb(
            STEP_WAITING_FIXED_COSTS,
            {"monthly_income": 300000}
        )
        result = handle_onboarding("u1", "家賃8万 スマホ1万", mock_ddb)
        # ご褒美枠確認が返ること
        assert "ご褒美" in result or "確認" in result or "円" in result

    def test_waiting_fixed_costs_invalid(self):
        mock_ddb = _make_ddb(
            STEP_WAITING_FIXED_COSTS,
            {"monthly_income": 300000}
        )
        result = handle_onboarding("u1", "よくわからない", mock_ddb)
        assert "固定費" in result or "読み取れ" in result

    def test_confirm_budget_yes(self):
        mock_ddb = _make_ddb(
            STEP_CONFIRM_REWARD_BUDGET,
            {"monthly_income": 300000, "fixed_costs_total": 150000, "reward_budget": 22500}
        )
        result = handle_onboarding("u1", "はい", mock_ddb)
        assert "ボーナス" in result

    def test_confirm_budget_with_new_amount(self):
        mock_ddb = _make_ddb(
            STEP_CONFIRM_REWARD_BUDGET,
            {"monthly_income": 300000, "fixed_costs_total": 150000, "reward_budget": 22500}
        )
        result = handle_onboarding("u1", "1万円でお願い", mock_ddb)
        # 変更された金額でボーナスステップに進む
        assert "10000" in result or "1万" in result or "ボーナス" in result

    def test_waiting_bonus_with_skip(self):
        mock_ddb = _make_ddb(
            STEP_WAITING_BONUS,
            {"monthly_income": 300000, "fixed_costs_total": 150000, "reward_budget": 22500}
        )
        result = handle_onboarding("u1", "なし", mock_ddb)
        assert "誕生日" in result

    def test_waiting_bonus_with_months(self):
        mock_ddb = _make_ddb(
            STEP_WAITING_BONUS,
            {"monthly_income": 300000, "fixed_costs_total": 150000, "reward_budget": 22500}
        )
        result = handle_onboarding("u1", "6月と12月 60万くらい", mock_ddb)
        assert "誕生日" in result
        # put_item の呼び出し履歴を全て確認（bonus_months がどれかの呼び出しに含まれる）
        all_calls = [c[0][2] for c in mock_ddb.put_item.call_args_list if len(c[0]) > 2]
        bonus_months_found = any(
            isinstance(c, dict) and 6 in c.get("bonus_months", [])
            for c in all_calls
        )
        assert bonus_months_found, f"bonus_months に 6 が見つからない。全 put_item 呼び出し: {all_calls}"

    def test_waiting_birthday_valid(self):
        mock_ddb = _make_ddb(
            STEP_WAITING_BIRTHDAY,
            {"monthly_income": 300000, "fixed_costs_total": 150000, "reward_budget": 22500}
        )
        mock_ddb.update_item.return_value = None
        result = handle_onboarding("u1", "8月20日", mock_ddb)
        assert "完了" in result or "セットアップ" in result

    def test_waiting_birthday_skip(self):
        mock_ddb = _make_ddb(
            STEP_WAITING_BIRTHDAY,
            {"monthly_income": 300000, "fixed_costs_total": 150000, "reward_budget": 22500}
        )
        mock_ddb.update_item.return_value = None
        result = handle_onboarding("u1", "スキップ", mock_ddb)
        assert "完了" in result or "セットアップ" in result

    def test_completed_state_returns_message(self):
        mock_ddb = _make_ddb(STEP_COMPLETED)
        result = handle_onboarding("u1", "もう一度", mock_ddb)
        assert "完了" in result or "セットアップ" in result
