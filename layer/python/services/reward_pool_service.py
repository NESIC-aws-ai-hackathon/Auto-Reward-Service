"""
ご褒美候補プール サービス

責務:
  1. build_keywords  : PREF_MEMORY → 楽天検索キーワードリスト生成
  2. score_items     : 商品リスト → RewardPoolItem + スコア算出
  3. merge_pool      : 差分マージ（item_id でマッチング）
  4. adjust_score    : スルー/購入フィードバックによるスコア調整

スコア算出式:
  base_score       = キーワードマッチ比率（最小 0.1、マッチあり最小 0.3）
  review_bonus     = min(review_average / 5.0, 1.0) * 0.2（レビュー10件未満は0）
  score            = clamp(base_score + review_bonus, 0.0, 1.0)

スコア調整（adjust_score）:
  "bought"  → +0.15
  "skip"    → −0.10
  clamp(score, 0.0, 1.0)
"""
from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Optional

from models.schemas import PrefMemory, RewardPool, RewardPoolItem, SK_PREFIX_REWARD_POOL
from services.dynamodb_service import DynamoDBService
from services.rakuten_service import RakutenHotel, RakutenProduct
from utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
DEFAULT_KEYWORDS_ENV = "RAKUTEN_DEFAULT_KEYWORDS"
MAX_ITEMS_ENV = "RAKUTEN_MAX_ITEMS_PER_POOL"

SCORE_OUTCOME_BOUGHT = 0.15
SCORE_OUTCOME_SKIP = -0.10
SCORE_MIN = 0.0
SCORE_MAX = 1.0

# タイプ別カテゴリアフィニティキーワード
CATEGORY_TYPE_KEYWORDS: dict[str, list[str]] = {
    "travel": ["旅行", "温泉", "ホテル", "観光", "旅", "宿", "リゾート"],
    "restaurant": ["グルメ", "外食", "レストラン", "ランチ", "ディナー", "食事", "料理"],
}
TYPE_BOOST_FACTOR = 1.3  # スコアを 30% ブースト


def _clamp(value: float, lo: float = SCORE_MIN, hi: float = SCORE_MAX) -> float:
    return max(lo, min(hi, value))


# ─────────────────────────────────────────
# キーワード生成
# ─────────────────────────────────────────
def build_keywords(
    pref: Optional[PrefMemory],
    defaults: Optional[list[str]] = None,
) -> list[str]:
    """
    PrefMemory の categories + positive items から楽天検索キーワードを最大5件生成する。

    優先順位:
      1. pref.categories から最大2件
      2. pref.items の positive・detected_at 新しい順から最大3件
      嗜好が空の場合は defaults を返す。

    Args:
        pref:     PREF_MEMORY# DynamoDB アイテム（None または空でも可）
        defaults: 嗜好なし時のデフォルトキーワードリスト

    Returns:
        重複排除済みキーワードリスト（最大5件）
    """
    if defaults is None:
        raw = os.environ.get(DEFAULT_KEYWORDS_ENV, "スイーツ,コスメ,本,入浴剤,アロマ")
        defaults = [kw.strip() for kw in raw.split(",") if kw.strip()]

    if pref is None:
        return defaults[:5]

    keywords: list[str] = []

    # categories から最大2件
    keywords.extend(pref.categories[:2])

    # positive items から detected_at 新しい順に最大3件
    positive_items = sorted(
        [item for item in (pref.items or []) if item.sentiment == "positive"],
        key=lambda x: x.detected_at or "",
        reverse=True,
    )
    keywords.extend([item.keyword for item in positive_items[:3]])

    # 重複排除（順序維持）
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        if kw and kw not in seen:
            seen.add(kw)
            unique.append(kw)

    if not unique:
        return defaults[:5]

    return unique[:5]


# ─────────────────────────────────────────
# スコアリング
# ─────────────────────────────────────────
def _calc_base_score_text(text: str, keywords: list[str]) -> float:
    """テキストへのキーワードマッチ率からベーススコアを算出する（コモディティ化）"""
    if not keywords:
        return 0.5

    target = text.lower()
    matched = sum(1 for kw in keywords if kw.lower() in target)
    if matched == 0:
        return 0.1
    return max(matched / len(keywords), 0.3)


def _calc_review_bonus_generic(review_average: float, review_count: int) -> float:
    """レビュー平均・件数からボーナススコアを算出する（最大 +0.2）"""
    if review_count < 10:
        return 0.0
    return min(review_average / 5.0, 1.0) * 0.2


def _calc_base_score(product: RakutenProduct, keywords: list[str]) -> float:
    """商品名・カテゴリへのキーワードマッチ率からベーススコアを算出する"""
    return _calc_base_score_text(product.name + " " + product.category_name, keywords)


def _calc_review_bonus(product: RakutenProduct) -> float:
    """レビュー平均・件数からボーナススコアを算出する（最大 +0.2）"""
    return _calc_review_bonus_generic(product.review_average, product.review_count)


def score_items(
    products: list[RakutenProduct],
    keywords: list[str],
) -> list[RewardPoolItem]:
    """
    RakutenProduct リストに嗜好スコアを付与し RewardPoolItem リストを返す。

    Returns:
        スコア降順でソートされた RewardPoolItem リスト
    """
    items: list[RewardPoolItem] = []
    for product in products:
        base = _calc_base_score(product, keywords)
        bonus = _calc_review_bonus(product)
        score = _clamp(base + bonus)
        items.append(
            RewardPoolItem(
                id=product.item_id,
                name=product.name,
                price=product.price,
                category=product.category_name,
                score=score,
                source_url=product.item_url if product.item_url else None,
                image_url=product.image_url,
                type="product",
            )
        )

    # スコア降順ソート
    items.sort(key=lambda x: x.score, reverse=True)
    return items


def score_hotels(
    hotels: list[RakutenHotel],
    keywords: list[str],
) -> list[RewardPoolItem]:
    """
    RakutenHotel リストに嗜好スコアを付与し RewardPoolItem（type="travel"）リストを返す。

    Returns:
        スコア降順でソートされた RewardPoolItem リスト
    """
    items: list[RewardPoolItem] = []
    for hotel in hotels:
        base = _calc_base_score_text(hotel.name + " " + hotel.location, keywords)
        bonus = _calc_review_bonus_generic(hotel.review_average, hotel.review_count)
        score = _clamp(base + bonus)
        items.append(
            RewardPoolItem(
                id=hotel.hotel_no,
                name=hotel.name,
                price=hotel.price,
                category=hotel.location,
                score=score,
                source_url=hotel.hotel_url if hotel.hotel_url else None,
                image_url=hotel.image_url,
                type="travel",
            )
        )

    items.sort(key=lambda x: x.score, reverse=True)
    return items


def score_restaurants(
    restaurants: list[Any],
    keywords: list[str],
) -> list[RewardPoolItem]:
    """
    HotPepperRestaurant リストに嗜好スコアを付与し RewardPoolItem（type="restaurant"）リストを返す。

    Returns:
        スコア降順でソートされた RewardPoolItem リスト
    """
    items: list[RewardPoolItem] = []
    for r in restaurants:
        base = _calc_base_score_text(r.name + " " + r.genre_name, keywords)
        score = _clamp(base)  # HotPepper はレビュー平均がないためボーナスなし
        items.append(
            RewardPoolItem(
                id=r.shop_id,
                name=r.name,
                price=r.price,
                category=r.genre_name,
                score=score,
                source_url=r.shop_url if r.shop_url else None,
                image_url=r.image_url,
                type="restaurant",
            )
        )

    items.sort(key=lambda x: x.score, reverse=True)
    return items


def apply_type_weights(
    items: list[RewardPoolItem],
    pref_categories: list[str],
) -> list[RewardPoolItem]:
    """
    ユーザーの嗜好カテゴリに基づいてタイプ別のスコアブーストを適用する。

    例: pref_categories に "旅行" が含まれる場合、type="travel" アイテムのスコアを +30%。

    Args:
        items:           RewardPoolItem リスト
        pref_categories: PrefMemory.categories（ユーザーの嗜好カテゴリ）

    Returns:
        スコア再計算後にスコア降順でソートされた RewardPoolItem リスト
    """
    if not pref_categories or not items:
        return items

    # pref_categories にマッチする type を特定
    cat_text = " ".join(pref_categories).lower()
    boosted_types: set[str] = {
        type_key
        for type_key, kws in CATEGORY_TYPE_KEYWORDS.items()
        if any(kw in cat_text for kw in kws)
    }

    if not boosted_types:
        return items

    result: list[RewardPoolItem] = []
    for item in items:
        if item.type in boosted_types:
            result.append(item.model_copy(update={"score": _clamp(item.score * TYPE_BOOST_FACTOR)}))
        else:
            result.append(item)

    result.sort(key=lambda x: x.score, reverse=True)
    return result


# ─────────────────────────────────────────
# 差分マージ
# ─────────────────────────────────────────
def merge_pool(
    existing: list[RewardPoolItem],
    new_items: list[RewardPoolItem],
    max_items: Optional[int] = None,
) -> list[RewardPoolItem]:
    """
    既存プールと新規取得アイテムを差分マージし、上位 max_items 件を返す。

    マージ方針:
      - 同じ item_id があれば: name・price・score を新規値で更新。outcome は保持。
      - 新規 item_id: 追加。
      - 既存にのみ存在する item_id（今回の楽天検索に出なかったもの）: 削除。

    Args:
        existing:  既存の RewardPoolItem リスト（DynamoDB から取得済み）
        new_items: 今回の楽天 API + スコアリング結果
        max_items: 上位件数上限（None の場合は環境変数 RAKUTEN_MAX_ITEMS_PER_POOL、デフォルト 20）

    Returns:
        スコア降順・上位 max_items 件の RewardPoolItem リスト
    """
    if max_items is None:
        max_items = int(os.environ.get(MAX_ITEMS_ENV, "20"))

    # 既存アイテムを id → item のマップに変換
    existing_map: dict[str, RewardPoolItem] = {item.id: item for item in existing}

    # 今回取得した id セット
    new_ids: set[str] = {item.id for item in new_items}

    merged: list[RewardPoolItem] = []
    for new_item in new_items:
        if new_item.id in existing_map:
            # 既存アイテムを更新（outcomeは保持、score/name/priceは新規値）
            old = existing_map[new_item.id]
            # outcome フィールドは RewardPoolItem に未定義だが、将来の拡張に備えて
            # 辞書経由で保持する（Pydantic extra="ignore" なので現状はそのまま）
            updated = RewardPoolItem(
                id=new_item.id,
                name=new_item.name,
                price=new_item.price,
                category=new_item.category,
                score=new_item.score,
                source_url=new_item.source_url,
                image_url=new_item.image_url,
                type=new_item.type,
            )
            merged.append(updated)
        else:
            # 新規追加
            merged.append(new_item)

    # スコア降順ソート → 上位 max_items 件に絞り込み
    merged.sort(key=lambda x: x.score, reverse=True)
    return merged[:max_items]


# ─────────────────────────────────────────
# スコア調整
# ─────────────────────────────────────────
def adjust_score(
    user_pk: str,
    item_id: str,
    outcome: str,
    ddb: DynamoDBService,
) -> None:
    """
    スルー (skip) または購入 (bought) フィードバックに基づき REWARD_POOL# のスコアを調整する。

    Args:
        user_pk:  `USER#{line_user_id}` 形式の DynamoDB PK
        item_id:  フィードバック対象の RewardPoolItem.id
        outcome:  "bought" または "skip"
        ddb:      DynamoDBService インスタンス

    Returns:
        None（DynamoDB を直接更新する副作用あり）
    """
    raw = ddb.get_item(user_pk, SK_PREFIX_REWARD_POOL)
    if raw is None:
        logger.warning("adjust_score_no_pool", user_pk=user_pk)
        return

    pool = RewardPool(**raw)
    target_idx: Optional[int] = None
    for idx, item in enumerate(pool.items):
        if item.id == item_id:
            target_idx = idx
            break

    if target_idx is None:
        logger.warning("adjust_score_item_not_found", item_id=item_id)
        return

    delta = SCORE_OUTCOME_BOUGHT if outcome == "bought" else SCORE_OUTCOME_SKIP
    old_score = pool.items[target_idx].score
    new_score = _clamp(old_score + delta)
    pool.items[target_idx] = RewardPoolItem(
        **{**pool.items[target_idx].model_dump(), "score": new_score}
    )

    logger.debug(
        "adjust_score_applied",
        item_id=item_id,
        outcome=outcome,
        old_score=old_score,
        new_score=new_score,
    )

    # 更新済みプールを保存
    ddb.put_item(
        user_pk,
        SK_PREFIX_REWARD_POOL,
        pool.model_dump(exclude={"pk", "sk"}),
    )
