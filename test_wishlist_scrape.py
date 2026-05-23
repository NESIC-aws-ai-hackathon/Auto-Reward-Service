"""Quick test for Amazon wishlist scraping - standalone"""
import re
import sys
sys.path.insert(0, "layer/python")

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

url = "https://www.amazon.co.jp/hz/wishlist/ls/1R5XZEM8OKD7F"
resp = requests.get(url, headers=HEADERS, timeout=15)
print(f"Status: {resp.status_code}, Length: {len(resp.text)}")

soup = BeautifulSoup(resp.text, "html.parser")
g_items = soup.find("ul", id="g-items")
if not g_items:
    print("ERROR: g-items not found")
    sys.exit(1)

items = g_items.find_all("li", attrs={"data-itemid": True})
print(f"Items found: {len(items)}")

for item in items:
    item_id = item.get("data-itemid", "")
    price_str = item.get("data-price", "")
    name_link = item.find("a", id=lambda x: x and "itemName_" in str(x))
    if name_link:
        title = name_link.get_text(strip=True)
        href = name_link.get("href", "")
        if href and not href.startswith("http"):
            href = f"https://www.amazon.co.jp{href}"
    else:
        title = "Unknown"
        href = ""
    
    img = item.find("img")
    image_url = img.get("src", "") if img else ""
    if image_url:
        image_url = re.sub(r"_SS\d+_", "_SS300_", image_url)
    
    price = None
    if price_str:
        try:
            price = int(float(price_str))
        except (ValueError, TypeError):
            pass
    
    print(f"  - {title[:60]}")
    print(f"    Price: {price}")
    print(f"    URL: {href[:80]}")
    print(f"    Image: {image_url[:80]}")
    print()
