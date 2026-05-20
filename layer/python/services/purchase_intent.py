"""
購入意図分類 (classifyPurchaseIntent) と安全チェック (validateBeforePurchase)

変更依頼書_2 §20, §21 準拠
"""
from __future__ import annotations

import re
from typing import Optional


# ─────────────────────────────────────────
# 購入意図分類
# ─────────────────────────────────────────
DECLINE_PATTERNS: list[str] = [
    "いらない",
    "やめる",
    "買わない",
    "戻して",
    "カートから出して",
    "今回はなし",
    "まだいい",
    "熟成させる",
    "やっぱいい",
    "やめとく",
    "キャンセル",
    "取り消し",
]

AMBIGUOUS_BUY_PATTERNS: list[str] = [
    "買って",
    "お願い",
    "いいよ",
    "OK",
    "ok",
    "はい",
    "任せる",
    "欲しい",
    "買いたい",
    "それで",
    "おすすめなら",
    "すすめて",
    "買っちゃおう",
    "ほしい",
    "いいね",
    "ありがと",
]

EXPLICIT_PURCHASE_PATTERNS: list[re.Pattern] = [
    re.compile(r"この商品を購入して"),
    re.compile(r"この内容で購入して"),
    re.compile(r"注文を確定して"),
    re.compile(r"この商品を注文して"),
    re.compile(r"はい、購入を確定します"),
    re.compile(r".+を購入して$"),
    re.compile(r"購入を確定"),
    re.compile(r"注文して$"),
]


def classify_purchase_intent(message: str, product_title: Optional[str] = None) -> str:
    """
    ユーザー発話を購入意図に分類する。

    Returns:
        "DECLINE" | "AMBIGUOUS_BUY" | "EXPLICIT_PURCHASE" | "OTHER"
    """
    text = message.strip()

    # 明示購入パターンを最優先でチェック
    for pattern in EXPLICIT_PURCHASE_PATTERNS:
        if pattern.search(text):
            return "EXPLICIT_PURCHASE"

    # 商品名指定の購入パターン
    if product_title and product_title in text and "購入" in text:
        return "EXPLICIT_PURCHASE"

    # 拒否パターン
    for keyword in DECLINE_PATTERNS:
        if keyword in text:
            return "DECLINE"

    # 曖昧な購入意思
    for keyword in AMBIGUOUS_BUY_PATTERNS:
        if keyword in text:
            return "AMBIGUOUS_BUY"

    return "OTHER"


# ─────────────────────────────────────────
# 安全チェック
# ─────────────────────────────────────────
def validate_before_purchase(
    *,
    status: str,
    price: float,
    quantity: int,
    explicit_approval_text: Optional[str],
    product_title: str,
    max_allowed_price: float,
    is_subscription: bool = False,
    payment_method_changed: bool = False,
    shipping_address_changed: bool = False,
) -> dict:
    """
    購入前安全チェック。

    Returns:
        {"ok": bool, "reasons": list[str]}
    """
    reasons: list[str] = []

    if status != "PURCHASE_APPROVED":
        reasons.append(f"ステータスが PURCHASE_APPROVED ではありません: {status}")

    if not explicit_approval_text:
        reasons.append("明示承認テキストがありません")
    elif classify_purchase_intent(explicit_approval_text, product_title) != "EXPLICIT_PURCHASE":
        reasons.append("明示承認テキストが明示購入文として判定されませんでした")

    if price > max_allowed_price:
        reasons.append(f"価格 {price} が上限 {max_allowed_price} を超過しています")

    if quantity != 1:
        reasons.append(f"数量が 1 ではありません: {quantity}")

    if is_subscription:
        reasons.append("定期便が検出されました")

    if payment_method_changed:
        reasons.append("支払い方法が変更されています")

    if shipping_address_changed:
        reasons.append("配送先が変更されています")

    return {"ok": len(reasons) == 0, "reasons": reasons}
