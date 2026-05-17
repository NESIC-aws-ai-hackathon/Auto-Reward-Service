"""
オンボーディングフロー — 状態機械

状態遷移:
  START → WAITING_INCOME → WAITING_FIXED_COSTS → CONFIRM_REWARD_BUDGET
        → WAITING_BONUS → WAITING_BIRTHDAY → COMPLETED

ご褒美枠算出: max(3000, min((月収 - 固定費総計) * 0.15, 30000))
金額抽出: regex ベース（「30万」→ 300000 / 「8万円」→ 80000 / 「50000」→ 50000）
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from services.dynamodb_service import DynamoDBService
from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 状態定数
# ─────────────────────────────────────────
STEP_WAITING_INCOME = "WAITING_INCOME"
STEP_WAITING_FIXED_COSTS = "WAITING_FIXED_COSTS"
STEP_CONFIRM_REWARD_BUDGET = "CONFIRM_REWARD_BUDGET"
STEP_WAITING_BONUS = "WAITING_BONUS"
STEP_WAITING_BIRTHDAY = "WAITING_BIRTHDAY"
STEP_COMPLETED = "COMPLETED"

# ─────────────────────────────────────────
# 返答テンプレート
# ─────────────────────────────────────────
MSG_WELCOME = (
    "はじめまして！リワードちゃんだよ✨\n"
    "あなたのお財布を守りながら、ちゃんとご褒美も楽しめるようサポートするね🎀\n\n"
    "まずは、毎月の手取り収入を教えて？（例: 25万、300000）"
)

MSG_ASK_FIXED_COSTS = (
    "ありがとう！\n次に、毎月かかる固定費を教えてね😊\n"
    "家賃・スマホ代・サブスクなどをまとめて教えてくれると嬉しいな✨\n"
    "（例:「家賃8万、スマホ1万、サブスク5千」または合計金額でもOK！）"
)

MSG_CONFIRM_BUDGET_TEMPLATE = (
    "計算してみたよ〜！\n"
    "毎月の手取り: {income:,}円\n"
    "固定費合計: {fixed:,}円\n"
    "→ ご褒美枠のおすすめ: **{budget:,}円/月** だよ🎉\n\n"
    "これでいい感じ？（「はい」か「変える」で教えてね）"
)

MSG_ASK_BONUS = (
    "了解だよ〜✨\n"
    "ボーナスはある？（「あり 6月と12月 60万」みたいに教えてもらえると嬉しい！）\n"
    "なければ「なし」でOK😊"
)

MSG_ASK_BIRTHDAY = (
    "最後に、誕生日を教えてもらえる？🎂（例: 8月20日）\n"
    "お誕生日前後にスペシャルなご褒美を提案するよ！\n"
    "教えたくない場合は「スキップ」でもOK✨"
)

MSG_COMPLETED = (
    "セットアップ完了！🎉\n"
    "これからリワードちゃんがお財布とご褒美を一緒に管理するね🎀\n"
    "何か買い物したり、疲れたときは気軽に話しかけてね！"
)

MSG_BUDGET_ADJUSTED = "わかった！それじゃあご褒美枠は {budget:,}円/月 で設定するね✨"
MSG_PARSE_ERROR_INCOME = "ごめん、金額がうまく読み取れなかったよ😢\n「25万」「300000」みたいに教えてね！"
MSG_PARSE_ERROR_FIXED = "固定費の金額がうまく読み取れなかった…\n合計金額（例: 15万）でもOKだよ😊"


# ─────────────────────────────────────────
# 金額抽出ユーティリティ
# ─────────────────────────────────────────
_MAN_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*万")
_DIGIT_PATTERN = re.compile(r"(\d{4,})")  # 4桁以上の数字を金額とみなす

def extract_amount(text: str) -> Optional[int]:
    """
    テキストから金額（円）を抽出する。

    優先順位:
    1. 「○万」形式（万円単位）
    2. 4桁以上の数字（円単位）

    Returns:
        抽出した金額（int 円）または None
    """
    # 万円パターン（合計を取る）
    man_matches = _MAN_PATTERN.findall(text)
    if man_matches:
        total = sum(float(m) * 10000 for m in man_matches)
        return int(total)

    # 4桁以上数字
    digit_matches = _DIGIT_PATTERN.findall(text)
    if digit_matches:
        # 最も大きい数字を金額とみなす
        return max(int(m) for m in digit_matches)

    return None


def _extract_multiple_amounts(text: str) -> list[int]:
    """「家賃8万、スマホ1万、5000円」のように複数金額を含むテキストから全て抽出する。"""
    amounts: list[int] = []

    # 万円パターン
    for m in _MAN_PATTERN.finditer(text):
        amounts.append(int(float(m.group(1)) * 10000))

    # 万を含まない数字（1000以上）
    # 万パターンで消費した部分を除いてから探す
    text_without_man = _MAN_PATTERN.sub("", text)
    for m in re.finditer(r"(\d{3,})", text_without_man):
        amounts.append(int(m.group(1)))

    return amounts


def _extract_birthday(text: str) -> Optional[str]:
    """
    テキストから誕生日を抽出し「MM-DD」形式で返す。

    対応形式:
    - 「8月20日」→ "08-20"
    - 「8/20」→ "08-20"
    - 「08-20」→ "08-20"
    """
    # 「X月Y日」形式
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{month:02d}-{day:02d}"

    # 「X/Y」形式
    m = re.search(r"(\d{1,2})/(\d{1,2})", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{month:02d}-{day:02d}"

    # 「MM-DD」形式
    m = re.search(r"(\d{2})-(\d{2})", text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{month:02d}-{day:02d}"

    return None


def _calc_reward_budget(income: int, fixed_costs: int) -> int:
    """ご褒美枠を算出する。max(3000, min(余剰 * 0.15, 30000))"""
    surplus = max(0, income - fixed_costs)
    return max(3000, min(int(surplus * 0.15), 30000))


def _is_affirmative(text: str) -> bool:
    """肯定応答かどうかを判定する。"""
    affirmatives = {"はい", "yes", "ok", "うん", "そうです", "そう", "いいよ", "おけ", "了解", "決定", "それで", "それでいい"}
    text_lower = text.lower().strip()
    return any(a in text_lower for a in affirmatives)


def _is_skip(text: str) -> bool:
    """スキップ指示かどうかを判定する。"""
    skips = {"スキップ", "skip", "なし", "ない", "いいえ", "no", "教えない"}
    text_lower = text.lower().strip()
    return any(s in text_lower for s in skips)


# ─────────────────────────────────────────
# オンボーディング状態管理
# ─────────────────────────────────────────
def _get_onboarding_state(user_id: str, ddb_service: DynamoDBService) -> dict:
    """DynamoDB からオンボーディング状態を取得する。"""
    pk = f"USER#{user_id}"
    item = ddb_service.get_item(pk=pk, sk="ONBOARDING_STATE#")
    return item or {}


def _save_onboarding_state(user_id: str, state: dict, ddb_service: DynamoDBService) -> None:
    """オンボーディング状態を DynamoDB に保存する。"""
    pk = f"USER#{user_id}"
    now = datetime.now(timezone.utc).isoformat()
    # TTL: 7日後（未完了オンボーディング自動削除）
    ttl = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())

    item = {
        "step": state.get("step", STEP_WAITING_INCOME),
        "monthly_income": state.get("monthly_income"),
        "fixed_costs_total": state.get("fixed_costs_total"),
        "reward_budget": state.get("reward_budget"),
        "bonus_months": state.get("bonus_months"),
        "bonus_amount": state.get("bonus_amount"),
        "birthday": state.get("birthday"),
        "updatedAt": now,
        "ttl": ttl,
    }
    # None 値を除去
    item = {k: v for k, v in item.items() if v is not None}
    ddb_service.put_item(pk, "ONBOARDING_STATE#", item)


def _complete_onboarding(user_id: str, state: dict, ddb_service: DynamoDBService) -> None:
    """
    オンボーディング完了 — UserProfile に情報を書き込む。
    """
    pk = f"USER#{user_id}"
    now = datetime.now(timezone.utc).isoformat()

    updates: dict = {
        "status": "ACTIVE",
        "updatedAt": now,
    }
    if state.get("monthly_income") is not None:
        updates["monthly_income"] = Decimal(str(state["monthly_income"]))
    if state.get("reward_budget") is not None:
        updates["reward_budget_monthly"] = Decimal(str(state["reward_budget"]))
    if state.get("birthday"):
        updates["birthday"] = state["birthday"]
    if state.get("bonus_months"):
        updates["bonus_months"] = state["bonus_months"]
    if state.get("bonus_amount"):
        updates["bonus_amount"] = state["bonus_amount"]

    ddb_service.update_item(pk=pk, sk="PROFILE#", updates=updates)

    # オンボーディング状態を COMPLETED に更新（TTL は延長しない）
    _save_onboarding_state(user_id, {"step": STEP_COMPLETED}, ddb_service)


# ─────────────────────────────────────────
# メインハンドラー
# ─────────────────────────────────────────
def handle_onboarding(
    user_id: str,
    text: Optional[str],
    ddb_service: DynamoDBService,
) -> str:
    """
    オンボーディングフローを処理する。

    現在の状態を DynamoDB から読み込み、ユーザーの入力を処理して次の状態に遷移する。
    text=None の場合は初回起動（follow イベント・初回メッセージフォールバック）とみなし、
    ウェルカムメッセージを返す。

    Args:
        user_id: LINE ユーザー ID
        text: ユーザーのメッセージ本文（None の場合はオンボーディング初回起動）
        ddb_service: DynamoDB サービスインスタンス

    Returns:
        リワードちゃんの返答テキスト
    """
    # text=None → 初回起動（follow イベント・初回メッセージフォールバック）
    if text is None:
        return start_onboarding(user_id, ddb_service)

    state = _get_onboarding_state(user_id, ddb_service)
    step = state.get("step", STEP_WAITING_INCOME)

    logger.info("handle_onboarding", user_id=user_id, step=step)

    # ─ WAITING_INCOME ─
    if step == STEP_WAITING_INCOME:
        amount = extract_amount(text)
        if amount is None or amount < 50000:  # 5万未満は誤入力とみなす
            return MSG_PARSE_ERROR_INCOME

        state["monthly_income"] = amount
        state["step"] = STEP_WAITING_FIXED_COSTS
        _save_onboarding_state(user_id, state, ddb_service)
        return MSG_ASK_FIXED_COSTS

    # ─ WAITING_FIXED_COSTS ─
    if step == STEP_WAITING_FIXED_COSTS:
        amounts = _extract_multiple_amounts(text)
        if not amounts:
            return MSG_PARSE_ERROR_FIXED

        fixed_total = sum(amounts)
        reward_budget = _calc_reward_budget(
            state.get("monthly_income", 0), fixed_total
        )
        state["fixed_costs_total"] = fixed_total
        state["reward_budget"] = reward_budget
        state["step"] = STEP_CONFIRM_REWARD_BUDGET
        _save_onboarding_state(user_id, state, ddb_service)

        return MSG_CONFIRM_BUDGET_TEMPLATE.format(
            income=state.get("monthly_income", 0),
            fixed=fixed_total,
            budget=reward_budget,
        )

    # ─ CONFIRM_REWARD_BUDGET ─
    if step == STEP_CONFIRM_REWARD_BUDGET:
        if _is_affirmative(text):
            state["step"] = STEP_WAITING_BONUS
            _save_onboarding_state(user_id, state, ddb_service)
            return MSG_ASK_BONUS
        else:
            # 金額変更の試み
            new_amount = extract_amount(text)
            if new_amount is not None and new_amount >= 1000:
                state["reward_budget"] = new_amount
                state["step"] = STEP_WAITING_BONUS
                _save_onboarding_state(user_id, state, ddb_service)
                return MSG_BUDGET_ADJUSTED.format(budget=new_amount) + "\n\n" + MSG_ASK_BONUS
            # 再確認
            state["step"] = STEP_WAITING_FIXED_COSTS
            _save_onboarding_state(user_id, state, ddb_service)
            return "わかった！もう一度固定費を教えてね😊\n" + MSG_ASK_FIXED_COSTS

    # ─ WAITING_BONUS ─
    if step == STEP_WAITING_BONUS:
        if not _is_skip(text):
            # ボーナス月と金額を抽出
            months: list[int] = []
            for m in re.finditer(r"(\d{1,2})\s*月", text):
                month = int(m.group(1))
                if 1 <= month <= 12:
                    months.append(month)

            bonus_amounts = _extract_multiple_amounts(text)
            # 月数値と重複する場合を除外（「6月 60万」の 6 を金額とみなさない）
            bonus_amounts = [a for a in bonus_amounts if a >= 10000]

            if months:
                state["bonus_months"] = sorted(set(months))
            if bonus_amounts:
                state["bonus_amount"] = max(bonus_amounts)  # 最大値をボーナス額とみなす

        state["step"] = STEP_WAITING_BIRTHDAY
        _save_onboarding_state(user_id, state, ddb_service)
        return MSG_ASK_BIRTHDAY

    # ─ WAITING_BIRTHDAY ─
    if step == STEP_WAITING_BIRTHDAY:
        if not _is_skip(text):
            birthday = _extract_birthday(text)
            if birthday:
                state["birthday"] = birthday

        # オンボーディング完了
        _complete_onboarding(user_id, state, ddb_service)
        return MSG_COMPLETED

    # COMPLETED（再オンボーディング要求などで呼ばれた場合）
    return "もうセットアップは完了してるよ✨ 何か変えたいことがあれば教えてね！"


def start_onboarding(user_id: str, ddb_service: DynamoDBService) -> str:
    """
    オンボーディングを開始（follow イベント時 or 明示的な開始要求）。

    DynamoDB に初期状態を保存してウェルカムメッセージを返す。
    """
    state = {"step": STEP_WAITING_INCOME}
    _save_onboarding_state(user_id, state, ddb_service)
    return MSG_WELCOME
