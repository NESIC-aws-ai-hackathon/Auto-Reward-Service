"""
位置情報検索サービス（OpenStreetMap Overpass API）

USE_MOCK_LOCATION=true の場合はモックデータを返す。
本番では OpenStreetMap Overpass API を使用して実際の周辺スポットを検索する。
APIキー不要・無料。
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
import urllib.parse
from urllib.error import URLError

from utils.logger import get_logger

logger = get_logger(__name__)

USE_MOCK_LOCATION = os.environ.get("USE_MOCK_LOCATION", "false") == "true"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT_SEC = 8   # Overpass クエリのタイムアウト

# lane_type → OSM タグのリスト（(key, value) のリスト）
LANE_TYPE_TO_OSM_TAGS: dict[str, list[tuple[str, str]]] = {
    "CAFE_REBOOT": [
        ("amenity", "cafe"),
        ("amenity", "bakery"),
        ("shop", "bakery"),
    ],
    "CONVENIENCE_RECOVERY": [
        ("shop", "convenience"),
    ],
    "SELF_COOKING_ESCAPE": [
        ("amenity", "restaurant"),
        ("amenity", "fast_food"),
        ("amenity", "ramen_restaurant"),
    ],
    "LOW_COST_RECOVERY": [
        ("shop", "convenience"),
        ("amenity", "pharmacy"),
        ("shop", "drugstore"),
    ],
    "RICHER_ESCAPE": [
        ("amenity", "restaurant"),
        ("shop", "mall"),
    ],
}


def search_nearby_places(
    lat: float,
    lng: float,
    lane_type: str,
    radius_m: int = 800,
) -> list[dict]:
    """現在地周辺のスポットを検索する。"""
    if USE_MOCK_LOCATION:
        return _mock_places(lat, lng, lane_type)

    try:
        return _search_overpass(lat, lng, lane_type, radius_m)
    except Exception as e:
        logger.warning("overpass_fallback_to_mock", error=str(e))
        return _mock_places(lat, lng, lane_type)


def _search_overpass(lat: float, lng: float, lane_type: str, radius_m: int) -> list[dict]:
    """OpenStreetMap Overpass API で周辺スポットを検索する。"""
    tags = LANE_TYPE_TO_OSM_TAGS.get(lane_type, [("amenity", "restaurant")])

    # Overpass QL クエリを構築
    node_queries = "\n".join(
        f'  node["{k}"="{v}"](around:{radius_m},{lat},{lng});'
        for k, v in tags
    )
    query = (
        f"[out:json][timeout:{OVERPASS_TIMEOUT_SEC}];\n"
        f"(\n{node_queries}\n);\n"
        f"out body 15;"
    )

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(OVERPASS_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "AutoRewardService/1.0")

    with urllib.request.urlopen(req, timeout=OVERPASS_TIMEOUT_SEC + 2) as resp:
        raw = json.loads(resp.read())

    results = []
    for el in raw.get("elements", []):
        tags_el = el.get("tags", {})
        name = tags_el.get("name") or tags_el.get("name:ja")
        if not name:
            continue  # 名前のないスポットはスキップ
        el_lat = el.get("lat", lat)
        el_lng = el.get("lon", lng)
        dist = _haversine(lat, lng, el_lat, el_lng)
        results.append({
            "name": name,
            "category": tags_el.get("amenity") or tags_el.get("shop") or "",
            "lat": el_lat,
            "lng": el_lng,
            "address": _build_address(tags_el),
            "distance_m": dist,
        })

    # 距離順でソートし上位5件
    results.sort(key=lambda x: x["distance_m"])
    return results[:5]


def _build_address(tags: dict) -> str:
    """OSM タグから住所文字列を生成する。"""
    parts = []
    for k in ("addr:city", "addr:suburb", "addr:street", "addr:housenumber"):
        v = tags.get(k)
        if v:
            parts.append(v)
    return "".join(parts) if parts else ""


def _mock_places(lat: float, lng: float, lane_type: str) -> list[dict]:
    """モックデータ: USE_MOCK_LOCATION=true またはエラー時のフォールバック。
    lat/lng を使って微妙に座標をずらすことで、場所によって異なるように見せる。"""
    seed = (round(lat, 2) * 100 + round(lng, 2) * 10) % 10
    offset = int(seed)

    mock_data: dict[str, list[dict]] = {
        "CAFE_REBOOT": [
            {"name": "駅前カフェ", "category": "cafe", "distance_m": 180 + offset * 5},
            {"name": "タリーズコーヒー", "category": "cafe", "distance_m": 350 + offset * 7},
            {"name": "コメダ珈琲店", "category": "cafe", "distance_m": 520 + offset * 3},
        ],
        "CONVENIENCE_RECOVERY": [
            {"name": "セブンイレブン", "category": "convenience", "distance_m": 80 + offset * 3},
            {"name": "ファミリーマート", "category": "convenience", "distance_m": 200 + offset * 8},
            {"name": "ローソン", "category": "convenience", "distance_m": 310 + offset * 4},
        ],
        "SELF_COOKING_ESCAPE": [
            {"name": "一蘭", "category": "restaurant", "distance_m": 400 + offset * 6},
            {"name": "松屋", "category": "fast_food", "distance_m": 150 + offset * 5},
            {"name": "丸亀製麺", "category": "restaurant", "distance_m": 600 + offset * 2},
        ],
        "LOW_COST_RECOVERY": [
            {"name": "ローソン", "category": "convenience", "distance_m": 100 + offset * 4},
            {"name": "マツモトキヨシ", "category": "pharmacy", "distance_m": 250 + offset * 6},
        ],
        "RICHER_ESCAPE": [
            {"name": "イタリアンダイニング ROSSO", "category": "restaurant", "distance_m": 500 + offset * 7},
            {"name": "焼肉きんぐ", "category": "restaurant", "distance_m": 600 + offset * 5},
        ],
    }
    places = mock_data.get(lane_type, [])
    result = []
    for p in places:
        result.append({
            **p,
            "lat": lat + 0.001 * (1 + offset * 0.1),
            "lng": lng + 0.001 * (1 + offset * 0.1),
            "address": "",
        })
    return result


def geocode_text(query: str) -> dict | None:
    """
    テキスト（駅名・エリア名）から緯度経度を取得する。
    OpenStreetMap Nominatim API を使用（APIキー不要、無料）。

    Returns:
        {"lat": float, "lng": float, "display_name": str} or None
    """
    safe_query = query.strip()[:100]
    if not safe_query:
        return None

    # 日本国内に絞る
    params = urllib.parse.urlencode({
        "q": safe_query,
        "format": "json",
        "limit": "1",
        "countrycodes": "jp",
        "accept-language": "ja",
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "AutoRewardService/1.0")

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read())
            if not results:
                return None
            first = results[0]
            return {
                "lat": float(first["lat"]),
                "lng": float(first["lon"]),
                "display_name": first.get("display_name", safe_query),
            }
    except (URLError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("geocode_failed", query=safe_query, error=str(e))
        return None


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """2点間の距離をメートルで計算（ハーバーサイン公式）。"""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return int(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))
