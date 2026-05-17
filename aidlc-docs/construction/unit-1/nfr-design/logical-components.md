# Logical Components — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**Unit**: Unit 1 — LINE Bot基盤

---

## 1. コンポーネント構成図

```
LINE Platform
    │  POST /webhook
    │  X-Line-Signature: {hmac}
    ▼
┌───────────────────────────────────────────┐
│  API Gateway HTTP API v2 (WebhookApi)     │
│                                           │
│  POST /webhook                            │
│  Throttle: 100 req/s / burst 200         │
└───────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────────┐
│  Lambda: WebhookHandlerFunction (256 MB / 10s)            │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  handler()                                          │  │
│  │   │                                                 │  │
│  │   ├─ [1] warmup check → 即 200                      │  │
│  │   ├─ [2] Signature Guard → 失敗 403                 │  │
│  │   ├─ [3] JSON parse events[]                        │  │
│  │   └─ [4] event ループ                               │  │
│  │          │                                          │  │
│  │          ├─ _route_event()                          │  │
│  │          │    ├─ type=="message" → _route_message() │  │
│  │          │    └─ その他 → ログのみ                   │  │
│  │          │                                          │  │
│  │          ├─ _route_message()                        │  │
│  │          │    ├─ text  → echo reply (Unit 1 stub)   │  │
│  │          │    ├─ image → 固定応答 (Unit 1 stub)      │  │
│  │          │    └─ other → UNSUPPORTED_REPLIES から選択│  │
│  │          │                                          │  │
│  │          └─ _handle_error() ←─ 例外発生時           │  │
│  │               └─ ERROR_REPLY を reply               │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  Module-Level Singletons:                                 │
│   _line_service: LineService（コールドスタート後再利用）       │
└───────────────────────────────────────────────────────────┘
    │                          │
    ▼                          ▼
┌─────────────────┐   ┌──────────────────────┐
│ Secrets Manager │   │ LINE Messaging API   │
│ ars/line        │   │ reply_message()      │
│ channel_secret  │   │ (reply token使用)    │
│ access_token    │   └──────────────────────┘
└─────────────────┘

EventBridge Scheduler (5分毎)
    │  {"source": "warmup"}
    └──► WebhookHandlerFunction (warmup ping)
```

---

## 2. コンポーネント一覧

### 2.1 AWS リソース

| コンポーネント名 | 種別 | Unit | 役割 |
|--------------|------|------|------|
| `WebhookApi` | API Gateway HTTP API v2 | Unit 1 新規 | LINE Webhook エンドポイント（POST /webhook） |
| `WebhookHandlerFunction` | Lambda | Unit 1 新規 | Webhook 受信・検証・ルーティング |
| `WarmupWebhookScheduler` | EventBridge Scheduler | Unit 1 新規 | 5 分毎ウォームアップ ping |
| `ArsCommonLayer` | Lambda Layer | Unit 0 共有 | line-bot-sdk / powertools / pydantic |
| `ArsLambdaRole` | IAM Role | Unit 0 共有 | Lambda 実行ロール（基底） |

### 2.2 Lambda 内部モジュール

| モジュール | 場所 | 役割 |
|---------|------|------|
| `webhook_handler.py` | `src/handlers/` | Lambda ハンドラ（Unit 1 追加） |
| `line_service.py` | Layer `services/` | LINE API ラッパー（Unit 0 実装済み） |
| `secrets.py` | Layer `utils/` | Secrets Manager キャッシュ（Unit 0 実装済み） |
| `logger.py` | Layer `utils/` | PIIMaskingLogger（Unit 0 実装済み） |
| `exceptions.py` | Layer `utils/` | LineServiceError 等（Unit 0 実装済み） |

---

## 3. データフロー

### 3.1 正常テキストメッセージ受信

```
LINE Platform
  │  POST /webhook (text message)
  │  X-Line-Signature: xxxxxxxx
  ▼
API Gateway
  │  スロットリング確認 → OK
  ▼
WebhookHandlerFunction
  │  [1] warmup? No
  │  [2] verify_signature() → OK
  │  [3] parse body → events[0]
  │  [4] _route_event(event)
  │       └─ type="message", message.type="text"
  │           └─ _route_message(event)
  │               └─ [Unit 1 stub] echo reply
  │                   └─ LineService.reply_message(replyToken, text)
  ▼
LINE Platform ← TextMessage(ユーザーのテキストをエコー)
  ▼
return {"statusCode": 200, "body": "OK"}
```

### 3.2 未対応メッセージ受信（スタンプ等）

```
LINE Platform → API Gateway → WebhookHandlerFunction
  │  message.type = "sticker"
  ▼
  _route_message()
   └─ random.choice(UNSUPPORTED_REPLIES)
       └─ LineService.reply_message(replyToken, text)
LINE Platform ← TextMessage(ランダム選択テキスト)
return 200
```

### 3.3 署名検証失敗

```
不正リクエスト → API Gateway → WebhookHandlerFunction
  │  verify_signature() → False
  ▼
return {"statusCode": 403, "body": "Forbidden"}
（LINE には何も送らない）
```

### 3.4 ウォームアップ ping

```
EventBridge Scheduler (5分毎)
  │  {"source": "warmup"}
  ▼
WebhookHandlerFunction
  │  event.get("source") == "warmup" → True
  ▼
return {"statusCode": 200, "body": "warm"}
（即座に返却、LineService 初期化なし）
```

---

## 4. IAM 権限設計

### WebhookHandlerFunction に必要な権限（Unit 1 時点）

| アクション | リソース | 理由 |
|----------|---------|------|
| `secretsmanager:GetSecretValue` | `arn:aws:secretsmanager:*:*:secret:ars/line*` | LINE チャネルシークレット・アクセストークン取得 |

> **Note**: DynamoDB アクセス権限は Unit 2 で追加。Unit 1 時点では不要。

---

## 5. 環境変数

Unit 0 Globals で設定済みの環境変数を WebhookHandlerFunction でも使用。

| 変数名 | 値 | 用途 |
|--------|-----|------|
| `LINE_SECRET_NAME` | `ars/line` | Secrets Manager キー名 |
| `LOG_LEVEL` | `INFO` | ロガー設定 |
| `TABLE_NAME` | `ArsTable` | Unit 2 以降で使用（Unit 1 では未使用） |
