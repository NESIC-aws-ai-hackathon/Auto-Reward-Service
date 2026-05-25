"""
WishlistService - Amazon公開ほしい物リスト連携。
ユーザーが登録した公開URL からアイテムを取得し、ご褒美候補として保存する。
"""
import hashlib
import json
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

from shared.data_access import DataAccess


class WishlistService:
    def __init__(self, da: DataAccess | None = None):
        self.da = da or DataAccess()

    def register_url(self, user_id: str, wishlist_url: str, display_name: str = "") -> dict:
        """公開ほしい物リストURLを登録する。"""
        # URL検証
        if not self._validate_url(wishlist_url):
            return {"error": "invalid_url", "message": "有効なAmazonほしい物リストURLを入力してください"}

        url_hash = hashlib.sha256(wishlist_url.encode()).hexdigest()[:12]
        now = datetime.now(timezone.utc).isoformat()

        source = {
            "wishlist_source_id": url_hash,
            "user_id": user_id,
            "source_type": "AMAZON_PUBLIC_WISHLIST",
            "wishlist_url": wishlist_url,
            "display_name": display_name or "Amazonほしい物リスト",
            "status": "ACTIVE",
            "last_synced_at": None,
            "created_at": now,
            "updated_at": now,
        }

        self.da.put_item(f"USER#{user_id}", f"WISHLIST_SOURCE#{url_hash}", source)
        return {"success": True, "source_id": url_hash}

    def sync_wishlist(self, user_id: str, source_id: str | None = None) -> dict:
        """ほしい物リストを同期（HTMLフェッチ→アイテム保存）。"""
        # ソース取得
        if source_id:
            source = self.da.get_item(f"USER#{user_id}", f"WISHLIST_SOURCE#{source_id}")
            sources = [source] if source else []
        else:
            sources = self.da.query_by_prefix(f"USER#{user_id}", "WISHLIST_SOURCE#", limit=10)

        if not sources:
            return {"error": "no_source", "message": "ほしい物リストが登録されていません"}

        total_items = []
        for src in sources:
            url = src.get("wishlist_url", "")
            sid = src.get("wishlist_source_id", "")
            if not url:
                continue

            items = self._fetch_and_parse(url)
            now = datetime.now(timezone.utc).isoformat()

            # ソースの同期日時更新
            self.da.update_item(f"USER#{user_id}", f"WISHLIST_SOURCE#{sid}", {
                "last_synced_at": now,
                "updated_at": now,
                "status": "ACTIVE" if items else "SYNC_FAILED",
            })

            # アイテム保存
            for item in items:
                item_id = hashlib.sha256(item["product_url"].encode()).hexdigest()[:12]
                existing = self.da.get_item(f"USER#{user_id}", f"WISHLIST_ITEM#{item_id}")

                if existing:
                    # 既存アイテム更新（last_seen更新、欲望熟成日数計算）
                    first_seen = existing.get("first_seen_at", now)
                    days = (datetime.fromisoformat(now.replace("Z", "+00:00")) -
                            datetime.fromisoformat(first_seen.replace("Z", "+00:00"))).days
                    self.da.update_item(f"USER#{user_id}", f"WISHLIST_ITEM#{item_id}", {
                        "last_seen_at": now,
                        "desire_aging_days": days,
                        "price": item.get("price", existing.get("price")),
                        "updated_at": now,
                    })
                else:
                    # 新規アイテム
                    self.da.put_item(f"USER#{user_id}", f"WISHLIST_ITEM#{item_id}", {
                        "wishlist_item_id": item_id,
                        "wishlist_source_id": sid,
                        "user_id": user_id,
                        "product_title": item.get("title", ""),
                        "product_url": item.get("product_url", ""),
                        "product_image_url": item.get("image_url", ""),
                        "price": item.get("price"),
                        "category": item.get("category", ""),
                        "status": "ACTIVE",
                        "desire_aging_days": 0,
                        "first_seen_at": now,
                        "last_seen_at": now,
                        "created_at": now,
                        "updated_at": now,
                    })

                total_items.append({**item, "item_id": item_id})

        return {"success": True, "items_synced": len(total_items), "items": total_items}

    def get_items(self, user_id: str, status: str = "ACTIVE") -> list[dict]:
        """ユーザーのほしい物リストアイテムを取得。"""
        items = self.da.query_by_prefix(f"USER#{user_id}", "WISHLIST_ITEM#", limit=50)
        if status:
            items = [i for i in items if i.get("status") == status]
        return items

    def get_reward_candidates(self, user_id: str, max_price: int | None = None) -> list[dict]:
        """ご褒美候補としてほしい物リストアイテムを返す。"""
        items = self.get_items(user_id, status="ACTIVE")

        candidates = []
        for item in items:
            price = item.get("price")
            if max_price and price and price > max_price:
                continue

            candidates.append({
                "name": item.get("product_title", ""),
                "price": price or 0,
                "url": item.get("product_url", ""),
                "image": item.get("product_image_url", ""),
                "shop": "Amazon",
                "source": "amazon_wishlist",
                "type": "product",
                "desire_aging_days": item.get("desire_aging_days", 0),
                "item_id": item.get("wishlist_item_id", ""),
            })

        # 欲望熟成日数が長い順（衝動買いでない証拠）
        candidates.sort(key=lambda x: x.get("desire_aging_days", 0), reverse=True)
        return candidates

    def update_item_status(self, user_id: str, item_id: str, status: str) -> dict:
        """アイテムのステータスを更新（PURCHASED, DECLINED等）。"""
        now = datetime.now(timezone.utc).isoformat()
        self.da.update_item(f"USER#{user_id}", f"WISHLIST_ITEM#{item_id}", {
            "status": status,
            "updated_at": now,
        })
        return {"success": True}

    def get_sources(self, user_id: str) -> list[dict]:
        """登録済みのほしい物リストソースを取得。"""
        return self.da.query_by_prefix(f"USER#{user_id}", "WISHLIST_SOURCE#", limit=10)

    def delete_source(self, user_id: str, source_id: str) -> dict:
        """ほしい物リストソースを削除。"""
        self.da.delete_item(f"USER#{user_id}", f"WISHLIST_SOURCE#{source_id}")
        return {"success": True}

    def _validate_url(self, url: str) -> bool:
        """Amazon公開ほしい物リストURLの検証。"""
        patterns = [
            r"https?://(www\.)?amazon\.co\.jp/.*/wishlist/.*",
            r"https?://(www\.)?amazon\.co\.jp/hz/wishlist/ls/[A-Z0-9]+",
            r"https?://(www\.)?amazon\.co\.jp/gp/registry/wishlist/[A-Z0-9]+",
        ]
        return any(re.match(p, url) for p in patterns)

    def _fetch_and_parse(self, url: str) -> list[dict]:
        """公開ほしい物リストHTMLをフェッチしてアイテムを抽出。"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                "Accept-Language": "ja-JP,ja;q=0.9",
                "Accept": "text/html,application/xhtml+xml",
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            return self._parse_wishlist_html(html)

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"Wishlist fetch failed: {e}")
            return []

    def _parse_wishlist_html(self, html: str) -> list[dict]:
        """Amazon公開ほしい物リストのHTMLからアイテム情報を抽出。"""
        items = []

        # data-itemid属性でアイテムブロックを検出
        item_blocks = re.findall(
            r'data-itemid="([^"]+)"[^>]*>(.+?)(?=data-itemid="|$)',
            html,
            re.DOTALL,
        )

        if not item_blocks:
            # 別パターン: id="item_" プレフィックス
            item_blocks = re.findall(
                r'id="item[_-]([^"]+)"[^>]*>(.+?)(?=id="item[_-]|$)',
                html,
                re.DOTALL,
            )

        for item_id, block in item_blocks[:30]:
            title = self._extract_title(block)
            price = self._extract_price(block)
            product_url = self._extract_product_url(block)
            image_url = self._extract_image_url(block)

            if title and product_url:
                items.append({
                    "title": title[:200],
                    "price": price,
                    "product_url": product_url,
                    "image_url": image_url,
                })

        return items

    def _extract_title(self, block: str) -> str:
        """タイトル抽出。"""
        # aria-label or title attr in link
        m = re.search(r'<a[^>]+(?:title|aria-label)="([^"]+)"', block)
        if m:
            return m.group(1).strip()
        # h2/h3 内テキスト
        m = re.search(r'<h[23][^>]*>([^<]+)</h[23]>', block)
        if m:
            return m.group(1).strip()
        # alt属性
        m = re.search(r'alt="([^"]{5,})"', block)
        if m:
            return m.group(1).strip()
        return ""

    def _extract_price(self, block: str) -> int | None:
        """価格抽出。"""
        # ¥1,234 or ￥1234 パターン
        m = re.search(r'[¥￥]\s*([\d,]+)', block)
        if m:
            return int(m.group(1).replace(",", ""))
        # data-price属性
        m = re.search(r'data-price="(\d+)"', block)
        if m:
            return int(m.group(1))
        return None

    def _extract_product_url(self, block: str) -> str:
        """商品URL抽出。"""
        m = re.search(r'href="(/dp/[^"]+|/gp/product/[^"]+)"', block)
        if m:
            path = m.group(1).split("?")[0]  # クエリパラメータ除去
            return f"https://www.amazon.co.jp{path}"
        m = re.search(r'href="(https://www\.amazon\.co\.jp/[^"]*(?:/dp/|/gp/product/)[^"]*)"', block)
        if m:
            return m.group(1).split("?")[0]
        return ""

    def _extract_image_url(self, block: str) -> str:
        """画像URL抽出。"""
        m = re.search(r'src="(https://[^"]*images-(?:na|fe|amazon)[^"]+)"', block)
        if m:
            return m.group(1)
        m = re.search(r'src="(https://m\.media-amazon\.com/images/[^"]+)"', block)
        if m:
            return m.group(1)
        return ""
