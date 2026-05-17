"""
キャラクター応答生成ハンドラー

設計方針:
- Bedrock Nova Micro にキャラクタープロンプトを送りリワードちゃん応答を生成
- 感情状態・直近会話コンテキストを注入
- Bedrock 失敗時はフォールバックメッセージを返す（BR-2-14）
"""
from __future__ import annotations

import os

from services.bedrock_service import BedrockService
from services.dynamodb_service import DynamoDBService
from utils.exceptions import BedrockError
from utils.logger import get_logger
from prompts.character_prompts import CHARACTER_SYSTEM_PROMPTS, build_character_prompt

logger = get_logger(__name__)

_bedrock = BedrockService()

# ─────────────────────────────────────────
# フォールバックメッセージ（Bedrock 不可用時）
# ─────────────────────────────────────────
FALLBACK_MESSAGES: dict[str, str] = {
    "friendly": "ちょっと考えすぎてフリーズしちゃった…💦 もう一度話しかけてみてね！",
    "polite": "申し訳ございません、少々調子が悪いようです。もう一度お試しください。",
    "devilish": "ちっ、今日は機嫌が悪いみたい😏 またあとでね。",
}

# ─────────────────────────────────────────
# 感情キーワード定義（ルールベース）
# ─────────────────────────────────────────
_TIRED_KEYWORDS = ["疲れた", "つかれた", "しんどい", "だるい", "ヘトヘト", "クタクタ", "げんなり"]
_HAPPY_KEYWORDS = ["嬉しい", "うれしい", "楽しい", "たのしい", "最高", "サイコー", "やったー", "わーい"]
_STRESSED_KEYWORDS = ["つらい", "辛い", "苦しい", "くるしい", "泣き", "泣いた", "落ち込んだ", "落ちてる", "きつい"]
_ANGRY_KEYWORDS = ["むかつく", "腹立つ", "イライラ", "怒る", "最悪"]


def _infer_emotion(text: str) -> dict:
    """
    テキストからルールベースで感情を推定する。

    Returns:
        {"emotion": str, "fatigue_level": int}
        emotion: neutral / tired / happy / stressed / angry
        fatigue_level: 0〜5
    """
    if any(kw in text for kw in _TIRED_KEYWORDS):
        return {"emotion": "tired", "fatigue_level": 3}
    if any(kw in text for kw in _STRESSED_KEYWORDS):
        return {"emotion": "stressed", "fatigue_level": 4}
    if any(kw in text for kw in _ANGRY_KEYWORDS):
        return {"emotion": "angry", "fatigue_level": 2}
    if any(kw in text for kw in _HAPPY_KEYWORDS):
        return {"emotion": "happy", "fatigue_level": 0}

    return {"emotion": "neutral", "fatigue_level": 0}


def _load_recent_chats(user_id: str, ddb_service: DynamoDBService, limit: int = 5) -> list[dict]:
    """
    DynamoDB から直近の会話ログを取得する。

    Args:
        user_id: LINE ユーザー ID
        ddb_service: DynamoDB サービスインスタンス
        limit: 取得するメッセージ数

    Returns:
        [{"role": str, "message": str}]（古い順）
    """
    pk = f"USER#{user_id}"
    try:
        items = ddb_service.query_by_pk(
            pk=pk,
            sk_prefix="CHAT#",
            limit=limit,
            descending=True,
        )
        # 古い順に並べ直す
        items = list(reversed(items))
        return [
            {"role": item.get("role", "user"), "message": item.get("message", "")}
            for item in items
        ]
    except Exception as e:
        logger.warning("_load_recent_chats failed", error=str(e))
        return []


def generate_reply(
    user_id: str,
    intent_result: dict,
    text: str,
    ddb_service: DynamoDBService,
    tone: str = "friendly",
) -> str:
    """
    リワードちゃんのキャラクター応答を生成する。

    Args:
        user_id: LINE ユーザー ID
        intent_result: classify_intent() の結果 {"intent": str, "confidence": float}
        text: ユーザーのメッセージ本文
        ddb_service: DynamoDB サービスインスタンス
        tone: キャラクタートーン（friendly / polite / devilish）

    Returns:
        リワードちゃんの返答テキスト（失敗時はフォールバックメッセージ）
    """
    intent = intent_result.get("intent", "CHAT")
    emotion_info = _infer_emotion(text)
    recent_chats = _load_recent_chats(user_id, ddb_service)

    system_prompt = CHARACTER_SYSTEM_PROMPTS.get(tone, CHARACTER_SYSTEM_PROMPTS["friendly"])
    user_prompt = build_character_prompt(
        user_message=text,
        intent=intent,
        emotion=emotion_info["emotion"],
        fatigue_level=emotion_info["fatigue_level"],
        recent_chats=recent_chats,
    )

    try:
        reply = _bedrock.invoke_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=300,
            temperature=0.8,
        )
        return reply.strip()
    except BedrockError as e:
        logger.warning("generate_reply bedrock error, using fallback", error=str(e))
        return FALLBACK_MESSAGES.get(tone, FALLBACK_MESSAGES["friendly"])
