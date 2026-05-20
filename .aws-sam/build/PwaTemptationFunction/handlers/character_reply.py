"""
キャラクター応答生成ハンドラー

設計方針:
- Bedrock Nova Micro にキャラクタープロンプトを送りふれまーるちゃん応答を生成
- 感情状態・直近会話コンテキストを注入
- Bedrock 失敗時はフォールバックメッセージを返す（BR-2-14）
"""
from __future__ import annotations

import os

from services.bedrock_service import BedrockService
from services.dynamodb_service import DynamoDBService
from utils.exceptions import BedrockError
from utils.logger import get_logger
from prompts.character_prompts import CHARACTER_SYSTEM_PROMPTS

logger = get_logger(__name__)

_bedrock = BedrockService()

# ─────────────────────────────────────────
# フォールバックメッセージ（Bedrock 不可用時）
# ─────────────────────────────────────────
FALLBACK_MESSAGES: dict[str, str] = {
    "friendly": "んー、ちょっと考えすぎてフリーズしちゃった…🌿 もう一度話しかけてみてね〜",
    "polite": "んー、ちょっと考えすぎてフリーズしちゃった…🌿 もう一度話しかけてみてね〜",
    "devilish": "んー、ちょっと考えすぎてフリーズしちゃった…🌿 もう一度話しかけてみてね〜",
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


def _load_recent_chats(user_id: str, ddb_service: DynamoDBService, limit: int = 20) -> list[dict]:
    """
    DynamoDB から直近の会話ログを取得する。

    Args:
        user_id: LINE ユーザー ID
        ddb_service: DynamoDB サービスインスタンス
        limit: 取得するメッセージ数（デフォルト20 = 約10往復分）

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
    ふれまーるちゃんのキャラクター応答を生成する。

    Bedrock Converse API のネイティブマルチターン形式を使い、
    直近の会話履歴を正しく user/assistant ロールとして渡すことで
    文脈のある自然な会話を実現する。

    Args:
        user_id: LINE ユーザー ID
        intent_result: classify_intent() の結果 {"intent": str, "confidence": float}
        text: ユーザーのメッセージ本文
        ddb_service: DynamoDB サービスインスタンス
        tone: キャラクタートーン（friendly / polite / devilish）

    Returns:
        ふれまーるちゃんの返答テキスト（失敗時はフォールバックメッセージ）
    """
    intent = intent_result.get("intent", "CHAT")
    emotion_info = _infer_emotion(text)
    recent_chats = _load_recent_chats(user_id, ddb_service)

    system_prompt = CHARACTER_SYSTEM_PROMPTS.get(tone, CHARACTER_SYSTEM_PROMPTS["friendly"])

    # コンテキスト指示をシステムプロンプトに追加
    context_addendum = _build_context_addendum(
        emotion=emotion_info["emotion"],
        fatigue_level=emotion_info["fatigue_level"],
        intent=intent,
    )
    full_system_prompt = system_prompt + "\n\n" + context_addendum

    # Converse API 用マルチターンメッセージ構築
    messages = _build_converse_messages(recent_chats, text)

    try:
        reply = _bedrock.invoke_converse(
            messages=messages,
            system_prompt=full_system_prompt,
            max_tokens=300,
            temperature=0.8,
        )
        return reply.strip()
    except BedrockError as e:
        logger.warning("generate_reply bedrock error, using fallback", error=str(e))
        return FALLBACK_MESSAGES.get(tone, FALLBACK_MESSAGES["friendly"])
    except Exception as e:
        logger.error("generate_reply unexpected error, using fallback", error=str(e), error_type=type(e).__name__)
        return FALLBACK_MESSAGES.get(tone, FALLBACK_MESSAGES["friendly"])


def _build_context_addendum(emotion: str, fatigue_level: int, intent: str) -> str:
    """感情・Intent 情報をシステムプロンプト補足として構築する"""
    parts = []
    if emotion != "neutral" or fatigue_level > 0:
        parts.append(f"## 現在のユーザー状態\n感情: {emotion}, 疲労度: {fatigue_level}/5")
    parts.append(f"## 今回の Intent\n{intent}")
    parts.append(
        "## 会話の指針\n"
        "- 直前の会話の流れを必ず踏まえて返答すること。話題が続いている場合は自然に続けること\n"
        "- ユーザーが質問に答えてくれたら、その内容に反応してから次の話題に移ること\n"
        "- 以前の会話で話した内容を覚えている前提で会話すること\n"
        "- 唐突に話題を変えないこと。文脈を読んで自然に繋げること"
    )
    return "\n\n".join(parts)


def _build_converse_messages(recent_chats: list[dict], current_text: str) -> list[dict]:
    """
    直近の会話履歴 + 今回のメッセージを Converse API の messages 形式に変換する。

    Converse API の制約:
    - messages は user/assistant が交互
    - 先頭は user ロール
    - 連続する同一ロールは結合する
    """
    messages = []

    for chat in recent_chats:
        role = chat.get("role", "user")
        msg = chat.get("message", "")
        if not msg or not msg.strip():
            continue
        # role の正規化（万が一不正な値が入っていた場合）
        if role not in ("user", "assistant"):
            role = "user"
        if messages and messages[-1]["role"] == role:
            # 同一ロールが続く場合、テキストを結合
            messages[-1]["content"][0]["text"] += "\n" + msg
        else:
            messages.append({
                "role": role,
                "content": [{"text": msg}],
            })

    # 今回のユーザーメッセージ追加
    if messages and messages[-1]["role"] == "user":
        messages[-1]["content"][0]["text"] += "\n" + current_text
    else:
        messages.append({
            "role": "user",
            "content": [{"text": current_text}],
        })

    # Converse API 制約: 先頭が assistant の場合、ダミー user メッセージを先頭に挿入
    if messages and messages[0]["role"] == "assistant":
        messages.insert(0, {"role": "user", "content": [{"text": "こんにちは"}]})

    # 履歴が長すぎる場合はトークン制限を避けるため最新10ターンに絞る
    if len(messages) > 10:
        messages = messages[-10:]
        # 切り詰め後も先頭が user であることを保証
        if messages[0]["role"] == "assistant":
            messages = messages[1:]

    return messages
