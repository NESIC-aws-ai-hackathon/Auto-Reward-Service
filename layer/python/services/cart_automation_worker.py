"""
カート搬送ワーカー (CartAutomationWorker) — インターフェースと実装

変更依頼書_2 §9, §12, §14 準拠

環境変数:
  CART_AUTOMATION_MODE: stub | nova_act | hybrid (default: stub)
  ENABLE_REAL_PURCHASE: true | false (default: false)
  NOVA_ACT_DEMO_MODE: true | false (default: true)
  MAX_PURCHASE_AMOUNT: int (default: 1000)
"""
from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
CART_AUTOMATION_MODE = os.getenv("CART_AUTOMATION_MODE", "stub")
ENABLE_REAL_PURCHASE = os.getenv("ENABLE_REAL_PURCHASE", "false").lower() == "true"
NOVA_ACT_DEMO_MODE = os.getenv("NOVA_ACT_DEMO_MODE", "true").lower() == "true"
MAX_PURCHASE_AMOUNT = int(os.getenv("MAX_PURCHASE_AMOUNT", "1000"))


# ─────────────────────────────────────────
# Result / Error types
# ─────────────────────────────────────────
NOVA_ACT_ERROR_CODES = [
    "LOGIN_REQUIRED",
    "MFA_REQUIRED",
    "CAPTCHA_REQUIRED",
    "USER_TAKEOVER_REQUIRED",
    "PRODUCT_NOT_FOUND",
    "PRICE_NOT_FOUND",
    "PRICE_LIMIT_EXCEEDED",
    "SUBSCRIPTION_DETECTED",
    "QUANTITY_MISMATCH",
    "CHECKOUT_PAGE_NOT_REACHED",
    "PAYMENT_METHOD_CHANGE_DETECTED",
    "SHIPPING_ADDRESS_CHANGE_DETECTED",
    "SAFETY_CHECK_FAILED",
    "PURCHASE_BUTTON_NOT_FOUND",
    "ORDER_CONFIRMATION_NOT_FOUND",
    "PAGE_STRUCTURE_CHANGED",
    "TIMEOUT",
    "UNKNOWN",
]

AUTOMATION_FALLBACK_REASONS = [
    "NOVA_ACT_START_FAILED",
    "LOGIN_NOT_READY",
    "MFA_OR_CAPTCHA_REQUIRED",
    "PAGE_STRUCTURE_CHANGED",
    "PRODUCT_PAGE_FAILED",
    "SAFETY_CHECK_FAILED",
    "TIMEOUT",
]


def _make_result(
    success: bool,
    status: str,
    *,
    error_code: Optional[str] = None,
    message: Optional[str] = None,
    order_id: Optional[str] = None,
) -> dict:
    result = {"success": success, "status": status}
    if error_code:
        result["error_code"] = error_code
    if message:
        result["message"] = message
    if order_id:
        result["order_id"] = order_id
    return result


# ─────────────────────────────────────────
# Interface
# ─────────────────────────────────────────
class CartAutomationWorker(ABC):
    """カート搬送の抽象インターフェース"""

    @abstractmethod
    def add_to_cart(
        self,
        *,
        user_id: str,
        recommendation_id: str,
        product_url: str,
        quantity: int = 1,
    ) -> dict:
        ...

    @abstractmethod
    def remove_from_cart(
        self,
        *,
        user_id: str,
        recommendation_id: str,
        product_url: str,
    ) -> dict:
        ...

    @abstractmethod
    def purchase(
        self,
        *,
        user_id: str,
        recommendation_id: str,
    ) -> dict:
        ...


# ─────────────────────────────────────────
# Stub Worker (常時安全)
# ─────────────────────────────────────────
class StubCartAutomationWorker(CartAutomationWorker):
    """実ブラウザ操作なし。即座に成功ステータスを返す。"""

    def add_to_cart(self, *, user_id, recommendation_id, product_url, quantity=1):
        logger.info(
            "stub_add_to_cart",
            user_id=user_id,
            recommendation_id=recommendation_id,
        )
        return _make_result(
            True, "CART_ADDED", message="[Stub] カートに追加しました"
        )

    def remove_from_cart(self, *, user_id, recommendation_id, product_url):
        logger.info(
            "stub_remove_from_cart",
            user_id=user_id,
            recommendation_id=recommendation_id,
        )
        return _make_result(
            True, "REMOVED_FROM_CART", message="[Stub] カートから削除しました"
        )

    def purchase(self, *, user_id, recommendation_id):
        logger.info(
            "stub_purchase",
            user_id=user_id,
            recommendation_id=recommendation_id,
        )
        if ENABLE_REAL_PURCHASE:
            return _make_result(
                True,
                "PURCHASE_SIMULATED",
                message="[Stub] 購入をシミュレートしました（実購入はスキップ）",
            )
        return _make_result(
            True,
            "PURCHASE_SIMULATED",
            message="[Stub] ENABLE_REAL_PURCHASE=false のため購入シミュレーション",
        )


# ─────────────────────────────────────────
# Nova Act Worker (Skeleton)
# ─────────────────────────────────────────
class NovaActCartAutomationWorker(CartAutomationWorker):
    """
    Nova Act を使ったブラウザ操作ワーカー (Skeleton)

    実装優先順位:
      Step 3: addToCart のみ実装
      Step 4: removeFromCart
      Step 5: purchase (購入直前停止)
      Step 6: real purchase
    """

    def add_to_cart(self, *, user_id, recommendation_id, product_url, quantity=1):
        logger.info(
            "nova_act_add_to_cart",
            user_id=user_id,
            recommendation_id=recommendation_id,
            product_url=product_url,
        )
        # TODO: Step 3 — Nova Act 実装
        # 1. getOrCreateBrowserSession
        # 2. openProductPage
        # 3. verifyProductPage (title, price, subscription, quantity)
        # 4. addCurrentProductToCart
        # 5. 証跡保存

        # 現段階では stub にフォールバック
        return _make_result(
            True,
            "CART_ADDED",
            message="[NovaAct/Skeleton] カート追加をシミュレートしました",
        )

    def remove_from_cart(self, *, user_id, recommendation_id, product_url):
        logger.info(
            "nova_act_remove_from_cart",
            user_id=user_id,
            recommendation_id=recommendation_id,
        )
        # TODO: Step 4 — Nova Act 実装
        return _make_result(
            True,
            "REMOVED_FROM_CART",
            message="[NovaAct/Skeleton] カート削除をシミュレートしました",
        )

    def purchase(self, *, user_id, recommendation_id):
        logger.info(
            "nova_act_purchase",
            user_id=user_id,
            recommendation_id=recommendation_id,
        )
        if not ENABLE_REAL_PURCHASE:
            # Step 5: 購入直前停止
            return _make_result(
                True,
                "READY_TO_PURCHASE",
                message="[NovaAct] ENABLE_REAL_PURCHASE=false — 購入直前で停止",
            )

        # Step 6: 実購入 (未実装 — safety check 必須)
        # TODO: verifyCheckoutBeforePurchase + confirmPurchase
        return _make_result(
            False,
            "FAILED",
            error_code="SAFETY_CHECK_FAILED",
            message="[NovaAct] Real purchase not yet implemented",
        )


# ─────────────────────────────────────────
# Factory
# ─────────────────────────────────────────
def get_cart_worker() -> CartAutomationWorker:
    """環境変数 CART_AUTOMATION_MODE に応じたワーカーを返す"""
    mode = os.getenv("CART_AUTOMATION_MODE", "stub")
    if mode == "nova_act":
        return NovaActCartAutomationWorker()
    elif mode == "hybrid":
        return HybridCartAutomationWorker()
    else:
        return StubCartAutomationWorker()


class HybridCartAutomationWorker(CartAutomationWorker):
    """Nova Act を試行し、失敗時に Stub へフォールバック"""

    def __init__(self):
        self._nova = NovaActCartAutomationWorker()
        self._stub = StubCartAutomationWorker()

    def add_to_cart(self, *, user_id, recommendation_id, product_url, quantity=1):
        try:
            result = self._nova.add_to_cart(
                user_id=user_id,
                recommendation_id=recommendation_id,
                product_url=product_url,
                quantity=quantity,
            )
            if result["success"]:
                return result
        except Exception as e:
            logger.warning("hybrid_nova_act_failed", error=str(e))

        logger.info("hybrid_fallback_to_stub", action="add_to_cart")
        result = self._stub.add_to_cart(
            user_id=user_id,
            recommendation_id=recommendation_id,
            product_url=product_url,
            quantity=quantity,
        )
        result["fallback_reason"] = "NOVA_ACT_START_FAILED"
        return result

    def remove_from_cart(self, *, user_id, recommendation_id, product_url):
        try:
            result = self._nova.remove_from_cart(
                user_id=user_id,
                recommendation_id=recommendation_id,
                product_url=product_url,
            )
            if result["success"]:
                return result
        except Exception as e:
            logger.warning("hybrid_nova_act_failed", error=str(e))

        result = self._stub.remove_from_cart(
            user_id=user_id,
            recommendation_id=recommendation_id,
            product_url=product_url,
        )
        result["fallback_reason"] = "NOVA_ACT_START_FAILED"
        return result

    def purchase(self, *, user_id, recommendation_id):
        try:
            result = self._nova.purchase(
                user_id=user_id, recommendation_id=recommendation_id
            )
            if result["success"]:
                return result
        except Exception as e:
            logger.warning("hybrid_nova_act_failed", error=str(e))

        result = self._stub.purchase(
            user_id=user_id, recommendation_id=recommendation_id
        )
        result["fallback_reason"] = "NOVA_ACT_START_FAILED"
        return result
