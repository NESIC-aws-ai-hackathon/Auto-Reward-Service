"""
Nova Act Amazon 購入フロー CLI

要件整理.md §10 / §9, §12, §14 準拠の購入自動化ツール。

フロー:
    1. Amazon にナビゲート（永続プロファイルで Cookie 復元）
    2. ログイン状態を検証（未ログインなら人間に手動ログインを促す）
    3. 商品検索 or 商品 URL 直行
    4. 商品ページの検証（タイトル / 価格 / 定期購入検出 / 価格上限）
    5. カートに追加
    6. レジ画面まで遷移
    7. ``--execute-purchase`` が指定された場合のみ「注文確定」を実行（既定は直前で停止）
    8. 実行結果 / トレースを ``runs/{timestamp}/`` に保存

使い方:
    # 初回 (手動ログインしてプロファイル作成)
    python tools/nova_act_smoke/purchase_amazon.py \\
        --query "抹茶 プリン" --max-price 1000 --setup-login

    # 通常実行 (購入直前で停止 = ENABLE_REAL_PURCHASE=false 相当)
    python tools/nova_act_smoke/purchase_amazon.py \\
        --query "抹茶 プリン" --max-price 1000

    # 実購入 (必ず ENABLE_REAL_PURCHASE=true と一緒に指定)
    python tools/nova_act_smoke/purchase_amazon.py \\
        --query "抹茶 プリン" --max-price 500 --execute-purchase

環境変数:
    NOVA_ACT_API_KEY                Nova Act API キー（必須）
    NOVA_ACT_USER_DATA_DIR          永続プロファイル保存先（既定: ~/.nova-act/ars-amazon）
    ENABLE_REAL_PURCHASE            true の場合のみ ``--execute-purchase`` が有効化
    MAX_PURCHASE_AMOUNT             許容最大金額（既定 1000 円）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────
# 結果コード（layer/python/services/cart_automation_worker.py と整合）
# ─────────────────────────────────────────
ERROR_CODES = {
    "LOGIN_REQUIRED": "Amazonアカウントへのログインが必要です",
    "MFA_REQUIRED": "二段階認証が必要です",
    "CAPTCHA_REQUIRED": "CAPTCHA が表示されました",
    "PRODUCT_NOT_FOUND": "条件に合う商品が見つかりませんでした",
    "PRICE_NOT_FOUND": "価格情報を取得できませんでした",
    "PRICE_LIMIT_EXCEEDED": "価格が上限を超えています",
    "SUBSCRIPTION_DETECTED": "定期購入商品が検出されました",
    "CHECKOUT_PAGE_NOT_REACHED": "レジ画面への遷移に失敗しました",
    "SAFETY_CHECK_FAILED": "購入直前の安全確認に失敗しました",
    "PURCHASE_BUTTON_NOT_FOUND": "購入確定ボタンが見つかりません",
    "ORDER_CONFIRMATION_NOT_FOUND": "注文確認画面に遷移できませんでした",
    "TIMEOUT": "タイムアウトしました",
    "UNKNOWN": "不明なエラー",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_result(success: bool, status: str, **kwargs) -> dict:
    return {"success": success, "status": status, "timestamp": _now_iso(), **kwargs}


def _write_result(out_dir: Path, result: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _take_screenshot(nova, out_dir: Path, name: str) -> Optional[str]:
    try:
        path = out_dir / f"{name}.png"
        img = nova.page.screenshot()
        path.write_bytes(img)
        return str(path)
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] screenshot failed: {e}", file=sys.stderr)
        return None


# ─────────────────────────────────────────
# Pydantic schemas (act_get 用)
# ─────────────────────────────────────────
def _build_schemas():
    """Pydantic スキーマを遅延構築（モジュールロード時に pydantic 必須にしない）。"""
    from pydantic import BaseModel

    class SignInStatus(BaseModel):
        is_signed_in: bool

    class ProductInfo(BaseModel):
        title: str
        price_jpy: int
        is_subscription: bool
        is_in_stock: bool

    class CheckoutSummary(BaseModel):
        total_jpy: int
        item_count: int
        has_subscription: bool
        ready_to_place_order: bool

    return SignInStatus, ProductInfo, CheckoutSummary


# ─────────────────────────────────────────
# Nova Act 実行フェーズ
# ─────────────────────────────────────────
def run(args: argparse.Namespace) -> dict:
    # ── 環境変数の整理
    api_key = os.environ.get("NOVA_ACT_API_KEY", "")
    if not api_key:
        return _make_result(
            False, "FAILED",
            error_code="UNKNOWN",
            message="NOVA_ACT_API_KEY が未設定です。https://nova.amazon.com/act で取得してください",
        )

    enable_real = os.environ.get("ENABLE_REAL_PURCHASE", "false").lower() == "true"
    max_price = int(os.environ.get("MAX_PURCHASE_AMOUNT", args.max_price))

    user_data_dir = args.user_data_dir or os.environ.get(
        "NOVA_ACT_USER_DATA_DIR",
        str(Path.home() / ".nova-act" / "ars-amazon"),
    )
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)

    # ── 出力ディレクトリ
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(__file__).resolve().parent / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] run_id={run_id}")
    print(f"[INFO] user_data_dir={user_data_dir}")
    print(f"[INFO] max_price=¥{max_price:,}  enable_real_purchase={enable_real}")

    # ── Nova Act 起動
    try:
        from nova_act import NovaAct, BOOL_SCHEMA  # noqa: F401
        from nova_act.types.act_errors import ActAgentError, ActClientError
    except Exception as e:  # noqa: BLE001
        return _make_result(
            False, "FAILED",
            error_code="UNKNOWN",
            message=f"nova-act SDK がインストールされていません: {e}",
            hint="pip install -r tools/nova_act_smoke/requirements-nova-act.txt を実行してください",
        )

    SignInStatus, ProductInfo, CheckoutSummary = _build_schemas()

    starting_page = args.product_url or "https://www.amazon.co.jp/"
    nova_kwargs = dict(
        starting_page=starting_page,
        user_data_dir=user_data_dir,
        clone_user_data_dir=False,
        logs_directory=str(out_dir),
        record_video=True,
        headless=args.headless,
    )

    with NovaAct(**nova_kwargs) as nova:
        # =============================================================
        # フェーズ 1: 初回セットアップモード (手動ログインだけ)
        # =============================================================
        if args.setup_login:
            print("\n[STEP] 1/1  ブラウザでAmazonに手動ログインしてください…")
            input("       ログインが完了したら Enter を押してください…")
            _take_screenshot(nova, out_dir, "01_post_login")
            return _make_result(
                True, "LOGIN_SETUP_DONE",
                run_id=run_id, user_data_dir=user_data_dir,
                message="プロファイルを保存しました。次回からはログイン不要で実行できます",
            )

        # =============================================================
        # フェーズ 2: ログイン状態の検証
        # =============================================================
        print("\n[STEP] 1/6  ログイン状態を確認中…")
        try:
            result = nova.act_get(
                "Am I signed in to Amazon? Look for the account name in the top-right corner.",
                schema=SignInStatus.model_json_schema(),
            )
            sign_in = SignInStatus.model_validate(result.parsed_response)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] sign-in check failed: {e}", file=sys.stderr)
            sign_in = SignInStatus(is_signed_in=False)

        _take_screenshot(nova, out_dir, "01_initial_state")

        if not sign_in.is_signed_in:
            if not args.allow_interactive_login:
                return _make_result(
                    False, "FAILED",
                    error_code="LOGIN_REQUIRED",
                    message=ERROR_CODES["LOGIN_REQUIRED"],
                    hint="--setup-login を付けて初回ログインを行うか、--allow-interactive-login を指定してください",
                )
            print("       未ログイン。手動でログインしてください…")
            input("       ログインが完了したら Enter を押してください…")
            _take_screenshot(nova, out_dir, "02_post_login")

        # =============================================================
        # フェーズ 3: 商品検索（product_url 指定時はスキップ）
        # =============================================================
        if not args.product_url:
            print(f"\n[STEP] 2/6  商品を検索中: {args.query!r} (上限 ¥{max_price:,})")
            try:
                nova.go_to_url("https://www.amazon.co.jp/")
                nova.act(
                    f'Search for "{args.query}" using the search bar at the top, '
                    f'then press Enter. Wait for the search results page to load.'
                )
                nova.act(
                    f"From the search results, click on the first product "
                    f"that costs ¥{max_price:,} or less and is not a subscription (定期おトク便). "
                    f"Avoid sponsored ads if possible."
                )
            except (ActAgentError, ActClientError) as e:
                _take_screenshot(nova, out_dir, "03_search_failed")
                return _make_result(
                    False, "FAILED",
                    error_code="PRODUCT_NOT_FOUND",
                    message=f"{ERROR_CODES['PRODUCT_NOT_FOUND']}: {e}",
                    run_id=run_id,
                )

        # =============================================================
        # フェーズ 4: 商品ページの検証
        # =============================================================
        print("\n[STEP] 3/6  商品ページを検証中…")
        _take_screenshot(nova, out_dir, "04_product_page")
        try:
            result = nova.act_get(
                "Extract the product title, price in JPY (integer, no comma), "
                "whether this is a subscription product (e.g. 定期おトク便), "
                "and whether it is in stock.",
                schema=ProductInfo.model_json_schema(),
            )
            product = ProductInfo.model_validate(result.parsed_response)
        except Exception as e:  # noqa: BLE001
            return _make_result(
                False, "FAILED",
                error_code="PRICE_NOT_FOUND",
                message=f"{ERROR_CODES['PRICE_NOT_FOUND']}: {e}",
                run_id=run_id,
            )

        print(f"       title={product.title!r}")
        print(f"       price=¥{product.price_jpy:,}  subscription={product.is_subscription}  in_stock={product.is_in_stock}")

        if product.is_subscription:
            return _make_result(
                False, "FAILED",
                error_code="SUBSCRIPTION_DETECTED",
                message=ERROR_CODES["SUBSCRIPTION_DETECTED"],
                product=product.model_dump(),
                run_id=run_id,
            )
        if not product.is_in_stock:
            return _make_result(
                False, "FAILED",
                error_code="PRODUCT_NOT_FOUND",
                message="在庫切れです",
                product=product.model_dump(),
                run_id=run_id,
            )
        if product.price_jpy <= 0 or product.price_jpy > max_price:
            return _make_result(
                False, "FAILED",
                error_code="PRICE_LIMIT_EXCEEDED",
                message=f"{ERROR_CODES['PRICE_LIMIT_EXCEEDED']} (¥{product.price_jpy:,} > ¥{max_price:,})",
                product=product.model_dump(),
                run_id=run_id,
            )

        # =============================================================
        # フェーズ 5: カートに追加
        # =============================================================
        print("\n[STEP] 4/6  カートに追加中…")
        try:
            nova.act(
                "Click the 'Add to Cart' button (カートに入れる). "
                "If a popup appears offering protection plans or related products, "
                "click 'No thanks' or close it."
            )
            time.sleep(2)  # アニメーション待機
            _take_screenshot(nova, out_dir, "05_cart_added")
        except (ActAgentError, ActClientError) as e:
            return _make_result(
                False, "FAILED",
                error_code="UNKNOWN",
                message=f"カート追加失敗: {e}",
                product=product.model_dump(),
                run_id=run_id,
            )

        if args.stop_after_cart:
            return _make_result(
                True, "CART_ADDED",
                message="カートに追加しました（--stop-after-cart 指定）",
                product=product.model_dump(),
                run_id=run_id,
            )

        # =============================================================
        # フェーズ 6: レジ画面まで遷移
        # =============================================================
        print("\n[STEP] 5/6  レジ画面に遷移中…")
        try:
            nova.go_to_url("https://www.amazon.co.jp/gp/cart/view.html")
            nova.act(
                "Click the 'Proceed to checkout' button (レジに進む). "
                "Do NOT change shipping address or payment method. "
                "Do NOT click the final 'Place your order' button yet."
            )
            time.sleep(3)
            _take_screenshot(nova, out_dir, "06_checkout_page")
        except (ActAgentError, ActClientError) as e:
            return _make_result(
                False, "FAILED",
                error_code="CHECKOUT_PAGE_NOT_REACHED",
                message=f"{ERROR_CODES['CHECKOUT_PAGE_NOT_REACHED']}: {e}",
                product=product.model_dump(),
                run_id=run_id,
            )

        # =============================================================
        # フェーズ 7: 注文内容の安全確認
        # =============================================================
        print("\n[STEP] 6/6  注文内容の安全確認…")
        try:
            result = nova.act_get(
                "Extract the order total in JPY (integer), the number of items, "
                "whether any item is a subscription, and whether the page is ready "
                "to place the order (i.e. the 'Place your order / 注文を確定する' button is visible).",
                schema=CheckoutSummary.model_json_schema(),
            )
            checkout = CheckoutSummary.model_validate(result.parsed_response)
        except Exception as e:  # noqa: BLE001
            return _make_result(
                False, "FAILED",
                error_code="SAFETY_CHECK_FAILED",
                message=f"{ERROR_CODES['SAFETY_CHECK_FAILED']}: {e}",
                product=product.model_dump(),
                run_id=run_id,
            )

        print(f"       total=¥{checkout.total_jpy:,}  items={checkout.item_count}  "
              f"sub={checkout.has_subscription}  ready={checkout.ready_to_place_order}")

        if checkout.has_subscription:
            return _make_result(
                False, "FAILED",
                error_code="SUBSCRIPTION_DETECTED",
                message=ERROR_CODES["SUBSCRIPTION_DETECTED"],
                product=product.model_dump(),
                checkout=checkout.model_dump(),
                run_id=run_id,
            )
        if checkout.total_jpy <= 0 or checkout.total_jpy > max_price:
            return _make_result(
                False, "FAILED",
                error_code="PRICE_LIMIT_EXCEEDED",
                message=f"合計金額が上限超過 (¥{checkout.total_jpy:,} > ¥{max_price:,})",
                product=product.model_dump(),
                checkout=checkout.model_dump(),
                run_id=run_id,
            )
        if checkout.item_count != 1:
            return _make_result(
                False, "FAILED",
                error_code="SAFETY_CHECK_FAILED",
                message=f"カート内アイテム数が想定外: {checkout.item_count}",
                product=product.model_dump(),
                checkout=checkout.model_dump(),
                run_id=run_id,
            )
        if not checkout.ready_to_place_order:
            return _make_result(
                False, "FAILED",
                error_code="PURCHASE_BUTTON_NOT_FOUND",
                message=ERROR_CODES["PURCHASE_BUTTON_NOT_FOUND"],
                product=product.model_dump(),
                checkout=checkout.model_dump(),
                run_id=run_id,
            )

        # =============================================================
        # フェーズ 8: 購入確定（ENABLE_REAL_PURCHASE=true かつ --execute-purchase 時のみ）
        # =============================================================
        if not (args.execute_purchase and enable_real):
            reason = []
            if not args.execute_purchase:
                reason.append("--execute-purchase 未指定")
            if not enable_real:
                reason.append("ENABLE_REAL_PURCHASE=false")
            return _make_result(
                True, "READY_TO_PURCHASE",
                message=f"購入直前で停止しました ({' / '.join(reason)})",
                product=product.model_dump(),
                checkout=checkout.model_dump(),
                run_id=run_id,
            )

        print("\n[STEP] 注文を確定します…")
        try:
            nova.act(
                "Click the 'Place your order' button (注文を確定する) exactly once. "
                "Wait for the order confirmation page to load."
            )
            time.sleep(5)
            _take_screenshot(nova, out_dir, "07_order_placed")
        except (ActAgentError, ActClientError) as e:
            return _make_result(
                False, "FAILED",
                error_code="ORDER_CONFIRMATION_NOT_FOUND",
                message=f"{ERROR_CODES['ORDER_CONFIRMATION_NOT_FOUND']}: {e}",
                product=product.model_dump(),
                checkout=checkout.model_dump(),
                run_id=run_id,
            )

        # 注文番号の取得
        try:
            from pydantic import BaseModel

            class OrderConfirmation(BaseModel):
                order_id: str
                order_placed: bool

            result = nova.act_get(
                "Extract the order number (order ID) from the confirmation page "
                "and whether the order was successfully placed.",
                schema=OrderConfirmation.model_json_schema(),
            )
            confirm = OrderConfirmation.model_validate(result.parsed_response)
            order_id = confirm.order_id if confirm.order_placed else None
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] order_id extraction failed: {e}", file=sys.stderr)
            order_id = None

        return _make_result(
            True, "PURCHASED",
            message="注文が完了しました",
            product=product.model_dump(),
            checkout=checkout.model_dump(),
            order_id=order_id,
            run_id=run_id,
        )


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Nova Act Amazon 購入フロー CLI (search → cart → checkout → purchase)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query", help="検索キーワード（例: '抹茶 プリン'）")
    group.add_argument("--product-url", help="Amazon 商品ページ URL を直接指定")
    group.add_argument("--setup-login", action="store_true",
                       help="初回ログイン専用モード（プロファイルを永続化するだけ）")

    parser.add_argument("--max-price", type=int, default=1000,
                        help="許容最大金額（円, 既定 1000）")
    parser.add_argument("--user-data-dir", default=None,
                        help="Chromium 永続プロファイル先（既定 ~/.nova-act/ars-amazon）")
    parser.add_argument("--allow-interactive-login", action="store_true",
                        help="未ログイン検出時に対話入力で待機する")
    parser.add_argument("--stop-after-cart", action="store_true",
                        help="カート追加までで停止（レジ画面に進まない）")
    parser.add_argument("--execute-purchase", action="store_true",
                        help="購入を実行する（ENABLE_REAL_PURCHASE=true との併用必須）")
    parser.add_argument("--headless", action="store_true",
                        help="ヘッドレスモードで実行（デバッグ時は外す）")

    args = parser.parse_args()

    try:
        result = run(args)
    except KeyboardInterrupt:
        result = _make_result(False, "FAILED", error_code="UNKNOWN",
                              message="ユーザーによる中断")
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        result = _make_result(False, "FAILED", error_code="UNKNOWN",
                              message=f"未捕捉エラー: {e}")

    # ── 出力ディレクトリにも保存（run_id があれば）
    if result.get("run_id"):
        out_dir = Path(__file__).resolve().parent / "runs" / result["run_id"]
        _write_result(out_dir, result)
        print(f"\n[OK] result saved to {out_dir / 'result.json'}")

    print("\n[RESULT]")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
