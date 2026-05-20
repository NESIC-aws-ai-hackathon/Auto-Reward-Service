"""
購入意図分類 (classifyPurchaseIntent) のユニットテスト

変更依頼書_2 §27 準拠
"""
import pytest
import sys
import os
import importlib.util

_LAYER = os.path.join(os.path.dirname(__file__), "..", "..", "layer", "python")
sys.path.insert(0, _LAYER)

# services/__init__.py が line_service (pydantic_core) を import するため直接ロード
_spec = importlib.util.spec_from_file_location(
    "services.purchase_intent",
    os.path.join(_LAYER, "services", "purchase_intent.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
classify_purchase_intent = _mod.classify_purchase_intent
validate_before_purchase = _mod.validate_before_purchase


class TestClassifyPurchaseIntent:
    """§20 意図判定テスト"""

    def test_decline_iraanai(self):
        assert classify_purchase_intent("いらない") == "DECLINE"

    def test_decline_cart_remove(self):
        assert classify_purchase_intent("カートから出して") == "DECLINE"

    def test_decline_yameru(self):
        assert classify_purchase_intent("やめる") == "DECLINE"

    def test_decline_kawanai(self):
        assert classify_purchase_intent("買わない") == "DECLINE"

    def test_decline_modoshite(self):
        assert classify_purchase_intent("戻して") == "DECLINE"

    def test_decline_mada_ii(self):
        assert classify_purchase_intent("まだいい") == "DECLINE"

    def test_decline_jukusei(self):
        assert classify_purchase_intent("熟成させる") == "DECLINE"

    def test_ambiguous_katte(self):
        assert classify_purchase_intent("買って") == "AMBIGUOUS_BUY"

    def test_ambiguous_onegai(self):
        assert classify_purchase_intent("お願い") == "AMBIGUOUS_BUY"

    def test_ambiguous_iiyo(self):
        assert classify_purchase_intent("いいよ") == "AMBIGUOUS_BUY"

    def test_ambiguous_ok(self):
        assert classify_purchase_intent("OK") == "AMBIGUOUS_BUY"

    def test_ambiguous_hai(self):
        assert classify_purchase_intent("はい") == "AMBIGUOUS_BUY"

    def test_ambiguous_makaseru(self):
        assert classify_purchase_intent("任せる") == "AMBIGUOUS_BUY"

    def test_ambiguous_hoshii(self):
        assert classify_purchase_intent("欲しい") == "AMBIGUOUS_BUY"

    def test_ambiguous_kaitai(self):
        assert classify_purchase_intent("買いたい") == "AMBIGUOUS_BUY"

    def test_ambiguous_katchao(self):
        assert classify_purchase_intent("買っちゃおう") == "AMBIGUOUS_BUY"

    def test_explicit_kono_shouhin(self):
        assert classify_purchase_intent("この商品を購入して") == "EXPLICIT_PURCHASE"

    def test_explicit_chumon_kakutei(self):
        assert classify_purchase_intent("注文を確定して") == "EXPLICIT_PURCHASE"

    def test_explicit_kono_naiyo(self):
        assert classify_purchase_intent("この内容で購入して") == "EXPLICIT_PURCHASE"

    def test_explicit_hai_kakutei(self):
        assert classify_purchase_intent("はい、購入を確定します") == "EXPLICIT_PURCHASE"

    def test_explicit_product_name(self):
        assert classify_purchase_intent("入浴剤を購入して", "入浴剤") == "EXPLICIT_PURCHASE"

    def test_other_tired(self):
        assert classify_purchase_intent("今日は疲れた") == "OTHER"

    def test_other_general(self):
        assert classify_purchase_intent("おはよう") == "OTHER"

    def test_other_question(self):
        assert classify_purchase_intent("今月の残りいくら？") == "OTHER"

    def test_explicit_takes_priority_over_ambiguous(self):
        """「この商品を購入して」は「買って」を含むが EXPLICIT_PURCHASE が優先"""
        assert classify_purchase_intent("この商品を購入して") == "EXPLICIT_PURCHASE"


class TestValidateBeforePurchase:
    """§21 安全チェックテスト"""

    def test_all_ok(self):
        result = validate_before_purchase(
            status="PURCHASE_APPROVED",
            price=800,
            quantity=1,
            explicit_approval_text="この商品を購入して",
            product_title="入浴剤",
            max_allowed_price=1000,
        )
        assert result["ok"] is True
        assert result["reasons"] == []

    def test_ng_status_not_approved(self):
        result = validate_before_purchase(
            status="CART_ADDED",
            price=800,
            quantity=1,
            explicit_approval_text="この商品を購入して",
            product_title="入浴剤",
            max_allowed_price=1000,
        )
        assert result["ok"] is False
        assert any("PURCHASE_APPROVED" in r for r in result["reasons"])

    def test_ng_no_approval_text(self):
        result = validate_before_purchase(
            status="PURCHASE_APPROVED",
            price=800,
            quantity=1,
            explicit_approval_text=None,
            product_title="入浴剤",
            max_allowed_price=1000,
        )
        assert result["ok"] is False
        assert any("明示承認テキスト" in r for r in result["reasons"])

    def test_ng_ambiguous_approval(self):
        result = validate_before_purchase(
            status="PURCHASE_APPROVED",
            price=800,
            quantity=1,
            explicit_approval_text="買って",
            product_title="入浴剤",
            max_allowed_price=1000,
        )
        assert result["ok"] is False
        assert any("明示購入文" in r for r in result["reasons"])

    def test_ng_price_exceeded(self):
        result = validate_before_purchase(
            status="PURCHASE_APPROVED",
            price=1500,
            quantity=1,
            explicit_approval_text="この商品を購入して",
            product_title="入浴剤",
            max_allowed_price=1000,
        )
        assert result["ok"] is False
        assert any("上限" in r for r in result["reasons"])

    def test_ng_quantity_not_one(self):
        result = validate_before_purchase(
            status="PURCHASE_APPROVED",
            price=800,
            quantity=2,
            explicit_approval_text="この商品を購入して",
            product_title="入浴剤",
            max_allowed_price=1000,
        )
        assert result["ok"] is False
        assert any("数量" in r for r in result["reasons"])

    def test_ng_subscription(self):
        result = validate_before_purchase(
            status="PURCHASE_APPROVED",
            price=800,
            quantity=1,
            explicit_approval_text="この商品を購入して",
            product_title="入浴剤",
            max_allowed_price=1000,
            is_subscription=True,
        )
        assert result["ok"] is False
        assert any("定期便" in r for r in result["reasons"])

    def test_ng_payment_method_changed(self):
        result = validate_before_purchase(
            status="PURCHASE_APPROVED",
            price=800,
            quantity=1,
            explicit_approval_text="この商品を購入して",
            product_title="入浴剤",
            max_allowed_price=1000,
            payment_method_changed=True,
        )
        assert result["ok"] is False
        assert any("支払い方法" in r for r in result["reasons"])

    def test_ng_shipping_changed(self):
        result = validate_before_purchase(
            status="PURCHASE_APPROVED",
            price=800,
            quantity=1,
            explicit_approval_text="この商品を購入して",
            product_title="入浴剤",
            max_allowed_price=1000,
            shipping_address_changed=True,
        )
        assert result["ok"] is False
        assert any("配送先" in r for r in result["reasons"])

    def test_multiple_failures(self):
        result = validate_before_purchase(
            status="CART_ADDED",
            price=2000,
            quantity=3,
            explicit_approval_text=None,
            product_title="入浴剤",
            max_allowed_price=1000,
            is_subscription=True,
        )
        assert result["ok"] is False
        assert len(result["reasons"]) >= 4
