"""
receipt_analyzer.py ユニットテスト

LLM 呼び出しはモックして、レシート解析ロジックを検証する。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_ddb():
    ddb = MagicMock()
    ddb.get_item.return_value = None
    ddb.put_item.return_value = None
    ddb.delete_item.return_value = None
    return ddb


def _receipt_response(
    parse_failed: bool = False,
    store_name: str | None = None,
    items: list | None = None,
    total_amount: int | None = None,
    confidence: float = 0.9,
    purchased_at: str | None = None,
) -> str:
    return json.dumps({
        "parse_failed": parse_failed,
        "store_name": store_name,
        "items": items or [],
        "total_amount": total_amount,
        "confidence": confidence,
        "purchased_at": purchased_at,
    })


SAMPLE_IMAGE = b"\xff\xd8\xff"  # JPEG マジックバイト（ダミー）


# ─────────────────────────────────────────
# 正常系
# ─────────────────────────────────────────

def test_analyze_single_item_high_confidence(mock_ddb):
    """単一アイテム・高確信度は即時保存"""
    from handlers import receipt_analyzer

    resp = _receipt_response(
        store_name="セブン-イレブン",
        items=[{"item_name": "プリン", "amount": 298, "category": "情緒安定費", "confidence": 0.95}],
        total_amount=298,
    )

    with patch("handlers.receipt_analyzer.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_image.return_value = resp
        reply, items = receipt_analyzer.analyze(SAMPLE_IMAGE, "image/jpeg", "user1", mock_ddb)

    assert "プリン" in reply
    assert len(items) == 1
    assert items[0]["store_name"] == "セブン-イレブン"
    assert items[0]["source"] == "receipt_image"


def test_analyze_multiple_items(mock_ddb):
    """複数アイテムは全て保存"""
    from handlers import receipt_analyzer

    resp = _receipt_response(
        store_name="コンビニ",
        items=[
            {"item_name": "おにぎり", "amount": 150, "category": "日常消費", "confidence": 0.92},
            {"item_name": "コーヒー", "amount": 120, "category": "情緒安定費", "confidence": 0.88},
        ],
        total_amount=270,
    )

    with patch("handlers.receipt_analyzer.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_image.return_value = resp
        reply, items = receipt_analyzer.analyze(SAMPLE_IMAGE, "image/jpeg", "user1", mock_ddb)

    assert len(items) == 2


# ─────────────────────────────────────────
# parse_failed
# ─────────────────────────────────────────

def test_analyze_parse_failed_returns_fallback(mock_ddb):
    """parse_failed=True の場合はフォールバックメッセージを返す"""
    from handlers import receipt_analyzer

    resp = _receipt_response(parse_failed=True)

    with patch("handlers.receipt_analyzer.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_image.return_value = resp
        reply, items = receipt_analyzer.analyze(SAMPLE_IMAGE, "image/jpeg", "user1", mock_ddb)

    assert "読み取れなかった" in reply
    assert items == []


# ─────────────────────────────────────────
# 低確信度 → PENDING_EXPENSE
# ─────────────────────────────────────────

def test_analyze_low_confidence_saves_pending(mock_ddb):
    """全アイテム確信度 < 0.7 → PENDING_EXPENSE に保存"""
    from handlers import receipt_analyzer

    resp = _receipt_response(
        store_name=None,
        items=[{"item_name": "不明な商品", "amount": 500, "category": "その他", "confidence": 0.5}],
        confidence=0.5,
    )

    with patch("handlers.receipt_analyzer.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_image.return_value = resp
        reply, items = receipt_analyzer.analyze(SAMPLE_IMAGE, "image/jpeg", "user1", mock_ddb)

    assert items == []
    assert "はい" in reply or "いいかな" in reply
    mock_ddb.put_item.assert_called_once()


# ─────────────────────────────────────────
# 金額範囲外
# ─────────────────────────────────────────

def test_analyze_amount_over_max(mock_ddb):
    """SEC-3-03: 金額が 9,999,999 超は confidence=0.0 → pending"""
    from handlers import receipt_analyzer

    resp = _receipt_response(
        items=[{"item_name": "ジュエリー", "amount": 10_000_000, "category": "高級ご褒美費", "confidence": 0.95}],
    )

    with patch("handlers.receipt_analyzer.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_image.return_value = resp
        reply, items = receipt_analyzer.analyze(SAMPLE_IMAGE, "image/jpeg", "user1", mock_ddb)

    assert items == []


# ─────────────────────────────────────────
# カテゴリバリデーション
# ─────────────────────────────────────────

def test_analyze_invalid_category_fallback(mock_ddb):
    """不明なカテゴリは「その他」にフォールバック"""
    from handlers import receipt_analyzer

    resp = _receipt_response(
        items=[{"item_name": "謎商品", "amount": 300, "category": "不明カテゴリ", "confidence": 0.9}],
    )

    with patch("handlers.receipt_analyzer.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_image.return_value = resp
        reply, items = receipt_analyzer.analyze(SAMPLE_IMAGE, "image/jpeg", "user1", mock_ddb)

    assert items[0]["category"] == "その他"


# ─────────────────────────────────────────
# LLM エラー耐性
# ─────────────────────────────────────────

def test_analyze_llm_error_returns_fallback(mock_ddb):
    """LLM 例外でもフォールバックメッセージを返す"""
    from handlers import receipt_analyzer

    with patch("handlers.receipt_analyzer.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_image.side_effect = Exception("Bedrock error")
        reply, items = receipt_analyzer.analyze(SAMPLE_IMAGE, "image/jpeg", "user1", mock_ddb)

    assert "読み取れなかった" in reply
    assert items == []


def test_analyze_empty_items_with_total_amount(mock_ddb):
    """items が空でも total_amount があれば1件として扱う"""
    from handlers import receipt_analyzer

    resp = _receipt_response(
        store_name="スーパー",
        items=[],
        total_amount=1500,
        confidence=0.8,
    )

    with patch("handlers.receipt_analyzer.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_image.return_value = resp
        reply, items = receipt_analyzer.analyze(SAMPLE_IMAGE, "image/jpeg", "user1", mock_ddb)

    assert len(items) == 1
    assert items[0]["amount"] == 1500
