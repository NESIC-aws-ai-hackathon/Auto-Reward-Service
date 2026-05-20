"""
楽天ウェブサービス API クライアント

対応 API:
  楽天市場商品検索 API 2017-07-06
  https://webservice.rakuten.co.jp/documentation/ichiba-item-search

設計方針:
- AppID は Secrets Manager からモジュールレベルキャッシュ
- 楽天APIは 1 req/秒レートリミット遵守 (time.sleep)
- HTTP エラー・タイムアウトは最大3回指数バックオフリトライ
- 全失敗時は RakutenAPIError を raise
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

import requests
from requests.exceptions import RequestException

from utils.exceptions import SecretsError
from utils.logger import get_logger
from utils.secrets import get_secret

logger = get_logger(__name__)

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
RAKUTEN_SEARCH_URL = (
    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
)
RAKUTEN_TRAVEL_URL = (
    "https://openapi.rakuten.co.jp/engine/api/Travel/KeywordHotelSearch/20170426"
)
MAX_RETRIES = 3
BACKOFF_BASE = 1.0          # 秒
RATE_LIMIT_SLEEP = 1.0      # 秒（1 req/s 遵守）
ITEM_NAME_MAX_LEN = 100     # 商品名の最大文字数
HOTEL_NAME_MAX_LEN = 100    # ホテル名の最大文字数
DEFAULT_MIN_PRICE = 300     # 円
DEFAULT_MAX_PRICE = 50_000  # 円


# ─────────────────────────────────────────
# 独自例外
# ─────────────────────────────────────────
class RakutenAPIError(Exception):
    """楽天 API 呼び出し失敗時に発生する例外"""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original


# ─────────────────────────────────────────
# データクラス
# ─────────────────────────────────────────
@dataclass
class RakutenProduct:
    """楽天 API から取得した商品情報の内部表現"""

    item_id: str
    name: str
    price: Decimal
    category_name: str
    item_url: str
    image_url: Optional[str]
    shop_name: str
    review_average: float
    review_count: int


@dataclass
class RakutenHotel:
    """楽天トラベル API から取得したホテル情報の内部表現"""

    hotel_no: str
    name: str
    price: Decimal       # 1人あたり最低料金（円）
    location: str        # エリア名
    hotel_url: str
    image_url: Optional[str]
    review_average: float
    review_count: int


# ─────────────────────────────────────────
# モジュールレベルキャッシュ（Secrets Manager）
# ─────────────────────────────────────────
_cached_app_id: Optional[str] = None
_cached_access_key: Optional[str] = None


def _get_credentials() -> tuple[str, str]:
    """楽天 AppID + AccessKey を Secrets Manager から取得し Lambda コンテキスト内でキャッシュする"""
    global _cached_app_id, _cached_access_key
    if _cached_app_id is not None and _cached_access_key is not None:
        return _cached_app_id, _cached_access_key

    secret_name = os.environ.get("RAKUTEN_SECRET_NAME", "ars/rakuten")
    try:
        secrets = get_secret(secret_name)
        app_id = secrets.get("RAKUTEN_APP_ID")
        access_key = secrets.get("RAKUTEN_ACCESS_KEY")
        if not app_id:
            raise RakutenAPIError(
                f"RAKUTEN_APP_ID が {secret_name} に存在しません"
            )
        if not access_key:
            raise RakutenAPIError(
                f"RAKUTEN_ACCESS_KEY が {secret_name} に存在しません"
            )
        _cached_app_id = app_id
        _cached_access_key = access_key
        return _cached_app_id, _cached_access_key
    except SecretsError as exc:
        raise RakutenAPIError("楽天認証情報の取得に失敗しました", exc) from exc


# ─────────────────────────────────────────
# HTTP呼び出し（リトライ付き）
# ─────────────────────────────────────────
def _call_with_retry(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    指定 URL+パラメータで GET リクエストを送り、最大 MAX_RETRIES 回リトライする。

    Returns:
        パースされた JSON レスポンス dict

    Raises:
        RakutenAPIError: 全リトライ失敗時
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=(3.0, 10.0))
            resp.raise_for_status()
            return resp.json()
        except RequestException as exc:
            last_exc = exc
            logger.warning(
                "rakuten_api_retry",
                attempt=attempt + 1,
                max_retries=MAX_RETRIES,
                error=str(exc),
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE * (2 ** attempt))

    raise RakutenAPIError(
        f"楽天 API {MAX_RETRIES} 回リトライ失敗", last_exc
    ) from last_exc


# ─────────────────────────────────────────
# レスポンスパース
# ─────────────────────────────────────────
def _parse_response(data: dict[str, Any]) -> list[RakutenProduct]:
    """
    楽天 API レスポンスを RakutenProduct リストに変換する。

    formatVersion=2 を前提（Items がフラット配列）。
    """
    products: list[RakutenProduct] = []
    items = data.get("Items", [])

    for item in items:
        try:
            # 画像 URL（最初の medium image を使用）
            image_urls: list[dict] = item.get("mediumImageUrls", [])
            image_url: Optional[str] = None
            if image_urls:
                raw_img = image_urls[0]
                image_url = raw_img.get("imageUrl") if isinstance(raw_img, dict) else raw_img

            products.append(
                RakutenProduct(
                    item_id=str(item.get("itemCode", "")),
                    name=str(item.get("itemName", ""))[:ITEM_NAME_MAX_LEN],
                    price=Decimal(str(item.get("itemPrice", 0))),
                    category_name=str(item.get("genreName", "")),
                    item_url=str(item.get("itemUrl", "")),
                    image_url=image_url,
                    shop_name=str(item.get("shopName", "")),
                    review_average=float(item.get("reviewAverage", 0.0)),
                    review_count=int(item.get("reviewCount", 0)),
                )
            )
        except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
            logger.warning("rakuten_parse_item_error", error=str(exc))
            continue

    return products


# ─────────────────────────────────────────
# パブリック API
# ─────────────────────────────────────────
def search_products(
    keyword: str,
    hits: int = 5,
    min_price: int = DEFAULT_MIN_PRICE,
    max_price: int = DEFAULT_MAX_PRICE,
) -> list[RakutenProduct]:
    """
    楽天市場商品検索 API で keyword に一致する商品を取得する。

    Args:
        keyword:   検索キーワード
        hits:      取得件数（楽天 API 上限: 30）
        min_price: 最低価格フィルタ（円）
        max_price: 最高価格フィルタ（円）

    Returns:
        RakutenProduct リスト（空リストも許容）

    Raises:
        RakutenAPIError: HTTP 通信が MAX_RETRIES 回失敗した場合
    """
    app_id, access_key = _get_credentials()
    params: dict[str, Any] = {
        "applicationId": app_id,
        "accessKey": access_key,
        "keyword": keyword,
        "hits": hits,
        "sort": "+reviewAverage",
        "minPrice": min_price,
        "maxPrice": max_price,
        "formatVersion": 2,
    }

    logger.debug("rakuten_search", keyword=keyword, hits=hits)
    data = _call_with_retry(RAKUTEN_SEARCH_URL, params)
    products = _parse_response(data)

    # レートリミット遵守（1 req/s）
    time.sleep(RATE_LIMIT_SLEEP)

    logger.debug("rakuten_search_result", keyword=keyword, count=len(products))
    return products


# ─────────────────────────────────────────
# 楽天トラベル ホテル検索
# ─────────────────────────────────────────
def _parse_hotel_response(data: dict[str, Any]) -> list[RakutenHotel]:
    """
    楽天トラベル KeywordHotelSearch レスポンスを RakutenHotel リストに変換する。

    formatVersion=2 あり（ネスト配列なし）と、なし（ネスト配列あり）の両方に対応。
    """
    hotels: list[RakutenHotel] = []
    for hotel_entry in data.get("hotels", []):
        try:
            # formatVersion=2 なし: hotel_entry は [{hotelBasicInfo: {...}}, ...]
            # formatVersion=2 あり: hotel_entry は {hotelBasicInfo: {...}, ...}
            if isinstance(hotel_entry, list):
                basic = next(
                    (h.get("hotelBasicInfo", {}) for h in hotel_entry if "hotelBasicInfo" in h),
                    {},
                )
            else:
                basic = hotel_entry.get("hotelBasicInfo", {})

            if not basic:
                continue

            hotels.append(
                RakutenHotel(
                    hotel_no=str(basic.get("hotelNo", "")),
                    name=str(basic.get("hotelName", ""))[:HOTEL_NAME_MAX_LEN],
                    price=Decimal(str(basic.get("hotelMinCharge", 0) or 0)),
                    location=str(basic.get("areaName", "")),
                    hotel_url=str(basic.get("hotelInformationUrl", "")),
                    image_url=basic.get("hotelImageUrl") or None,
                    review_average=float(basic.get("reviewAverage", 0.0) or 0.0),
                    review_count=int(basic.get("reviewCount", 0) or 0),
                )
            )
        except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
            logger.warning("rakuten_parse_hotel_error", error=str(exc))
            continue

    return hotels


def search_hotels(
    keyword: str,
    hits: int = 5,
) -> list[RakutenHotel]:
    """
    楽天トラベル KeywordHotelSearch API でキーワードに一致するホテルを取得する。
    同一 AppID（ars/rakuten）を使用。

    Args:
        keyword: 検索キーワード
        hits:    取得件数（楽天トラベル API 上限: 30）

    Returns:
        RakutenHotel リスト（空リストも許容）

    Raises:
        RakutenAPIError: HTTP 通信が MAX_RETRIES 回失敗した場合
    """
    app_id, access_key = _get_credentials()
    params: dict[str, Any] = {
        "applicationId": app_id,
        "accessKey": access_key,
        "keyword": keyword,
        "hits": hits,
        "formatVersion": 2,
    }

    logger.debug("rakuten_hotel_search", keyword=keyword, hits=hits)
    data = _call_with_retry(RAKUTEN_TRAVEL_URL, params)
    hotels = _parse_hotel_response(data)

    # レートリミット遵守（1 req/s）
    time.sleep(RATE_LIMIT_SLEEP)

    logger.debug("rakuten_hotel_search_result", keyword=keyword, count=len(hotels))
    return hotels
