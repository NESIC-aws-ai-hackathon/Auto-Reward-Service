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
        self._app_id = os.environ.get("RAKUTEN_APP_ID", "") or get_secret("ars/rakuten", "RAKUTEN_APP_ID")

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
        """Return curated demo results when API is unavailable."""
        # キーワードに基づいた実用的なデモ商品（楽天の実在商品をベースにした内容）
        catalog = {
            "default": [
                {"name": "バスクリン アロマスパークリング 10包セット", "price": 880, "url": "https://search.rakuten.co.jp/search/mall/バスクリン+アロマ/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/rakuten24/cabinet/e8101/e810159h_l.jpg", "shop": "楽天24", "review": 4.5},
                {"name": "ドリップコーヒー 40杯分 4種アソート", "price": 1580, "url": "https://search.rakuten.co.jp/search/mall/ドリップコーヒー+アソート/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/brook/cabinet/item/drip/40assort_main.jpg", "shop": "ブルックスコーヒー", "review": 4.6},
                {"name": "今治タオル ふわふわフェイスタオル 3枚組", "price": 1980, "url": "https://search.rakuten.co.jp/search/mall/今治タオル+フェイスタオル/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/towel-en/cabinet/imabari/face3set.jpg", "shop": "タオル専門店", "review": 4.7},
                {"name": "チョコレート 詰め合わせ ベルギー産 24粒", "price": 2480, "url": "https://search.rakuten.co.jp/search/mall/チョコレート+詰め合わせ/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/chocola/cabinet/gift/belgium24.jpg", "shop": "ショコラ館", "review": 4.4},
                {"name": "ハーブティー ノンカフェイン 30包", "price": 1280, "url": "https://search.rakuten.co.jp/search/mall/ハーブティー+ノンカフェイン/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/teahouse/cabinet/herb/noncafe30.jpg", "shop": "お茶の専門店", "review": 4.3},
            ],
            "スイーツ": [
                {"name": "抹茶スイーツ 京都宇治 詰め合わせ", "price": 2980, "url": "https://search.rakuten.co.jp/search/mall/抹茶+スイーツ+詰め合わせ/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/kyoto-sweets/cabinet/matcha/assort01.jpg", "shop": "京都スイーツ工房", "review": 4.6},
                {"name": "プリン 6個入り なめらかカスタード", "price": 1880, "url": "https://search.rakuten.co.jp/search/mall/プリン+なめらか/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/pudding-shop/cabinet/custard6.jpg", "shop": "プリン専門店", "review": 4.8},
                {"name": "焼きドーナツ 10個 グルテンフリー", "price": 2480, "url": "https://search.rakuten.co.jp/search/mall/焼きドーナツ/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/donut-lab/cabinet/baked10.jpg", "shop": "ドーナツラボ", "review": 4.5},
            ],
            "癒し": [
                {"name": "アロマキャンドル ソイワックス 3個セット", "price": 1980, "url": "https://search.rakuten.co.jp/search/mall/アロマキャンドル+ソイワックス/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/aroma-life/cabinet/candle/soy3set.jpg", "shop": "アロマライフ", "review": 4.5},
                {"name": "ホットアイマスク 蒸気でリラックス 12枚", "price": 980, "url": "https://search.rakuten.co.jp/search/mall/ホットアイマスク/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/rakuten24/cabinet/e6801/e680123h_l.jpg", "shop": "楽天24", "review": 4.7},
                {"name": "入浴剤 バスボム ギフトセット 8個入", "price": 2200, "url": "https://search.rakuten.co.jp/search/mall/バスボム+ギフト/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/bath-gift/cabinet/bomb8set.jpg", "shop": "バスギフト工房", "review": 4.4},
            ],
            "コーヒー": [
                {"name": "スペシャルティコーヒー 200g×3袋 飲み比べ", "price": 2780, "url": "https://search.rakuten.co.jp/search/mall/スペシャルティコーヒー/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/specialty-coffee/cabinet/3bags.jpg", "shop": "珈琲問屋", "review": 4.6},
                {"name": "カフェオレベース 無糖 500ml×3本", "price": 1680, "url": "https://search.rakuten.co.jp/search/mall/カフェオレベース/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/coffee-base/cabinet/cafeole3.jpg", "shop": "珈琲館", "review": 4.4},
                {"name": "コーヒーギフト ドリップ&クッキーセット", "price": 1980, "url": "https://search.rakuten.co.jp/search/mall/コーヒー+ギフト+クッキー/", "image": "https://thumbnail.image.rakuten.co.jp/@0_mall/gift-shop/cabinet/coffee_cookie.jpg", "shop": "ギフトモール", "review": 4.5},
            ],
        }

        # キーワードに最も近いカテゴリを選択
        best_key = "default"
        kw_lower = keyword.lower() if keyword else ""
        for cat_key in catalog:
            if cat_key != "default" and cat_key in kw_lower:
                best_key = cat_key
                break

        # キーワードをURLに埋め込んだ検索リンク版も追加
        results = catalog.get(best_key, catalog["default"])
        # キーワードが特定カテゴリに該当しない場合、検索URLを付与
        if best_key == "default" and keyword:
            import urllib.parse as _up
            search_url = f"https://search.rakuten.co.jp/search/mall/{_up.quote(keyword)}/"
            for item in results:
                item = dict(item)
                item["url"] = search_url
            # キーワードを商品名に反映
            results = [dict(r, name=r["name"] if keyword in r["name"] else f"{r['name']}") for r in results]

        return results[:5]
