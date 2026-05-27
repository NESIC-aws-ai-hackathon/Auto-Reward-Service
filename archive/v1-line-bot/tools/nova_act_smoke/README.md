# Nova Act 検証ツール (smoke test)

要件整理.md §10 準拠の Nova Act 単体検証スクリプトです。

## 目的

Nova Act の動作確認を LINE Bot/PWA 経由ではなく、ローカル CLI で完結させる。

## 使い方

```bash
python tools/nova_act_smoke/search_reward_candidate.py \
  --query "抹茶 プリン" \
  --max-results 3 \
  --output sample_output.json
```

## 出力例 (sample_output.json)

```json
[
  {
    "name": "抹茶プリン",
    "amount": 320,
    "url": "https://...",
    "image_url": "https://...",
    "source": "nova_act",
    "tags": ["抹茶", "プリン", "スイーツ"],
    "confidence": 0.78
  }
]
```

## 環境変数

```env
ENABLE_NOVA_ACT=true            # Nova Act を有効化
ENABLE_NOVA_ACT_SMOKE=true      # スモーク導線を有効化
NOVA_ACT_SYNC_IN_LINE_CHAT=false # LINE Bot 同期で呼ばない (既定)
```

## フォールバック動作

`nova-act` SDK 未インストール or 失敗時は以下にフォールバックします：

1. **Nova Act** (`source: nova_act`)
2. **External API** (楽天) (`source: rakuten_api`)
3. **Static** (`source: static`)

どのレイヤがヒットしたかは `meta.status` と `meta.provider` で確認できます。

## PWA 経由の同等検証

```bash
curl -X POST https://6seky2k0ge.execute-api.ap-northeast-1.amazonaws.com/api/nova-act/smoke \
  -H "Authorization: Bearer <LINE Login ID Token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "抹茶 プリン", "max_results": 3}'
```

レスポンスには候補リストと `meta` (status/provider/duration_ms) が含まれます。

---

# Amazon 自動購入 CLI (`purchase_amazon.py`)

要件整理.md §9 / §12 / §14 準拠で、Amazon ログイン → 商品検索 → カート追加 → レジ → 注文確定 までを完全自動化する CLI。

## 動作要件

- Python 3.10+
- Chromium が動く環境（macOS / Windows / Linux デスクトップ または Playwright ベースのコンテナ）
- ⚠️ **Lambda では動かない**（ブラウザがないため）。ローカル CLI もしくは ECS Fargate（Worker モード）で実行する。

## セットアップ

```bash
# 1. 依存をインストール
pip install -r tools/nova_act_smoke/requirements-nova-act.txt
playwright install chromium

# 2. API キーを取得 (https://nova.amazon.com/act)
export NOVA_ACT_API_KEY=nova_act_...

# 3. 初回ログイン (永続プロファイル作成)
python tools/nova_act_smoke/purchase_amazon.py --setup-login --query dummy
# → 開いた Chromium で手動ログイン → Enter キーで保存
```

## 通常実行（購入直前で停止）

```bash
python tools/nova_act_smoke/purchase_amazon.py \
  --query "抹茶 プリン" \
  --max-price 1000
```

実行結果は `tools/nova_act_smoke/runs/<run_id>/result.json` に保存されます。
動画・スクリーンショット・Nova Act トレースも同階層に出力されます。

## 商品 URL を直接指定

```bash
python tools/nova_act_smoke/purchase_amazon.py \
  --product-url "https://www.amazon.co.jp/dp/B0XXXXXXX" \
  --max-price 1500
```

## 実購入の実行

実購入は **2 つのフラグを必ず併用**しないと走りません（安全策）：

```bash
ENABLE_REAL_PURCHASE=true \
  python tools/nova_act_smoke/purchase_amazon.py \
    --query "抹茶 プリン" \
    --max-price 500 \
    --execute-purchase
```

## 主な引数

| 引数 | 説明 |
|------|------|
| `--query <kw>` | Amazon で検索するキーワード |
| `--product-url <url>` | 商品ページ URL を直接指定（`--query` と排他） |
| `--setup-login` | 初回ログイン専用モード（プロファイルだけ作って終了） |
| `--max-price <yen>` | 許容最大金額（既定 1000）|
| `--user-data-dir <dir>` | 永続プロファイルの保存先（既定 `~/.nova-act/ars-amazon`） |
| `--allow-interactive-login` | 未ログイン検出時に Enter 待ちで人間ログインを受け付ける |
| `--stop-after-cart` | カート追加までで停止（レジに進まない） |
| `--execute-purchase` | 注文確定を実行（`ENABLE_REAL_PURCHASE=true` との併用必須） |
| `--headless` | ヘッドレスモード（デバッグ時は外す） |

## 安全ガード

以下を満たさない限り注文確定には進まない：

- 価格上限 (`--max-price` / `MAX_PURCHASE_AMOUNT`) 以内
- 定期おトク便ではない
- 在庫あり
- カート内アイテム数 == 1
- 「注文を確定する」ボタンが表示済み
- `ENABLE_REAL_PURCHASE=true` かつ `--execute-purchase` が両方指定されている

## エラーコード

`cart_automation_worker.py` の `NOVA_ACT_ERROR_CODES` と整合：

| コード | 意味 |
|--------|------|
| `LOGIN_REQUIRED` | 未ログイン |
| `MFA_REQUIRED` | 二段階認証要求 |
| `CAPTCHA_REQUIRED` | CAPTCHA 検出 |
| `PRODUCT_NOT_FOUND` | 商品なし / 在庫切れ |
| `PRICE_NOT_FOUND` | 価格取得失敗 |
| `PRICE_LIMIT_EXCEEDED` | 価格上限超過 |
| `SUBSCRIPTION_DETECTED` | 定期おトク便検出 |
| `CHECKOUT_PAGE_NOT_REACHED` | レジ遷移失敗 |
| `SAFETY_CHECK_FAILED` | 安全確認失敗 |
| `PURCHASE_BUTTON_NOT_FOUND` | 注文確定ボタン不在 |
| `ORDER_CONFIRMATION_NOT_FOUND` | 注文完了画面に遷移できず |
| `TIMEOUT` | タイムアウト |
| `UNKNOWN` | その他 |

---

# Docker / ECS Worker (`Dockerfile` + `worker.py`)

`purchase_amazon.py` をコンテナ化し、DynamoDB の `CART_AUTOMATION_JOB#` を Worker から処理する。

## イメージのビルド

```bash
cd tools/nova_act_smoke
docker build -t ars-nova-act-worker:latest .
```

## ローカルで Worker を試す

```bash
docker run --rm \
  -e NOVA_ACT_API_KEY=$NOVA_ACT_API_KEY \
  -e AWS_REGION=ap-northeast-1 \
  -e ARS_TABLE_NAME=ArsTable \
  -e ENABLE_REAL_PURCHASE=false \
  -e MAX_PURCHASE_AMOUNT=1000 \
  -v $HOME/.nova-act:/home/nova/.nova-act \
  -v $HOME/.aws:/home/nova/.aws:ro \
  ars-nova-act-worker:latest
```

`-v $HOME/.nova-act` でログイン済みプロファイルを共有。
本番 ECS 環境では EFS マウントに置き換える。

## ECS Fargate デプロイの流れ（後続フェーズ）

1. ECR にイメージを push
2. EFS Access Point で `/home/nova/.nova-act` をマウント（プロファイル永続化）
3. ECS Task Definition: 2vCPU / 4GB, EFS マウント, Secrets Manager から `NOVA_ACT_API_KEY` 注入
4. Lambda `CartJobService` から `ecs:RunTask` でジョブごとに Task を起動
   - もしくは EventBridge Schedule で定期 Polling
5. Worker は QUEUED ジョブを 1 件取って実行 → DynamoDB に結果を書き戻して終了

## ローカル CLI モード（Worker ではなく直接 CLI として使う）

```bash
docker run --rm -it \
  -e NOVA_ACT_API_KEY=$NOVA_ACT_API_KEY \
  -v $HOME/.nova-act:/home/nova/.nova-act \
  --entrypoint python \
  ars-nova-act-worker:latest \
  /app/purchase_amazon.py --query "抹茶 プリン" --max-price 1000
```

