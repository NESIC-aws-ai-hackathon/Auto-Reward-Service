# U8 デプロイ＆動作確認手順書

## 前提条件

- AWS CLI / SAM CLI インストール済み
- プロファイル `share` 設定済み（ap-northeast-1）
- 既存 `ArsTable` (DynamoDB) がデプロイ済み
- Node.js 18+ / Python 3.13+ インストール済み
- Amazon Bedrock で Nova Sonic (`amazon.nova-sonic-v1:0`) が有効化済み（us-east-1）
- Amazon Bedrock で Claude 3.5 Sonnet が有効化済み（us-east-1）

---

## 1. VAPID鍵の生成

Push通知に必要なVAPID鍵ペアを生成する（初回のみ）:

```bash
# Node.js の web-push パッケージで生成
npx web-push generate-vapid-keys
```

出力される `Public Key` と `Private Key` を控えておく。

---

## 2. SAM デプロイ

```bash
cd u8

# ビルド
sam build

# デプロイ（パラメータ上書き）
sam deploy \
  --profile share \
  --parameter-overrides \
    "Env=dev" \
    "ArsTableName=ArsTable" \
    "VapidPrivateKey=<生成したPrivate Key>" \
    "VapidPublicKey=<生成したPublic Key>" \
    "VapidSubject=mailto:admin@example.com"
```

### 確認ポイント
- [x] CloudFormation スタック `ars-u8-pwa` が `CREATE_COMPLETE` / `UPDATE_COMPLETE`
- [x] リソース作成確認:
  - Cognito User Pool
  - API Gateway HTTP API
  - API Gateway WebSocket API（音声ゲートウェイ）
  - Lambda `ars-u8-api-dev`
  - Lambda `ars-u8-voice-gw-dev`
  - Lambda `ars-u8-analysis-dev`
  - SQS `ars-u8-analysis-queue-dev`
  - S3 バケット（フロントエンドホスティング）
  - CloudFront ディストリビューション
  - EventBridge ルール（diary + reprocess）

---

## 3. デモユーザー作成

```bash
# Cognito User Pool ID を取得
USER_POOL_ID=$(aws cognito-idp list-user-pools --max-results 10 --profile share \
  --query "UserPools[?Name=='ars-u8-user-pool-dev'].Id" --output text)

# デモユーザー作成
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username demo@example.com \
  --user-attributes Name=email,Value=demo@example.com Name=email_verified,Value=true \
  --temporary-password TempPass123! \
  --profile share

# パスワードを恒久化
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username demo@example.com \
  --password DemoPass123! \
  --permanent \
  --profile share
```

---

## 4. フロントエンドビルド＆デプロイ

```bash
cd u8/frontend

# .env 作成
cat > .env.production << EOF
VITE_API_URL=https://<API Gateway URL>
VITE_VOICE_WS_URL=wss://<WebSocket API URL>
VITE_COGNITO_USER_POOL_ID=<UserPoolId>
VITE_COGNITO_CLIENT_ID=<UserPoolClientId>
VITE_VAPID_PUBLIC_KEY=<生成したPublic Key>
EOF

# ビルド
npm install
npm run build

# S3にアップロード
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name ars-u8-pwa --profile share \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucket'].OutputValue" --output text)

aws s3 sync dist/ s3://$BUCKET_NAME/ --delete --profile share

# CloudFront キャッシュ無効化
DIST_ID=$(aws cloudformation describe-stacks --stack-name ars-u8-pwa --profile share \
  --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistribution'].OutputValue" --output text)

aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*" --profile share
```

---

## 5. 動作確認シナリオ

### 5-1. PWA基盤 + 認証（U8-A）

| # | 操作 | 期待結果 |
|---|------|---------|
| 1 | CloudFront URL にアクセス | ログイン画面が表示される |
| 2 | demo@example.com / DemoPass123! でログイン | チャット画面に遷移する |
| 3 | 画面下部に5タブナビが表示 | チャット/ダッシュボード/日記/ご褒美/設定 |
| 4 | 設定画面で表示名を「テスト太郎」に変更 | 保存成功メッセージ |
| 5 | PWAとしてインストール可能（Chrome: アドレスバーのインストールアイコン） | ホーム画面に追加できる |

### 5-2. 音声チャット（U8-B）

| # | 操作 | 期待結果 |
|---|------|---------|
| 1 | チャット画面で「話しかける」ボタンをタップ | マイクアクセス許可ダイアログ |
| 2 | 許可して話しかける「今日は仕事が大変だった」 | ふれまーるちゃんが音声で応答する（Nova Sonic） |
| 3 | 会話中にTranscriptが画面に表示される | ユーザーとアシスタントの吹き出し |
| 4 | 「おわる」ボタンで会話終了 | セッション終了表示 |
| 5 | テキスト入力で「疲れた」と送信 | テキストで返答（フォールバックモード） |
| 6 | DynamoDB確認: `VOICE_SESSION#` | voice_provider=bedrock_nova_sonic, status=completed |
| 7 | DynamoDB確認: `CONVERSATION_TURN#` | source=pwa_sonic_voice, 会話内容が保存 |
| 8 | DynamoDB確認: `ANALYSIS_JOB#` | status=queued → completed |

```bash
# DynamoDB 確認コマンド例
aws dynamodb query \
  --table-name ArsTable \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "USER#<user_id>"}}' \
  --profile share \
  --query "Items[?begins_with(SK.S, 'VOICE_SESSION#')]"
```

### 5-3. ライフログ + 日記（U8-C）

| # | 操作 | 期待結果 |
|---|------|---------|
| 1 | 会話終了後、SQSキューを確認 | メッセージが処理される |
| 2 | CloudWatch Logs: `ars-u8-analysis-dev` | process_conversation 正常完了 |
| 3 | DynamoDB確認: `LIFE_LOG#2026-05-24#` | 会話から抽出されたライフログ |
| 4 | 手動でEventBridge diary実行 | 日記サマリが生成される |
| 5 | DynamoDB確認: `DAILY_FUREMARU_SUMMARY#2026-05-24` | ふれまーるちゃん口調の日記 |

```bash
# EventBridge ルールの手動実行（diary生成テスト）
aws lambda invoke \
  --function-name ars-u8-analysis-dev \
  --payload '{"trigger": "scheduled_diary"}' \
  --cli-binary-format raw-in-base64-out \
  --profile share \
  output.json && cat output.json
```

### 5-4. ストレス判定 + 回復提案（U8-D）

| # | 操作 | 期待結果 |
|---|------|---------|
| 1 | 会話終了後しばらく待つ | ストレス判定が実行される |
| 2 | DynamoDB確認: `STRESS_SUMMARY#2026-05-24` | stress_level: 1-5, factors, mood |
| 3 | PWA「ご褒美」タブをタップ | 回復案画面が表示される |
| 4 | ストレスバッジ（Lv.X）が表示 | ストレスレベルに応じた色 |
| 5 | 0円回復案カードが2-3枚表示 | ふれまーるちゃん口調のテキスト |
| 6 | 「やってみる」をタップ | 「えらい！お疲れ様♪」表示 |
| 7 | DynamoDB確認: `REWARD_PERMIT#` | レコードが作成されている |
| 8 | 再度開いて「今日はいいや」をタップ | `REWARD_SKIP#` が作成 |

### 5-5. ダッシュボード + 日記UI（U8-E）

| # | 操作 | 期待結果 |
|---|------|---------|
| 1 | 「ダッシュボード」タブをタップ | ダッシュボード画面表示 |
| 2 | 甘やかし枠のプログレスバー | 残額/予算が正しく表示 |
| 3 | ストレスレベル表示 | 今日のストレス（レベル+気分） |
| 4 | 最近の支出リスト | 会話から抽出された支出が表示 |
| 5 | 「日記」タブをタップ | 日記一覧が表示される |
| 6 | 日記カードをタップ | 全文が展開表示される |
| 7 | 日記がない場合 | 「まだ日記がないよ。話しかけたら書いてあげるね♪」 |

### 5-6. Push通知（U8-C/D統合）

| # | 操作 | 期待結果 |
|---|------|---------|
| 1 | 設定画面で通知を有効化 | ブラウザ通知許可ダイアログ |
| 2 | 通知を許可 | Push購読がサーバーに保存される |
| 3 | DynamoDB確認: `PUSH_SUBSCRIPTION#` | endpoint, keys が保存 |
| 4 | 日記生成後 | Push通知「📖 今日の日記ができたよ」が届く |
| 5 | ストレスレベル3以上の場合 | Push通知「💆 ちょっと休憩しない？」が届く |

---

## 6. E2Eデモシナリオ（一連の流れ）

以下の手順を上から順に実行し、全機能が連携動作することを確認:

1. **ログイン** → demo@example.com でサインイン
2. **設定** → 表示名「テスト太郎」、甘やかし枠「10000」円、通知ON
3. **音声会話** → 「今日は仕事が忙しくて疲れた。お昼にカフェでコーヒー飲んだ、450円。でも美味しかった」
4. **会話終了** → セッション終了
5. **待機（30秒〜1分）** → SQS → Analysis Lambda 実行
6. **DynamoDB確認**:
   - `LIFE_LOG#2026-05-24#000` — category: 活動, content: 仕事が忙しい
   - `LIFE_LOG#2026-05-24#001` — category: 支出, content: カフェでコーヒー
   - `EXPENSE#` — amount: 450
   - `STRESS_SUMMARY#2026-05-24` — stress_level: 3程度
7. **ご褒美タブ** → 回復案カードが表示される（0円回復案あり）
8. **ダッシュボード** → 残り ¥9,550 / ¥10,000、支出にコーヒー450円
9. **日記生成**（手動Lambda実行 or 22:00 JST自動）
10. **日記タブ** → ふれまーるちゃんの日記が表示される
11. **Push通知** → 「📖 今日の日記ができたよ」通知を受信

---

## 7. トラブルシューティング

| 症状 | 確認箇所 | 対処 |
|------|---------|------|
| ログインできない | Cognito User Pool | デモユーザーのステータス確認。FORCE_CHANGE_PASSWORD なら admin-set-user-password 再実行 |
| 音声が応答しない | CloudWatch: ars-u8-voice-gw-dev | Bedrock Nova Sonic モデルアクセス有効化確認。us-east-1へのアクセス権限確認 |
| ライフログが生成されない | CloudWatch: ars-u8-analysis-dev | Bedrock us-east-1 へのアクセス権限確認。Claude Sonnet モデルアクセス有効化 |
| Push通知が届かない | DynamoDB: PUSH_SUBSCRIPTION# | VAPID鍵の一致確認。Service Worker登録状態確認 |
| ダッシュボード表示されない | ブラウザDevTools Network | API レスポンスの中身確認。CORS設定確認 |
| CORS エラー | API Gateway 設定 | FrontendOrigin パラメータにCloudFront URLを設定 |

---

## 8. クリーンアップ

```bash
# スタック削除（S3バケットは先に空にする必要あり）
aws s3 rm s3://$BUCKET_NAME --recursive --profile share
sam delete --stack-name ars-u8-pwa --profile share
```
