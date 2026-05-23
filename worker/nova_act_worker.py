"""
Nova Act Worker — Amazon商品検索ワーカー

仕組み:
  1. DynamoDB を定期ポーリングし queued ジョブを取得
  2. Nova Act (Playwright ベース) で Amazon.co.jp を操作
  3. 匿名状態で商品検索（ログイン不要）
  4. 商品名・価格・画像URL・商品URL・ASINを抽出
  5. 結果を DynamoDB に保存（REWARD_POOL# + 検索ジョブ結果）

重要方針:
  - Nova Actでやること: Amazon商品検索・情報抽出のみ
  - Nova Actでやらないこと: ログイン、カート投入、購入操作

実行方法:
  pip install nova-act boto3
  python worker/nova_act_worker.py

環境変数:
  AWS_PROFILE: AWS プロファイル名 (default: share)
  AWS_REGION: リージョン (default: ap-northeast-1)
  NOVA_ACT_PROFILE_DIR: ブラウザプロファイルのパス (空でも可 - 匿名検索)
  S3_SCREENSHOT_BUCKET: スクリーンショット保存バケット
  POLL_INTERVAL: ポーリング間隔秒 (default: 5)
  DDB_TABLE_NAME: DynamoDB テーブル名 (default: ArsTable)
"""
from __future__ import annotations

import os
import sys
import time
import json
import uuid
import traceback
from datetime import datetime, timezone
from pathlib import Path

import boto3

# ─── 設定 ───
AWS_PROFILE = os.getenv("AWS_PROFILE", "share")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
DDB_TABLE_NAME = os.getenv("DDB_TABLE_NAME", "ArsTable")
S3_BUCKET = os.getenv("S3_SCREENSHOT_BUCKET", "ars-nova-act-screenshots")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))
NOVA_ACT_PROFILE_DIR = os.getenv("NOVA_ACT_PROFILE_DIR", "")

# ジョブの SK プレフィックス
SEARCH_JOB_PK_PREFIX = "NOVA_ACT_SEARCH_JOB#"

# ─── AWS クライアント ───
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
ddb = session.resource("dynamodb").Table(DDB_TABLE_NAME)
s3 = session.client("s3")


def log(level: str, msg: str, **kwargs):
    """シンプルなログ出力"""
    ts = datetime.now().strftime("%H:%M:%S")
    extra = " ".join(f"{k}={v}" for k, v in kwargs.items())
    print(f"[{ts}] [{level}] {msg} {extra}")


# ─── DynamoDB 操作 ───
def poll_pending_jobs() -> list[dict]:
    """queued ステータスの検索ジョブをスキャンで取得"""
    from boto3.dynamodb.conditions import Attr

    resp = ddb.scan(
        FilterExpression=(
            Attr("PK").begins_with(SEARCH_JOB_PK_PREFIX)
            & Attr("status").eq("queued")
        ),
    )
    items = resp.get("Items", [])

    while "LastEvaluatedKey" in resp:
        resp = ddb.scan(
            FilterExpression=(
                Attr("PK").begins_with(SEARCH_JOB_PK_PREFIX)
                & Attr("status").eq("queued")
            ),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))

    return items


def update_job_status(job_id: str, status: str, **extra_fields):
    """検索ジョブのステータスを更新"""
    pk = f"{SEARCH_JOB_PK_PREFIX}{job_id}"
    sk = "META#"
    now = datetime.now(timezone.utc).isoformat()

    update_expr_parts = ["#s = :status", "updated_at = :now"]
    attr_names = {"#s": "status"}
    attr_values = {":status": status, ":now": now}

    for key, val in extra_fields.items():
        if val is not None:
            placeholder = f":{key}"
            update_expr_parts.append(f"{key} = {placeholder}")
            attr_values[placeholder] = val

    ddb.update_item(
        Key={"PK": pk, "SK": sk},
        UpdateExpression="SET " + ", ".join(update_expr_parts),
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )


def save_search_results(job_id: str, candidates: list[dict]):
    """検索結果をジョブ結果レコードに保存"""
    pk = f"{SEARCH_JOB_PK_PREFIX}{job_id}"
    sk = "RESULT#"
    now = datetime.now(timezone.utc).isoformat()

    ddb.put_item(Item={
        "PK": pk,
        "SK": sk,
        "entityType": "NOVA_ACT_SEARCH_RESULT",
        "status": "completed",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "created_at": now,
    })


def save_to_reward_pool(user_id: str, candidates: list[dict]):
    """検索結果をユーザーの REWARD_POOL# に保存"""
    now = datetime.now(timezone.utc).isoformat()
    for c in candidates:
        candidate_id = str(uuid.uuid4())
        pk = user_id  # "USER#{lineUserId}" 形式
        sk = f"REWARD_POOL#{candidate_id}"
        ddb.put_item(Item={
            "PK": pk,
            "SK": sk,
            "entityType": "REWARD_POOL",
            **c,
            "saved_at": now,
        })


def upload_screenshot(job_id: str, step: str, screenshot_bytes: bytes) -> str:
    """スクリーンショットを S3 にアップロード、Presigned URL を返す"""
    key = f"screenshots/{job_id}/{step}.png"
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=screenshot_bytes,
            ContentType="image/png",
        )
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=3600,
        )
        return url
    except Exception as e:
        log("ERROR", f"S3 upload failed: {e}")
        return ""


# ─── Nova Act Amazon検索 ───
def process_search_job(job: dict):
    """1つの検索ジョブを Nova Act で処理する"""
    job_id = job.get("job_id", "")
    user_id = job.get("userId", "")
    query = job.get("query", "")
    max_price = int(job.get("max_price", 5000))

    log("INFO", f"Processing search job", job_id=job_id, query=query, max_price=max_price)

    update_job_status(job_id, "processing")

    try:
        from nova_act import NovaAct

        nova_kwargs = {}
        if NOVA_ACT_PROFILE_DIR:
            nova_kwargs["user_data_dir"] = NOVA_ACT_PROFILE_DIR

        with NovaAct(starting_page="https://www.amazon.co.jp", **nova_kwargs) as nova:
            # Step 1: Amazon検索
            log("INFO", "Searching Amazon...", query=query)
            result = nova.act(
                f"Search for '{query}' using the search bar on Amazon.co.jp. "
                f"Type the query and press Enter or click the search button.",
                timeout=30000,
            )

            time.sleep(3)  # 検索結果ページのロード待ち

            # Step 2: 検索結果から商品情報を抽出
            log("INFO", "Extracting product info from search results...")
            result = nova.act(
                f"Look at the search results on this page. "
                f"For each of the top 5 products visible, extract: "
                f"1. Product name "
                f"2. Price (number only, in yen) "
                f"3. The product URL (from the link) "
                f"4. The product image URL "
                f"Report the information you found.",
                timeout=30000,
            )

            # スクリーンショット
            try:
                ss = nova.page.screenshot()
                upload_screenshot(job_id, "search_results", ss)
            except Exception:
                pass

            # Step 3: 各商品ページを開いてASIN等を取得
            # Nova Actの応答からテキスト情報を解析
            candidates = _extract_candidates_from_page(nova, query, max_price)

            if candidates:
                # 結果保存
                save_search_results(job_id, candidates)
                save_to_reward_pool(user_id, candidates)
                update_job_status(job_id, "completed", candidate_count=len(candidates))
                log("INFO", f"Search job completed", job_id=job_id, count=len(candidates))
            else:
                update_job_status(job_id, "completed", candidate_count=0)
                log("WARN", "No candidates extracted", job_id=job_id)

    except ImportError:
        log("ERROR", "nova-act package not installed. Install with: pip install nova-act")
        update_job_status(job_id, "failed", error="nova-act パッケージがインストールされていません")
    except Exception as e:
        error_msg = str(e)[:500]
        log("ERROR", f"Search job failed: {error_msg}", job_id=job_id)
        traceback.print_exc()
        update_job_status(job_id, "failed", error=error_msg)


def _extract_candidates_from_page(nova, query: str, max_price: int) -> list[dict]:
    """Nova Actのページから商品候補情報を抽出する"""
    try:
        # ページのURLからASINを抽出するパターン
        import re

        result = nova.act(
            "Extract product information from the current search results page. "
            "For each visible product, get: "
            "1. Full product name "
            "2. Price in yen (numbers only) "
            "3. The ASIN from the product link (it's in the URL like /dp/BXXXXXXXXX) "
            "Return the data as a JSON array with keys: name, price, asin",
            timeout=30000,
        )

        # Nova Actの応答テキストからJSONを抽出
        response_text = str(result.response) if result.response else ""
        candidates = []

        # JSON配列を探す
        json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
        if json_match:
            try:
                items = json.loads(json_match.group())
                for item in items[:5]:
                    name = str(item.get("name", ""))[:80]
                    price = int(item.get("price", 0))
                    asin = str(item.get("asin", ""))

                    if not name or price <= 0:
                        continue
                    if price > max_price:
                        continue

                    candidates.append({
                        "name": name,
                        "amount": price,
                        "currency": "JPY",
                        "asin": asin,
                        "url": f"https://www.amazon.co.jp/dp/{asin}" if asin else "",
                        "source": "nova_act_amazon",
                        "tags": query.split(),
                        "reward_type": "product",
                        "confidence": 0.8,
                        "reason": "Nova ActがAmazonで見つけた商品",
                    })
            except json.JSONDecodeError:
                log("WARN", "Failed to parse JSON from Nova Act response")

        return candidates
    except Exception as e:
        log("ERROR", f"Extraction failed: {e}")
        return []


# ─── メインループ ───
def main():
    log("INFO", "Nova Act Amazon Search Worker started",
        profile=AWS_PROFILE,
        region=AWS_REGION,
        table=DDB_TABLE_NAME,
        poll_interval=POLL_INTERVAL)
    log("INFO", "Mode: Amazon商品検索のみ（カート投入・購入操作なし）")

    if NOVA_ACT_PROFILE_DIR:
        log("INFO", f"Browser profile: {NOVA_ACT_PROFILE_DIR}")

    while True:
        try:
            jobs = poll_pending_jobs()
            if jobs:
                log("INFO", f"Found {len(jobs)} queued search job(s)")
                for job in jobs:
                    process_search_job(job)

        except KeyboardInterrupt:
            log("INFO", "Worker stopped by user")
            break
        except Exception as e:
            log("ERROR", f"Poll loop error: {e}")
            traceback.print_exc()

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
