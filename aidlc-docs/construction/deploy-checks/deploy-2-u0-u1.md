# Deploy Round 2 確認手順 — Unit 0 + Unit 1

**対象**: AGENTS.md デプロイ 2 回目  
**内容**: LINE Webhook 疎通 / 署名検証 / エコー応答  
**前提**: Deploy Round 1（Unit 0）が成功済みであること

---

## 1. ビルド・デプロイ

```powershell
cd "Z:\oono.toshiki\OneDrive - Business1\code\AIハッカソン\Auto-Reward-Service"

# SAM ビルド
sam build

# SAM デプロイ（profile=share）
sam deploy --profile share
```

### 期待されるデプロイログ

```
CloudFormation events from changeset:
CREATE_IN_PROGRESS  AWS::Serverless::HttpApi          WebhookApi
CREATE_COMPLETE     AWS::Serverless::HttpApi          WebhookApi
CREATE_IN_PROGRESS  AWS::Serverless::Function         WebhookHandlerFunction
CREATE_COMPLETE     AWS::Serverless::Function         WebhookHandlerFunction
CREATE_IN_PROGRESS  AWS::Logs::LogGroup               WebhookFunctionLogGroup
CREATE_COMPLETE     AWS::Logs::LogGroup               WebhookFunctionLogGroup
CREATE_IN_PROGRESS  AWS::IAM::Role                    SchedulerExecutionRole
CREATE_COMPLETE     AWS::IAM::Role                    SchedulerExecutionRole
CREATE_IN_PROGRESS  AWS::Scheduler::Schedule          WarmupWebhookScheduler
CREATE_COMPLETE     AWS::Scheduler::Schedule          WarmupWebhookScheduler
CREATE_COMPLETE     AWS::CloudFormation::Stack        auto-reward-service
Successfully created/updated stack - auto-reward-service in ap-northeast-1
```

---

## 2. デプロイ後リソース確認

### 2.1 Webhook エンドポイント URL 取得

```powershell
aws cloudformation describe-stacks `
  --stack-name auto-reward-service `
  --profile share `
  --query "Stacks[0].Outputs[?OutputKey=='WebhookApiEndpoint'].OutputValue" `
  --output text
```

期待出力例:
```
https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/webhook
```

### 2.2 Lambda 関数確認

```powershell
aws lambda get-function `
  --function-name WebhookHandlerFunction `
  --profile share `
  --query "Configuration.{State:State,MemorySize:MemorySize,Timeout:Timeout,Runtime:Runtime}" `
  --output json
```

期待出力:
```json
{
  "State": "Active",
  "MemorySize": 256,
  "Timeout": 10,
  "Runtime": "python3.14"
}
```

### 2.3 API Gateway 確認

```powershell
aws apigatewayv2 get-apis `
  --profile share `
  --query "Items[?Name=='auto-reward-service'].{Name:Name,ApiEndpoint:ApiEndpoint,ProtocolType:ProtocolType}" `
  --output json
```

期待出力（Name は SAM 自動生成）:
```json
[{ "ProtocolType": "HTTP", "ApiEndpoint": "https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com" }]
```

### 2.4 EventBridge Scheduler 確認

```powershell
aws scheduler get-schedule `
  --name WarmupWebhookScheduler `
  --profile share `
  --query "{State:State,ScheduleExpression:ScheduleExpression}" `
  --output json
```

期待出力:
```json
{
  "State": "ENABLED",
  "ScheduleExpression": "rate(5 minutes)"
}
```

---

## 3. LINE Developers Console 設定

1. [LINE Developers Console](https://developers.line.biz/) にログイン
2. 対象チャネル → **Messaging API 設定**
3. **Webhook URL** に以下を設定:
   ```
   https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/webhook
   ```
4. **Webhook の利用** を ON に設定
5. **「検証」ボタン** をクリック → `200 OK` が返ることを確認

---

## 4. LINE アプリからの疎通テスト

### 4.1 テキストメッセージ疎通

1. LINE アプリで対象 Bot に「こんにちは」と送信
2. **期待**: 「こんにちは」がエコーで返ってくる

### 4.2 スタンプ疎通

1. LINE アプリで対象 Bot にスタンプを送信
2. **期待**: 以下のいずれかが返ってくる
   - 「スタンプかわいい〜！でもリワードちゃん、文字の方が得意なんだ😊」
   - 「ん〜それはまだ読めないかも！テキストで話しかけてくれると嬉しいな〜」
   - 「おっ、それ気になる！…けど今はテキストだけ対応してるんだ〜ごめんね🥲」

---

## 5. CloudWatch Logs 確認

```powershell
# 最新のログイベントを確認（LINE から送信後）
aws logs tail /aws/lambda/WebhookHandlerFunction `
  --since 10m `
  --profile share
```

確認ポイント:
- `signature_verification_failed` が出ていないこと
- `event_processing_error` が出ていないこと
- ログに LINE ユーザー ID / メッセージ本文が **平文で** 含まれていないこと（PII マスク確認）

---

## 6. 完了チェックリスト

- [ ] `sam deploy` 成功（全 5 リソース CREATE_COMPLETE）
- [ ] `WebhookApiEndpoint` URL 取得済み
- [ ] `WebhookHandlerFunction` State = Active
- [ ] LINE Developers Console の検証 → 200 OK
- [ ] LINE から「こんにちは」→ エコー応答確認
- [ ] LINE からスタンプ → `UNSUPPORTED_REPLIES` のいずれかが返ること確認
- [ ] CloudWatch Logs で PII 非出力確認
