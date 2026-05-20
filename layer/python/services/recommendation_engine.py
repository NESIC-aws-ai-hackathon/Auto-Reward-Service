"""
レコメンド生成エンジン

変更依頼書_2 §6 準拠 — 欲望在庫からの最適なレコメンド生成
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from services.dynamodb_service import DynamoDBService
from services.wishlist_service import get_active_items_for_recommendation
from services.bedrock_service import BedrockService
from models.schemas import SK_PREFIX_RECOMMENDATION
from utils.logger import get_logger

logger = get_logger(__name__)


def generate_recommendation(
    user_id: str,
    ddb: DynamoDBService,
    *,
    max_price: Optional[float] = None,
    fatigue_level: Optional[int] = None,
) -> Optional[dict]:
    """
    ユーザーの欲望在庫・余剰費・疲労度から最適な商品レコメンドを生成する。

    Returns:
        Recommendation dict or None
    """
    pk = f"USER#{user_id}"

    # ユーザー設定取得
    profile = ddb.get_item(pk=pk, sk="PROFILE#") or {}
    monthly_summary = _get_current_monthly_summary(pk, ddb)
    remaining = int(monthly_summary.get("remaining", 0)) if monthly_summary else 0

    # 上限金額決定
    effective_max = max_price or remaining or 5000

    # ACTIVE な欲望在庫を取得
    candidates = get_active_items_for_recommendation(user_id, ddb, max_price=effective_max)

    if not candidates:
        logger.info("no_recommendation_candidates", user_id=user_id)
        return None

    # 過去のDECLINED履歴を除外
    declined_urls = _get_declined_urls(pk, ddb)
    candidates = [c for c in candidates if c.get("product_url") not in declined_urls]

    if not candidates:
        return None

    # スコアリング: 熟成日数 × 価格適正度 × 疲労度ブースト
    scored = []
    for item in candidates:
        score = _calculate_score(item, remaining, fatigue_level)
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_item = scored[0][1]

    # 買っていい理由生成
    reason_text = _generate_reason(best_item, remaining, fatigue_level)

    # Recommendation レコード作成
    rec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    rec_sk = f"{SK_PREFIX_RECOMMENDATION}{rec_id}"

    rec_data = {
        "recommendation_id": rec_id,
        "user_id": user_id,
        "type": "WISHLIST_PRODUCT",
        "title": best_item.get("product_title", ""),
        "description": best_item.get("category", ""),
        "reason_text": reason_text,
        "product_url": best_item.get("product_url", ""),
        "product_image_url": best_item.get("product_image_url"),
        "price": best_item.get("price"),
        "status": "RECOMMENDED",
        "createdAt": now,
        "updatedAt": now,
    }

    ddb.put_item(pk, rec_sk, rec_data)

    return rec_data


def get_active_recommendation(user_id: str, ddb: DynamoDBService) -> Optional[dict]:
    """直近のアクティブなレコメンドを取得"""
    pk = f"USER#{user_id}"
    recs = ddb.query_begins_with(pk=pk, sk_prefix=SK_PREFIX_RECOMMENDATION)

    active_statuses = {
        "RECOMMENDED", "NOTIFICATION_SENT", "CART_ADDING", "CART_ADDED",
        "WAITING_USER_DECISION", "PURCHASE_CONFIRMATION_REQUIRED",
    }
    active_recs = [r for r in recs if r.get("status") in active_statuses]

    if not active_recs:
        return None

    # 最新を返す
    active_recs.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return active_recs[0]


def update_recommendation_status(
    user_id: str,
    recommendation_id: str,
    new_status: str,
    ddb: DynamoDBService,
) -> bool:
    """レコメンドのステータスを更新する"""
    pk = f"USER#{user_id}"
    sk = f"{SK_PREFIX_RECOMMENDATION}{recommendation_id}"
    now = datetime.now(timezone.utc).isoformat()

    try:
        ddb.update_item(pk, sk, {"status": new_status, "updatedAt": now})
        logger.info(
            "recommendation_status_updated",
            recommendation_id=recommendation_id,
            new_status=new_status,
        )
        return True
    except Exception as e:
        logger.error("recommendation_status_update_failed", error=str(e))
        return False


def _calculate_score(
    item: dict, remaining: int, fatigue_level: Optional[int]
) -> float:
    """レコメンドスコアを計算"""
    score = 0.0

    # 熟成日数ボーナス (max 40点)
    aging_days = item.get("desire_aging_days", 0)
    score += min(aging_days * 2, 40)

    # 価格適正度 (max 30点): 残額の 30-70% が最適
    price = float(item.get("price", 0) or 0)
    if remaining > 0 and price > 0:
        ratio = price / remaining
        if 0.1 <= ratio <= 0.5:
            score += 30
        elif ratio <= 0.7:
            score += 20
        elif ratio <= 1.0:
            score += 10

    # 疲労度ブースト (max 30点)
    if fatigue_level is not None:
        score += min(fatigue_level * 6, 30)

    return score


def _generate_reason(item: dict, remaining: int, fatigue_level: Optional[int]) -> str:
    """買っていい理由テキストを生成 (ふれまーるちゃん口調)"""
    title = item.get("product_title", "これ")
    aging = item.get("desire_aging_days", 0)
    price = item.get("price", 0)

    lines = []

    if aging >= 14:
        lines.append(f"この商品はほしい物リストに入ってから{aging}日目だよ。")
        lines.append("衝動買いじゃなくて、しっかり熟成された欲望です！")
    elif aging >= 7:
        lines.append(f"リストに入れてから{aging}日。ちゃんと考えてる証拠だね。")
    else:
        lines.append("まだリストに入れたばかりだけど…")

    if fatigue_level and fatigue_level >= 3:
        lines.append("\n今日は疲れてるみたいだし、自分へのご褒美にちょうどいいかも。")

    if remaining > 0 and price:
        if float(price) <= remaining * 0.5:
            lines.append("今月のご褒美枠にもしっかり収まってるよ！")
        elif float(price) <= remaining:
            lines.append("ご褒美枠ギリギリだけど…たまにはいいよね。")

    lines.append("\nこれは浪費じゃなくて、明日の自分を守るための保守費だよ✨")

    return "\n".join(lines)


def _get_current_monthly_summary(pk: str, ddb: DynamoDBService) -> Optional[dict]:
    """今月のサマリーを取得"""
    now = datetime.now(timezone.utc)
    month_sk = f"MONTHLY_SUMMARY#{now.strftime('%Y-%m')}"
    return ddb.get_item(pk=pk, sk=month_sk)


def _get_declined_urls(pk: str, ddb: DynamoDBService) -> set:
    """DECLINED されたレコメンドの商品URLを取得"""
    recs = ddb.query_begins_with(pk=pk, sk_prefix=SK_PREFIX_RECOMMENDATION)
    return {r.get("product_url") for r in recs if r.get("status") == "DECLINED"}
