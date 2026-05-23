"""
Nova Act ECS Worker — DynamoDB の CART_AUTOMATION_JOB# を購読して Amazon 自動購入を実行

設計:
    1. Lambda 側 (CartJobService) は `CART_AUTOMATION_JOB#{jobId}` を CartJobsByStatus GSI に
       status=PENDING で投入する
    2. 本ワーカー (ECS Fargate Task または常駐コンテナ) が GSI を Query して PENDING ジョブを取得
    3. 取得した job を IN_PROGRESS に更新し、purchase_amazon.py のフローを実行
    4. 結果に応じて COMPLETED / FAILED / REQUIRES_HUMAN に遷移し、result を書き戻す

実行例:
    docker run --rm \\
        -e NOVA_ACT_API_KEY=... \\
        -e AWS_REGION=ap-northeast-1 \\
        -e ARS_TABLE_NAME=ArsTable \\
        -e ENABLE_REAL_PURCHASE=false \\
        -e MAX_PURCHASE_AMOUNT=1000 \\
        -v $HOME/.nova-act:/root/.nova-act \\
        ars-nova-act-worker:latest

注意:
    - 本ワーカーは長期常駐ではなく、1 ジョブ実行して終了するシングルショット型を想定
    - EventBridge → Fargate RunTask で起動し、ジョブが無ければ即時終了
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 同階層の purchase_amazon を import するため
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("nova_act_worker")

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
TABLE_NAME = os.environ.get("ARS_TABLE_NAME", "ArsTable")
GSI_NAME = os.environ.get("ARS_JOB_GSI_NAME", "CartJobsByStatus")
POLL_BATCH = int(os.environ.get("WORKER_POLL_BATCH", "5"))


def _ddb():
    import boto3
    return boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_pending_jobs(limit: int) -> list[dict]:
    """status=QUEUED の CartAutomationJob を取得。

    Phase 1: GSI 未整備のため Scan + Filter を使用（ジョブ数が少ない前提）。
    Phase 2: `CartJobsByStatus` GSI (PK=status, SK=createdAt) を作成して Query に置き換える。
    """
    from boto3.dynamodb.conditions import Attr

    table = _ddb()
    if GSI_NAME and os.environ.get("USE_GSI", "false").lower() == "true":
        from boto3.dynamodb.conditions import Key
        resp = table.query(
            IndexName=GSI_NAME,
            KeyConditionExpression=Key("status").eq("QUEUED"),
            Limit=limit,
        )
        return resp.get("Items", [])

    resp = table.scan(
        FilterExpression=(
            Attr("status").eq("QUEUED") & Attr("SK").begins_with("CART_AUTOMATION_JOB#")
        ),
        Limit=limit * 10,  # Scan は Limit が pre-filter なので多めに
    )
    return resp.get("Items", [])[:limit]


def mark_job(job: dict, *, status: str, result: dict | None = None) -> None:
    table = _ddb()
    now = _now_iso()
    update_expr = "SET #s = :s, updatedAt = :u"
    expr_attr_names = {"#s": "status"}
    expr_attr_values = {":s": status, ":u": now}
    if status == "RUNNING":
        update_expr += ", started_at = :st"
        expr_attr_values[":st"] = now
    elif status in ("COMPLETED", "FAILED", "REQUIRES_HUMAN"):
        update_expr += ", completed_at = :ct"
        expr_attr_values[":ct"] = now
    if result is not None:
        update_expr += ", #r = :r"
        expr_attr_names["#r"] = "result"
        expr_attr_values[":r"] = result
        if result.get("error_code"):
            update_expr += ", error_code = :ec, error_message = :em"
            expr_attr_values[":ec"] = result["error_code"]
            expr_attr_values[":em"] = result.get("message", "")
    table.update_item(
        Key={"PK": job["PK"], "SK": job["SK"]},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_values,
    )


def execute_job(job: dict) -> dict:
    """1 ジョブを Nova Act CLI 経由で実行"""
    import purchase_amazon

    action = job.get("action", "ADD_TO_CART")
    product_url = job.get("product_url") or job.get("productUrl")
    query = job.get("query")
    max_price = int(job.get("max_allowed_price", job.get("maxAllowedPrice", 1000)))

    args = argparse.Namespace(
        query=query,
        product_url=product_url,
        setup_login=False,
        max_price=max_price,
        user_data_dir=os.environ.get("NOVA_ACT_USER_DATA_DIR"),
        allow_interactive_login=False,
        stop_after_cart=(action == "ADD_TO_CART"),
        execute_purchase=(action == "PURCHASE"),
        headless=True,
    )

    logger.info(
        "execute_job_start job_id=%s action=%s query=%r product_url=%s max_price=%s",
        job.get("job_id") or job.get("jobId"),
        action, query, product_url, max_price,
    )
    started = time.time()
    try:
        result = purchase_amazon.run(args)
    except Exception as e:  # noqa: BLE001
        logger.exception("execute_job_exception")
        result = {"success": False, "status": "FAILED", "error_code": "UNKNOWN",
                  "message": str(e)}
    result["duration_ms"] = int((time.time() - started) * 1000)
    return result


def main():
    logger.info(
        "nova_act_worker_start region=%s table=%s gsi=%s",
        REGION, TABLE_NAME, GSI_NAME,
    )

    try:
        jobs = fetch_pending_jobs(POLL_BATCH)
    except Exception:
        logger.exception("fetch_pending_jobs_failed")
        sys.exit(2)

    if not jobs:
        logger.info("no_pending_jobs")
        return

    logger.info("pending_jobs count=%d", len(jobs))

    for job in jobs:
        job_id = job.get("job_id") or job.get("jobId") or job.get("SK")
        try:
            mark_job(job, status="RUNNING")
            result = execute_job(job)
            terminal_status = {
                "PURCHASED": "COMPLETED",
                "READY_TO_PURCHASE": "COMPLETED",
                "CART_ADDED": "COMPLETED",
                "LOGIN_SETUP_DONE": "COMPLETED",
            }.get(result.get("status"), "FAILED")
            # 人間対応が必要なエラーは REQUIRES_HUMAN
            if result.get("error_code") in ("LOGIN_REQUIRED", "MFA_REQUIRED", "CAPTCHA_REQUIRED"):
                terminal_status = "REQUIRES_HUMAN"
            mark_job(job, status=terminal_status, result=result)
            logger.info(
                "job_done job_id=%s terminal_status=%s success=%s",
                job_id, terminal_status, result.get("success"),
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("job_error job_id=%s", job_id)
            try:
                mark_job(job, status="FAILED", result={"error": str(e)})
            except Exception:
                logger.exception("mark_job_failed_after_error")


if __name__ == "__main__":
    main()
