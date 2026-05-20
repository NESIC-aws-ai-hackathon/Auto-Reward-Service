"""
reward_proposal.py のユニットテスト（Unit 5）

テスト対象:
- _filter_candidates : 余裕額フィルタリング + スコアソート
- _build_calendar_context : カレンダーイベント → コンテキスト文字列
- propose_reward : メインロジック
  - 余裕額 0 → やんわり止め
  - 候補なし → フォールバック
  - 正常系 → Bedrock 呼び出し + 履歴保存
  - Bedrock エラー → フォールバック
  - Google Calendar コンテキスト付き
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from handlers.reward_proposal import (
    _build_calendar_context,
    _filter_candidates,
    propose_reward,
)
from models.schemas import RewardPoolItem


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────

def _make_item(
    item_id: str = "item001",
    name: str = "スイーツ",
    price: str = "500",
    score: float = 0.5,
    item_type: str = "product",
) -> RewardPoolItem:
    return RewardPoolItem(
        id=item_id,
        name=name,
        price=Decimal(price),
        category="スイーツ",
        score=score,
        source_url=f"https://item.rakuten.co.jp/{item_id}",
        type=item_type,
    )


def _make_ddb_with_pool(items: list[RewardPoolItem]) -> MagicMock:
    """RewardPoolItem リストを持つ DDB モックを返す"""
    mock = MagicMock()

    # PROFILE# は空
    def get_item_side_effect(pk, sk):
        if sk == "PROFILE#":
            return {"reward_budget_monthly": "10000"}
        if sk == "REWARD_POOL#":
            return {
                "items": [
                    {
                        "id": i.id,
                        "name": i.name,
                        "price": i.price,
                        "category": i.category,
                        "score": i.score,
                        "source_url": i.source_url,
                        "type": i.type,
                    }
                    for i in items
                ]
            }
        return None

    mock.get_item.side_effect = get_item_side_effect
    mock.query_by_pk.return_value = []  # 今月の支出 = 0
    mock.put_item.return_value = None
    return mock


# ─────────────────────────────────────────
# _filter_candidates テスト
# ─────────────────────────────────────────

class TestFilterCandidates:

    def test_空プール_空リストを返す(self):
        result = _filter_candidates([], Decimal("10000"))
        assert result == []

    def test_全件余裕額以内_スコア降順で返す(self):
        items = [
            _make_item("a", score=0.3, price="500"),
            _make_item("b", score=0.8, price="1000"),
            _make_item("c", score=0.5, price="2000"),
        ]
        result = _filter_candidates(items, Decimal("5000"))
        assert [i.id for i in result] == ["b", "c", "a"]

    def test_余裕額超過アイテムは除外される(self):
        items = [
            _make_item("cheap", price="500"),
            _make_item("expensive", price="20000"),
        ]
        result = _filter_candidates(items, Decimal("10000"))
        assert len(result) == 1
        assert result[0].id == "cheap"

    def test_ちょうど余裕額と同額は含まれる(self):
        items = [_make_item("exact", price="10000")]
        result = _filter_candidates(items, Decimal("10000"))
        assert len(result) == 1

    def test_max_count_で上限制限される(self):
        items = [_make_item(str(i), price="100", score=float(i) / 10) for i in range(10)]
        result = _filter_candidates(items, Decimal("10000"), max_count=3)
        assert len(result) == 3

    def test_余裕額以内の候補が0件_空リストを返す(self):
        items = [_make_item("expensive", price="50000")]
        result = _filter_candidates(items, Decimal("3000"))
        assert result == []


# ─────────────────────────────────────────
# _build_calendar_context テスト
# ─────────────────────────────────────────

class TestBuildCalendarContext:

    def test_空リスト_Noneを返す(self):
        assert _build_calendar_context([]) is None

    def test_サマリーなしイベント_Noneを返す(self):
        events = [{"start": "2026-05-16"}, {"description": "メモ"}]
        assert _build_calendar_context(events) is None

    def test_1件のイベント_コンテキスト文字列を返す(self):
        events = [{"summary": "朝会"}]
        result = _build_calendar_context(events)
        assert result is not None
        assert "朝会" in result

    def test_複数イベント_最大3件を含む(self):
        events = [
            {"summary": "朝会"},
            {"summary": "昼休み"},
            {"summary": "夕会"},
            {"summary": "4件目"},  # 4件目は除外
        ]
        result = _build_calendar_context(events)
        assert result is not None
        assert "朝会" in result
        assert "昼休み" in result
        assert "夕会" in result
        assert "4件目" not in result

    def test_一部サマリーなし_有効なものだけ含む(self):
        events = [
            {"summary": "有効なイベント"},
            {"description": "サマリーなし"},
        ]
        result = _build_calendar_context(events)
        assert result is not None
        assert "有効なイベント" in result


# ─────────────────────────────────────────
# propose_reward テスト
# ─────────────────────────────────────────

class TestProposeReward:

    def test_余裕額0以下_やんわり止めを返す(self):
        ddb = MagicMock()
        # 予算 5000、支出 10000（超過）
        ddb.get_item.return_value = {"reward_budget_monthly": "5000"}
        ddb.query_by_pk.return_value = [
            {"amount": "10000", "SK": "EXPENSE#2026-05-01T..."}
        ]
        ddb.put_item.return_value = None

        with patch("handlers.reward_proposal._calendar_service") as mock_cal:
            mock_cal.is_connected.return_value = False
            result = propose_reward("u1", "疲れた", ddb)

        assert result  # 空でない
        # 止めメッセージが返る（"うーん" や "来月" を含む）
        assert any(kw in result for kw in ["来月", "カツカツ", "予算", "おあずけ"])
        # 提案履歴保存が呼ばれた
        ddb.put_item.assert_called()

    def test_候補なし_フォールバックを返す(self):
        ddb = MagicMock()
        ddb.get_item.side_effect = lambda pk, sk: (
            {"reward_budget_monthly": "10000"} if sk == "PROFILE#" else None
        )
        ddb.query_by_pk.return_value = []

        with patch("handlers.reward_proposal._calendar_service") as mock_cal:
            mock_cal.is_connected.return_value = False
            result = propose_reward("u1", "疲れた", ddb)

        assert result
        assert any(kw in result for kw in ["見つからなかった", "候補", "明日"])

    def test_正常系_Bedrockの返答を返す(self):
        pool_items = [_make_item("item1", price="800", score=0.8)]
        ddb = _make_ddb_with_pool(pool_items)

        with patch("handlers.reward_proposal._bedrock") as mock_bedrock, \
             patch("handlers.reward_proposal._calendar_service") as mock_cal:
            mock_bedrock.invoke_text.return_value = "スイーツおすすめだよ！"
            mock_cal.is_connected.return_value = False
            result = propose_reward("u1", "疲れた", ddb)

        assert result == "スイーツおすすめだよ！"
        mock_bedrock.invoke_text.assert_called_once()

    def test_Bedrockエラー_フォールバックを返す(self):
        from utils.exceptions import BedrockError

        pool_items = [_make_item("item1", price="800")]
        ddb = _make_ddb_with_pool(pool_items)

        with patch("handlers.reward_proposal._bedrock") as mock_bedrock, \
             patch("handlers.reward_proposal._calendar_service") as mock_cal:
            mock_bedrock.invoke_text.side_effect = BedrockError("Throttled")
            mock_cal.is_connected.return_value = False
            result = propose_reward("u1", "疲れた", ddb)

        assert result
        # フォールバックメッセージが返る
        assert any(kw in result for kw in ["フリーズ", "調子", "もう一回"])

    def test_tone_polite_対応メッセージ(self):
        """口調廃止後: polite指定でも単一キャラ（ふれまーるちゃん）のメッセージが返る"""
        ddb = MagicMock()
        ddb.get_item.return_value = {"reward_budget_monthly": "5000"}
        ddb.query_by_pk.return_value = [{"amount": "10000"}]
        ddb.put_item.return_value = None

        with patch("handlers.reward_proposal._calendar_service") as mock_cal:
            mock_cal.is_connected.return_value = False
            result = propose_reward("u1", "疲れた", ddb, tone="polite")

        # slack不足なので止めメッセージが返る（口調は廃止されたのでカツカツメッセージ）
        assert isinstance(result, str) and len(result) > 0

    def test_Google_Calendarコンテキストあり_プロンプトに反映(self):
        pool_items = [_make_item("item1", price="800")]
        ddb = _make_ddb_with_pool(pool_items)

        captured_prompt: list[str] = []

        def fake_invoke(prompt, **kwargs):
            captured_prompt.append(prompt)
            return "今日も会議お疲れ！スイーツどうぞ✨"

        with patch("handlers.reward_proposal._bedrock") as mock_bedrock, \
             patch("handlers.reward_proposal._calendar_service") as mock_cal:
            mock_bedrock.invoke_text.side_effect = fake_invoke
            mock_cal.is_connected.return_value = True
            mock_cal.get_today_events.return_value = [{"summary": "重要な会議"}]
            result = propose_reward("u1", "疲れた", ddb)

        assert captured_prompt
        assert "重要な会議" in captured_prompt[0]

    def test_提案履歴_DynamoDBに保存される(self):
        pool_items = [_make_item("item1", price="800", score=0.9)]
        ddb = _make_ddb_with_pool(pool_items)

        with patch("handlers.reward_proposal._bedrock") as mock_bedrock, \
             patch("handlers.reward_proposal._calendar_service") as mock_cal:
            mock_bedrock.invoke_text.return_value = "おすすめだよ！"
            mock_cal.is_connected.return_value = False
            propose_reward("u1", "疲れた", ddb)

        # put_item が呼ばれた（提案履歴保存）
        ddb.put_item.assert_called()
        call_args = ddb.put_item.call_args
        _, kwargs = call_args
        # item_name が含まれている
        item_arg = call_args[0][2] if len(call_args[0]) >= 3 else call_args[1].get("item", {})
        # REWARD_SUGGESTION# SK で保存された
        sk_arg = call_args[0][1] if len(call_args[0]) >= 2 else call_args[1].get("sk", "")
        assert "REWARD_SUGGESTION#" in str(sk_arg)

    def test_Calendarエラー_コンテキストなしで続行(self):
        pool_items = [_make_item("item1", price="800")]
        ddb = _make_ddb_with_pool(pool_items)

        with patch("handlers.reward_proposal._bedrock") as mock_bedrock, \
             patch("handlers.reward_proposal._calendar_service") as mock_cal:
            mock_bedrock.invoke_text.return_value = "おすすめ！"
            mock_cal.is_connected.return_value = True
            mock_cal.get_today_events.side_effect = Exception("Calendar API Error")
            result = propose_reward("u1", "疲れた", ddb)

        # エラーでも返答は返る
        assert result == "おすすめ！"
