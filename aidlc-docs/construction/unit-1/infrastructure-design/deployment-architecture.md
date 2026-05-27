# Deployment Architecture — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**Unit**: Unit 1 — LINE Bot基盤

---

## 1. Unit 1 追加後のシステムアーキテクチャ

```
LINE Platform
    │  POST /webhook
    │  X-Line-Signature: {hmac}
    │
    ▼
┌────────────────────────────────────────────────────────────────────┐
│ AWS ap-northeast-1                                                  │
│                                                                     │
│  ┌──────────────────────────────────────────┐                      │
│  │  API Gateway HTTP API v2 (WebhookApi)    │                      │
│  │  POST /webhook                           │                      │
│  │  Throttle: 100 req/s / burst 200         │                      │
│  └──────────────────────┬───────────────────┘                      │
│                         │                                           │
│                         ▼                                           │
│  ┌──────────────────────────────────────────┐                      │
│  │  Lambda: WebhookHandlerFunction          │                      │
│  │  256 MB / 10s / python3.14               │                      │
│  │  Role: ArsLambdaRole                     │                      │
│  │  Layer: ArsCommonLayer                   │                      │
│  │                                          │                      │
│  │  [1] warmup? → 即 200                    │                      │
│  │  [2] verify_signature → 失敗: 403         │◄──┐                 │
│  │  [3] route_event → route_message         │   │ 5分毎            │
│  │  [4] reply_message / error fallback      │   │                  │
│  └────────────┬─────────────────────────────┘   │                  │
│               │                                  │                  │
│               ▼                                  │                  │
│  ┌────────────────────┐   ┌─────────────────────┴──────────────┐  │
│  │  LINE Messaging API │   │  EventBridge Scheduler             │  │
│  │  Reply / Push       │   │  WarmupWebhookScheduler            │  │
│  └────────────────────┘   │  rate(5min) → {"source":"warmup"}  │  │
│                            │  Role: SchedulerExecutionRole      │  │
│                            └────────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────┐  ┌─────────────────────────────────────┐  │
│  │  Secrets Manager    │  │  CloudWatch Logs                    │  │
│  │  ars/line           │  │  /aws/lambda/WebhookHandlerFunction │  │
│  │  channel_secret     │  │  保持: 30日                         │  │
│  │  access_token       │  └─────────────────────────────────────┘  │
│  └─────────────────────┘                                           │
│                                                                     │
│  ─────── Unit 0 既存リソース（変更なし）───────                       │
│  ArsTable (DynamoDB)  ArsCommonLayer  ArsLambdaRole                │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. リクエストフロー詳細

### 2.1 正常テキストメッセージ（Unit 1 スタブ：エコー応答）

```
LINE App → LINE Platform
             │ POST https://{api-id}.execute-api.ap-northeast-1.amazonaws.com/webhook
             │ X-Line-Signature: {hmac-sha256}
             ▼
         API Gateway (WebhookApi)
             │ スロットリング確認 (100 req/s) → OK
             │ Lambda Proxy Integration
             ▼
         WebhookHandlerFunction
             │ warmup? No
             │ verify_signature() → OK
             │ parse events[0].type = "message"
             │ _route_event → _route_message
             │ message.type = "text"
             │ [Unit 1 stub] echo: reply_message(replyToken, [TextMessage(text)])
             ▼
         LINE Messaging API (Reply API)
             │ HTTP 200
             ▼
         LINE Platform → LINE App (メッセージ表示)
         
         WebhookHandlerFunction → API Gateway
             │ {"statusCode": 200, "body": "OK"}
             ▼
         LINE Platform (Webhook レスポンス受信)
```

### 2.2 署名検証失敗

```
不正リクエスト
    │ POST /webhook (X-Line-Signature なし or 不正)
    ▼
API Gateway → WebhookHandlerFunction
    │ verify_signature() → False
    ▼
{"statusCode": 403, "body": "Forbidden"}
    └─ LINE Platform / 攻撃者 → 403 受信
```

### 2.3 ウォームアップ

```
EventBridge Scheduler (5分毎)
    │ InvokeFunction (SchedulerExecutionRole)
    │ Payload: {"source": "warmup"}
    ▼
WebhookHandlerFunction
    │ event.get("source") == "warmup" → True
    ▼
{"statusCode": 200, "body": "warm"}
（LineService 初期化なし・Secrets 呼び出しなし）
```

---

## 3. SAM スタック差分（Unit 0 → Unit 1）

### 追加リソース

| 論理 ID | 種別 | 変更種別 |
|--------|------|---------|
| `WebhookApi` | AWS::Serverless::HttpApi | **追加** |
| `WebhookHandlerFunction` | AWS::Serverless::Function | **追加** |
| `WarmupWebhookScheduler` | AWS::Scheduler::Schedule | **追加** |
| `SchedulerExecutionRole` | AWS::IAM::Role | **追加** |
| `WebhookFunctionLogGroup` | AWS::Logs::LogGroup | **追加** |

### 変更なしリソース

| 論理 ID | 種別 | 理由 |
|--------|------|------|
| `ArsTable` | DynamoDB | Unit 1 でアクセスしない |
| `ArsCommonLayer` | Lambda Layer | Layer 自体は変更なし |
| `ArsLambdaRole` | IAM Role | `ars/line` 権限は既存ポリシーに含まれる |

### Outputs 追加

```yaml
Outputs:
  WebhookApiEndpoint:
    Description: LINE Webhook URL (POST /webhook)
    Value: !Sub "https://${WebhookApi}.execute-api.${AWS::Region}.amazonaws.com/webhook"
```

---

## 4. デプロイ手順（Deploy Round 2）

AGENTS.md に従い Unit 0 + Unit 1 の **2 回目デプロイ**として実施。

```powershell
# ビルド
sam build

# デプロイ
sam deploy --profile share
```

### デプロイ後の疎通確認

```powershell
# 1. スタックステータス確認
aws cloudformation describe-stacks `
  --stack-name auto-reward-service `
  --profile share `
  --query "Stacks[0].StackStatus"

# 2. API Gateway エンドポイント URL 取得
aws cloudformation describe-stacks `
  --stack-name auto-reward-service `
  --profile share `
  --query "Stacks[0].Outputs[?OutputKey=='WebhookApiEndpoint'].OutputValue" `
  --output text

# 3. Lambda 存在確認
aws lambda get-function `
  --function-name WebhookHandlerFunction `
  --profile share `
  --query "Configuration.{State:State, MemorySize:MemorySize, Timeout:Timeout}"

# 4. LINE Developers Console でエンドポイント URL を Webhook URL に設定
# → 「検証」ボタンで HTTP 200 を確認
```

### LINE からの疎通テスト

1. LINE Developers Console の Webhook URL に `{WebhookApiEndpoint}` を設定
2. LINE アプリから「こんにちは」と送信
3. エコー応答（「こんにちは」が返ってくる）を確認
4. スタンプ送信 → `UNSUPPORTED_REPLIES` のいずれかが返ることを確認
