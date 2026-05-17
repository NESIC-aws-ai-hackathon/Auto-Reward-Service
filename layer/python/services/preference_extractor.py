"""
嗜好自動抽出 — 会話から PREF_MEMORY を育てる

設計方針:
- Push 後の返信や通常会話から嗜好情報を抽出
- Bedrock (Nova Lite) で JSON 形式の嗜好データを生成
- 既存の PREF_MEMORY と重複排除して追加
- 抽出失敗は WARNING ログに留め処理続行
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from services.bedrock_service import get_bedrock_service
from services.dynamodb_service import DynamoDBService
from models.schemas import SK_PREF_MEMORY, ENTITY_PREF_MEMORY
from utils.logger import get_logger

logger = get_logger(__name__)

_JST = timezone(timedelta(hours=9))

EXTRACTION_PROMPT = """以下のユーザー発言から嗜好情報を JSON で抽出してください。

<user_message>{user_message}</user_message>

出力形式（JSON のみ出力してください）:
{{
  "category": "food" | "entertainment" | "hobby" | "lifestyle" | "fashion" | "place" | "brand" | "other" | null,
  "items": ["具体的な好み1", "好み2"],
  "sentiment": "positive" | "negative" | "neutral",
  "context": "補足情報（よく行く、最近ハマってる、など）"
}}

嗜好情報が含まれない場合:
{{"category": null, "items": [], "sentiment": "neutral", "context": null}}
"""


def extract_and_save_preferences(
    user_id: str,
    user_message: str,
    ddb: DynamoDBService,
) -> Optional[dict]:
    """会話から嗜好を抽出し、PREF_MEMORY に保存する。

    Args:
        user_id: LINE ユーザー ID
        user_message: ユーザーの発言テキスト
        ddb: DynamoDB サービス

    Returns:
        抽出結果 dict（items がある場合）。抽出なしまたは失敗時は None。
    """
    # 短すぎるメッセージはスキップ
    if len(user_message) < 3:
        return None

    # Bedrock で嗜好抽出
    extracted = _extract_with_bedrock(user_message)
    if not extracted or not extracted.get("items"):
        return None

    # PREF_MEMORY に保存
    _save_to_pref_memory(user_id, extracted, ddb)
    return extracted


def _extract_with_bedrock(user_message: str) -> Optional[dict]:
    """Bedrock で嗜好情報を抽出する"""
    try:
        bedrock = get_bedrock_service()
        prompt = EXTRACTION_PROMPT.format(user_message=user_message)
        raw_response = bedrock.invoke_text(prompt)

        # JSON パース
        result = json.loads(raw_response.strip())
        if not isinstance(result, dict):
            return None
        if not result.get("items"):
            return None
        return result
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("preference_extraction_failed", error=str(e))
        return None


def _save_to_pref_memory(user_id: str, extracted: dict, ddb: DynamoDBService) -> None:
    """抽出した嗜好を PREF_MEMORY に保存する（重複排除）"""
    pk = f"USER#{user_id}"
    now = datetime.now(_JST).isoformat()

    # 既存データ取得
    existing = ddb.get_item(pk=pk, sk=SK_PREF_MEMORY)

    if existing:
        existing_items = existing.get("items") or []
        existing_categories = existing.get("categories") or []
    else:
        existing_items = []
        existing_categories = []

    category = extracted.get("category", "other")
    new_items = extracted.get("items", [])
    sentiment = extracted.get("sentiment", "positive")

    # 既存キーワードの集合
    existing_keywords = {item.get("keyword", "") for item in existing_items}

    # 新しいアイテムを追加（重複排除）
    added = False
    for item_keyword in new_items:
        if item_keyword and item_keyword not in existing_keywords:
            existing_items.append({
                "keyword": item_keyword,
                "category": category or "other",
                "sentiment": sentiment,
                "detected_at": now,
            })
            existing_keywords.add(item_keyword)
            added = True

    if not added:
        return

    # カテゴリリスト更新
    if category and category not in existing_categories:
        existing_categories.append(category)

    # DynamoDB 保存
    if existing:
        ddb.update_item(pk=pk, sk=SK_PREF_MEMORY, updates={
            "items": existing_items,
            "categories": existing_categories,
            "updated_at": now,
        })
    else:
        ddb.put_item(pk=pk, sk=SK_PREF_MEMORY, item={
            "entityType": ENTITY_PREF_MEMORY,
            "items": existing_items,
            "categories": existing_categories,
            "updated_at": now,
        })
