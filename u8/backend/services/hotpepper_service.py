"""
HotpepperService - ホットペッパーグルメAPIでレストラン検索。
エンドポイント: https://webservice.recruit.co.jp/hotpepper/gourmet/v1/
"""
import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from shared.secrets import get_secret

HOTPEPPER_URL = "https://webservice.recruit.co.jp/hotpepper/gourmet/v1/"
MAX_RETRIES = 3
BACKOFF_BASE = 1.0

# ホットペッパー予算コード
BUDGET_CODES = {
    500: "B001",
    1000: "B002",
    1500: "B003",
    2000: "B004",
    3000: "B005",
    4000: "B006",
    5000: "B008",
    7000: "B009",
    10000: "B010",
    15000: "B011",
    20000: "B012",
    30000: "B013",
}

# ジャンルコード
GENRE_CODES = {
    "居酒屋": "G001",
    "ダイニングバー": "G002",
    "創作料理": "G003",
    "和食": "G004",
    "洋食": "G005",
    "イタリアン": "G006",
    "中華": "G007",
    "焼肉": "G008",
    "韓国料理": "G017",
    "アジア料理": "G009",
    "カフェ": "G014",
    "スイーツ": "G014",
    "ラーメン": "G013",
    "カレー": "G015",
}


class HotpepperService:
    def __init__(self):
        self._api_key = os.environ.get("HOTPEPPER_API_KEY", "") or get_secret("ars/hotpepper/api-key")

    def search_restaurants(
        self,
        keyword: str = "",
        lat: float | None = None,
        lng: float | None = None,
        budget_max: int | None = None,
        genre: str | None = None,
        range_km: int = 3,
        count: int = 5,
    ) -> list[dict]:
        """ホットペッパーグルメAPIでレストランを検索する。"""
        if not self._api_key:
            return self._mock_results(keyword or genre or "カフェ")

        params = {
            "key": self._api_key,
            "format": "json",
            "count": str(min(count, 10)),
        }

        if keyword:
            params["keyword"] = keyword
        if lat and lng:
            params["lat"] = str(lat)
            params["lng"] = str(lng)
            params["range"] = str(self._km_to_range(range_km))
        if budget_max:
            code = self._get_budget_code(budget_max)
            if code:
                params["budget"] = code
        if genre:
            code = GENRE_CODES.get(genre, "")
            if code:
                params["genre"] = code

        url = f"{HOTPEPPER_URL}?{urllib.parse.urlencode(params)}"

        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ARS/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                shops = data.get("results", {}).get("shop", [])
                return [self._convert_to_candidate(shop) for shop in shops[:count]]

            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BACKOFF_BASE * (2 ** attempt))
                    continue
                break

        return self._mock_results(keyword or genre or "カフェ")

    def _convert_to_candidate(self, shop: dict) -> dict:
        """ホットペッパーAPIレスポンスをARS候補フォーマットに変換。"""
        budget = shop.get("budget", {})
        budget_avg = budget.get("average", "") if isinstance(budget, dict) else ""

        # 予算文字列から数値を推定
        price = self._parse_budget_text(budget_avg)

        return {
            "name": shop.get("name", ""),
            "price": price,
            "budget_text": budget_avg,
            "url": shop.get("urls", {}).get("pc", ""),
            "image": shop.get("photo", {}).get("mobile", {}).get("l", ""),
            "shop": shop.get("name", ""),
            "genre": shop.get("genre", {}).get("name", ""),
            "address": shop.get("address", ""),
            "access": shop.get("mobile_access", shop.get("access", "")),
            "source": "hotpepper",
            "type": "restaurant",
        }

    def _get_budget_code(self, max_price: int) -> str:
        """金額から最適な予算コードを返す。"""
        for threshold, code in sorted(BUDGET_CODES.items()):
            if max_price <= threshold:
                return code
        return "B013"

    def _km_to_range(self, km: int) -> int:
        """kmをホットペッパーのrangeパラメータに変換。"""
        if km <= 1:
            return 2  # 500m
        elif km <= 2:
            return 3  # 1000m
        elif km <= 3:
            return 4  # 2000m
        else:
            return 5  # 3000m

    def _parse_budget_text(self, text: str) -> int:
        """予算テキスト（例: '2001～3000円'）から平均値を推定。"""
        if not text:
            return 0
        import re
        numbers = re.findall(r"\d+", text.replace(",", ""))
        if len(numbers) >= 2:
            return (int(numbers[0]) + int(numbers[1])) // 2
        elif numbers:
            return int(numbers[0])
        return 0

    def _mock_results(self, keyword: str) -> list[dict]:
        """APIキーなし時のモック結果。"""
        return [
            {
                "name": f"森のカフェ ({keyword}おすすめ)",
                "price": 800,
                "budget_text": "〜1000円",
                "url": "",
                "image": "",
                "shop": "森のカフェ",
                "genre": "カフェ",
                "address": "東京都渋谷区",
                "access": "駅から徒歩5分",
                "source": "hotpepper",
                "type": "restaurant",
            },
            {
                "name": f"ほっこり茶房 ({keyword})",
                "price": 1200,
                "budget_text": "1001〜1500円",
                "url": "",
                "image": "",
                "shop": "ほっこり茶房",
                "genre": "カフェ",
                "address": "東京都新宿区",
                "access": "駅から徒歩3分",
                "source": "hotpepper",
                "type": "restaurant",
            },
            {
                "name": f"やすらぎダイニング ({keyword})",
                "price": 2500,
                "budget_text": "2001〜3000円",
                "url": "",
                "image": "",
                "shop": "やすらぎダイニング",
                "genre": "和食",
                "address": "東京都目黒区",
                "access": "駅から徒歩7分",
                "source": "hotpepper",
                "type": "restaurant",
            },
        ]
