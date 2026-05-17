"""
LINE リッチメニュー自動登録スクリプト

使い方:
  pip install requests
  LINE_CHANNEL_ACCESS_TOKEN=xxx python scripts/register_rich_menu.py

リッチメニューを LINE に登録し、全ユーザーのデフォルトに設定します。
"""
from __future__ import annotations

import os
import sys
import json
import requests
import urllib3

# 社内プロキシ環境では SSL 証明書検証をスキップ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_VERIFY = False

# ─────────────────────────────────────────
# リッチメニュー定義（6ボタン、2行3列）
# ─────────────────────────────────────────
RICH_MENU = {
    "size": {"width": 2500, "height": 1686},
    "selected": True,
    "name": "リワードちゃんメニュー",
    "chatBarText": "メニューを開く",
    "areas": [
        # 1行目: ダッシュボード / 話す / おすすめ
        {
            "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
            "action": {
                "type": "uri",
                "label": "📊 ダッシュボード",
                "uri": os.environ.get("LIFF_DASHBOARD_URL", "https://liff.line.me/2010106872-9t0gN1D6"),
            },
        },
        {
            "bounds": {"x": 833, "y": 0, "width": 834, "height": 843},
            "action": {
                "type": "postback",
                "label": "🎀 話す",
                "data": "action=start_talk",
                "displayText": "話しかけてみる",
            },
        },
        {
            "bounds": {"x": 1667, "y": 0, "width": 833, "height": 843},
            "action": {
                "type": "postback",
                "label": "🎁 おすすめ",
                "data": "action=start_recommend",
                "displayText": "おすすめしてもらう",
            },
        },
        # 2行目: 支出を記録 / 今月の残り / 設定
        {
            "bounds": {"x": 0, "y": 843, "width": 833, "height": 843},
            "action": {
                "type": "postback",
                "label": "📝 支出を記録",
                "data": "action=quick_expense",
                "displayText": "支出を記録する",
            },
        },
        {
            "bounds": {"x": 833, "y": 843, "width": 834, "height": 843},
            "action": {
                "type": "postback",
                "label": "📋 今月の残り",
                "data": "action=monthly_summary",
                "displayText": "今月のレポートを見る",
            },
        },
        {
            "bounds": {"x": 1667, "y": 843, "width": 833, "height": 843},
            "action": {
                "type": "uri",
                "label": "⚙️ 設定",
                "uri": os.environ.get("LIFF_ONBOARDING_URL", "https://liff.line.me/2010106872-9t0gN1D6/onboarding"),
            },
        },
    ],
}


def get_token() -> str:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        print("ERROR: LINE_CHANNEL_ACCESS_TOKEN が設定されていません", file=sys.stderr)
        print("export LINE_CHANNEL_ACCESS_TOKEN=<your_token>", file=sys.stderr)
        sys.exit(1)
    return token


def create_rich_menu(token: str) -> str:
    """リッチメニューを作成し rich_menu_id を返す"""
    resp = requests.post(
        "https://api.line.me/v2/bot/richmenu",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=RICH_MENU,
        timeout=15,
        verify=_VERIFY,
    )
    if not resp.ok:
        print(f"❌ リッチメニュー作成失敗 HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
    resp.raise_for_status()
    rich_menu_id = resp.json()["richMenuId"]
    print(f"✅ リッチメニュー作成: {rich_menu_id}")
    return rich_menu_id


def upload_image(token: str, rich_menu_id: str, image_path: str) -> None:
    """リッチメニュー画像をアップロードする（オプション）"""
    if not os.path.exists(image_path):
        print(f"⚠️ 画像ファイルが見つかりません: {image_path} — スキップします")
        return
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    content_type = "image/png" if image_path.endswith(".png") else "image/jpeg"
    resp = requests.post(
        f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
        headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
        data=img_bytes,
        timeout=30,
        verify=_VERIFY,
    )
    resp.raise_for_status()
    print(f"✅ 画像アップロード完了: {image_path}")


def set_default_rich_menu(token: str, rich_menu_id: str) -> None:
    """全ユーザーのデフォルトリッチメニューに設定する"""
    resp = requests.post(
        f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
        verify=_VERIFY,
    )
    resp.raise_for_status()
    print(f"✅ デフォルトリッチメニュー設定完了")


def list_rich_menus(token: str) -> None:
    """登録済みリッチメニュー一覧を表示する"""
    resp = requests.get(
        "https://api.line.me/v2/bot/richmenu/list",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
        verify=_VERIFY,
    )
    resp.raise_for_status()
    menus = resp.json().get("richmenus", [])
    print(f"\n📋 登録済みリッチメニュー ({len(menus)}件):")
    for m in menus:
        print(f"  - {m['richMenuId']}: {m['name']}")


def delete_all_rich_menus(token: str) -> None:
    """登録済みのリッチメニューを全て削除する（クリーンアップ用）"""
    resp = requests.get(
        "https://api.line.me/v2/bot/richmenu/list",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
        verify=_VERIFY,
    )
    resp.raise_for_status()
    for m in resp.json().get("richmenus", []):
        mid = m["richMenuId"]
        requests.delete(
            f"https://api.line.me/v2/bot/richmenu/{mid}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
            verify=_VERIFY,
        )
        print(f"🗑️ 削除: {mid}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="LINE リッチメニュー管理")
    parser.add_argument("--image", default="", help="リッチメニュー画像ファイルパス（省略可）")
    parser.add_argument("--list", action="store_true", help="登録済み一覧を表示")
    parser.add_argument("--clean", action="store_true", help="既存メニューを全削除してから登録")
    args = parser.parse_args()

    token = get_token()

    if args.list:
        list_rich_menus(token)
        return

    if args.clean:
        print("🗑️ 既存のリッチメニューを削除中...")
        delete_all_rich_menus(token)

    rich_menu_id = create_rich_menu(token)

    if args.image:
        upload_image(token, rich_menu_id, args.image)
    else:
        print("ℹ️ --image を指定すると画像をアップロードできます")
        print("   例: python scripts/register_rich_menu.py --image assets/rich_menu.png")

    set_default_rich_menu(token, rich_menu_id)

    print(f"\n🎉 完了！リッチメニューID: {rich_menu_id}")
    print("LINE アプリを再起動して確認してください。")


if __name__ == "__main__":
    main()
