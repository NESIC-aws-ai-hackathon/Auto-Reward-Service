"""
余裕額算出エンジン（Unit 5: スライス 5-1）

責務:
  1. get_monthly_spending : 今月の EXPENSE# アイテムから支出合計を集計
  2. get_reward_budget    : プロファイルからご褒美予算を取得（ボーナス月は加算）
  3. calculate_slack      : 余裕額 = max(reward_budget - monthly_spending, 0)

設計方針:
  - 余裕額は常に 0 以上（下限クランプ）
  - reward_budget_monthly が未設定の場合は DEFAULT_REWARD_BUDGET = 5000 円を使用
  - ボーナス月は bonus_amount の 10% をご褒美枠に加算
  - DynamoDB エラーは WARNING ログに留め、0 円として処理継続
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from models.schemas import SK_PREFIX_EXPENSE, SK_PREFIX_MONTHLY_SUMMARY
from services.dynamodb_service import DynamoDBService
from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
DEFAULT_REWARD_BUDGET = Decimal("5000")  # 嗜好未登録ユーザー向けデフォルト（円）
CARRYOVER_RATE = 0.5                     # 繰り越し率デフォルト（F2-07）
_JST = timezone(timedelta(hours=9))


def calculate_monthly_budget(
    base_budget: int,
    last_month_remaining: int,
    bonus_amount: int = 0,
    carryover_rate: float = CARRYOVER_RATE,
) -> dict:
    """
    今月のご褒美枠を算出する（F2-07 繰り越し機能）。

    繰り越しルール:
      - 繰り越し率: デフォルト 50%
      - 繰り越し上限: 基本枠と同額（最大でも月予算の2倍に制限）
      - 繰り越しはマイナスにならない（超過支出月は 0 として扱う）

    Args:
        base_budget:           基本ご褒美予算（円）
        last_month_remaining:  先月の未使用額（円）
        bonus_amount:          ボーナス加算額（円、デフォルト 0）
        carryover_rate:        繰り越し率（デフォルト 0.5 = 50%）

    Returns:
        {
            "base_budget":      int,  # 基本予算
            "carryover_amount": int,  # 繰り越し額（0以上）
            "bonus_amount":     int,  # ボーナス加算額
            "total_budget":     int,  # 総予算 = base + carryover + bonus
        }
    """
    carryover = min(
        int(last_month_remaining * carryover_rate),  # 未使用額の carryover_rate
        base_budget,                                   # 上限 = 基本枠
    )
    carryover = max(carryover, 0)  # マイナス防止（超過支出月の翌月）

    total_budget = base_budget + carryover + bonus_amount

    return {
        "base_budget": base_budget,
        "carryover_amount": carryover,
        "bonus_amount": bonus_amount,
        "total_budget": total_budget,
    }


def get_last_month_remaining(
    user_id: str,
    ddb: DynamoDBService,
) -> int:
    """
    先月の MonthlyExpenseSummary から未使用残額を取得する（F2-07）。

    先月サマリーが存在しない場合（新規ユーザー・初回利用）は 0 を返す。
    超過支出月（残額マイナス）は 0 にクランプする。

    Args:
        user_id: LINE ユーザー ID
        ddb:     DynamoDB サービスインスタンス

    Returns:
        先月の残額（0 以上整数）
    """
    now = datetime.now(_JST)
    first_of_this_month = now.replace(day=1)
    last_month_dt = first_of_this_month - timedelta(days=1)
    last_month_str = last_month_dt.strftime("%Y-%m")

    pk = f"USER#{user_id}"
    sk = f"{SK_PREFIX_MONTHLY_SUMMARY}{last_month_str}"

    try:
        item = ddb.get_item(pk=pk, sk=sk)
        if not item:
            return 0

        # total_budget が保存済みならそれを使用、なければ reward_budget にフォールバック
        total_budget_raw = item.get("total_budget") or item.get("reward_budget") or 0
        total_amount_raw = item.get("total_amount") or 0

        total_budget = Decimal(str(total_budget_raw))
        total_amount = Decimal(str(total_amount_raw))
        remaining = int(total_budget - total_amount)
        return max(remaining, 0)  # マイナス（超過支出月）は 0
    except Exception as e:
        logger.warning("get_last_month_remaining_failed", error=str(e))
        return 0


def get_monthly_spending(
    user_id: str,
    ddb: DynamoDBService,
    year_month: Optional[str] = None,
) -> Decimal:
    """
    今月の支出合計を EXPENSE# アイテムから集計する。

    Args:
        user_id:    LINE ユーザー ID
        ddb:        DynamoDB サービスインスタンス
        year_month: "YYYY-MM" 形式（None の場合は現在月）

    Returns:
        今月の支出合計（Decimal、エラー時は Decimal("0")）
    """
    if year_month is None:
        year_month = datetime.now(_JST).strftime("%Y-%m")

    pk = f"USER#{user_id}"
    sk_prefix = f"{SK_PREFIX_EXPENSE}{year_month}"

    try:
        items = ddb.query_by_pk(pk=pk, sk_prefix=sk_prefix)
    except Exception as e:
        logger.warning("get_monthly_spending_failed", error=str(e))
        return Decimal("0")

    total = Decimal("0")
    for item in items:
        amount = item.get("amount")
        if amount is not None:
            try:
                total += Decimal(str(amount))
            except (InvalidOperation, TypeError):
                logger.warning("invalid_expense_amount", value=str(amount))

    return total


def get_reward_budget(profile: dict) -> Decimal:
    """
    プロファイルから今月のご褒美予算を取得する。

    ボーナス月であれば bonus_amount の 10% をご褒美枠に加算する。
    reward_budget_monthly が未設定・無効の場合は DEFAULT_REWARD_BUDGET を返す。

    Args:
        profile: DynamoDB から取得した PROFILE# アイテム（dict）

    Returns:
        今月のご褒美予算（Decimal）
    """
    budget_raw = profile.get("reward_budget_monthly")
    if budget_raw is None:
        return DEFAULT_REWARD_BUDGET

    try:
        budget = Decimal(str(budget_raw))
    except (InvalidOperation, TypeError):
        return DEFAULT_REWARD_BUDGET

    if budget <= Decimal("0"):
        return DEFAULT_REWARD_BUDGET

    # ボーナス月チェック
    current_month = datetime.now(_JST).month
    bonus_months: list = profile.get("bonus_months") or []

    if current_month in bonus_months:
        bonus_amount_raw = profile.get("bonus_amount")
        if bonus_amount_raw is not None:
            try:
                bonus_amount = Decimal(str(bonus_amount_raw))
                # ボーナスの 10% をご褒美枠に加算
                budget += bonus_amount * Decimal("0.1")
                logger.info("bonus_month_budget_expanded", month=current_month)
            except (InvalidOperation, TypeError):
                pass

    return budget


def calculate_slack(
    user_id: str,
    ddb: DynamoDBService,
    profile: dict,
    year_month: Optional[str] = None,
) -> tuple[Decimal, Decimal]:
    """
    余裕額を算出する（繰り越し機能 F2-07 対応）。

    余裕額 = max(total_budget − 今月の支出合計, 0)
    total_budget = base_budget + carryover + bonus_amount

    Args:
        user_id:    LINE ユーザー ID
        ddb:        DynamoDB サービスインスタンス
        profile:    PROFILE# DynamoDB アイテム（dict）
        year_month: "YYYY-MM" 形式（None の場合は現在月）

    Returns:
        (slack, total_budget) のタプル
          slack:        余裕額（0 以上保証）
          total_budget: 今月の総ご褒美予算（繰り越し込み）
    """
    base_budget = get_reward_budget(profile)

    # 繰り越し計算（F2-07）
    carryover_rate = float(profile.get("carryover_rate", CARRYOVER_RATE))
    last_remaining = get_last_month_remaining(user_id, ddb)
    budget_info = calculate_monthly_budget(
        base_budget=int(base_budget),
        last_month_remaining=last_remaining,
        carryover_rate=carryover_rate,
    )
    total_budget = Decimal(str(budget_info["total_budget"]))

    spending = get_monthly_spending(user_id, ddb, year_month)
    slack = max(total_budget - spending, Decimal("0"))

    logger.info(
        "calculate_slack",
        base_budget=str(base_budget),
        carryover=str(budget_info["carryover_amount"]),
        total_budget=str(total_budget),
        spending=str(spending),
        slack=str(slack),
    )
    return slack, total_budget
