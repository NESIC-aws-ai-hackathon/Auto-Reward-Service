"""
ホットペッパーグルメ API クライアント（Growth フェーズ）

対応 API:
  ホットペッパーグルメサーチ API v1
  https://webservice.recruit.co.jp/hotpepper/gourmet/v1/

設計方針:
- API キーは Secrets Manager (ars/hotpepper/api-key) からモジュールレベルキャッシュ
- ENABLE_RESTAURANT_SEARCH=true のときのみ呼び出される
- HTTP エラーは最大3回指数バックオフリトライ
- 全失敗時は HotPepperAPIError を raise
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
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
HOTPEPPER_SEARCH_URL = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
MAX_RETRIES = 3
BACKOFF_BASE = 1.0      # 秒
RATE_LIMIT_SLEEP = 0.5  # 秒（HotPepper は 1 req/s 制限なし）
NAME_MAX_LEN = 100


# ─────────────────────────────────────────
# 独自例外
# ─────────────────────────────────────────
class HotPepperAPIError(Exception):
    """ホットペッパー API 呼び出し失敗時に発生する例外"""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original


# ─────────────────────────────────────────
# データクラス
# ─────────────────────────────────────────
@dataclass
class HotPepperRestaurant:
    """ホットペッパー API から取得した店舗情報の内部表現"""

    shop_id: str
    name: str
    price: Decimal       # 予算（円）
    genre_name: str
    shop_url: str
    image_url: Optional[str]
    station_name: str    # 最寄り駅


# ─────────────────────────────────────────
# モジュールレベルキャッシュ（Secrets Manager）
# ─────────────────────────────────────────
_cached_api_key: Optional[str] = None


def _get_api_key() -> str:
    """ホットペッパー API キーを Secrets Manager から取得し Lambda コンテキスト内でキャッシュする"""
    global _cached_api_key
    if _cached_api_key is not None:
        return _cached_api_key

    secret_name = os.environ.get("HOTPEPPER_SECRET_NAME", "ars/hotpepper/api-key")
    try:
        secrets = get_secret(secret_name)
        api_key = secrets.get("HOTPEPPER_API_KEY")
        if not api_key:
            raise HotPepperAPIError(
                f"HOTPEPPER_API_KEY が {secret_name} に存在しません"
            )
        _cached_api_key = api_key
        return _cached_api_key
    except SecretsError as exc:
        raise HotPepperAPIError("ホットペッパー APIキーの取得に失敗しました", exc) from exc


# ─────────────────────────────────────────
# 予算文字列パース
# ─────────────────────────────────────────
def _parse_budget(budget_str: str) -> Decimal:
    """
    HotPepper の予算文字列を Decimal に変換する。

    例:
      "2001～3000円" → Decimal("2001")
      "3000円"       → Decimal("3000")
      ""             → Decimal("0")
    """
    cleaned = re.sub(r"[円,\s]", "", str(budget_str))
    # 範囲表記の場合は下限を取る
    if "～" in cleaned or "~" in cleaned:
        cleaned = re.split(r"[～~]", cleaned)[0]
    try:
        return Decimal(cleaned) if cleaned else Decimal("0")
    except ArithmeticError:
        return Decimal("0")


# ─────────────────────────────────────────
# HTTP 呼び出し（リトライ付き）
# ─────────────────────────────────────────
def _call_with_retry(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    指定 URL+パラメータで GET リクエストを送り、最大 MAX_RETRIES 回リトライする。

    Returns:
        パースされた JSON レスポンス dict

    Raises:
        HotPepperAPIError: 全リトライ失敗時
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
                "hotpepper_api_retry",
                attempt=attempt + 1,
                max_retries=MAX_RETRIES,
                error=str(exc),
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE * (2 ** attempt))

    raise HotPepperAPIError(
        f"ホットペッパー API {MAX_RETRIES} 回リトライ失敗", last_exc
    ) from last_exc


# ─────────────────────────────────────────
# レスポンスパース
# ─────────────────────────────────────────
def _parse_response(data: dict[str, Any]) -> list[HotPepperRestaurant]:
    """
    ホットペッパー API レスポンスを HotPepperRestaurant リストに変換する。
    """
    restaurants: list[HotPepperRestaurant] = []
    shops = data.get("results", {}).get("shop", [])

    for shop in shops:
        try:
            budget_str = (shop.get("budget", {}) or {}).get("average", "0") or "0"
            price = _parse_budget(budget_str)

            photo = (shop.get("photo", {}) or {}).get("pc", {}) or {}
            image_url: Optional[str] = photo.get("m") or None

            restaurants.append(
                HotPepperRestaurant(
                    shop_id=str(shop.get("id", "")),
                    name=str(shop.get("name", ""))[:NAME_MAX_LEN],
                    price=price,
                    genre_name=str((shop.get("genre", {}) or {}).get("name", "")),
                    shop_url=str((shop.get("urls", {}) or {}).get("pc", "")),
                    image_url=image_url,
                    station_name=str(shop.get("station_name", "")),
                )
            )
        except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
            logger.warning("hotpepper_parse_shop_error", error=str(exc))
            continue

    return restaurants


# ─────────────────────────────────────────
# パブリック API
# ─────────────────────────────────────────
def search_restaurants(
    keyword: str,
    count: int = 5,
) -> list[HotPepperRestaurant]:
    """
    ホットペッパーグルメサーチ API でキーワードに一致する飲食店を取得する。

    Args:
        keyword: 検索キーワード
        count:   取得件数（上限 100）

    Returns:
        HotPepperRestaurant リスト（空リストも許容）

    Raises:
        HotPepperAPIError: HTTP 通信が MAX_RETRIES 回失敗した場合
    """
    api_key = _get_api_key()
    params: dict[str, Any] = {
        "key": api_key,
        "keyword": keyword,
        "count": count,
        "format": "json",
    }

    logger.debug("hotpepper_search", keyword=keyword, count=count)
    data = _call_with_retry(HOTPEPPER_SEARCH_URL, params)
    restaurants = _parse_response(data)

    # レートリミット遵守
    time.sleep(RATE_LIMIT_SLEEP)

    logger.debug("hotpepper_search_result", keyword=keyword, count=len(restaurants))
    return restaurants


def search_nearby_restaurants(
    lat: float,
    lng: float,
    keyword: str = "",
    range_code: int = 3,
    count: int = 5,
) -> list[HotPepperRestaurant]:
    """
    ホットペッパーグルメサーチ API で現在地周辺の飲食店を検索する。

    Args:
        lat:        緯度
        lng:        経度
        keyword:    追加キーワード（例: "カフェ"）
        range_code: 検索範囲（1: 300m, 2: 500m, 3: 1000m, 4: 2000m, 5: 3000m）
        count:      取得件数

    Returns:
        HotPepperRestaurant リスト
    """
    api_key = _get_api_key()
    params: dict[str, Any] = {
        "key": api_key,
        "lat": lat,
        "lng": lng,
        "range": range_code,
        "count": count,
        "format": "json",
        "order": 4,  # おすすめ順
    }
    if keyword:
        params["keyword"] = keyword

    logger.debug("hotpepper_nearby_search", lat=lat, lng=lng, keyword=keyword)
    data = _call_with_retry(HOTPEPPER_SEARCH_URL, params)
    restaurants = _parse_response(data)

    time.sleep(RATE_LIMIT_SLEEP)

    logger.debug("hotpepper_nearby_result", count=len(restaurants))
    return restaurants
