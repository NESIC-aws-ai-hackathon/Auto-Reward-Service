"""
tests/unit/test_character_reply.py

キャラクター応答生成ハンドラーのユニットテスト
- 感情推定（_infer_emotion）
- 直近チャット取得（_load_recent_chats）
- 応答生成（generate_reply）の成功・フォールバック
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from character_reply import (
    generate_reply,
    _infer_emotion,
    _load_recent_chats,
    FALLBACK_MESSAGES,
)


# ─────────────────────────────────────────
# _infer_emotion テスト
# ─────────────────────────────────────────

class TestInferEmotion:
    def test_tired_keywords(self):
        result = _infer_emotion("今日すごく疲れた")
        assert result["emotion"] == "tired"
        assert result["fatigue_level"] > 0

    def test_stressed_keywords(self):
        result = _infer_emotion("つらい日だった")
        assert result["emotion"] == "stressed"
        assert result["fatigue_level"] >= 3

    def test_happy_keywords(self):
        result = _infer_emotion("今日は最高だった！")
        assert result["emotion"] == "happy"
        assert result["fatigue_level"] == 0

    def test_angry_keywords(self):
        result = _infer_emotion("むかつく出来事があった")
        assert result["emotion"] == "angry"

    def test_neutral_text(self):
        result = _infer_emotion("今日はランチを食べた")
        assert result["emotion"] == "neutral"
        assert result["fatigue_level"] == 0

    def test_neutral_empty_string(self):
        result = _infer_emotion("")
        assert result["emotion"] == "neutral"


# ─────────────────────────────────────────
# _load_recent_chats テスト
# ─────────────────────────────────────────

class TestLoadRecentChats:
    def test_returns_recent_chats(self):
        mock_ddb = MagicMock()
        # descending=True で取得→ reversed で古い順に並び直す
        # descending で取得される順: 最新先（assistant が先）
        mock_ddb.query_by_pk.return_value = [
            {"PK": "USER#u1", "SK": "CHAT#2026-05-16T12:00:01", "role": "assistant", "message": "やあ！"},
            {"PK": "USER#u1", "SK": "CHAT#2026-05-16T12:00:00", "role": "user", "message": "こんにちは"},
        ]
        result = _load_recent_chats("u1", mock_ddb)
        # reversed されて古い順（user が先）
        assert len(result) == 2
        assert result[0]["role"] == "user"

    def test_returns_empty_on_error(self):
        mock_ddb = MagicMock()
        mock_ddb.query_by_pk.side_effect = Exception("DB Error")
        result = _load_recent_chats("u1", mock_ddb)
        assert result == []

    def test_query_by_pk_called_with_correct_params(self):
        mock_ddb = MagicMock()
        mock_ddb.query_by_pk.return_value = []
        _load_recent_chats("u1", mock_ddb, limit=3)
        mock_ddb.query_by_pk.assert_called_once_with(
            pk="USER#u1",
            sk_prefix="CHAT#",
            limit=3,
            descending=True,
        )


# ─────────────────────────────────────────
# generate_reply テスト
# ─────────────────────────────────────────

class TestGenerateReply:
    @patch("character_reply._bedrock")
    def test_successful_reply_friendly(self, mock_bedrock):
        mock_bedrock.invoke_text.return_value = "今日も頑張ったね！えらいよ〜😊"
        mock_ddb = MagicMock()
        mock_ddb.query_by_pk.return_value = []

        result = generate_reply(
            user_id="u1",
            intent_result={"intent": "REWARD", "confidence": 0.9},
            text="疲れた",
            ddb_service=mock_ddb,
            tone="friendly",
        )
        assert result == "今日も頑張ったね！えらいよ〜😊"
        mock_bedrock.invoke_text.assert_called_once()

    @patch("character_reply._bedrock")
    def test_bedrock_error_returns_fallback(self, mock_bedrock):
        from utils.exceptions import BedrockError
        mock_bedrock.invoke_text.side_effect = BedrockError("Error")
        mock_ddb = MagicMock()
        mock_ddb.query_by_pk.return_value = []

        result = generate_reply(
            user_id="u1",
            intent_result={"intent": "CHAT", "confidence": 0.5},
            text="やあ",
            ddb_service=mock_ddb,
            tone="friendly",
        )
        assert result == FALLBACK_MESSAGES["friendly"]

    @patch("character_reply._bedrock")
    def test_polite_tone_uses_polite_system_prompt(self, mock_bedrock):
        mock_bedrock.invoke_text.return_value = "ありがとうございます。"
        mock_ddb = MagicMock()
        mock_ddb.query_by_pk.return_value = []

        generate_reply(
            user_id="u1",
            intent_result={"intent": "GREET", "confidence": 1.0},
            text="こんにちは",
            ddb_service=mock_ddb,
            tone="polite",
        )
        call_kwargs = mock_bedrock.invoke_text.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt") or ""
        assert "polite" in system_prompt or "丁寧" in system_prompt or "敬語" in system_prompt

    @patch("character_reply._bedrock")
    def test_tired_emotion_injected_in_prompt(self, mock_bedrock):
        mock_bedrock.invoke_text.return_value = "つらかったね…💖"
        mock_ddb = MagicMock()
        mock_ddb.query_by_pk.return_value = []

        generate_reply(
            user_id="u1",
            intent_result={"intent": "REWARD", "confidence": 0.9},
            text="しんどい",
            ddb_service=mock_ddb,
        )
        call_kwargs = mock_bedrock.invoke_text.call_args
        prompt = call_kwargs.kwargs.get("prompt") or call_kwargs.args[0]
        assert "tired" in prompt or "疲" in prompt  # 感情がプロンプトに注入されている

    @patch("character_reply._bedrock")
    def test_fallback_message_per_tone(self, mock_bedrock):
        """全トーンのフォールバックメッセージが存在する"""
        assert "friendly" in FALLBACK_MESSAGES
        assert "polite" in FALLBACK_MESSAGES
        assert "devilish" in FALLBACK_MESSAGES
        for tone, msg in FALLBACK_MESSAGES.items():
            assert len(msg) > 0

    @patch("character_reply._bedrock")
    def test_reply_is_stripped(self, mock_bedrock):
        mock_bedrock.invoke_text.return_value = "  こんにちは！  \n"
        mock_ddb = MagicMock()
        mock_ddb.query_by_pk.return_value = []

        result = generate_reply(
            user_id="u1",
            intent_result={"intent": "GREET", "confidence": 1.0},
            text="やあ",
            ddb_service=mock_ddb,
        )
        assert result == "こんにちは！"
