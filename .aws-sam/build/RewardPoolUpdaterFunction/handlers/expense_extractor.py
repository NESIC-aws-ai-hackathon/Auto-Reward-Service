"""
支出抽出ハンドラ

ユーザーテキストから支出情報を抽出し、確認・明確化フローを管理する。

Reply-First パターン: 呼び出し元 (webhook_handler) が LINE に返信後に
_save_expense_items() を呼んで DynamoDB 保存を行う。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from models.schemas import (
    ARS_CATEGORIES,
    SK_PREFIX_EXPENSE,
    SK_PREFIX_MONTHLY_SUMMARY,
    SK_PENDING_EXPENSE,
    SK_PENDING_CLARIFICATION,
)
from services.bedrock_service import get_bedrock_service
from services.dynamodb_service import DynamoDBService
from prompts.expense_prompt import (
    build_expense_prompt,
    build_clarification_prompt,
    _SYSTEM_PROMPT,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# 金額の有効範囲 (BR-3-03)
_AMOUNT_MIN = 1
_AMOUNT_MAX = 9_999_999

# 確信度しきい値
_CONFIDENCE_THRESHOLD = 0.7

# TTL
_CLARIFICATION_TTL_SECONDS = 10 * 60         # 10 分
_PENDING_EXPENSE_TTL_SECONDS = 24 * 60 * 60  # 24 時間

# リトライ上限 (BR-3-02)
_CLARIFICATION_MAX_RETRY = 2

# デフォルト月次ご褒美予算（プロフィール未設定時）
_DEFAULT_REWARD_BUDGET = 30_000


# ─────────────────────────────────────────
# 公開関数
# ─────────────────────────────────────────

def extract(
    text: str,
    user_id: str,
    ddb: DynamoDBService,
) -> tuple[str, list[dict]]:
    """テキストから支出を抽出する。

    Returns:
        (reply_text, items_to_save) のタプル。
        items_to_save は webhook_handler が post-reply で DDB に保存する。
    """
    pk = f"USER#{user_id}"

    # PENDING_CLARIFICATION チェック（先に処理）
    pending_clarif = ddb.get_item(pk=pk, sk=SK_PENDING_CLARIFICATION)
    if pending_clarif:
        return handle_clarification(text, user_id, pending_clarif, ddb)

    # LLM で抽出
    prompt = build_expense_prompt(text)
    try:
        raw = get_bedrock_service().invoke_text(
            prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=1000,
        )
        parsed = _parse_json(raw)
    except Exception as e:
        logger.warning("expense_extract_llm_error", error=str(e))
        return _non_expense_reply(), []

    if not parsed.get("is_expense", False):
        return _non_expense_reply(), []

    items_raw: list[dict] = parsed.get("items", [])
    if not items_raw:
        return _non_expense_reply(), []

    items_to_save: list[dict] = []
    clarif_needed: list[dict] = []
    confirm_needed: list[dict] = []

    for item in items_raw:
        item = _normalize_item(item)
        amount = item.get("amount")
        confidence = item.get("confidence", 1.0)

        # SEC-3-03: 金額範囲外 → confidence=0.0
        if amount is not None:
            if not (_AMOUNT_MIN <= amount <= _AMOUNT_MAX):
                item["confidence"] = 0.0
                confidence = 0.0

        if amount is None:
            clarif_needed.append(item)
        elif confidence < _CONFIDENCE_THRESHOLD:
            confirm_needed.append(item)
        else:
            items_to_save.append(item)

    # 追加質問が必要な場合（最初のアイテムのみ）
    if clarif_needed:
        first = clarif_needed[0]
        _save_pending_clarification(pk, [first], ddb)
        item_label = first.get("item_name") or "お買い物"
        return (
            f"「{item_label}」いくらだったの？金額を教えてくれると記録するよ🍮",
            items_to_save,
        )

    # 確認待ちアイテムが存在
    if confirm_needed:
        first = confirm_needed[0]
        amount_str = f"{first['amount']:,}" if first.get("amount") else "?"
        item_label = first.get("item_name") or "お買い物"
        _save_pending_expense(pk, first, first.get("raw_text", ""), ddb)
        reply = (
            f"「{item_label}」{amount_str}円でいいかな？\n"
            f"「はい」で記録するね🍮"
        )
        return reply, items_to_save

    if not items_to_save:
        return _non_expense_reply(), []

    # 月次集計取得→返信テキスト構築
    month_sk = _month_sk()
    monthly = ddb.get_item(pk=pk, sk=month_sk) or {}
    current_total = int(monthly.get("total_amount", 0))
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    reward_budget = int(profile.get("reward_budget_monthly", _DEFAULT_REWARD_BUDGET))

    added_total = sum(it.get("amount", 0) for it in items_to_save)
    new_total = current_total + added_total
    remaining = max(0, reward_budget - new_total)

    reply = _build_saved_reply(items_to_save, new_total, remaining)
    return reply, items_to_save


def handle_clarification(
    text: str,
    user_id: str,
    pending: dict,
    ddb: DynamoDBService,
) -> tuple[str, list[dict]]:
    """PENDING_CLARIFICATION の追加質問への回答を処理する。"""
    pk = f"USER#{user_id}"
    retry_count = int(pending.get("retry_count", 0))
    partial_items: list[dict] = pending.get("partial_items", [])

    # リトライ上限
    if retry_count >= _CLARIFICATION_MAX_RETRY:
        ddb.delete_item(pk=pk, sk=SK_PENDING_CLARIFICATION)
        return "ごめんね、金額が分からなかったから今回は記録しないね🥲\nまた教えてね！", []

    # LLM で金額を再抽出
    prompt = build_clarification_prompt(text, partial_items)
    try:
        raw = get_bedrock_service().invoke_text(
            prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=500,
        )
        parsed = _parse_json(raw)
    except Exception as e:
        logger.warning("clarification_llm_error", error=str(e))
        parsed = {}

    items_raw: list[dict] = parsed.get("items", [])
    recovered = None
    if items_raw:
        item = _normalize_item(items_raw[0])
        # partial_items の情報でパッチ
        if partial_items:
            base = partial_items[0]
            item["item_name"] = item.get("item_name") or base.get("item_name")
            item["store_name"] = item.get("store_name") or base.get("store_name")
            item["category"] = item.get("category") or base.get("category", "その他")
        if item.get("amount") is not None:
            recovered = item

    if recovered is None:
        # まだ金額不明 → retry_count++ して再質問
        new_retry = retry_count + 1
        now = datetime.now(timezone.utc).isoformat()
        ttl = int((datetime.now(timezone.utc) + timedelta(seconds=_CLARIFICATION_TTL_SECONDS)).timestamp())
        ddb.put_item(pk, SK_PENDING_CLARIFICATION, {
            **pending,
            "retry_count": new_retry,
            "updatedAt": now,
            "ttl": ttl,
        })
        item_label = partial_items[0].get("item_name") if partial_items else "お買い物"
        return f"金額が読み取れなかったよ😅「{item_label}」の金額をもう一度教えてね（例: 320円）", []

    # 成功 → PENDING_CLARIFICATION 削除
    ddb.delete_item(pk=pk, sk=SK_PENDING_CLARIFICATION)

    # 確信度チェック
    confidence = recovered.get("confidence", 1.0)
    amount = recovered.get("amount")
    if amount is not None and not (_AMOUNT_MIN <= amount <= _AMOUNT_MAX):
        recovered["confidence"] = 0.0
        confidence = 0.0

    if confidence < _CONFIDENCE_THRESHOLD:
        amount_str = f"{amount:,}" if amount else "?"
        item_label = recovered.get("item_name") or "お買い物"
        _save_pending_expense(pk, recovered, text, ddb)
        return (
            f"「{item_label}」{amount_str}円でいいかな？「はい」で記録するね🍮",
            [],
        )

    # 月次集計
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    reward_budget = int(profile.get("reward_budget_monthly", _DEFAULT_REWARD_BUDGET))
    month_sk = _month_sk()
    monthly = ddb.get_item(pk=pk, sk=month_sk) or {}
    current_total = int(monthly.get("total_amount", 0))
    new_total = current_total + (amount or 0)
    remaining = max(0, reward_budget - new_total)

    return _build_saved_reply([recovered], new_total, remaining), [recovered]


def confirm_pending_expense(
    user_id: str,
    pending: dict,
    ddb: DynamoDBService,
) -> tuple[str, list[dict]]:
    """PENDING_EXPENSE を確認・保存する。"""
    pk = f"USER#{user_id}"
    ddb.delete_item(pk=pk, sk=SK_PENDING_EXPENSE)

    item = pending.get("extracted", {})
    amount = item.get("amount", 0)

    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    reward_budget = int(profile.get("reward_budget_monthly", _DEFAULT_REWARD_BUDGET))
    month_sk = _month_sk()
    monthly = ddb.get_item(pk=pk, sk=month_sk) or {}
    current_total = int(monthly.get("total_amount", 0))
    new_total = current_total + int(amount)
    remaining = max(0, reward_budget - new_total)

    return _build_saved_reply([item], new_total, remaining), [item]


def reject_pending_expense(
    user_id: str,
    ddb: DynamoDBService,
) -> str:
    """PENDING_EXPENSE を削除（記録しない）。"""
    pk = f"USER#{user_id}"
    ddb.delete_item(pk=pk, sk=SK_PENDING_EXPENSE)
    return "わかった、今回は記録しないね🙅\nまた何か買ったら教えてね！"


# ─────────────────────────────────────────
# 内部ヘルパー
# ─────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    """LLM レスポンスから JSON を抽出する。"""
    text = raw.strip()
    # コードブロックを除去
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    # 最初の { ... } を抽出
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        logger.warning("json_parse_failed", raw=text[:200])
        return {}


def _normalize_item(item: dict) -> dict:
    """カテゴリバリデーション・型変換を行う。"""
    cat = item.get("category", "その他")
    if cat not in ARS_CATEGORIES:
        cat = "その他"
    amount = item.get("amount")
    if amount is not None:
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            amount = None
    return {
        "item_name": item.get("item_name"),
        "amount": amount,
        "store_name": item.get("store_name"),
        "category": cat,
        "confidence": float(item.get("confidence", 1.0)),
    }


def _save_pending_clarification(pk: str, partial_items: list[dict], ddb: DynamoDBService) -> None:
    now = datetime.now(timezone.utc).isoformat()
    ttl = int((datetime.now(timezone.utc) + timedelta(seconds=_CLARIFICATION_TTL_SECONDS)).timestamp())
    ddb.put_item(pk, SK_PENDING_CLARIFICATION, {
        "waiting_for": "amount",
        "partial_items": partial_items,
        "retry_count": 0,
        "created_at": now,
        "ttl": ttl,
    })


def _save_pending_expense(pk: str, item: dict, raw_text: str, ddb: DynamoDBService) -> None:
    now = datetime.now(timezone.utc).isoformat()
    ttl = int((datetime.now(timezone.utc) + timedelta(seconds=_PENDING_EXPENSE_TTL_SECONDS)).timestamp())
    ddb.put_item(pk, SK_PENDING_EXPENSE, {
        "extracted": item,
        "confidence": item.get("confidence", 0.0),
        "raw_text": raw_text,
        "status": "AWAITING_CONFIRM",
        "expires_at": datetime.fromtimestamp(ttl, tz=timezone.utc).isoformat(),
        "created_at": now,
        "ttl": ttl,
    })


def _build_saved_reply(items: list[dict], new_total: int, remaining: int) -> str:
    """保存確認メッセージを構築する。"""
    if len(items) == 1:
        item = items[0]
        item_label = item.get("item_name") or item.get("category") or "お買い物"
        amount = item.get("amount", 0)
        first_line = f"「{item_label}」{amount:,}円ね、覚えた〜🍮"
    else:
        lines = []
        for it in items:
            label = it.get("item_name") or it.get("category") or "お買い物"
            lines.append(f"・{label} {it.get('amount', 0):,}円")
        first_line = "\n".join(lines) + "\n全部覚えたよ〜🍮"

    return (
        f"{first_line}\n"
        f"今月のご褒美は合計 {new_total:,}円。"
        f"まだ {remaining:,}円使えるよ！"
    )


def _non_expense_reply() -> str:
    """支出でない場合は空文字を返す（webhook_handler が通常返信フローに委譲）。"""
    return ""


def _month_sk() -> str:
    """今月の SK を返す（例: MONTHLY_SUMMARY#2026-05）。"""
    return SK_PREFIX_MONTHLY_SUMMARY + datetime.now(timezone.utc).strftime("%Y-%m")
