"""
追加機能のユニットテスト — Unit 7 拡張
talk_starter / recommend_flow / quick_expense / monthly_report / streak / postback routing
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────
# talk_starter テスト
# ─────────────────────────────────────────

class TestTalkStarter:

    def test_メッセージが返る(self):
        from services.talk_starter import generate_talk_starter
        ddb = MagicMock()
        ddb.get_item.return_value = {}
        result = generate_talk_starter("U123", ddb)
        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert len(result[0]["text"]) > 0

    def test_記念日近い場合リマインダー(self):
        from services.talk_starter import generate_talk_starter
        ddb = MagicMock()
        tomorrow = date.today() + timedelta(days=3)
        ann_date = f"{tomorrow.month:02d}-{tomorrow.day:02d}"
        ddb.get_item.return_value = {
            "anniversaries": [{"name": "彼女の誕生日", "date": ann_date}]
        }
        result = generate_talk_starter("U123", ddb)
        assert "彼女の誕生日" in result[0]["text"]
        assert "3日" in result[0]["text"]


# ─────────────────────────────────────────
# recommend_flow テスト
# ─────────────────────────────────────────

class TestRecommendFlow:

    def test_start_recommend_状態作成(self):
        from services.recommend_flow import start_recommend
        ddb = MagicMock()
        result = start_recommend("U123", ddb)
        assert result[0]["type"] == "text"
        assert "おすすめ" in result[0]["text"]
        ddb.put_item.assert_called_once()

    def test_handle_WAITING_CATEGORY(self):
        from services.recommend_flow import handle_recommend_reply
        ddb = MagicMock()
        state = {"step": "WAITING_CATEGORY", "created_at": "2026-05-17T00:00:00"}
        result = handle_recommend_reply("U123", "リラックス", state, ddb)
        assert "予算" in result[0]["text"]
        ddb.put_item.assert_called_once()

    @patch("services.recommend_flow._bedrock")
    def test_handle_WAITING_BUDGET_Bedrock呼び出し(self, mock_bedrock):
        from services.recommend_flow import handle_recommend_reply
        mock_bedrock.invoke_text.return_value = "① 入浴剤 🛁 1,500円\n② アロマオイル 🌿 990円\n③ ハンドクリーム ✨ 800円\n気になるのあった？😊"
        ddb = MagicMock()
        ddb.get_item.return_value = {"categories": ["美容"]}
        state = {"step": "WAITING_BUDGET", "category": "リラックス", "created_at": ""}
        result = handle_recommend_reply("U123", "3000円", state, ddb)
        assert len(result) == 1
        ddb.delete_item.assert_called_once()


# ─────────────────────────────────────────
# quick_expense テスト
# ─────────────────────────────────────────

class TestQuickExpense:

    def test_show_options_quickReply付き(self):
        from services.quick_expense import show_quick_expense_options
        result = show_quick_expense_options("U123")
        assert result[0]["type"] == "text"
        assert "quickReply" in result[0]
        assert len(result[0]["quickReply"]["items"]) == 7

    def test_WAITING_CATEGORY_カテゴリ確定(self):
        from services.quick_expense import handle_quick_expense_reply
        ddb = MagicMock()
        state = {"step": "WAITING_CATEGORY"}
        msgs, items = handle_quick_expense_reply("U123", "☕ カフェ", state, ddb)
        assert "いくらだった" in msgs[0]["text"]
        assert items == []
        ddb.put_item.assert_called_once()

    def test_WAITING_AMOUNT_記録(self):
        from services.quick_expense import handle_quick_expense_reply
        ddb = MagicMock()
        state = {"step": "WAITING_AMOUNT", "category": "カフェ"}
        msgs, items = handle_quick_expense_reply("U123", "650", state, ddb)
        assert "650円" in msgs[0]["text"]
        assert len(items) == 1
        assert items[0]["amount"] == 650

    def test_WAITING_AMOUNT_無効金額(self):
        from services.quick_expense import handle_quick_expense_reply
        ddb = MagicMock()
        state = {"step": "WAITING_AMOUNT", "category": "カフェ"}
        msgs, items = handle_quick_expense_reply("U123", "わからない", state, ddb)
        assert items == []

    def test_直接入力_状態クリア(self):
        from services.quick_expense import handle_quick_expense_reply
        ddb = MagicMock()
        state = {"step": "WAITING_CATEGORY"}
        msgs, items = handle_quick_expense_reply("U123", "✏️ 直接入力", state, ddb)
        assert "教えてね" in msgs[0]["text"]
        ddb.delete_item.assert_called_once()


# ─────────────────────────────────────────
# monthly_report テスト
# ─────────────────────────────────────────

class TestMonthlyReport:

    def test_正常系_FlexMessage返却(self):
        from services.monthly_report import generate_monthly_report
        ddb = MagicMock()
        ddb.get_item.side_effect = [
            {"carryover_rate": 0.5, "reward_budget_monthly": Decimal("24000")},  # PROFILE#
            {"total_budget": 24000, "total_amount": Decimal("8000"), "expense_count": 5, "carryover_amount": 4000},  # MONTHLY_SUMMARY#
        ]
        ddb.query_by_pk.return_value = [
            {"ars_category": "カフェ", "amount": Decimal("2800")},
            {"ars_category": "スイーツ", "amount": Decimal("1500")},
        ]
        result = generate_monthly_report("U123", ddb)
        assert result[0]["type"] == "flex"
        assert "レポート" in result[0]["altText"]

    def test_サマリーなし_0ベース(self):
        from services.monthly_report import generate_monthly_report
        ddb = MagicMock()
        ddb.get_item.side_effect = [
            {},    # PROFILE#
            None,  # MONTHLY_SUMMARY#
        ]
        ddb.query_by_pk.return_value = []
        result = generate_monthly_report("U123", ddb)
        assert result[0]["type"] == "flex"


# ─────────────────────────────────────────
# streak テスト
# ─────────────────────────────────────────

class TestStreak:

    def test_初回記録_streak_1(self):
        from services.streak import update_streak
        ddb = MagicMock()
        ddb.get_item.return_value = None
        result = update_streak("U123", ddb)
        ddb.put_item.assert_called_once()
        call_args = ddb.put_item.call_args[0][2]
        assert call_args["current_streak"] == 1

    def test_連続記録_streak増加(self):
        from services.streak import update_streak
        ddb = MagicMock()
        yesterday = str(date.today() - timedelta(days=1))
        ddb.get_item.return_value = {"current_streak": 2, "longest_streak": 2, "last_record_date": yesterday}
        result = update_streak("U123", ddb)
        call_args = ddb.put_item.call_args[0][2]
        assert call_args["current_streak"] == 3
        assert result == "3日連続で記録してくれてる！えらい〜✨"

    def test_同日二回目_None(self):
        from services.streak import update_streak
        ddb = MagicMock()
        ddb.get_item.return_value = {"current_streak": 3, "longest_streak": 3, "last_record_date": str(date.today())}
        result = update_streak("U123", ddb)
        assert result is None
        ddb.put_item.assert_not_called()

    def test_1日空き_リセット(self):
        from services.streak import update_streak
        ddb = MagicMock()
        two_days_ago = str(date.today() - timedelta(days=2))
        ddb.get_item.return_value = {"current_streak": 5, "longest_streak": 5, "last_record_date": two_days_ago}
        result = update_streak("U123", ddb)
        call_args = ddb.put_item.call_args[0][2]
        assert call_args["current_streak"] == 1
        assert call_args["longest_streak"] == 5

    def test_7日マイルストーン(self):
        from services.streak import update_streak
        ddb = MagicMock()
        yesterday = str(date.today() - timedelta(days=1))
        ddb.get_item.return_value = {"current_streak": 6, "longest_streak": 6, "last_record_date": yesterday}
        result = update_streak("U123", ddb)
        assert "1週間" in result


# ─────────────────────────────────────────
# postback routing テスト
# ─────────────────────────────────────────

class TestPostbackRouting:

    @patch("handlers.webhook_handler.get_line_service")
    @patch("handlers.webhook_handler._get_ddb")
    @patch("handlers.webhook_handler.generate_talk_starter")
    def test_start_talk_Replyで応答(self, mock_talk, mock_ddb, mock_line):
        from handlers.webhook_handler import _handle_postback
        mock_talk.return_value = [{"type": "text", "text": "最近どう？"}]
        mock_ddb.return_value = MagicMock()

        event = {
            "type": "postback",
            "postback": {"data": "action=start_talk"},
            "replyToken": "token123",
            "source": {"userId": "U123"},
        }
        _handle_postback(event)
        mock_line().reply_message.assert_called_once()

    @patch("handlers.webhook_handler.get_line_service")
    @patch("handlers.webhook_handler._get_ddb")
    @patch("handlers.webhook_handler.start_recommend")
    def test_start_recommend_Replyで応答(self, mock_rec, mock_ddb, mock_line):
        from handlers.webhook_handler import _handle_postback
        mock_rec.return_value = [{"type": "text", "text": "おすすめ！"}]
        mock_ddb.return_value = MagicMock()

        event = {
            "type": "postback",
            "postback": {"data": "action=start_recommend"},
            "replyToken": "token123",
            "source": {"userId": "U123"},
        }
        _handle_postback(event)
        mock_line().reply_message.assert_called_once()

    @patch("handlers.webhook_handler.get_line_service")
    @patch("handlers.webhook_handler._get_ddb")
    @patch("handlers.webhook_handler.generate_monthly_report")
    def test_monthly_summary_Replyで応答(self, mock_report, mock_ddb, mock_line):
        from handlers.webhook_handler import _handle_postback
        mock_report.return_value = [{"type": "flex", "altText": "レポート", "contents": {}}]
        mock_ddb.return_value = MagicMock()

        event = {
            "type": "postback",
            "postback": {"data": "action=monthly_summary"},
            "replyToken": "token123",
            "source": {"userId": "U123"},
        }
        _handle_postback(event)
        mock_line().reply_message.assert_called_once()

    @patch("handlers.webhook_handler.get_line_service")
    @patch("handlers.webhook_handler._get_ddb")
    def test_purchased_支出記録(self, mock_ddb, mock_line):
        from handlers.webhook_handler import _handle_postback
        ddb = MagicMock()
        mock_ddb.return_value = ddb
        ddb.get_item.side_effect = [None, None]  # streak, profile

        event = {
            "type": "postback",
            "postback": {"data": "action=purchased&item=bathbomb&amount=2200"},
            "replyToken": "token123",
            "source": {"userId": "U123"},
        }
        _handle_postback(event)
        mock_line().reply_message.assert_called_once()

    @patch("handlers.webhook_handler.get_line_service")
    @patch("handlers.webhook_handler._get_ddb")
    def test_unknown_action_fallback(self, mock_ddb, mock_line):
        from handlers.webhook_handler import _handle_postback
        mock_ddb.return_value = MagicMock()

        event = {
            "type": "postback",
            "postback": {"data": "action=unknown_thing"},
            "replyToken": "token123",
            "source": {"userId": "U123"},
        }
        _handle_postback(event)
        call_args = mock_line().reply_message.call_args[0][1]
        assert "わからなかった" in call_args[0]["text"]


# ─────────────────────────────────────────
# profile_updater テスト
# ─────────────────────────────────────────

class TestProfileUpdater:

    @patch("services.profile_updater._bedrock")
    def test_income更新(self, mock_bedrock):
        from services.profile_updater import handle_profile_update
        mock_bedrock.invoke_text.return_value = '{"update_type":"income","data":{"monthly_income":320000}}'
        ddb = MagicMock()
        ddb.get_item.return_value = {"costs": []}
        result = handle_profile_update("U123", "昇給して手取り32万になった", ddb)
        assert "昇給" in result
        ddb.update_item.assert_called()

    @patch("services.profile_updater._bedrock")
    def test_fixed_cost_remove(self, mock_bedrock):
        from services.profile_updater import handle_profile_update
        mock_bedrock.invoke_text.return_value = '{"update_type":"fixed_cost_remove","data":{"name":"Netflix"}}'
        ddb = MagicMock()
        ddb.get_item.return_value = {"costs": [{"name": "Netflix", "amount": 990}]}
        result = handle_profile_update("U123", "Netflix解約した", ddb)
        assert "削除" in result
        ddb.put_item.assert_called()

    @patch("services.profile_updater._bedrock")
    def test_anniversary_add(self, mock_bedrock):
        from services.profile_updater import handle_profile_update
        mock_bedrock.invoke_text.return_value = '{"update_type":"anniversary_add","data":{"name":"彼女の誕生日","date":"08-03"}}'
        ddb = MagicMock()
        ddb.get_item.return_value = {"anniversaries": []}
        result = handle_profile_update("U123", "彼女の誕生日8月3日", ddb)
        assert "メモ" in result or "更新" in result
        ddb.update_item.assert_called()

    @patch("services.profile_updater._bedrock")
    def test_unknown_graceful(self, mock_bedrock):
        from services.profile_updater import handle_profile_update
        mock_bedrock.invoke_text.return_value = '{"update_type":"unknown","data":{}}'
        ddb = MagicMock()
        result = handle_profile_update("U123", "今日はいい天気ですね", ddb)
        assert "わからなかった" in result or "読み取れ" in result


# ─────────────────────────────────────────
# 記念日の会話中自然収集テスト
# ─────────────────────────────────────────

class TestAnniversaryDetect:

    def test_誕生日を検出して保存(self):
        from handlers.webhook_handler import _detect_anniversary
        ddb = MagicMock()
        ddb.get_item.return_value = {"anniversaries": []}
        _detect_anniversary("U123", "誕生日は9月15日なんだ", ddb)
        ddb.update_item.assert_called_once()
        updates = ddb.update_item.call_args[1]["updates"]
        assert any(a["name"] == "誕生日" and a["date"] == "09-15" for a in updates["anniversaries"])

    def test_結婚記念日を検出して保存(self):
        from handlers.webhook_handler import _detect_anniversary
        ddb = MagicMock()
        ddb.get_item.return_value = {"anniversaries": []}
        _detect_anniversary("U123", "結婚記念日は6月15日だよ", ddb)
        ddb.update_item.assert_called_once()
        updates = ddb.update_item.call_args[1]["updates"]
        assert any(a["name"] == "結婚記念日" for a in updates["anniversaries"])

    def test_パターン非一致_保存しない(self):
        from handlers.webhook_handler import _detect_anniversary
        ddb = MagicMock()
        _detect_anniversary("U123", "今日はいい天気だね", ddb)
        ddb.update_item.assert_not_called()

    def test_既存の同名記念日を更新(self):
        from handlers.webhook_handler import _detect_anniversary
        ddb = MagicMock()
        ddb.get_item.return_value = {"anniversaries": [{"name": "誕生日", "date": "03-10"}]}
        _detect_anniversary("U123", "誕生日 9月15日に変わった", ddb)
        ddb.update_item.assert_called_once()
        updates = ddb.update_item.call_args[1]["updates"]
        assert updates["anniversaries"][0]["date"] == "09-15"


# ─────────────────────────────────────────
# Flex Message カード（おすすめ結果）テスト
# ─────────────────────────────────────────

class TestRecommendFlexMessage:

    @patch("services.recommend_flow._bedrock")
    def test_WAITING_BUDGET_Flex返却(self, mock_bedrock):
        from services.recommend_flow import handle_recommend_reply
        mock_bedrock.invoke_text.return_value = "① バスボム 🛁 2,000円\n② アロマオイル 990円\n③ 入浴剤セット 1,500円\n気になるのあった？😊"
        ddb = MagicMock()
        ddb.get_item.return_value = {}
        state = {"step": "WAITING_BUDGET", "category": "リラックス"}
        result = handle_recommend_reply("U123", "3000円", state, ddb)
        assert len(result) == 1
        assert result[0]["type"] == "flex"
        assert "気になる" in result[0]["contents"]["footer"]["contents"][0]["action"]["label"]

    @patch("services.recommend_flow._bedrock")
    def test_Bedrock失敗_フォールバック(self, mock_bedrock):
        from services.recommend_flow import handle_recommend_reply
        mock_bedrock.invoke_text.side_effect = Exception("timeout")
        ddb = MagicMock()
        ddb.get_item.return_value = {}
        state = {"step": "WAITING_BUDGET", "category": "グルメ"}
        result = handle_recommend_reply("U123", "1000円", state, ddb)
        assert len(result) == 1
        assert result[0]["type"] == "flex"


# ─────────────────────────────────────────
# クイック支出 残予算表示テスト
# ─────────────────────────────────────────

class TestQuickExpenseRemainingBudget:

    def test_WAITING_AMOUNT_残予算表示あり(self):
        from services.quick_expense import handle_quick_expense_reply
        ddb = MagicMock()
        ddb.get_item.return_value = {"reward_budget_monthly": 20000}
        state = {"step": "WAITING_AMOUNT", "category": "カフェ"}
        with patch("services.finance_engine.calculate_slack") as mock_slack:
            from decimal import Decimal
            mock_slack.return_value = (Decimal("15000"), Decimal("20000"))
            msgs, items = handle_quick_expense_reply("U123", "500", state, ddb)
        assert "14,500円" in msgs[0]["text"]
        assert items[0]["amount"] == 500

    def test_WAITING_AMOUNT_slack取得失敗_graceful(self):
        from services.quick_expense import handle_quick_expense_reply
        ddb = MagicMock()
        ddb.get_item.side_effect = Exception("DDB error")
        state = {"step": "WAITING_AMOUNT", "category": "カフェ"}
        msgs, items = handle_quick_expense_reply("U123", "500", state, ddb)
        # 残予算なしで正常返却
        assert items[0]["amount"] == 500
