# API 設定ガイド — Auto-Reward-Service

このドキュメントでは、サービスが利用する各 API の登録方法・取得するキーの種類・保存先をまとめます。

---

## 概要：シークレット管理の設計

| 利用 API | 必須/任意 | 保存先 (AWS Secrets Manager) |
|---------|---------|---------------------------|
| LINE Messaging API | **必須** | `ars/line` |
| Amazon Bedrock | **必須** | IAM ロール制御（キー不要） |
| Google Calendar API | 任意 | `ars/google` |
| 楽天ウェブサービス | 任意 | `ars/rakuten` |
| ホットペッパー Gourmet | 任意 (Growth) | `ars/hotpepper/api-key` |

Lambda は AWS Secrets Manager から実行時に値を取得します。各シークレットはモジュールレベルでキャッシュされ、同一コンテナの 2 回目以降の呼び出しでは再取得しません。

---

## 1. LINE Messaging API

### 1-1. 登録・取得手順

1. [LINE Developers コンソール](https://developers.line.biz/) にログイン
2. プロバイダーを選択（または新規作成）し、**Messaging API チャンネル** を作成
3. チャンネル基本設定タブで以下を取得:
   - **Channel Secret** → `LINE_CHANNEL_SECRET`
4. Messaging API タブ → 「チャンネルアクセストークン（長期）」を発行:
   - **Channel Access Token** → `LINE_ACCESS_TOKEN`

### 1-2. Webhook URL の設定

デプロイ後、Messaging API タブ → Webhook 設定で以下の URL を登録:

```
https://<ApiEndpoint>/webhook
```

> `sam deploy` 後の出力 `WebhookApiEndpoint` の値を使用してください。

### 1-3. LIFF アプリの設定

1. LIFF タブ → LIFF アプリを追加
2. エンドポイント URL: `https://<ApiEndpoint>/liff`
3. スコープ: `profile`, `openid`
4. 作成後に LIFF ID を確認し、`template.yaml` の `LIFF_CHANNEL_ID` が Channel ID と一致することを確認

### 1-4. Secrets Manager への保存

```bash
aws secretsmanager create-secret \
  --name ars/line \
  --secret-string '{
    "LINE_CHANNEL_SECRET": "YOUR_CHANNEL_SECRET",
    "LINE_ACCESS_TOKEN":   "YOUR_ACCESS_TOKEN"
  }' \
  --profile share
```

既存シークレットを更新する場合:

```bash
aws secretsmanager put-secret-value \
  --secret-id ars/line \
  --secret-string '{
    "LINE_CHANNEL_SECRET": "YOUR_CHANNEL_SECRET",
    "LINE_ACCESS_TOKEN":   "YOUR_ACCESS_TOKEN"
  }' \
  --profile share
```

---

## 2. Amazon Bedrock

追加の API キーは不要です。IAM ロール `ArsLambdaRole` に `bedrock:InvokeModel` 権限が付与されています。

### 2-1. モデルアクセスの有効化（初回のみ）

1. AWS コンソール → **Amazon Bedrock** → モデルアクセス（東京リージョン）
2. 以下のモデルのアクセスをリクエスト（無料・即時承認）:
   - `Amazon Nova Lite` (`amazon.nova-lite-v1:0`)
   - `Amazon Nova Micro` (`amazon.nova-micro-v1:0`)
3. ステータスが「アクセス権限付与済み」になるまで待機（通常数分）

### 2-2. 使用モデル一覧

| 環境変数 | モデル ID | 用途 |
|---------|---------|-----|
| `BEDROCK_TEXT_MODEL_ID` | `amazon.nova-lite-v1:0` | キャラクター応答・おすすめ生成 |
| `BEDROCK_IMAGE_MODEL_ID` | `amazon.nova-lite-v1:0` | レシート画像解析 |
| `BEDROCK_INTENT_MODEL_ID` | `amazon.nova-lite-v1:0` | インテント分類 |
| `BEDROCK_FALLBACK_MODEL_ID` | `amazon.nova-lite-v1:0` | フォールバック |

---

## 3. Google Calendar API

ユーザーが LIFF 画面で「Googleと連携する」ボタンを押したときに使用します。任意機能です。

### 3-1. Google Cloud Console での設定

1. [Google Cloud Console](https://console.cloud.google.com/) → プロジェクトを作成（または既存を選択）
2. **API とサービス** → **ライブラリ** → 「Google Calendar API」を有効化
3. **OAuth 同意画面** を設定:
   - アプリ名: `Auto Reward Service`
   - スコープ: `https://www.googleapis.com/auth/calendar.events.readonly`
   - テストユーザーを追加（公開前）
4. **認証情報** → 「OAuth 2.0 クライアント ID」を作成:
   - アプリの種類: **ウェブ アプリケーション**
   - 承認済みのリダイレクト URI:
     ```
     https://<ApiEndpoint>/api/calendar/callback
     ```
   - 作成後に **クライアント ID** と **クライアントシークレット** を取得

### 3-2. Secrets Manager への保存

```bash
aws secretsmanager create-secret \
  --name ars/google \
  --secret-string '{
    "client_id":     "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uri":  "https://<ApiEndpoint>/api/calendar/callback"
  }' \
  --profile share
```

> `redirect_uri` は `sam deploy` 後の `WebhookApiEndpoint` の値のベース URL に `/api/calendar/callback` を付けたものになります。

---

## 4. 楽天ウェブサービス

おすすめ候補をパーソナライズするために使用します。任意機能です。

### 4-1. アプリ ID の取得

1. [楽天デベロッパー](https://webservice.rakuten.co.jp/) にログイン（楽天 ID 必須）
2. 「アプリ ID 発行」→ 新規アプリを登録:
   - アプリ名: `Auto Reward Service`
   - アプリ URL: API Gateway のベース URL
3. 登録後に表示される **アプリ ID** を控える

### 4-2. Secrets Manager への保存

```bash
aws secretsmanager create-secret \
  --name ars/rakuten \
  --secret-string '{
    "RAKUTEN_APP_ID": "YOUR_RAKUTEN_APP_ID"
  }' \
  --profile share
```

---

## 5. ホットペッパー Gourmet API（Growth フェーズ）

グルメカテゴリ選択時のレストランおすすめで使用します。  
`ENABLE_RESTAURANT_SEARCH=true` を Lambda 環境変数に設定した場合のみ呼び出されます。

### 5-1. API キーの取得

1. [リクルート WEB サービス](https://webservice.recruit.co.jp/) にアクセス
2. アカウント登録後、**API キーの取得** → アプリケーションを登録
3. 取得した **APIキー** を控える

### 5-2. Secrets Manager への保存

```bash
aws secretsmanager create-secret \
  --name ars/hotpepper/api-key \
  --secret-string '{
    "HOTPEPPER_API_KEY": "YOUR_API_KEY"
  }' \
  --profile share
```

> IAM ポリシー `ArsSecretsManagerPolicy` に `ars/hotpepper*` のアクセス権を追加する必要があります（`template.yaml` を更新してから再デプロイ）。

---

## 6. Secrets Manager の確認コマンド

登録済みのシークレット一覧を確認:

```bash
aws secretsmanager list-secrets \
  --query "SecretList[?starts_with(Name, 'ars/')].{Name:Name,LastChanged:LastChangedDate}" \
  --output table \
  --profile share
```

特定シークレットの値を確認（キー名のみ、値は表示しない）:

```bash
aws secretsmanager get-secret-value \
  --secret-id ars/line \
  --profile share \
  --query "SecretString" \
  --output text | python -c "import sys,json; print(list(json.load(sys.stdin).keys()))"
```

---

## 7. 設定チェックリスト（デプロイ前確認）

### 必須（デモに直結）

- [ ] `ars/line` に `LINE_CHANNEL_SECRET` と `LINE_ACCESS_TOKEN` が登録済み
- [ ] LINE Developers で Webhook URL が設定済み、Webhook 利用: ON
- [ ] Bedrock コンソールで Nova Lite のアクセスが有効化済み
- [ ] `sam deploy` が成功し、`WebhookApiEndpoint` が出力されている

### 任意（Google Calendar 連携を使う場合）

- [ ] `ars/google` に `client_id`, `client_secret`, `redirect_uri` が登録済み
- [ ] Google Cloud Console でリダイレクト URI が `ars/google.redirect_uri` と一致している
- [ ] OAuth 同意画面のテストユーザーにデモアカウントが追加済み

### 任意（楽天おすすめを使う場合）

- [ ] `ars/rakuten` に `RAKUTEN_APP_ID` が登録済み

---

## 8. リッチメニュー登録

リッチメニューは LINE Developers コンソールで設定するか、スクリプトで自動登録できます:

```bash
LINE_CHANNEL_ACCESS_TOKEN="YOUR_ACCESS_TOKEN" \
  python scripts/register_rich_menu.py
```

画像ファイルを一緒にアップロードする場合:

```bash
LINE_CHANNEL_ACCESS_TOKEN="YOUR_ACCESS_TOKEN" \
  python scripts/register_rich_menu.py --image path/to/richmenu.png
```
