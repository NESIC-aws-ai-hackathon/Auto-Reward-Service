"""
Nova Act サービス — サーバーサイドでAmazonカートに商品を追加する

仕組み:
  1. ユーザーがAmazonにログインした際のセッションCookie（session-id等）を
     DynamoDB に保存
  2. ふれまーるちゃんが商品を選んだ時、保存したCookieを使って
     サーバーサイドからAmazonのカート追加エンドポイントにリクエスト
  3. ユーザーのAmazonカートに実際に商品が入る

これにより「勝手にカートに入っている」体験を実現する。
"""
from __future__ import annotations

import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional
from http.cookiejar import CookieJar, Cookie
import time

from utils.logger import get_logger

logger = get_logger(__name__)

# Amazon エンドポイント
AMAZON_CART_ADD_URL = "https://www.amazon.co.jp/gp/aws/cart/add.html"
AMAZON_PRODUCT_URL = "https://www.amazon.co.jp/dp/{asin}"

# ブラウザを模倣するヘッダー
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def add_to_cart_server_side(asin: str, cookies_dict: dict) -> dict:
    """
    サーバーサイドからAmazonのカートに商品を追加する。
    
    ユーザーのAmazonセッションCookieを使って、gp/aws/cart/add.html に
    GETリクエストを送信。成功すればユーザーのカートに商品が入る。
    
    Args:
        asin: 追加する商品のASIN
        cookies_dict: ユーザーのAmazon Cookie (session-id, ubid-acbjp 等)
    
    Returns:
        {"success": bool, "message": str, "cart_url": str}
    """
    if not asin:
        return {"success": False, "message": "ASINが指定されていません"}
    if not cookies_dict:
        return {"success": False, "message": "Amazonセッションが保存されていません。先にAmazonにログインしてください。"}

    # カート追加URL
    params = urllib.parse.urlencode({
        "ASIN.1": asin,
        "Quantity.1": "1",
    })
    url = f"{AMAZON_CART_ADD_URL}?{params}"

    # Cookie文字列を構築
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies_dict.items())

    # リクエスト
    headers = {**BROWSER_HEADERS, "Cookie": cookie_str}
    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        # リダイレクトを追跡
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        resp = opener.open(req, timeout=10)
        body = resp.read().decode("utf-8", errors="replace")
        status = resp.status

        logger.info("nova_act_cart_add_response",
                    status=status,
                    url=resp.url,
                    body_length=len(body),
                    has_cart_content="カート" in body or "Cart" in body)

        # 成功判定:
        # - ステータス200
        # - レスポンスに "カートに追加されました" or "Added to Cart" or カート内容が表示
        success_indicators = [
            "カートに追加されました",
            "カートの小計",
            "Added to Cart",
            "Subtotal",
            "proceed-to-checkout",
            "カートに入っています",
            "sc-subtotal",
        ]
        is_success = any(indicator in body for indicator in success_indicators)

        # 失敗判定
        failure_indicators = [
            "カートは空です",
            "Cart is empty",
            "現在お取り扱いできません",
            "この商品は現在お取り扱いできません",
        ]
        is_failure = any(indicator in body for indicator in failure_indicators)

        if is_success and not is_failure:
            logger.info("nova_act_cart_add_success", asin=asin)
            return {
                "success": True,
                "message": "カートに追加しました！",
                "cart_url": "https://www.amazon.co.jp/gp/cart/view.html",
            }
        elif is_failure:
            logger.warning("nova_act_cart_add_failed_empty", asin=asin)
            return {
                "success": False,
                "message": "カートに追加できませんでした。商品が取り扱い終了か、セッションが切れている可能性があります。",
                "needs_relogin": True,
            }
        else:
            # 判定できない場合（リダイレクトでログインページに飛ばされた等）
            if "ap/signin" in (resp.url or "") or "signIn" in body:
                logger.warning("nova_act_session_expired", asin=asin)
                return {
                    "success": False,
                    "message": "Amazonセッションが期限切れです。再ログインしてください。",
                    "needs_relogin": True,
                }
            # それ以外 - 一応成功扱い（リダイレクト先がカートページの場合等）
            logger.info("nova_act_cart_add_uncertain", asin=asin, final_url=resp.url)
            return {
                "success": True,
                "message": "カートに追加リクエストを送信しました",
                "cart_url": "https://www.amazon.co.jp/gp/cart/view.html",
            }

    except urllib.error.HTTPError as e:
        logger.error("nova_act_http_error", status=e.code, asin=asin)
        return {"success": False, "message": f"Amazon接続エラー (HTTP {e.code})"}
    except urllib.error.URLError as e:
        logger.error("nova_act_url_error", error=str(e), asin=asin)
        return {"success": False, "message": "Amazon接続エラー"}
    except Exception as e:
        logger.error("nova_act_unexpected_error", error=str(e), asin=asin)
        return {"success": False, "message": f"予期しないエラー: {str(e)}"}


def save_amazon_cookies(user_id: str, cookies_dict: dict, ddb) -> bool:
    """ユーザーのAmazon CookieをDynamoDBに保存する"""
    try:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        ddb.put_item(f"USER#{user_id}", "AMAZON_SESSION", {
            "entityType": "AMAZON_SESSION",
            "amazon_linked": True,
            "cookies": json.dumps(cookies_dict),
            "updated_at": ts,
            "linked_at": ts,
        })
        logger.info("amazon_cookies_saved", user_id=user_id[:10])
        return True
    except Exception as e:
        logger.error("amazon_cookies_save_failed", error=str(e))
        return False


def get_amazon_cookies(user_id: str, ddb) -> Optional[dict]:
    """ユーザーのAmazon CookieをDynamoDBから取得する"""
    try:
        item = ddb.get_item(f"USER#{user_id}", "AMAZON_SESSION")
        if not item or not item.get("cookies"):
            return None
        return json.loads(item["cookies"])
    except Exception as e:
        logger.error("amazon_cookies_get_failed", error=str(e))
        return None
