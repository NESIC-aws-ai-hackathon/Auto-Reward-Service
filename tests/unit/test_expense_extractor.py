"""
expense_extractor.py ユニットテスト

LLM 呼び出しはモックして、抽出ロジック・フロー制御を検証する。
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────
# フィクスチャ
# ─────────────────────────────────────────

@pytest.fixture
def mock_ddb():
    ddb = MagicMock()
    ddb.get_item.return_value = None
    ddb.put_item.return_value = None
    ddb.delete_item.return_value = None
    return ddb


def _make_llm_response(is_expense: bool, items: list[dict]) -> str:
    return json.dumps({"is_expense": is_expense, "items": items})


# ─────────────────────────────────────────
# 正常系: 支出として抽出・保存
# ─────────────────────────────────────────

def test_extract_single_expense_high_confidence(mock_ddb):
    """確信度 >= 0.7 の支出を即時保存する"""
    from handlers import expense_extractor

    llm_resp = _make_llm_response(True, [
        {"item_name": "プリン", "amount": 320, "store_name": None, "category": "情緒安定費", "confidence": 0.9}
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.extract("プリン買った 320円", "user1", mock_ddb)

    assert "プリン" in reply
    assert "320" in reply
    assert len(items) == 1
    assert items[0]["amount"] == 320
    assert items[0]["category"] == "情緒安定費"


def test_extract_non_expense_returns_empty(mock_ddb):
    """支出でないテキストは空文字と空リストを返す"""
    from handlers import expense_extractor

    llm_resp = _make_llm_response(False, [])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.extract("今日も疲れた", "user1", mock_ddb)

    assert reply == ""
    assert items == []


def test_extract_multiple_items(mock_ddb):
    """複数アイテムをまとめて保存する"""
    from handlers import expense_extractor

    llm_resp = _make_llm_response(True, [
        {"item_name": "コーヒー", "amount": 500, "store_name": "スタバ", "category": "情緒安定費", "confidence": 0.95},
        {"item_name": "サンドイッチ", "amount": 450, "store_name": "スタバ", "category": "日常消費", "confidence": 0.90},
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.extract("スタバでコーヒーとサンドイッチ買った", "user1", mock_ddb)

    assert len(items) == 2
    assert "全部" in reply or "コーヒー" in reply


# ─────────────────────────────────────────
# 正常系: 確認フロー
# ─────────────────────────────────────────

def test_extract_low_confidence_saves_pending(mock_ddb):
    """確信度 < 0.7 は PENDING_EXPENSE に保存して確認を返す"""
    from handlers import expense_extractor

    llm_resp = _make_llm_response(True, [
        {"item_name": "何か", "amount": 1500, "store_name": None, "category": "その他", "confidence": 0.5}
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.extract("買い物した", "user1", mock_ddb)

    assert "はい" in reply or "いいかな" in reply
    assert items == []  # 保存は pending
    mock_ddb.put_item.assert_called_once()


def test_extract_null_amount_saves_clarification(mock_ddb):
    """amount が None の場合は PENDING_CLARIFICATION に保存して質問を返す"""
    from handlers import expense_extractor

    llm_resp = _make_llm_response(True, [
        {"item_name": "プリン", "amount": None, "store_name": None, "category": "情緒安定費", "confidence": 0.9}
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.extract("プリン買った", "user1", mock_ddb)

    assert "いくら" in reply
    assert items == []
    mock_ddb.put_item.assert_called_once()


# ─────────────────────────────────────────
# セキュリティ: 金額範囲外
# ─────────────────────────────────────────

def test_extract_amount_over_max_sets_zero_confidence(mock_ddb):
    """SEC-3-03: 金額が 9,999,999 を超えると confidence=0.0 → 確認フロー"""
    from handlers import expense_extractor

    llm_resp = _make_llm_response(True, [
        {"item_name": "なんか高いもの", "amount": 10_000_000, "store_name": None, "category": "その他", "confidence": 0.95}
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.extract("高いもの買った", "user1", mock_ddb)

    # confidence=0.0 → pending_expense に保存
    assert items == []
    mock_ddb.put_item.assert_called()


def test_extract_amount_zero_sets_zero_confidence(mock_ddb):
    """SEC-3-03: 金額 0 は範囲外 → confidence=0.0"""
    from handlers import expense_extractor

    llm_resp = _make_llm_response(True, [
        {"item_name": "無料サンプル", "amount": 0, "store_name": None, "category": "その他", "confidence": 0.99}
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.extract("もらった", "user1", mock_ddb)

    assert items == []


# ─────────────────────────────────────────
# 明確化フロー
# ─────────────────────────────────────────

def test_handle_clarification_success(mock_ddb):
    """追加質問への回答で金額が取れた場合は即時保存"""
    from handlers import expense_extractor

    pending = {
        "waiting_for": "amount",
        "partial_items": [{"item_name": "プリン", "category": "情緒安定費", "confidence": 0.9}],
        "retry_count": 0,
    }

    llm_resp = _make_llm_response(True, [
        {"item_name": "プリン", "amount": 320, "store_name": None, "category": "情緒安定費", "confidence": 0.9}
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.handle_clarification("320円", "user1", pending, mock_ddb)

    assert len(items) == 1
    assert items[0]["amount"] == 320
    mock_ddb.delete_item.assert_called_once()


def test_handle_clarification_retry_limit(mock_ddb):
    """BR-3-02: リトライ上限 (2) を超えたら諦めメッセージ"""
    from handlers import expense_extractor

    pending = {
        "waiting_for": "amount",
        "partial_items": [],
        "retry_count": 2,
    }

    reply, items = expense_extractor.handle_clarification("えーと", "user1", pending, mock_ddb)

    assert items == []
    assert "記録しない" in reply
    mock_ddb.delete_item.assert_called_once()


def test_handle_clarification_still_null_increments_retry(mock_ddb):
    """追加質問への回答でも金額不明な場合は retry_count++ して再質問"""
    from handlers import expense_extractor

    pending = {
        "waiting_for": "amount",
        "partial_items": [{"item_name": "お菓子", "category": "その他"}],
        "retry_count": 0,
    }

    llm_resp = _make_llm_response(True, [
        {"item_name": "お菓子", "amount": None, "category": "その他", "confidence": 0.6}
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.handle_clarification("安かった", "user1", pending, mock_ddb)

    assert items == []
    assert "もう一度" in reply or "金額" in reply
    # retry_count を更新する put_item が呼ばれる
    mock_ddb.put_item.assert_called_once()


# ─────────────────────────────────────────
# 確認フロー: confirm/reject
# ─────────────────────────────────────────

def test_confirm_pending_expense(mock_ddb):
    """CONFIRM_YES: pending_expense を削除して items を返す"""
    from handlers import expense_extractor

    pending = {
        "extracted": {"item_name": "何か", "amount": 1500, "category": "その他", "confidence": 0.5},
        "confidence": 0.5,
        "raw_text": "買い物した",
    }

    reply, items = expense_extractor.confirm_pending_expense("user1", pending, mock_ddb)

    assert len(items) == 1
    assert items[0]["amount"] == 1500
    mock_ddb.delete_item.assert_called_once()


def test_reject_pending_expense(mock_ddb):
    """CONFIRM_NO: pending_expense を削除して空リストを返す"""
    from handlers import expense_extractor

    reply = expense_extractor.reject_pending_expense("user1", mock_ddb)

    assert "記録しない" in reply
    mock_ddb.delete_item.assert_called_once()


# ─────────────────────────────────────────
# PENDING_CLARIFICATION チェック（extract 冒頭）
# ─────────────────────────────────────────

def test_extract_routes_to_clarification_when_pending(mock_ddb):
    """PENDING_CLARIFICATION が存在する場合は handle_clarification にルーティング"""
    from handlers import expense_extractor

    pending_clarif = {
        "waiting_for": "amount",
        "partial_items": [{"item_name": "プリン"}],
        "retry_count": 0,
    }
    mock_ddb.get_item.side_effect = lambda pk, sk: pending_clarif if sk == "PENDING_CLARIFICATION#" else None

    llm_resp = _make_llm_response(True, [
        {"item_name": "プリン", "amount": 320, "category": "情緒安定費", "confidence": 0.9}
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.extract("320円", "user1", mock_ddb)

    assert len(items) == 1


# ─────────────────────────────────────────
# カテゴリバリデーション
# ─────────────────────────────────────────

def test_extract_invalid_category_fallback(mock_ddb):
    """LLM が不明なカテゴリを返した場合は「その他」にフォールバック"""
    from handlers import expense_extractor

    llm_resp = _make_llm_response(True, [
        {"item_name": "謎の支出", "amount": 1000, "category": "存在しないカテゴリ", "confidence": 0.9}
    ])

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = llm_resp
        reply, items = expense_extractor.extract("なんか買った", "user1", mock_ddb)

    assert items[0]["category"] == "その他"


# ─────────────────────────────────────────
# JSON パースエラー耐性
# ─────────────────────────────────────────

def test_extract_llm_returns_invalid_json(mock_ddb):
    """LLM が JSON でないテキストを返した場合は空を返す"""
    from handlers import expense_extractor

    with patch("handlers.expense_extractor.get_bedrock_service") as mock_bedrock:
        mock_bedrock.return_value.invoke_text.return_value = "すみません、わかりません"
        reply, items = expense_extractor.extract("あれ買った", "user1", mock_ddb)

    assert reply == ""
    assert items == []
