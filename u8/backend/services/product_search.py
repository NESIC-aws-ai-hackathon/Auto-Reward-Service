"""
ProductSearchService - Rakuten product search for the U8 PWA.
Simplified version of the original layer/python/services/rakuten_service.py.
"""
import os
import time
import json
import urllib.request
import urllib.parse
import urllib.error
from shared.config import get_config
from shared.secrets import get_secret

RAKUTEN_SEARCH_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
MAX_RETRIES = 3
BACKOFF_BASE = 1.0


class ProductSearchService:
    def __init__(self):
        self.config = get_config()
        self._app_id = os.environ.get("RAKUTEN_APP_ID", "") or get_secret("ars/rakuten", "app_id")

    def search(self, keyword: str = "", category: str = "", max_price: str = "") -> list[dict]:
        """Search Rakuten Ichiba for products."""
        if not self._app_id:
            # Return mock data if no API key configured
            return self._mock_results(keyword or category)

        params = {
            "applicationId": self._app_id,
            "format": "json",
            "hits": "10",
            "sort": "+itemPrice",
        }

        if keyword:
            params["keyword"] = keyword
        if category:
            genre = self._category_to_genre(category)
            if genre:
                params["genreId"] = genre
        if max_price:
            params["maxPrice"] = max_price

        url = f"{RAKUTEN_SEARCH_URL}?{urllib.parse.urlencode(params)}"

        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ARS/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                items = data.get("Items", [])
                results = []
                for item_wrap in items[:10]:
                    item = item_wrap.get("Item", item_wrap)
                    image_urls = item.get("mediumImageUrls", [])
                    image = ""
                    if image_urls and isinstance(image_urls, list) and len(image_urls) > 0:
                        img_item = image_urls[0]
                        image = img_item.get("imageUrl", "") if isinstance(img_item, dict) else str(img_item)

                    results.append({
                        "name": item.get("itemName", "")[:100],
                        "price": item.get("itemPrice", 0),
                        "url": item.get("itemUrl", ""),
                        "image": image,
                        "shop": item.get("shopName", ""),
                        "review": item.get("reviewAverage", 0),
                    })

                return results

            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BACKOFF_BASE * (2 ** attempt))
                    continue
                break

        return self._mock_results(keyword or category)

    def _category_to_genre(self, category: str) -> str:
        """Map friendly category names to Rakuten genre IDs."""
        mapping = {
            "スイーツ": "100227",
            "お菓子": "100227",
            "カフェ": "101240",
            "コーヒー": "310890",
            "紅茶": "310891",
            "入浴剤": "215783",
            "アロマ": "503371",
            "文房具": "215129",
            "本": "200162",
            "マンガ": "200348",
            "ゲーム": "101205",
            "コスメ": "100939",
        }
        return mapping.get(category, "")

    def _mock_results(self, keyword: str) -> list[dict]:
        """Return mock results when API is unavailable."""
        mock_items = [
            {"name": f"【おすすめ】{keyword}セット", "price": 1280, "url": "", "image": "", "shop": "森のお店", "review": 4.5},
            {"name": f"{keyword} ギフトボックス", "price": 2480, "url": "", "image": "", "shop": "ほっこり堂", "review": 4.2},
            {"name": f"プチ贅沢 {keyword}", "price": 980, "url": "", "image": "", "shop": "リラックス商店", "review": 4.8},
        ]
        return mock_items
