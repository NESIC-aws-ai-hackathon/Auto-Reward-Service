"""
Intent 分類ハンドラー

Bedrock Nova Micro に Intent 分類プロンプトを送信し、
{"intent": str, "confidence": float} を返す。

失敗時は UNKNOWN にフォールバック（BR-2-01 / BR-2-14）。
"""
from __future__ import annotations

import json
import os

from services.bedrock_service import BedrockService
from utils.exceptions import BedrockError
from utils.logger import get_logger
from prompts.intent_prompt import INTENT_SYSTEM_PROMPT, build_intent_prompt

logger = get_logger(__name__)

_bedrock = BedrockService()

# Intent分類用モデル（環境変数で上書き可能、ap-northeast-1ではnova-liteを使用）
_INTENT_MODEL_ID = os.environ.get("BEDROCK_INTENT_MODEL_ID", "amazon.nova-lite-v1:0")

# フォールバック戻り値
_FALLBACK: dict = {"intent": "UNKNOWN", "confidence": 0.0}


def classify_intent(text: str) -> dict:
    """
    ユーザーテキストの Intent を分類する。

    Args:
        text: ユーザーのメッセージ（1000 文字以内を想定）

    Returns:
        {"intent": str, "confidence": float}
        Bedrock 呼び出し失敗時は {"intent": "UNKNOWN", "confidence": 0.0}
    """
    prompt = build_intent_prompt(text)

    try:
        raw = _bedrock.invoke_text(
            prompt=prompt,
            system_prompt=INTENT_SYSTEM_PROMPT,
            max_tokens=100,
            model_id=_INTENT_MODEL_ID,
        )
    except BedrockError as e:
        logger.warning("classify_intent bedrock error, fallback to UNKNOWN", error=str(e))
        return dict(_FALLBACK)
    except Exception as e:
        logger.error("classify_intent unexpected error, fallback to UNKNOWN", error=str(e), error_type=type(e).__name__)
        return dict(_FALLBACK)

    # Bedrock の出力から JSON を抽出
    result = _parse_intent_response(raw)
    logger.info("classify_intent", intent=result.get("intent"), confidence=result.get("confidence"))
    return result


def _parse_intent_response(raw: str) -> dict:
    """Bedrock の返答から intent / confidence を抽出する。"""
    raw = raw.strip()

    # JSON ブロックを抽出（```json ... ``` の場合も対応）
    if "```" in raw:
        for block in raw.split("```"):
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            if block.startswith("{"):
                raw = block
                break

    # 最初の { } を探す
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        logger.warning("intent response has no JSON", raw=raw[:200])
        return dict(_FALLBACK)

    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        logger.warning("intent response JSON parse error", raw=raw[:200])
        return dict(_FALLBACK)

    intent = str(data.get("intent", "UNKNOWN")).upper()
    try:
        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    return {"intent": intent, "confidence": confidence}
