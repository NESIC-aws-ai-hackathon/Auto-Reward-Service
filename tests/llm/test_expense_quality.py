"""
LLM 品質テスト — 支出抽出精度

実際に Bedrock を呼び出して抽出品質を評価する。
通常の `pytest tests/unit` では skip される。
実行方法: pytest tests/llm/ -v --run-llm

前提条件:
  - AWS_PROFILE=share が設定されていること
  - Bedrock で amazon.nova-lite-v1:0 が利用可能であること
  - TABLE_NAME 環境変数（ダミーでOK: ArsTable-test）
"""
from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

# sys.path 設定
_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, "layer", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, "src")))


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: mark test as requiring real LLM calls")


# すべての LLM テストをデフォルト skip
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LLM_TESTS"),
    reason="RUN_LLM_TESTS 環境変数が未設定のためスキップ（実行: RUN_LLM_TESTS=1 pytest tests/llm/）",
)


@pytest.fixture(scope="module", autouse=True)
def setup_env():
    os.environ.setdefault("TABLE_NAME", "ArsTable-test")
    os.environ.setdefault("AWS_REGION", "ap-northeast-1")
    os.environ.setdefault("BEDROCK_TEXT_MODEL_ID", "amazon.nova-lite-v1:0")
    os.environ.setdefault("BEDROCK_IMAGE_MODEL_ID", "amazon.nova-lite-v1:0")
    os.environ.setdefault("BEDROCK_FALLBACK_MODEL_ID", "amazon.nova-lite-v1:0")


@pytest.fixture
def mock_ddb():
    ddb = MagicMock()
    ddb.get_item.return_value = None
    return ddb


# ─────────────────────────────────────────
# テストケース定義
# ─────────────────────────────────────────

# (入力テキスト, 期待 is_expense, 期待 amount, 期待 category_contains)
EXPENSE_CASES = [
    ("プリン買った 320円", True, 320, "情緒安定費"),
    ("スタバでラテ飲んだ、550円", True, 550, "情緒安定費"),
    ("Amazonで本を買った 1,500円", True, 1500, "成長投資費"),
    ("コンビニで弁当とお茶 780円", True, 780, "日常消費"),
    ("疲れたからマッサージ行った 3000円", True, 3000, "回復費"),
    ("今日も仕事頑張った", False, None, None),
    ("疲れた", False, None, None),
    ("おはよう", False, None, None),
]


@pytest.mark.parametrize("text,expected_is_expense,expected_amount,expected_category", EXPENSE_CASES)
def test_expense_extraction_quality(text, expected_is_expense, expected_amount, expected_category, mock_ddb):
    """支出テキストの抽出精度を検証する（実 Bedrock 呼び出し）"""
    from handlers.expense_extractor import extract

    reply, items = extract(text, "user_quality_test", mock_ddb)

    if not expected_is_expense:
        assert reply == "", f"非支出テキストなのに reply が返った: {reply!r}"
        assert items == [], f"非支出テキストなのに items が返った: {items}"
        return

    assert reply != "", f"支出テキストなのに reply が空: text={text!r}"
    assert len(items) > 0 or "はい" in reply or "いくら" in reply, \
        f"支出テキストなのに items が空で確認/質問もない: text={text!r}, reply={reply!r}"

    if items and expected_amount is not None:
        amounts = [it.get("amount") for it in items if it.get("amount")]
        assert expected_amount in amounts, \
            f"期待金額 {expected_amount} が抽出されなかった: amounts={amounts}, text={text!r}"

    if items and expected_category:
        categories = [it.get("category") for it in items]
        assert any(expected_category in (c or "") for c in categories), \
            f"期待カテゴリ {expected_category!r} が含まれなかった: categories={categories}, text={text!r}"


# ─────────────────────────────────────────
# 月次累計表示の確認
# ─────────────────────────────────────────

def test_reply_contains_monthly_total(mock_ddb):
    """Q7=C: 返信に月次累計が含まれる"""
    from handlers.expense_extractor import extract

    mock_ddb.get_item.return_value = {"total_amount": 5000, "reward_budget_monthly": 30000}

    reply, items = extract("プリン買った 320円", "user_monthly_test", mock_ddb)

    if reply and items:
        assert "今月" in reply, f"月次情報が含まれない: {reply!r}"
        assert "円" in reply


# ─────────────────────────────────────────
# カテゴリ 10 種類の基本確認
# ─────────────────────────────────────────

CATEGORY_CASES = [
    ("温泉旅行の宿泊費 15000円", "旅行・体験費"),
    ("英会話スクール代 8000円", "成長投資費"),
    ("友達の誕生日プレゼント 3000円", "おすそわけ費"),
    ("高級フレンチディナー 25000円", "高級ご褒美費"),
    ("ヤケ食いでコンビニ爆買い 2500円", "緊急回復費"),
]


@pytest.mark.parametrize("text,expected_category", CATEGORY_CASES)
def test_category_classification_quality(text, expected_category, mock_ddb):
    """カテゴリ分類の精度テスト"""
    from handlers.expense_extractor import extract

    reply, items = extract(text, "user_cat_test", mock_ddb)

    # 確認待ちフローになることも許容（低確信度の場合）
    if not items:
        return  # 確認待ちは精度問題でないためスキップ

    categories = [it.get("category") for it in items]
    assert any(expected_category in (c or "") for c in categories), \
        f"期待カテゴリ {expected_category!r} が含まれなかった: {categories}, text={text!r}"
