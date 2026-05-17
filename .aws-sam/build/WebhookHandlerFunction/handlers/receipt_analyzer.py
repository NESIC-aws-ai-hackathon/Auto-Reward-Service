"""
レシート画像解析ハンドラ

LINE から送られた画像を Bedrock Nova Lite (マルチモーダル) で解析する。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

from models.schemas import (
    ARS_CATEGORIES,
    SK_PREFIX_MONTHLY_SUMMARY,
    SK_PENDING_EXPENSE,
)
from services.bedrock_service import get_bedrock_service
from services.dynamodb_service import DynamoDBService
from prompts.receipt_prompt import RECEIPT_TEXT_PROMPT, RECEIPT_SYSTEM_PROMPT
from utils.logger import get_logger

logger = get_logger(__name__)

_AMOUNT_MIN = 1
_AMOUNT_MAX = 9_999_999
_CONFIDENCE_THRESHOLD = 0.7
_PENDING_EXPENSE_TTL_SECONDS = 24 * 60 * 60  # 24 時間
_DEFAULT_REWARD_BUDGET = 30_000


def analyze(
    image_bytes: bytes,
    content_type: str,
    user_id: str,
    ddb: DynamoDBService,
) -> tuple[str, list[dict]]:
    """レシート画像を解析して支出情報を抽出する。

    Args:
        image_bytes: LINE から取得した画像バイナリ
        content_type: "image/jpeg" など
        user_id: LINE ユーザー ID
        ddb: DynamoDB サービス

    Returns:
        (reply_text, items_to_save) のタプル。
        items_to_save は webhook_handler が post-reply で DDB に保存する。
    """
    pk = f"USER#{user_id}"

    try:
        raw = get_bedrock_service().invoke_image(
            prompt=RECEIPT_TEXT_PROMPT,
            image_bytes=image_bytes,
            media_type=content_type,
            max_tokens=1500,
        )
        parsed = _parse_json(raw)
    except Exception as e:
        logger.warning("receipt_analyze_llm_error", error=str(e))
        return _failed_reply(), []

    if parsed.get("parse_failed", False):
        return _failed_reply(), []

    items_raw: list[dict] = parsed.get("items", [])
    if not items_raw:
        # アイテムなし → total_amount のみある場合は1件として扱う
        total = parsed.get("total_amount")
        if total:
            items_raw = [{
                "item_name": None,
                "amount": total,
                "category": "その他",
                "confidence": parsed.get("confidence", 0.8),
            }]

    if not items_raw:
        return _failed_reply(), []

    store_name = parsed.get("store_name")
    items_to_save: list[dict] = []
    confirm_needed: list[dict] = []

    for item in items_raw:
        item = _normalize_item(item, store_name)
        amount = item.get("amount")
        confidence = item.get("confidence", 1.0)

        if amount is not None and not (_AMOUNT_MIN <= amount <= _AMOUNT_MAX):
            item["confidence"] = 0.0
            confidence = 0.0

        if confidence < _CONFIDENCE_THRESHOLD:
            confirm_needed.append(item)
        else:
            items_to_save.append(item)

    # 確認待ちアイテム（先頭のみ）
    if confirm_needed and not items_to_save:
        first = confirm_needed[0]
        amount = first.get("amount")
        amount_str = f"{amount:,}" if amount else "?"
        item_label = first.get("item_name") or store_name or "お買い物"
        _save_pending_expense(pk, first, ddb)
        return (
            f"レシート読んだよ📄「{item_label}」{amount_str}円でいいかな？\n"
            f"「はい」で記録するね🍮",
            [],
        )

    if not items_to_save:
        return _failed_reply(), []

    # 月次集計→返信
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    reward_budget = int(profile.get("reward_budget_monthly", _DEFAULT_REWARD_BUDGET))
    month_sk = SK_PREFIX_MONTHLY_SUMMARY + datetime.now(timezone.utc).strftime("%Y-%m")
    monthly = ddb.get_item(pk=pk, sk=month_sk) or {}
    current_total = int(monthly.get("total_amount", 0))

    added_total = sum(it.get("amount", 0) or 0 for it in items_to_save)
    new_total = current_total + added_total
    remaining = max(0, reward_budget - new_total)

    reply = _build_receipt_reply(items_to_save, store_name, new_total, remaining)
    return reply, items_to_save


# ─────────────────────────────────────────
# 内部ヘルパー
# ─────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        logger.warning("receipt_json_parse_failed", raw=text[:200])
        return {}


def _normalize_item(item: dict, store_name: str | None) -> dict:
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
        "store_name": item.get("store_name") or store_name,
        "category": cat,
        "confidence": float(item.get("confidence", 1.0)),
        "source": "receipt_image",
    }


def _save_pending_expense(pk: str, item: dict, ddb: DynamoDBService) -> None:
    now = datetime.now(timezone.utc).isoformat()
    ttl = int((datetime.now(timezone.utc) + timedelta(seconds=_PENDING_EXPENSE_TTL_SECONDS)).timestamp())
    ddb.put_item(pk, SK_PENDING_EXPENSE, {
        "extracted": item,
        "confidence": item.get("confidence", 0.0),
        "raw_text": "",
        "status": "AWAITING_CONFIRM",
        "expires_at": datetime.fromtimestamp(ttl, tz=timezone.utc).isoformat(),
        "created_at": now,
        "ttl": ttl,
    })


def _build_receipt_reply(
    items: list[dict],
    store_name: str | None,
    new_total: int,
    remaining: int,
) -> str:
    store_label = f"「{store_name}」の" if store_name else ""
    if len(items) == 1:
        item = items[0]
        item_label = item.get("item_name") or "お買い物"
        amount = item.get("amount", 0)
        first_line = f"レシート読んだよ📄{store_label}「{item_label}」{amount:,}円ね、覚えた〜🍮"
    else:
        lines = [f"レシート読んだよ📄{store_label}"]
        for it in items:
            label = it.get("item_name") or "不明"
            lines.append(f"・{label} {it.get('amount', 0):,}円")
        first_line = "\n".join(lines) + "\n全部覚えたよ〜🍮"

    return (
        f"{first_line}\n"
        f"今月のご褒美は合計 {new_total:,}円。"
        f"まだ {remaining:,}円使えるよ！"
    )


def _failed_reply() -> str:
    return (
        "レシートが読み取れなかったよ😅\n"
        "金額と何を買ったかをテキストで教えてくれると記録できるよ！"
    )
