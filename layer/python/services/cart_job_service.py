"""
カート搬送ジョブ管理サービス

変更依頼書_2 §11 準拠 — 非同期ジョブの作成・実行・状態管理
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from services.dynamodb_service import DynamoDBService
from services.cart_automation_worker import get_cart_worker, ENABLE_REAL_PURCHASE, MAX_PURCHASE_AMOUNT
from services.notification_service import (
    create_cart_added_notification,
    create_login_required_notification,
    create_notification,
)
from services.purchase_intent import validate_before_purchase
from models.schemas import SK_PREFIX_CART_AUTOMATION_JOB, SK_PREFIX_RECOMMENDATION
from utils.logger import get_logger

logger = get_logger(__name__)


def create_cart_job(
    user_id: str,
    recommendation_id: str,
    action: str,
    ddb: DynamoDBService,
    *,
    product_url: Optional[str] = None,
    expected_product_title: Optional[str] = None,
    expected_price: Optional[float] = None,
    explicit_approval_text: Optional[str] = None,
) -> dict:
    """
    カート搬送ジョブを作成し即時実行する。

    action: ADD_TO_CART | REMOVE_FROM_CART | PURCHASE
    """
    pk = f"USER#{user_id}"
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    sk = f"{SK_PREFIX_CART_AUTOMATION_JOB}{job_id}"

    job_data = {
        "job_id": job_id,
        "user_id": user_id,
        "recommendation_id": recommendation_id,
        "action": action,
        "provider": get_cart_worker().__class__.__name__.replace("CartAutomationWorker", "").upper() or "STUB",
        "mode": _get_mode(),
        "status": "QUEUED",
        "product_url": product_url,
        "expected_product_title": expected_product_title,
        "expected_price": expected_price,
        "quantity": 1,
        "max_allowed_price": MAX_PURCHASE_AMOUNT,
        "explicit_approval_text": explicit_approval_text,
        "createdAt": now,
        "updatedAt": now,
    }

    ddb.put_item(pk, sk, job_data)
    logger.info("cart_job_created", job_id=job_id, action=action)

    # 即時実行
    result = _execute_job(user_id, job_id, job_data, ddb)
    return result


def _execute_job(user_id: str, job_id: str, job_data: dict, ddb: DynamoDBService) -> dict:
    """ジョブを実行する"""
    pk = f"USER#{user_id}"
    sk = f"{SK_PREFIX_CART_AUTOMATION_JOB}{job_id}"
    action = job_data["action"]
    recommendation_id = job_data["recommendation_id"]
    now = datetime.now(timezone.utc).isoformat()

    # ステータスを RUNNING に
    ddb.update_item(pk, sk, {"status": "RUNNING", "started_at": now, "updatedAt": now})

    worker = get_cart_worker()

    try:
        if action == "ADD_TO_CART":
            result = worker.add_to_cart(
                user_id=user_id,
                recommendation_id=recommendation_id,
                product_url=job_data.get("product_url", ""),
                quantity=job_data.get("quantity", 1),
            )
        elif action == "REMOVE_FROM_CART":
            result = worker.remove_from_cart(
                user_id=user_id,
                recommendation_id=recommendation_id,
                product_url=job_data.get("product_url", ""),
            )
        elif action == "PURCHASE":
            # 購入前安全チェック
            safety = validate_before_purchase(
                status="PURCHASE_APPROVED",
                price=float(job_data.get("expected_price") or 0),
                quantity=job_data.get("quantity", 1),
                explicit_approval_text=job_data.get("explicit_approval_text"),
                product_title=job_data.get("expected_product_title", ""),
                max_allowed_price=float(job_data.get("max_allowed_price", MAX_PURCHASE_AMOUNT)),
            )
            if not safety["ok"]:
                _finish_job(pk, sk, "FAILED", ddb, error_code="SAFETY_CHECK_FAILED",
                           error_message="; ".join(safety["reasons"]))
                return {"success": False, "status": "FAILED", "reasons": safety["reasons"]}

            result = worker.purchase(
                user_id=user_id,
                recommendation_id=recommendation_id,
            )
        else:
            result = {"success": False, "status": "FAILED", "message": f"Unknown action: {action}"}

    except Exception as e:
        logger.error("cart_job_execution_error", error=str(e), job_id=job_id)
        _finish_job(pk, sk, "FAILED", ddb, error_code="UNKNOWN", error_message=str(e))
        return {"success": False, "status": "FAILED", "error": str(e)}

    # 結果に基づいて状態更新
    final_status = result.get("status", "FAILED")
    _finish_job(
        pk, sk, final_status, ddb,
        error_code=result.get("error_code"),
        error_message=result.get("message"),
        fallback_reason=result.get("fallback_reason"),
    )

    # Recommendation ステータスも同期
    _sync_recommendation_status(pk, recommendation_id, final_status, ddb)

    # 通知作成
    _create_result_notification(user_id, job_data, result, ddb)

    return result


def _finish_job(
    pk: str, sk: str, status: str, ddb: DynamoDBService, **extra
) -> None:
    """ジョブを完了状態にする"""
    now = datetime.now(timezone.utc).isoformat()
    updates = {"status": status, "finished_at": now, "updatedAt": now}
    for k, v in extra.items():
        if v is not None:
            updates[k] = v
    ddb.update_item(pk, sk, updates)


def _sync_recommendation_status(
    pk: str, recommendation_id: str, job_status: str, ddb: DynamoDBService
) -> None:
    """ジョブ結果をRecommendationステータスに反映"""
    rec_sk = f"{SK_PREFIX_RECOMMENDATION}{recommendation_id}"
    status_map = {
        "CART_ADDED": "CART_ADDED",
        "REMOVED_FROM_CART": "REMOVED_FROM_CART",
        "PURCHASED": "PURCHASED",
        "PURCHASE_SIMULATED": "PURCHASE_SIMULATED",
        "READY_TO_PURCHASE": "PURCHASE_SIMULATED",
        "LOGIN_REQUIRED": "WAITING_USER_DECISION",
        "MFA_REQUIRED": "WAITING_USER_DECISION",
        "CAPTCHA_REQUIRED": "WAITING_USER_DECISION",
        "USER_TAKEOVER_REQUIRED": "WAITING_USER_DECISION",
        "FAILED": "ERROR",
    }
    new_status = status_map.get(job_status)
    if new_status:
        now = datetime.now(timezone.utc).isoformat()
        ddb.update_item(pk, rec_sk, {"status": new_status, "updatedAt": now})


def _create_result_notification(
    user_id: str, job_data: dict, result: dict, ddb: DynamoDBService
) -> None:
    """ジョブ結果に基づく通知を作成"""
    status = result.get("status", "")
    recommendation_id = job_data.get("recommendation_id", "")
    product_title = job_data.get("expected_product_title", "商品")

    if status == "CART_ADDED":
        create_cart_added_notification(
            user_id, ddb,
            product_title=product_title,
            reason_text="今のあなたにちょうどよさそう✨",
            recommendation_id=recommendation_id,
        )
    elif status in ("LOGIN_REQUIRED", "MFA_REQUIRED", "CAPTCHA_REQUIRED", "USER_TAKEOVER_REQUIRED"):
        create_login_required_notification(
            user_id, ddb,
            recommendation_id=recommendation_id,
        )
    elif status in ("PURCHASED", "PURCHASE_SIMULATED"):
        create_notification(
            user_id, ddb,
            notification_type="PURCHASE_READY",
            title=f"✅ {product_title} の購入処理完了",
            message_text=f"{product_title} の購入処理が完了したよ！\nお疲れさまでした✨",
            recommendation_id=recommendation_id,
        )


def _get_mode() -> str:
    """現在のカート搬送モードを取得"""
    import os
    return os.getenv("CART_AUTOMATION_MODE", "stub")


def get_cart_job(user_id: str, job_id: str, ddb: DynamoDBService) -> Optional[dict]:
    """ジョブを取得"""
    pk = f"USER#{user_id}"
    sk = f"{SK_PREFIX_CART_AUTOMATION_JOB}{job_id}"
    return ddb.get_item(pk=pk, sk=sk)
