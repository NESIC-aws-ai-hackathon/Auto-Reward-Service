"""
クイック支出入力 — リッチメニュー「📝 支出を記録」

postback action=quick_expense で呼ばれ、カテゴリ選択→金額入力の2ステップで支出を記録。
状態管理: QUICK_EXPENSE_STATE# (TTL: 10分)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from services.dynamodb_service import DynamoDBService
from utils.logger import get_logger

logger = get_logger(__name__)

SK_QUICK_EXPENSE = "QUICK_EXPENSE_STATE#"

QUICK_CATEGORIES = [
    ("☕", "カフェ"),
    ("🍽️", "ランチ"),
    ("🍰", "スイーツ"),
    ("📚", "本・漫画"),
    ("🎮", "ゲーム"),
    ("💊", "日用品"),
]


def show_quick_expense_options(user_id: str) -> list[dict]:
    """カテゴリ選択のクイックリプライ付きメッセージを返す"""
    items = [
        {
            "type": "action",
            "action": {"type": "message", "label": f"{emoji} {name}", "text": f"{emoji} {name}"},
        }
        for emoji, name in QUICK_CATEGORIES
    ]
    items.append({
        "type": "action",
        "action": {"type": "message", "label": "✏️ 直接入力", "text": "✏️ 直接入力"},
    })

    return [{
        "type": "text",
        "text": "何に使った？🎀",
        "quickReply": {"items": items},
    }]


def handle_quick_expense_reply(
    user_id: str, text: str, state: dict, ddb: DynamoDBService
) -> tuple[list[dict], list[dict]]:
    """クイック支出入力の中間状態を処理する。(messages, items_to_save) を返す"""
    step = state.get("step", "")
    pk = f"USER#{user_id}"

    if step == "WAITING_CATEGORY":
        # カテゴリ確定 → 金額質問
        category = _extract_category(text)
        if category == "直接入力":
            ddb.delete_item(pk, SK_QUICK_EXPENSE)
            return [{"type": "text", "text": "OK！何にいくら使ったか教えてね🎀\n（例: カフェ 650円）"}], []

        ttl = int(time.time()) + 600
        ddb.put_item(pk, SK_QUICK_EXPENSE, {
            "step": "WAITING_AMOUNT",
            "category": category,
            "ttl": ttl,
        })
        return [{"type": "text", "text": f"{category}ね！いくらだった？"}], []

    elif step == "WAITING_AMOUNT":
        # 金額確定 → 記録
        category = state.get("category", "その他")
        amount = _extract_amount(text)
        ddb.delete_item(pk, SK_QUICK_EXPENSE)

        if amount is None or amount <= 0:
            return [{"type": "text", "text": "金額がわからなかったよ😅 数字で教えてね！"}], []

        items_to_save = [{"item_name": category, "amount": amount, "category": category, "source": "quick"}]

        # 残予算を表示
        remaining_text = ""
        try:
            from services.finance_engine import calculate_slack
            profile = ddb.get_item(pk=f"USER#{user_id}", sk="PROFILE#") or {}
            slack, _ = calculate_slack(user_id, ddb, profile)
            # 記録後の残予算（まだ DB 未保存なので slack から amount を差し引いて推定）
            remaining = max(int(slack) - amount, 0)
            remaining_text = f"\n今月の残り: {remaining:,}円"
        except Exception:
            pass

        reply = f"{category} {amount}円ね、覚えた〜✨{remaining_text}"
        return [{"type": "text", "text": reply}], items_to_save

    else:
        ddb.delete_item(pk, SK_QUICK_EXPENSE)
        return [{"type": "text", "text": "ん？最初からやり直してね🎀"}], []


def start_quick_expense_state(user_id: str, ddb: DynamoDBService) -> None:
    """クイック支出の WAITING_CATEGORY 状態を開始"""
    pk = f"USER#{user_id}"
    ttl = int(time.time()) + 600
    ddb.put_item(pk, SK_QUICK_EXPENSE, {
        "step": "WAITING_CATEGORY",
        "ttl": ttl,
    })


def _extract_category(text: str) -> str:
    """テキストからカテゴリを判定"""
    for emoji, name in QUICK_CATEGORIES:
        if name in text or emoji in text:
            return name
    if "直接" in text:
        return "直接入力"
    return text.strip()[:10]


def _extract_amount(text: str) -> int | None:
    """テキストから金額を抽出"""
    import re
    text = text.replace(",", "").replace("，", "").replace("円", "").strip()
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    return None
