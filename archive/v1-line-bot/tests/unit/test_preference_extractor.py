"""
preference_extractor サービスのユニットテスト
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from services.preference_extractor import (
    EXTRACTION_PROMPT,
    _extract_with_bedrock,
    _save_to_pref_memory,
    extract_and_save_preferences,
)


class TestExtractWithBedrock:
    @patch("services.preference_extractor.get_bedrock_service")
    def test_extracts_food_preference(self, mock_get_bedrock):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_text.return_value = json.dumps({
            "category": "food",
            "items": ["豚骨ラーメン", "一蘭"],
            "sentiment": "positive",
            "context": "よく行く",
        })
        mock_get_bedrock.return_value = mock_bedrock

        result = _extract_with_bedrock("豚骨！一蘭よく行くよ")
        assert result is not None
        assert result["category"] == "food"
        assert "豚骨ラーメン" in result["items"]

    @patch("services.preference_extractor.get_bedrock_service")
    def test_no_preference_returns_none(self, mock_get_bedrock):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_text.return_value = json.dumps({
            "category": None,
            "items": [],
            "sentiment": "neutral",
            "context": None,
        })
        mock_get_bedrock.return_value = mock_bedrock

        result = _extract_with_bedrock("ありがとう")
        assert result is None

    @patch("services.preference_extractor.get_bedrock_service")
    def test_bedrock_error_returns_none(self, mock_get_bedrock):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_text.side_effect = Exception("Bedrock error")
        mock_get_bedrock.return_value = mock_bedrock

        result = _extract_with_bedrock("テスト")
        assert result is None

    @patch("services.preference_extractor.get_bedrock_service")
    def test_invalid_json_returns_none(self, mock_get_bedrock):
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_text.return_value = "not json"
        mock_get_bedrock.return_value = mock_bedrock

        result = _extract_with_bedrock("テスト")
        assert result is None


class TestSaveToPrefMemory:
    def test_creates_new_pref_memory(self):
        ddb = MagicMock()
        ddb.get_item.return_value = None

        _save_to_pref_memory("U123", {
            "category": "food",
            "items": ["豚骨ラーメン"],
            "sentiment": "positive",
        }, ddb)

        ddb.put_item.assert_called_once()
        call_kwargs = ddb.put_item.call_args
        item = call_kwargs.kwargs.get("item") or call_kwargs[1].get("item")
        assert len(item["items"]) == 1
        assert item["items"][0]["keyword"] == "豚骨ラーメン"

    def test_appends_to_existing_pref_memory(self):
        ddb = MagicMock()
        ddb.get_item.return_value = {
            "PK": "USER#U123",
            "SK": "PREF_MEMORY#",
            "items": [{"keyword": "プリン", "category": "food", "sentiment": "positive"}],
            "categories": ["food"],
        }

        _save_to_pref_memory("U123", {
            "category": "food",
            "items": ["豚骨ラーメン"],
            "sentiment": "positive",
        }, ddb)

        ddb.update_item.assert_called_once()
        call_kwargs = ddb.update_item.call_args
        updates = call_kwargs.kwargs.get("updates") or call_kwargs[1].get("updates")
        assert len(updates["items"]) == 2

    def test_deduplicates_existing_items(self):
        ddb = MagicMock()
        ddb.get_item.return_value = {
            "PK": "USER#U123",
            "SK": "PREF_MEMORY#",
            "items": [{"keyword": "プリン", "category": "food", "sentiment": "positive"}],
            "categories": ["food"],
        }

        _save_to_pref_memory("U123", {
            "category": "food",
            "items": ["プリン"],  # 既に存在するアイテム
            "sentiment": "positive",
        }, ddb)

        # 重複のため update_item は呼ばれない
        ddb.update_item.assert_not_called()
        ddb.put_item.assert_not_called()

    def test_adds_new_category(self):
        ddb = MagicMock()
        ddb.get_item.return_value = {
            "PK": "USER#U123",
            "SK": "PREF_MEMORY#",
            "items": [{"keyword": "プリン", "category": "food", "sentiment": "positive"}],
            "categories": ["food"],
        }

        _save_to_pref_memory("U123", {
            "category": "entertainment",
            "items": ["ワンピース"],
            "sentiment": "positive",
        }, ddb)

        ddb.update_item.assert_called_once()
        updates = ddb.update_item.call_args.kwargs.get("updates") or ddb.update_item.call_args[1].get("updates")
        assert "entertainment" in updates["categories"]


class TestExtractAndSavePreferences:
    def test_short_message_skipped(self):
        ddb = MagicMock()
        result = extract_and_save_preferences("U123", "ok", ddb)
        assert result is None

    @patch("services.preference_extractor._extract_with_bedrock")
    def test_no_items_returns_none(self, mock_extract):
        mock_extract.return_value = {"category": None, "items": [], "sentiment": "neutral"}
        ddb = MagicMock()
        result = extract_and_save_preferences("U123", "ありがとうございます", ddb)
        assert result is None

    @patch("services.preference_extractor._save_to_pref_memory")
    @patch("services.preference_extractor._extract_with_bedrock")
    def test_saves_extracted_preferences(self, mock_extract, mock_save):
        mock_extract.return_value = {
            "category": "food",
            "items": ["カレー"],
            "sentiment": "positive",
            "context": "好き",
        }
        ddb = MagicMock()
        result = extract_and_save_preferences("U123", "カレーが好き！", ddb)
        assert result is not None
        assert result["category"] == "food"
        mock_save.assert_called_once()
