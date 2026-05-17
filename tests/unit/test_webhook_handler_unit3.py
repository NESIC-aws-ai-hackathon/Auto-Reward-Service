"""
webhook_handler.py Unit 3 拡張テスト

支出記録フロー（EXPENSE, CONFIRM_YES/NO, PENDING_CLARIFICATION, image）を検証する。
"""
from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from webhook_handler import handler


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────

def _make_apigw_event(body: str) -> dict:
    return {
        "headers": {"x-line-signature": "valid_sig"},
        "body": body,
        "isBase64Encoded": False,
    }


def _text_event(text: str, reply_token: str = "rt1", user_id: str = "U001") -> dict:
    return {
        "type": "message",
        "replyToken": reply_token,
        "source": {"type": "user", "userId": user_id},
        "message": {"type": "text", "id": "m1", "text": text},
    }


def _image_event(msg_id: str = "img001", reply_token: str = "rt_img", user_id: str = "U001") -> dict:
    return {
        "type": "message",
        "replyToken": reply_token,
        "source": {"type": "user", "userId": user_id},
        "message": {"type": "image", "id": msg_id},
    }


def _body(events: list[dict]) -> str:
    return json.dumps({"events": events})


@pytest.fixture
def mock_line():
    svc = MagicMock()
    svc.verify_signature.return_value = True
    with patch("webhook_handler.get_line_service", return_value=svc):
        yield svc


@pytest.fixture
def mock_ddb():
    m = MagicMock()
    m.get_item.side_effect = lambda pk=None, sk=None: (
        {"entityType": "PROFILE", "status": "ACTIVE", "tone": "friendly"}
        if sk == "PROFILE#" else None
    )
    m.put_item.return_value = None
    m.update_item.return_value = None
    m.increment_atomic_counter.return_value = 1
    m.add_to_monthly_summary.return_value = {}
    with patch("webhook_handler._get_ddb", return_value=m):
        yield m


# ─────────────────────────────────────────
# EXPENSE intent → expense_extractor.extract
# ─────────────────────────────────────────

class TestExpenseIntentRouting:
    def test_expense_intent_calls_extractor(self, mock_line, mock_ddb):
        """EXPENSE intent は expense_extractor.extract に委譲される"""
        with patch("webhook_handler.classify_intent", return_value={"intent": "EXPENSE", "confidence": 0.9}):
            with patch("handlers.expense_extractor.extract", return_value=("プリン320円、覚えた〜🍮\n今月 320円。まだ 29,680円使えるよ！", [])) as mock_extract:
                result = handler(_make_apigw_event(_body([_text_event("プリン買った 320円")])), None)

        assert result["statusCode"] == 200
        mock_extract.assert_called_once()
        called_text = mock_extract.call_args[0][0]
        assert called_text == "プリン買った 320円"

    def test_expense_empty_reply_falls_through_to_chat(self, mock_line, mock_ddb):
        """expense_extractor.extract が空を返したら通常チャットフローへ"""
        with patch("webhook_handler.classify_intent", return_value={"intent": "EXPENSE", "confidence": 0.9}):
            with patch("handlers.expense_extractor.extract", return_value=("", [])):
                with patch("webhook_handler.generate_reply", return_value="チャット返信") as mock_generate:
                    result = handler(_make_apigw_event(_body([_text_event("何か買ったかも")])), None)

        assert result["statusCode"] == 200
        mock_generate.assert_called_once()


# ─────────────────────────────────────────
# PENDING_CLARIFICATION チェック
# ─────────────────────────────────────────

class TestPendingClarificationFlow:
    def test_pending_clarification_skips_classify_intent(self, mock_line, mock_ddb):
        """PENDING_CLARIFICATION がある場合は classify_intent を呼ばない"""
        pending = {"waiting_for": "amount", "partial_items": [{"item_name": "プリン"}], "retry_count": 0}

        def get_item_side(pk=None, sk=None):
            if sk == "PROFILE#":
                return {"entityType": "PROFILE", "status": "ACTIVE", "tone": "friendly"}
            return pending if sk == "PENDING_CLARIFICATION#" else None

        mock_ddb.get_item.side_effect = get_item_side

        with patch("handlers.expense_extractor.handle_clarification", return_value=("プリン320円！", [{"amount": 320}])) as mock_clarif:
            with patch("webhook_handler.classify_intent") as mock_classify:
                result = handler(_make_apigw_event(_body([_text_event("320円")])), None)

        mock_clarif.assert_called_once()
        mock_classify.assert_not_called()
        assert result["statusCode"] == 200


# ─────────────────────────────────────────
# PENDING_EXPENSE + CONFIRM_YES/NO
# ─────────────────────────────────────────

class TestPendingExpenseConfirm:
    def _setup_pending(self, mock_ddb):
        pending = {"extracted": {"item_name": "何か", "amount": 1500, "category": "その他"}, "confidence": 0.5, "raw_text": ""}

        def get_item_side(pk=None, sk=None):
            if sk == "PROFILE#":
                return {"entityType": "PROFILE", "status": "ACTIVE", "tone": "friendly"}
            if sk == "PENDING_CLARIFICATION#":
                return None
            if sk == "PENDING_EXPENSE#":
                return pending
            return None

        mock_ddb.get_item.side_effect = get_item_side
        return pending

    def test_confirm_yes_calls_confirm_pending_expense(self, mock_line, mock_ddb):
        """CONFIRM_YES は confirm_pending_expense に委譲する"""
        self._setup_pending(mock_ddb)
        with patch("webhook_handler.classify_intent", return_value={"intent": "CONFIRM_YES", "confidence": 0.95}):
            with patch("handlers.expense_extractor.confirm_pending_expense", return_value=("覚えた！", [{"amount": 1500}])) as mock_confirm:
                result = handler(_make_apigw_event(_body([_text_event("はい")])), None)

        mock_confirm.assert_called_once()
        assert result["statusCode"] == 200

    def test_confirm_no_calls_reject_pending_expense(self, mock_line, mock_ddb):
        """CONFIRM_NO は reject_pending_expense に委譲する"""
        self._setup_pending(mock_ddb)
        with patch("webhook_handler.classify_intent", return_value={"intent": "CONFIRM_NO", "confidence": 0.95}):
            with patch("handlers.expense_extractor.reject_pending_expense", return_value="記録しないね") as mock_reject:
                result = handler(_make_apigw_event(_body([_text_event("いいえ")])), None)

        mock_reject.assert_called_once()
        assert result["statusCode"] == 200

    def test_other_intent_falls_through_with_pending_expense(self, mock_line, mock_ddb):
        """PENDING_EXPENSE あり + CHAT intent → 通常フロー（pending はそのまま）"""
        self._setup_pending(mock_ddb)
        with patch("webhook_handler.classify_intent", return_value={"intent": "CHAT", "confidence": 0.8}):
            with patch("webhook_handler.generate_reply", return_value="チャット") as mock_generate:
                result = handler(_make_apigw_event(_body([_text_event("今日も疲れた")])), None)

        mock_generate.assert_called_once()
        assert result["statusCode"] == 200


# ─────────────────────────────────────────
# 画像メッセージ → receipt_analyzer
# ─────────────────────────────────────────

class TestImageMessageRouting:
    def test_image_calls_receipt_analyzer(self, mock_line, mock_ddb):
        """画像メッセージは receipt_analyzer.analyze に委譲される"""
        mock_line.get_message_content.return_value = b"\xff\xd8\xff"
        with patch("handlers.receipt_analyzer.analyze", return_value=("レシート読んだよ！", [])) as mock_analyze:
            result = handler(_make_apigw_event(_body([_image_event()])), None)

        assert result["statusCode"] == 200
        mock_analyze.assert_called_once()
        args = mock_analyze.call_args[1] if mock_analyze.call_args[1] else mock_analyze.call_args[0]

    def test_image_get_content_failure_returns_fallback(self, mock_line, mock_ddb):
        """画像取得失敗時はフォールバックメッセージを返す"""
        from utils.exceptions import LineServiceError
        mock_line.get_message_content.side_effect = LineServiceError("取得失敗")
        result = handler(_make_apigw_event(_body([_image_event()])), None)

        assert result["statusCode"] == 200
        call_args = mock_line.reply_message.call_args[0]
        reply_text = call_args[1][0]["text"]
        assert "取得できなかった" in reply_text


# ─────────────────────────────────────────
# _save_expense_items: DDB 保存の確認
# ─────────────────────────────────────────

class TestSaveExpenseItems:
    def test_save_expense_items_calls_put_and_monthly_summary(self, mock_ddb):
        """_save_expense_items は put_item と add_to_monthly_summary を呼ぶ"""
        import webhook_handler as wh

        mock_ddb.get_item.return_value = {"reward_budget_monthly": 30000}
        wh._save_expense_items(
            user_id="U001",
            items=[{"item_name": "プリン", "amount": 320, "category": "情緒安定費", "source": "text", "confidence": 0.9}],
            ddb=mock_ddb,
        )

        mock_ddb.put_item.assert_called_once()
        mock_ddb.add_to_monthly_summary.assert_called_once()

    def test_save_expense_items_empty_list_noop(self, mock_ddb):
        """空リストは何もしない"""
        import webhook_handler as wh

        wh._save_expense_items(user_id="U001", items=[], ddb=mock_ddb)

        mock_ddb.put_item.assert_not_called()
        mock_ddb.add_to_monthly_summary.assert_not_called()
