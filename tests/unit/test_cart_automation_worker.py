"""
CartAutomationWorker のユニットテスト

変更依頼書_2 §27 準拠
"""
import pytest
import sys
import os
import importlib.util
from unittest.mock import patch, MagicMock

_LAYER = os.path.join(os.path.dirname(__file__), "..", "..", "layer", "python")
sys.path.insert(0, _LAYER)

# 環境変数を stub に設定
os.environ["CART_AUTOMATION_MODE"] = "stub"
os.environ["ENABLE_REAL_PURCHASE"] = "false"
os.environ["NOVA_ACT_DEMO_MODE"] = "true"
os.environ["MAX_PURCHASE_AMOUNT"] = "1000"

# utils.logger モックを先に用意
sys.modules["utils"] = MagicMock()
sys.modules["utils.logger"] = MagicMock()
sys.modules["utils.logger"].get_logger = MagicMock(return_value=MagicMock())

_spec = importlib.util.spec_from_file_location(
    "services.cart_automation_worker",
    os.path.join(_LAYER, "services", "cart_automation_worker.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

StubCartAutomationWorker = _mod.StubCartAutomationWorker
NovaActCartAutomationWorker = _mod.NovaActCartAutomationWorker
HybridCartAutomationWorker = _mod.HybridCartAutomationWorker
get_cart_worker = _mod.get_cart_worker


class TestStubCartAutomationWorker:
    """Stub ワーカーテスト"""

    def setup_method(self):
        self.worker = StubCartAutomationWorker()

    def test_add_to_cart_returns_cart_added(self):
        result = self.worker.add_to_cart(
            user_id="user1",
            recommendation_id="rec1",
            product_url="https://amazon.co.jp/dp/B123",
            quantity=1,
        )
        assert result["success"] is True
        assert result["status"] == "CART_ADDED"

    def test_remove_from_cart_returns_removed(self):
        result = self.worker.remove_from_cart(
            user_id="user1",
            recommendation_id="rec1",
            product_url="https://amazon.co.jp/dp/B123",
        )
        assert result["success"] is True
        assert result["status"] == "REMOVED_FROM_CART"

    def test_purchase_returns_simulated(self):
        result = self.worker.purchase(
            user_id="user1",
            recommendation_id="rec1",
        )
        assert result["success"] is True
        assert result["status"] == "PURCHASE_SIMULATED"


class TestNovaActCartAutomationWorker:
    """Nova Act ワーカー (skeleton) テスト"""

    def setup_method(self):
        self.worker = NovaActCartAutomationWorker()

    def test_add_to_cart_skeleton(self):
        result = self.worker.add_to_cart(
            user_id="user1",
            recommendation_id="rec1",
            product_url="https://amazon.co.jp/dp/B123",
            quantity=1,
        )
        assert result["success"] is True
        assert result["status"] == "CART_ADDED"

    def test_purchase_without_real_purchase_stops(self):
        """ENABLE_REAL_PURCHASE=false で購入直前停止"""
        result = self.worker.purchase(
            user_id="user1",
            recommendation_id="rec1",
        )
        assert result["success"] is True
        assert result["status"] == "READY_TO_PURCHASE"


class TestHybridCartAutomationWorker:
    """Hybrid ワーカーテスト"""

    def setup_method(self):
        self.worker = HybridCartAutomationWorker()

    def test_add_to_cart_hybrid(self):
        result = self.worker.add_to_cart(
            user_id="user1",
            recommendation_id="rec1",
            product_url="https://amazon.co.jp/dp/B123",
            quantity=1,
        )
        assert result["success"] is True
        assert result["status"] == "CART_ADDED"


class TestGetCartWorker:
    """Factory テスト"""

    def test_stub_mode(self):
        os.environ["CART_AUTOMATION_MODE"] = "stub"
        # Reload the module constants
        _mod.CART_AUTOMATION_MODE = "stub"
        worker = _mod.get_cart_worker()
        assert isinstance(worker, _mod.StubCartAutomationWorker)

    def test_nova_act_mode(self):
        os.environ["CART_AUTOMATION_MODE"] = "nova_act"
        _mod.CART_AUTOMATION_MODE = "nova_act"
        worker = _mod.get_cart_worker()
        assert isinstance(worker, _mod.NovaActCartAutomationWorker)

    def test_hybrid_mode(self):
        os.environ["CART_AUTOMATION_MODE"] = "hybrid"
        _mod.CART_AUTOMATION_MODE = "hybrid"
        worker = _mod.get_cart_worker()
        assert isinstance(worker, _mod.HybridCartAutomationWorker)
