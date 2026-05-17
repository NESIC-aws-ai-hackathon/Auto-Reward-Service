"""
finance_engine.py のユニットテスト（Unit 5: スライス 5-7）

テスト方針:
- 余裕額は常に 0 以上を保証
- reward_budget_monthly 未設定時はデフォルト 5000 円
- ボーナス月はご褒美枠が拡大される
- DynamoDB エラーは 0 円として処理継続
- 繰り越し機能 (F2-07): 先月未使用額の 50% を繰り越す
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from services.finance_engine import (
    CARRYOVER_RATE,
    DEFAULT_REWARD_BUDGET,
    calculate_monthly_budget,
    calculate_slack,
    get_last_month_remaining,
    get_monthly_spending,
    get_reward_budget,
)


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────

def _make_expense_item(amount) -> dict:
    return {"PK": "USER#u1", "SK": "EXPENSE#2026-05-01T...", "amount": amount}


def _make_ddb(items: list[dict]) -> MagicMock:
    mock = MagicMock()
    mock.query_by_pk.return_value = items
    return mock


# ─────────────────────────────────────────
# get_monthly_spending テスト
# ─────────────────────────────────────────

class TestGetMonthlySpending:

    def test_支出なし_0円を返す(self):
        ddb = _make_ddb([])
        result = get_monthly_spending("u1", ddb, "2026-05")
        assert result == Decimal("0")

    def test_支出1件_合計を返す(self):
        ddb = _make_ddb([_make_expense_item("1000")])
        result = get_monthly_spending("u1", ddb, "2026-05")
        assert result == Decimal("1000")

    def test_支出複数件_合計を返す(self):
        ddb = _make_ddb([
            _make_expense_item("500"),
            _make_expense_item("1200"),
            _make_expense_item("300"),
        ])
        result = get_monthly_spending("u1", ddb, "2026-05")
        assert result == Decimal("2000")

    def test_Decimal型の金額も合計できる(self):
        ddb = _make_ddb([_make_expense_item(Decimal("980"))])
        result = get_monthly_spending("u1", ddb, "2026-05")
        assert result == Decimal("980")

    def test_無効な金額はスキップされる(self):
        ddb = _make_ddb([
            _make_expense_item("1000"),
            {"PK": "USER#u1", "SK": "EXPENSE#...", "amount": "invalid"},
            _make_expense_item("500"),
        ])
        result = get_monthly_spending("u1", ddb, "2026-05")
        assert result == Decimal("1500")

    def test_amountなしアイテムはスキップされる(self):
        ddb = _make_ddb([
            {"PK": "USER#u1", "SK": "EXPENSE#..."},
            _make_expense_item("800"),
        ])
        result = get_monthly_spending("u1", ddb, "2026-05")
        assert result == Decimal("800")

    def test_DynamoDBエラー_0円を返す(self):
        ddb = MagicMock()
        ddb.query_by_pk.side_effect = Exception("DynamoDB Error")
        result = get_monthly_spending("u1", ddb, "2026-05")
        assert result == Decimal("0")

    def test_年月省略_現在月で検索される(self):
        ddb = _make_ddb([_make_expense_item("2000")])
        result = get_monthly_spending("u1", ddb)
        assert result == Decimal("2000")
        # query_by_pk が呼ばれたことを確認
        ddb.query_by_pk.assert_called_once()
        _, kwargs = ddb.query_by_pk.call_args
        assert "sk_prefix" in kwargs
        # sk_prefix が "EXPENSE#YYYY-MM" 形式であること
        assert kwargs["sk_prefix"].startswith("EXPENSE#")


# ─────────────────────────────────────────
# get_reward_budget テスト
# ─────────────────────────────────────────

class TestGetRewardBudget:

    def test_reward_budget_monthly未設定_デフォルト5000円(self):
        profile = {}
        assert get_reward_budget(profile) == DEFAULT_REWARD_BUDGET

    def test_reward_budget_monthly設定済み_値を返す(self):
        profile = {"reward_budget_monthly": "20000"}
        assert get_reward_budget(profile) == Decimal("20000")

    def test_reward_budget_monthly_Decimal型(self):
        profile = {"reward_budget_monthly": Decimal("15000")}
        assert get_reward_budget(profile) == Decimal("15000")

    def test_reward_budget_monthly_0以下_デフォルトを返す(self):
        profile = {"reward_budget_monthly": "0"}
        assert get_reward_budget(profile) == DEFAULT_REWARD_BUDGET

    def test_reward_budget_monthly_無効値_デフォルトを返す(self):
        profile = {"reward_budget_monthly": "invalid"}
        assert get_reward_budget(profile) == DEFAULT_REWARD_BUDGET

    def test_ボーナス月でない_予算そのまま(self):
        profile = {
            "reward_budget_monthly": "20000",
            "bonus_months": [6, 12],
            "bonus_amount": 400000,
        }
        with patch("services.finance_engine.datetime") as mock_dt:
            mock_dt.now.return_value.month = 5  # 5月 = 非ボーナス月
            result = get_reward_budget(profile)
        assert result == Decimal("20000")

    def test_ボーナス月_bonus_amountの10パーセント加算(self):
        profile = {
            "reward_budget_monthly": "20000",
            "bonus_months": [6, 12],
            "bonus_amount": 400000,
        }
        with patch("services.finance_engine.datetime") as mock_dt:
            mock_dt.now.return_value.month = 6  # 6月 = ボーナス月
            result = get_reward_budget(profile)
        # 20000 + 400000 * 0.1 = 60000
        assert result == Decimal("60000")

    def test_ボーナス月だがbonus_amount未設定_予算そのまま(self):
        profile = {
            "reward_budget_monthly": "20000",
            "bonus_months": [6, 12],
        }
        with patch("services.finance_engine.datetime") as mock_dt:
            mock_dt.now.return_value.month = 6
            result = get_reward_budget(profile)
        assert result == Decimal("20000")


# ─────────────────────────────────────────
# calculate_slack テスト
# ─────────────────────────────────────────

class TestCalculateSlack:

    def test_支出0円_余裕額は予算全額(self):
        ddb = _make_ddb([])
        profile = {"reward_budget_monthly": "10000"}
        slack, budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert slack == Decimal("10000")
        assert budget == Decimal("10000")

    def test_支出が予算未満_差額を返す(self):
        ddb = _make_ddb([_make_expense_item("3000")])
        profile = {"reward_budget_monthly": "10000"}
        slack, budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert slack == Decimal("7000")
        assert budget == Decimal("10000")

    def test_支出が予算ちょうど_余裕額0(self):
        ddb = _make_ddb([_make_expense_item("10000")])
        profile = {"reward_budget_monthly": "10000"}
        slack, budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert slack == Decimal("0")

    def test_支出が予算超過_余裕額は0以上を保証(self):
        ddb = _make_ddb([_make_expense_item("15000")])
        profile = {"reward_budget_monthly": "10000"}
        slack, budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert slack == Decimal("0")
        # 余裕額は絶対に負にならない
        assert slack >= Decimal("0")

    def test_予算未設定_デフォルト5000円で計算(self):
        ddb = _make_ddb([_make_expense_item("2000")])
        profile = {}
        slack, budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert budget == DEFAULT_REWARD_BUDGET
        assert slack == Decimal("3000")

    def test_DynamoDBエラー_余裕額は予算全額(self):
        ddb = MagicMock()
        ddb.get_item.return_value = None
        ddb.query_by_pk.side_effect = Exception("DynamoDB Error")
        profile = {"reward_budget_monthly": "10000"}
        slack, budget = calculate_slack("u1", ddb, profile, "2026-05")
        # エラー時は spending = 0 として処理
        assert slack == Decimal("10000")


# ─────────────────────────────────────────
# calculate_monthly_budget テスト（F2-07 繰り越し機能）
# ─────────────────────────────────────────

class TestCalculateMonthlyBudget:

    def test_ケース1_通常月_先月未使用て8000円(self):
        # 基本枚: 20,000 / 先月未使用: 8,000 / ボーナス: 0
        # 繰り越し = min(8000 * 0.5, 20000) = 4000
        result = calculate_monthly_budget(20000, 8000)
        assert result["carryover_amount"] == 4000
        assert result["total_budget"] == 24000
        assert result["base_budget"] == 20000
        assert result["bonus_amount"] == 0

    def test_ケース2_ボーナス月_繰り越しじ4000(self):
        # 基本枚: 20,000 / 先月未使用: 8,000 / ボーナス: 30,000
        # 繰り越し = 4,000
        # 総予算 = 20,000 + 4,000 + 30,000 = 54,000
        result = calculate_monthly_budget(20000, 8000, bonus_amount=30000)
        assert result["carryover_amount"] == 4000
        assert result["bonus_amount"] == 30000
        assert result["total_budget"] == 54000

    def test_ケース3_先月使い切った_繰り越し0(self):
        # 基本枚: 20,000 / 先月未使用: 0 / ボーナス: 0
        result = calculate_monthly_budget(20000, 0)
        assert result["carryover_amount"] == 0
        assert result["total_budget"] == 20000

    def test_ケース4_繰り越し上限適用(self):
        # 基本枚: 20,000 / 先月未使用: 50,000
        # 繰り越し = min(50000 * 0.5, 20000) = min(25000, 20000) = 20000
        result = calculate_monthly_budget(20000, 50000)
        assert result["carryover_amount"] == 20000
        assert result["total_budget"] == 40000

    def test_先月超過支出_繰り越し0(self):
        # 先月未使用のマイナス（超過支出月）は 0 にクランプ
        result = calculate_monthly_budget(20000, -5000)
        assert result["carryover_amount"] == 0
        assert result["total_budget"] == 20000

    def test_カスタム繰り越し率100パーセント(self):
        # 繰り越し率 1.0 (上限は基本枚と同額)
        result = calculate_monthly_budget(20000, 8000, carryover_rate=1.0)
        # min(8000 * 1.0, 20000) = 8000
        assert result["carryover_amount"] == 8000
        assert result["total_budget"] == 28000

    def test_繰り越し率0_繰り越し0(self):
        result = calculate_monthly_budget(20000, 8000, carryover_rate=0.0)
        assert result["carryover_amount"] == 0
        assert result["total_budget"] == 20000

    def test_デフォルト繰り越し率はCARRYOVER_RATE(self):
        assert CARRYOVER_RATE == 0.5


# ─────────────────────────────────────────
# get_last_month_remaining テスト（F2-07）
# ─────────────────────────────────────────

class TestGetLastMonthRemaining:

    def test_先月サマリーなし_0を返す(self):
        ddb = MagicMock()
        ddb.get_item.return_value = None
        result = get_last_month_remaining("u1", ddb)
        assert result == 0

    def test_total_budgetあり_残額を返す(self):
        ddb = MagicMock()
        ddb.get_item.return_value = {
            "total_budget": 24000,
            "total_amount": Decimal("8000"),
        }
        result = get_last_month_remaining("u1", ddb)
        assert result == 16000

    def test_total_budgetなし_reward_budgetにフォールバック(self):
        # 先月に total_budget がない古いアイテムの演算
        ddb = MagicMock()
        ddb.get_item.return_value = {
            "reward_budget": "20000",
            "total_amount": Decimal("12000"),
        }
        result = get_last_month_remaining("u1", ddb)
        assert result == 8000

    def test_先月超過支出_0にクランプ(self):
        ddb = MagicMock()
        ddb.get_item.return_value = {
            "total_budget": 20000,
            "total_amount": Decimal("25000"),  # 超過支出
        }
        result = get_last_month_remaining("u1", ddb)
        assert result == 0

    def test_DynamoDBエラー_0を返す(self):
        ddb = MagicMock()
        ddb.get_item.side_effect = Exception("DynamoDB Error")
        result = get_last_month_remaining("u1", ddb)
        assert result == 0


# ─────────────────────────────────────────
# calculate_slack 繰り越し統合テスト（F2-07）
# ─────────────────────────────────────────

class TestCalculateSlackWithCarryover:
    """繰り越しありの calculate_slack 統合テスト"""

    def _make_ddb_with_last_month(self, last_summary: dict | None, spending_items: list) -> MagicMock:
        ddb = MagicMock()
        ddb.get_item.return_value = last_summary
        ddb.query_by_pk.return_value = spending_items
        return ddb

    def test_繰り越しあり_total_budgetに繰り越し分加算(self):
        # 基本枚 20000, 先月残 8000 → 繰り越し 4000 → total_budget 24000
        ddb = self._make_ddb_with_last_month(
            {"total_budget": 20000, "total_amount": Decimal("12000")},
            [],
        )
        profile = {"reward_budget_monthly": "20000"}
        slack, total_budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert total_budget == Decimal("24000")
        assert slack == Decimal("24000")

    def test_先月サマリーなし_基本枚のみ(self):
        ddb = self._make_ddb_with_last_month(None, [])
        profile = {"reward_budget_monthly": "20000"}
        slack, total_budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert total_budget == Decimal("20000")
        assert slack == Decimal("20000")

    def test_繰り越しあり_予算内に収まる支出(self):
        # total_budget 24000, 支出 8000 → slack 16000
        ddb = self._make_ddb_with_last_month(
            {"total_budget": 20000, "total_amount": Decimal("12000")},
            [_make_expense_item("8000")],
        )
        profile = {"reward_budget_monthly": "20000"}
        slack, total_budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert total_budget == Decimal("24000")
        assert slack == Decimal("16000")

    def test_carryover_rate_profileから読み込む(self):
        # carryover_rate=0.3 → 繰り越し = min(8000 * 0.3, 20000) = 2400
        ddb = self._make_ddb_with_last_month(
            {"total_budget": 20000, "total_amount": Decimal("12000")},
            [],
        )
        profile = {"reward_budget_monthly": "20000", "carryover_rate": 0.3}
        slack, total_budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert total_budget == Decimal("22400")

    def test_繰り越しあり_予算超過支出_slack_0保証(self):
        # total_budget 24000, 支出 30000 → slack = 0
        ddb = self._make_ddb_with_last_month(
            {"total_budget": 20000, "total_amount": Decimal("12000")},
            [_make_expense_item("30000")],
        )
        profile = {"reward_budget_monthly": "20000"}
        slack, total_budget = calculate_slack("u1", ddb, profile, "2026-05")
        assert slack == Decimal("0")
        assert slack >= Decimal("0")
