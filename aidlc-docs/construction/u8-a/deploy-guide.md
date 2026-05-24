# U8-A デプロイ確認手順書

## 対象: 1回目デプロイ — PWA基盤 + Cognito認証

### 前提条件
- AWS CLI 設定済み（profile: `share`）
- SAM CLI インストール済み
- Node.js 18+ インストール済み

---

## 1. バックエンドデプロイ

```bash
cd u8/

# SAM ビルド & デプロイ
sam build
sam deploy --profile share --guided
# ※ 初回は guided で設定。以降は samconfig.toml 利用

# 出力確認 (Outputs)
# - ApiUrl
# - UserPoolId
# - UserPoolClientId
# - CloudFrontUrl
# - FrontendBucketName
```

### 確認項目
- [ ] CloudFormation スタック `ars-u8-pwa` が CREATE_COMPLETE
- [ ] Cognito User Pool が作成されている
- [ ] API Gateway HTTP API が作成されている
- [ ] Lambda `ars-u8-api-dev` が作成されている
- [ ] S3 バケットが作成されている
- [ ] CloudFront Distribution が作成されている

---

## 2. デモユーザー作成

```bash
# デプロイ出力の UserPoolId を使用
USER_POOL_ID=<出力されたUserPoolId>

aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username demo@example.com \
  --temporary-password TempPass123! \
  --user-attributes Name=email,Value=demo@example.com Name=email_verified,Value=true \
  --message-action SUPPRESS \
  --profile share

# パスワードを永続化（admin-set-user-password）
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username demo@example.com \
  --password "DemoPass123!" \
  --permanent \
  --profile share
```

### 確認項目
- [ ] demo@example.com ユーザーが CONFIRMED 状態

---

## 3. フロントエンドビルド & デプロイ

```bash
cd frontend/

# .env ファイル作成（デプロイ出力の値を使用）
cat > .env.production << EOF
VITE_API_URL=<ApiUrl出力>
VITE_COGNITO_USER_POOL_ID=<UserPoolId出力>
VITE_COGNITO_CLIENT_ID=<UserPoolClientId出力>
EOF

# ビルド
npm install
npm run build

# S3 にアップロード
BUCKET_NAME=<FrontendBucketName出力>
aws s3 sync dist/ s3://$BUCKET_NAME/ --delete --profile share

# CloudFront キャッシュ無効化
CF_DIST_ID=<CloudFrontDistributionId>
aws cloudfront create-invalidation --distribution-id $CF_DIST_ID --paths "/*" --profile share
```

### 確認項目
- [ ] `npm run build` が成功
- [ ] S3 に dist/ の内容がアップロードされている

---

## 4. 疎通確認

### 4-1. PWA アクセス確認
1. ブラウザで `<CloudFrontUrl>` にアクセス
2. ログイン画面が表示される
3. 「🎮 デモアカウントでお試し」をクリック
4. チャット画面（プレースホルダー）にリダイレクトされる

### 4-2. API 疎通確認（curl）

```bash
API_URL=<ApiUrl出力>
CLIENT_ID=<UserPoolClientId出力>

# トークン取得
TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id $CLIENT_ID \
  --auth-parameters USERNAME=demo@example.com,PASSWORD=DemoPass123! \
  --profile share \
  --query 'AuthenticationResult.AccessToken' --output text)

# 注: USER_PASSWORD_AUTH を有効にしていない場合は
# ブラウザのDevToolsからトークンを取得してもOK

# GET /api/settings
curl -H "Authorization: Bearer $TOKEN" $API_URL/api/settings

# PUT /api/settings
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"display_name":"デモ太郎","diary_time":"22:30","monthly_surplus":5000}' \
  $API_URL/api/settings

# GET /api/user/me
curl -H "Authorization: Bearer $TOKEN" $API_URL/api/user/me
```

### 確認項目
- [ ] GET /api/settings → 200 + デフォルト設定が返る
- [ ] PUT /api/settings → 200 + `updated_fields` に設定したフィールドが含まれる
- [ ] GET /api/user/me → 200 + user_id と display_name が返る
- [ ] 認証なしリクエスト → 401

### 4-3. 設定画面 UI 確認
1. ログイン後、下部ナビの「⚙️ 設定」をタップ
2. 各フィールドに入力して「保存する」
3. ページリロード後も値が保持されている
4. 「ログアウト」→ ログイン画面に戻る

---

## 5. template.yaml への追加リソース（U8-A分）

| リソース種別 | 論理名 | 説明 |
|-------------|--------|------|
| Cognito::UserPool | UserPool | ユーザー認証基盤 |
| Cognito::UserPoolClient | UserPoolClient | SPA用クライアント |
| Serverless::HttpApi | HttpApi | REST API (JWT認証付き) |
| Serverless::Function | ApiFunction | API Lambda (256MB/29s) |
| S3::Bucket | FrontendBucket | SPA静的ホスティング |
| S3::BucketPolicy | FrontendBucketPolicy | CloudFront OAC許可 |
| CloudFront::OAC | CloudFrontOAC | S3アクセス制御 |
| CloudFront::Distribution | CloudFrontDistribution | CDN配信 |

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| CORS エラー | API Gateway の AllowOrigins に CloudFront URL を追加 |
| 401 Unauthorized | JWT トークン期限切れ → 再ログイン |
| CloudFront 403 | OAC 設定 + BucketPolicy を確認 |
| SPA リロードで 404 | CloudFront CustomErrorResponses で 403/404 → index.html |
