"""
ご褒美候補プール 日次バッチ更新 Lambda ハンドラ

トリガー: EventBridge Scheduler (cron(0 17 * * ? *) = JST 02:00)

処理フロー:
  1. DynamoDB GSI (entityType=PROFILE) で全アクティブユーザーの PK を取得
  2. ユーザーごとに PREF_MEMORY# → キーワード生成 → 楽天 API 検索 → スコアリング → 差分マージ → DynamoDB 保存
  3. 楽天 API 無料枚ガード（900 リクエスト上限）
  4. PoolUpdateResult を CloudWatch Logs に出力

環境変数:
  TABLE_NAME                  - DynamoDB テーブル名
  RAKUTEN_SECRET_NAME         - Secrets Manager シークレット名 (ars/rakuten)
  HOTPEPPER_SECRET_NAME       - Secrets Manager シークレット名 (ars/hotpepper/api-key)
  RAKUTEN_DEFAULT_KEYWORDS    - 嵐好なし時のデフォルトキーワード（カンマ区切り）
  RAKUTEN_MAX_ITEMS_PER_POOL  - プール最大アイテム数（デフォルト: 20）
  RAKUTEN_HITS_PER_KEYWORD    - キーワードあたり取得件数（デフォルト: 5）
  ENABLE_HOTEL_SEARCH         - 楽天トラベル検索有効化 (true/false、デフォルト: true)
  HOTEL_HITS_PER_KEYWORD      - ホテルキーワードあたり取得件数（デフォルト: 3）
  ENABLE_RESTAURANT_SEARCH    - ホットペッパー検索有効化 (true/false、デフォルト: false)
  RESTAURANT_HITS_PER_KEYWORD - レストランキーワードあたり取得件数（デフォルト: 3）
"""
from __future__ import annotations

import datetime
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from models.schemas import (
    ENTITY_PROFILE,
    ENTITY_PREF_MEMORY,
    PrefMemory,
    RewardPool,
    SK_PREFIX_REWARD_POOL,
    SK_PREF_MEMORY,
)
from services.dynamodb_service import DynamoDBService, get_dynamodb_service
from services import rakuten_service
from services.rakuten_service import RakutenAPIError, search_hotels, search_products
from services.hotpepper_service import HotPepperAPIError, search_restaurants
from services import reward_pool_service
from services.reward_pool_service import (
    apply_type_weights,
    build_keywords,
    merge_pool,
    score_hotels,
    score_items,
    score_restaurants,
)
from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
MAX_RAKUTEN_REQUESTS = 900  # 無料枠 1,000 の 90% でセーフティストップ
HITS_PER_KEYWORD = int(os.environ.get("RAKUTEN_HITS_PER_KEYWORD", "5"))
ENABLE_HOTEL_SEARCH = os.environ.get("ENABLE_HOTEL_SEARCH", "true").lower() == "true"
HOTEL_HITS_PER_KEYWORD = int(os.environ.get("HOTEL_HITS_PER_KEYWORD", "3"))
ENABLE_RESTAURANT_SEARCH = os.environ.get("ENABLE_RESTAURANT_SEARCH", "false").lower() == "true"
RESTAURANT_HITS_PER_KEYWORD = int(os.environ.get("RESTAURANT_HITS_PER_KEYWORD", "3"))
DEFAULT_KEYWORDS_RAW = os.environ.get(
    "RAKUTEN_DEFAULT_KEYWORDS", "スイーツ,コスメ,本,入浴剤,アロマ"
)
DEFAULT_KEYWORDS: list[str] = [kw.strip() for kw in DEFAULT_KEYWORDS_RAW.split(",") if kw.strip()]


# ─────────────────────────────────────────
# 結果サマリー
# ─────────────────────────────────────────
@dataclass
class PoolUpdateResult:
    total_users: int = 0
    success_count: int = 0
    skip_count: int = 0
    error_count: int = 0
    total_items_fetched: int = 0
    executed_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    )


# ─────────────────────────────────────────
# 全ユーザー PK 取得
# ─────────────────────────────────────────
def _get_all_user_pks(ddb: DynamoDBService) -> list[str]:
    """
    DynamoDB entityType-index GSI で PROFILE エンティティを Query し、
    アクティブユーザーの PK リストを返す。
    """
    items = ddb.query_by_gsi(
        entity_type=ENTITY_PROFILE,
        filter_expr={"status": "ACTIVE"},
    )
    return [item["PK"] for item in items if "PK" in item]


# ─────────────────────────────────────────
# per-user 更新
# ─────────────────────────────────────────
def _update_user_pool(user_pk: str, ddb: DynamoDBService) -> int:
    """
    1 ユーザーの REWARD_POOL# を更新する。

    Returns:
        今回取得した楽天商品アイテムの合計件数

    Raises:
        RakutenAPIError: 楽天 API 全失敗時
    """
    # PREF_MEMORY# 取得（存在しない場合は None → デフォルトキーワード使用）
    pref_raw = ddb.get_item(user_pk, SK_PREF_MEMORY)
    pref: Optional[PrefMemory] = None
    if pref_raw:
        try:
            pref = PrefMemory(
                pk=pref_raw.get("PK", ""),
                categories=pref_raw.get("categories", []),
                items=pref_raw.get("items", []),
                updated_at=pref_raw.get("updatedAt") or pref_raw.get("updated_at"),
            )
        except Exception as e:
            logger.warning("pref_memory_parse_error", user_pk=user_pk, error=str(e))

    # キーワード生成
    keywords = build_keywords(pref, DEFAULT_KEYWORDS)
    logger.debug("pool_update_keywords", user_pk=user_pk, count=len(keywords))

    # 楽天 API 検索（キーワードごとに順次実行）
    all_products = []
    for keyword in keywords:
        try:
            products = search_products(keyword, hits=HITS_PER_KEYWORD)
            all_products.extend(products)
        except RakutenAPIError:
            # 1 キーワードが失敗しても他を続行（全キーワード失敗時は呼び出し元が処理）
            logger.warning("pool_update_keyword_error", keyword="[MASKED]")

    if not all_products:
        raise RakutenAPIError(f"全キーワードで楽天 API 検索失敗: {user_pk}")

    # スコアリング（商品）
    new_items = score_items(all_products, keywords)

    # ─── 楽天トラベル ホテル検索（ENABLE_HOTEL_SEARCH=true 時） ───
    if ENABLE_HOTEL_SEARCH:
        for keyword in keywords:
            try:
                hotels = search_hotels(keyword, hits=HOTEL_HITS_PER_KEYWORD)
                new_items.extend(score_hotels(hotels, keywords))
            except RakutenAPIError:
                logger.warning("pool_update_hotel_keyword_error", keyword="[MASKED]")

    # ─── ホットペッパー レストラン検索（ENABLE_RESTAURANT_SEARCH=true 時） ───
    if ENABLE_RESTAURANT_SEARCH:
        for keyword in keywords:
            try:
                restaurants = search_restaurants(keyword, count=RESTAURANT_HITS_PER_KEYWORD)
                new_items.extend(score_restaurants(restaurants, keywords))
            except HotPepperAPIError:
                logger.warning("pool_update_restaurant_keyword_error", keyword="[MASKED]")

    # タイプ重みづけ（pref_categories に旅行・グルメ系があればブースト）
    if pref and pref.categories:
        new_items = apply_type_weights(new_items, pref.categories)

    # 既存プール取得
    existing_raw = ddb.get_item(user_pk, SK_PREFIX_REWARD_POOL)
    existing_items: list[RewardPoolItem] = []
    if existing_raw:
        raw_items = existing_raw.get("items") or []
        for raw in raw_items:
            try:
                existing_items.append(RewardPoolItem(**raw))
            except Exception:
                pass

    # 差分マージ
    merged = merge_pool(existing_items, new_items)

    # DynamoDB 保存
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    pool_data = {
        "items": [item.model_dump() for item in merged],
        "updated_at": now,
        "entity_type": "REWARD_POOL",
    }
    ddb.put_item(user_pk, SK_PREFIX_REWARD_POOL, pool_data)

    logger.debug(
        "pool_updated",
        user_pk=user_pk,
        items_count=len(merged),
    )
    return len(all_products)


# ─────────────────────────────────────────
# Lambda エントリポイント
# ─────────────────────────────────────────
def lambda_handler(event: dict[str, Any], context: Any) -> None:
    """
    EventBridge Scheduler から呼び出される日次バッチ Lambda ハンドラ。

    正常終了後に PoolUpdateResult を CloudWatch Logs に出力する。
    Lambda 自体は常に正常終了（None 返却）する。
    """
    logger.info("pool_update_batch_started")
    ddb = get_dynamodb_service()
    result = PoolUpdateResult()

    # 全ユーザー PK 取得
    user_pks = _get_all_user_pks(ddb)
    result.total_users = len(user_pks)
    logger.info("pool_update_users_found", total_users=result.total_users)

    total_requests = 0

    for user_pk in user_pks:
        # 楽天 API 無料枠ガード
        if total_requests >= MAX_RAKUTEN_REQUESTS:
            logger.warning(
                "rakuten_request_limit_reached",
                processed=result.success_count + result.error_count,
                remaining=result.total_users - result.success_count - result.error_count - result.skip_count,
            )
            result.skip_count += 1
            continue

        try:
            fetched_count = _update_user_pool(user_pk, ddb)
            result.success_count += 1
            result.total_items_fetched += fetched_count
            # キーワード数 × 1 リクエストとしてカウント（保守的に5と仮定）
            total_requests += 5
        except RakutenAPIError as exc:
            logger.warning(
                "pool_update_user_error",
                user_pk=user_pk,
                error=str(exc),
            )
            result.error_count += 1
        except Exception as exc:
            logger.error(
                "pool_update_user_unexpected_error",
                user_pk=user_pk,
                error=str(exc),
            )
            result.error_count += 1

    # 完了サマリー出力
    logger.info(
        "pool_update_complete",
        total_users=result.total_users,
        success_count=result.success_count,
        skip_count=result.skip_count,
        error_count=result.error_count,
        total_items_fetched=result.total_items_fetched,
        executed_at=result.executed_at,
    )
