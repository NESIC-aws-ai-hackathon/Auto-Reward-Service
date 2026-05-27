"""
tests/unit/test_intent_classifier.py

Intent 分類ハンドラーのユニットテスト
- Bedrock を mock し classify_intent() の出力を検証
- JSON パース失敗時の UNKNOWN フォールバックを検証
- BedrockError 時の UNKNOWN フォールバックを検証
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from intent_classifier import classify_intent, _parse_intent_response


# ─────────────────────────────────────────
# _parse_intent_response テスト
# ─────────────────────────────────────────

class TestParseIntentResponse:
    def test_valid_json(self):
        raw = '{"intent": "EXPENSE", "confidence": 0.95}'
        result = _parse_intent_response(raw)
        assert result["intent"] == "EXPENSE"
        assert result["confidence"] == pytest.approx(0.95)

    def test_lowercase_intent_converted_to_upper(self):
        raw = '{"intent": "expense", "confidence": 0.8}'
        result = _parse_intent_response(raw)
        assert result["intent"] == "EXPENSE"

    def test_json_in_code_block(self):
        raw = '```json\n{"intent": "REWARD", "confidence": 0.9}\n```'
        result = _parse_intent_response(raw)
        assert result["intent"] == "REWARD"
        assert result["confidence"] == pytest.approx(0.9)

    def test_json_with_surrounding_text(self):
        raw = 'Based on the message, the intent is:\n{"intent": "GREET", "confidence": 1.0}'
        result = _parse_intent_response(raw)
        assert result["intent"] == "GREET"

    def test_no_json_returns_unknown(self):
        result = _parse_intent_response("すみません、わかりません")
        assert result["intent"] == "UNKNOWN"
        assert result["confidence"] == 0.0

    def test_invalid_json_returns_unknown(self):
        result = _parse_intent_response("{intent: EXPENSE}")  # 不正 JSON
        assert result["intent"] == "UNKNOWN"

    def test_confidence_clamped_to_0_1(self):
        raw = '{"intent": "CHAT", "confidence": 1.5}'
        result = _parse_intent_response(raw)
        assert result["confidence"] == pytest.approx(1.0)

    def test_confidence_negative_clamped(self):
        raw = '{"intent": "CHAT", "confidence": -0.1}'
        result = _parse_intent_response(raw)
        assert result["confidence"] == pytest.approx(0.0)

    def test_missing_confidence_defaults_to_zero(self):
        raw = '{"intent": "UNKNOWN"}'
        result = _parse_intent_response(raw)
        assert result["confidence"] == 0.0


# ─────────────────────────────────────────
# classify_intent テスト
# ─────────────────────────────────────────

class TestClassifyIntent:
    @patch("intent_classifier._bedrock")
    def test_expense_intent(self, mock_bedrock):
        mock_bedrock.invoke_text.return_value = '{"intent": "EXPENSE", "confidence": 0.95}'
        result = classify_intent("プリン買った 320円")
        assert result["intent"] == "EXPENSE"
        assert result["confidence"] == pytest.approx(0.95)
        mock_bedrock.invoke_text.assert_called_once()

    @patch("intent_classifier._bedrock")
    def test_reward_intent(self, mock_bedrock):
        mock_bedrock.invoke_text.return_value = '{"intent": "REWARD", "confidence": 0.88}'
        result = classify_intent("疲れた、ご褒美ほしい")
        assert result["intent"] == "REWARD"

    @patch("intent_classifier._bedrock")
    def test_greet_intent(self, mock_bedrock):
        mock_bedrock.invoke_text.return_value = '{"intent": "GREET", "confidence": 1.0}'
        result = classify_intent("こんにちは！")
        assert result["intent"] == "GREET"

    @patch("intent_classifier._bedrock")
    def test_confirm_yes_intent(self, mock_bedrock):
        mock_bedrock.invoke_text.return_value = '{"intent": "CONFIRM_YES", "confidence": 0.99}'
        result = classify_intent("はい、それでお願い")
        assert result["intent"] == "CONFIRM_YES"

    @patch("intent_classifier._bedrock")
    def test_bedrock_error_returns_unknown(self, mock_bedrock):
        from utils.exceptions import BedrockError
        mock_bedrock.invoke_text.side_effect = BedrockError("タイムアウト")
        result = classify_intent("何かテキスト")
        assert result["intent"] == "UNKNOWN"
        assert result["confidence"] == 0.0

    @patch("intent_classifier._bedrock")
    def test_bedrock_returns_invalid_json_falls_back(self, mock_bedrock):
        mock_bedrock.invoke_text.return_value = "解析できません"
        result = classify_intent("テスト")
        assert result["intent"] == "UNKNOWN"

    @patch("intent_classifier._bedrock")
    def test_system_prompt_is_passed(self, mock_bedrock):
        """system_prompt パラメータが渡されることを確認（SEC-2-01）"""
        mock_bedrock.invoke_text.return_value = '{"intent": "CHAT", "confidence": 0.7}'
        classify_intent("テスト")
        call_kwargs = mock_bedrock.invoke_text.call_args
        # system_prompt が None 以外で渡されていること
        assert call_kwargs.kwargs.get("system_prompt") is not None

    @patch("intent_classifier._bedrock")
    def test_user_message_wrapped_in_tag(self, mock_bedrock):
        """ユーザー入力が <user_message> タグで囲まれることを確認（プロンプトインジェクション防止）"""
        mock_bedrock.invoke_text.return_value = '{"intent": "CHAT", "confidence": 0.7}'
        classify_intent("テストメッセージ")
        call_kwargs = mock_bedrock.invoke_text.call_args
        prompt = call_kwargs.kwargs.get("prompt") or call_kwargs.args[0]
        assert "<user_message>" in prompt
        assert "テストメッセージ" in prompt
        assert "</user_message>" in prompt
