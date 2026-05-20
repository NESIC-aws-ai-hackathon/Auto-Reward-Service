"""
reward_matcher.py のユニットテスト
"""
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# ─── layer/python のインポート問題を回避 ───
# services/__init__.py → line_service → linebot → pydantic_core (Linux binary)
# sys.modules にモックを仕込んでインポートチェーンを断ち切る

_mock_bedrock_mod = MagicMock()
_mock_bedrock_instance = MagicMock()
_mock_bedrock_mod.BedrockService.return_value = _mock_bedrock_instance

_mock_ddb_mod = MagicMock()
_mock_logger_mod = MagicMock()
_mock_logger_mod.get_logger = MagicMock(return_value=MagicMock())

# services パッケージ全体をモック → reward_matcher だけ本物をインポート
sys.modules["services"] = MagicMock()
sys.modules["services.bedrock_service"] = _mock_bedrock_mod
sys.modules["services.dynamodb_service"] = _mock_ddb_mod
sys.modules["utils"] = MagicMock()
sys.modules["utils.logger"] = _mock_logger_mod

# reward_matcher をインポート（依存先はモック済み）
import importlib
import os
spec = importlib.util.spec_from_file_location(
    "services.reward_matcher",
    os.path.join(os.path.dirname(__file__), "..", "..", "layer", "python", "services", "reward_matcher.py"),
)
_rm_mod = importlib.util.module_from_spec(spec)
sys.modules["services.reward_matcher"] = _rm_mod
spec.loader.exec_module(_rm_mod)

match_rewards_to_lane = _rm_mod.match_rewards_to_lane
_parse_reward_json = _rm_mod._parse_reward_json
_LANE_TO_REWARD_CATEGORIES = _rm_mod._LANE_TO_REWARD_CATEGORIES
_DEFAULT_REWARDS = _rm_mod._DEFAULT_REWARDS


class TestMatchRewardsToLane:
    """match_rewards_to_lane のテスト"""

    def setup_method(self):
        self.mock_ddb = MagicMock()
        self.mock_ddb.get_item.return_value = {
            "food": {"likes": ["ラーメン", "カフェ", "プリン"]},
        }
        self.mock_ddb.query_by_pk.return_value = []

    @patch("services.reward_matcher._generate_personalized_rewards")
    def test_returns_rewards_for_cafe(self, mock_gen):
        mock_gen.return_value = [
            {"name": "ラテ", "price": 500, "emoji": "☕", "source": "bedrock_generated", "score": 70},
        ]
        result = match_rewards_to_lane(
            user_id="U123",
            lane_type="CAFE_REBOOT",
            places=[{"name": "駅前カフェ", "distance_m": 200}],
            budget_remaining=5000,
            ddb=self.mock_ddb,
        )
        assert len(result) >= 1
        assert all("reward_id" in r for r in result)

    def test_returns_defaults_when_no_results(self):
        with patch("services.reward_matcher._generate_personalized_rewards", return_value=[]):
            result = match_rewards_to_lane(
                user_id="U123",
                lane_type="CONVENIENCE_RECOVERY",
                places=[],
                budget_remaining=500,
                ddb=self.mock_ddb,
            )
        assert len(result) >= 1
        assert result[0]["source"] == "default"

    def test_pool_items_included(self):
        self.mock_ddb.query_by_pk.return_value = [
            {"name": "入浴剤セット", "price": 400, "category": "回復費", "emoji": "🛁"},
        ]
        with patch("services.reward_matcher._generate_personalized_rewards", return_value=[]):
            result = match_rewards_to_lane(
                user_id="U123",
                lane_type="LOW_COST_RECOVERY",
                places=[],
                budget_remaining=1000,
                ddb=self.mock_ddb,
            )
        pool_names = [r["name"] for r in result if r.get("source") == "reward_pool"]
        assert "入浴剤セット" in pool_names


class TestParseRewardJson:
    """_parse_reward_json のテスト"""

    def test_valid_json(self):
        raw = '[{"name": "プリン", "price": 300, "emoji": "🍮", "reason": "おいしい"}]'
        result = _parse_reward_json(raw)
        assert len(result) == 1
        assert result[0]["name"] == "プリン"
        assert result[0]["price"] == 300

    def test_json_with_surrounding_text(self):
        raw = 'おすすめ: [{"name": "ケーキ", "price": 500, "emoji": "🍰"}] です'
        result = _parse_reward_json(raw)
        assert len(result) == 1
        assert result[0]["name"] == "ケーキ"

    def test_invalid_json(self):
        assert _parse_reward_json("これはJSONではない") == []

    def test_empty_array(self):
        assert _parse_reward_json("[]") == []


class TestLaneToRewardCategories:
    """カテゴリマッピングのテスト"""

    def test_all_lanes_have_mapping(self):
        for lane_type in ["CAFE_REBOOT", "CONVENIENCE_RECOVERY", "SELF_COOKING_ESCAPE",
                          "LOW_COST_RECOVERY", "RICHER_ESCAPE"]:
            assert lane_type in _LANE_TO_REWARD_CATEGORIES

    def test_all_lanes_have_defaults(self):
        for lane_type in ["CAFE_REBOOT", "CONVENIENCE_RECOVERY", "SELF_COOKING_ESCAPE",
                          "LOW_COST_RECOVERY", "RICHER_ESCAPE"]:
            assert lane_type in _DEFAULT_REWARDS
