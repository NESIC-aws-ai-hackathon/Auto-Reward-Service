# Deployment Architecture — Unit 2: リワードちゃんキャラクター

**作成日**: 2026-05-16  
**Unit**: Unit 2 — LINE Bot会話

---

## 1. Unit 2 追加後のシステムアーキテクチャ

```
LINE Platform
    │  POST /webhook
    │  X-Line-Signature: {hmac}
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ AWS ap-northeast-1                                                       │
│                                                                          │
│  ┌──────────────────────────────────────────┐                           │
│  │  API Gateway HTTP API v2 (WebhookApi)    │                           │
│  │  POST /webhook                           │                           │
│  │  Throttle: 100 req/s / burst 200         │                           │
│  └──────────────────────┬───────────────────┘                           │
│                         │                                                │
│                         ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Lambda: WebhookHandlerFunction (256 MB / 10s / python3.13)      │   │
│  │  Role: ArsLambdaRole  Layer: ArsCommonLayer                      │   │
│  │  ENV: TABLE_NAME / DAILY_CHAT_LIMIT=50 / BEDROCK_TEXT_MODEL_ID   │   │
│  │                                                                   │   │
│  │  [1] warmup? → 即 200                                             │   │
│  │  [2] verify_signature → 失敗: 403                                  │   │
│  │  [3] _route_message()                                             │   │
│  │       │                                                           │   │
│  │       ├─ [A] 入力長ガード（> 1000文字） → 固定文言 reply            │   │
│  │       ├─ [B] 日次カウントチェック（DAILY_COUNT）→ 上限: 退場演出    │   │
│  │       │       └─ dynamodb_service.increment_daily_count()         │   │
│  │       │                                                           │   │
│  │       ├─ [C] intent_classifier.classify_intent()                  │   │
│  │       │       └─ bedrock_service.invoke_text(Nova Micro)          │   │──► Amazon Bedrock
│  │       │                                                           │   │    nova-micro-v1:0
│  │       ├─ [D] Intent ディスパッチ                                   │   │
│  │       │       ├─ ONBOARD → onboarding_flow.handle_onboarding()    │   │
│  │       │       │    └─ dynamodb_service (ONBOARDING_STATE)         │──►│   DynamoDB
│  │       │       └─ その他 → character_reply.generate_reply()        │   │   ArsTable
│  │       │               ├─ _infer_emotion() (ルールベース)           │   │
│  │       │               ├─ _load_recent_chat_logs() (Query CHAT)    │──►│
│  │       │               └─ bedrock_service.invoke_text(Nova Micro)  │──►│   Bedrock
│  │       │                                                           │   │
│  │       ├─ [E] line_service.reply_message() ← ここで 3秒タイマー終了│──►│   LINE API
│  │       │                                                           │   │
│  │       └─ [F] Post-Reply 操作（失敗は WARNING のみ）                 │   │
│  │               ├─ _save_chat_log() → PutItem CHAT#{ts}             │──►│   DynamoDB
│  │               ├─ _update_daily_count() → UpdateItem ADD 1         │──►│
│  │               └─ _detect_preferences() → PutItem PREF_MEMORY      │──►│
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ─────── 既存リソース（変更なし）──────────────────────────────────────   │
│                                                                          │
│  ┌──────────────────────────┐  ┌────────────────────────────────────┐   │
│  │  Secrets Manager         │  │  EventBridge Scheduler             │   │
│  │  ars/line                │  │  WarmupWebhookScheduler            │   │
│  │  (LINE secrets)          │  │  rate(5min) → warmup ping          │   │
│  └──────────────────────────┘  └────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  DynamoDB ArsTable (PAY_PER_REQUEST)                             │   │
│  │                                                                   │   │
│  │  Unit 2 アクセスパターン:                                          │   │
│  │  USER#{id} | PROFILE            (GetItem)                        │   │
│  │  USER#{id} | ONBOARDING_STATE   (Get/Put/Delete)                 │   │
│  │  USER#{id} | DAILY_COUNT#{date} (UpdateItem ADD 1)               │   │
│  │  USER#{id} | CHAT#{ISO8601}     (PutItem / Query Limit=5)        │   │
│  │  USER#{id} | PREF_MEMORY#*      (PutItem)                        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  CloudWatch Logs                                                  │   │
│  │  /aws/lambda/WebhookHandlerFunction (保持 30日)                   │   │
│  │  Unit 2 追加ログ: intent_classified / onboarding_step_changed 等  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Unit 2 の template.yaml 変更サマリー

| 変更種別 | リソース / 設定 | 変更内容 |
|---|---|---|
| **追加** | `Globals.Environment.Variables.DAILY_CHAT_LIMIT` | `"50"` |
| **変更** | `WebhookHandlerFunction.Properties.CodeUri` | `src/handlers/` → `src/` |
| **変更** | `WebhookHandlerFunction.Properties.Handler` | `webhook_handler.handler` → `handlers/webhook_handler.handler` |
| 変更なし | `ArsBedrockPolicy` | `bedrock:InvokeModel` は Unit 0 で定義済み |
| 変更なし | `ArsDynamoDBPolicy` | DynamoDB CRUD は Unit 0 で定義済み |
| 変更なし | その他すべてのリソース | — |

---

## 3. リクエストフロー詳細（Unit 2 追加分）

### 通常会話フロー（例: 「疲れた」）

```
1. LINE Platform → POST /webhook (X-Line-Signature 付き)
2. API Gateway → Lambda invoke
3. warmup check: False → 継続
4. verify_signature: OK → 継続
5. route_message("疲れた"):
   a. 入力長チェック: 3文字 < 1000 → OK
   b. daily_count: UpdateItem ADD 1 → count=1 < 50 → OK
   c. classify_intent("疲れた"):
      → Nova Micro 呼び出し (~0.5s) → intent="REWARD", confidence=0.9
   d. dispatch(REWARD) → character_reply.generate_reply():
      → Query CHAT#{recent 5} (~0.05s)
      → infer_emotion("疲れた") → emotion="tired", fatigue_level=3
      → Nova Micro 呼び出し (~0.8s) → reply_text="今日も頑張ったね〜💙..."
   e. reply_message(reply_token, reply_text)  ← ここまで ~1.5s < 3s
   f. PutItem CHAT#{user_ts} (user message)
   g. PutItem CHAT#{bot_ts} (bot reply)
   h. 嗜好検出: キーワードマッチ → なし → スキップ

合計レイテンシ: ~1.5秒（目標 3秒以内 ✅）
```

### オンボーディングフロー（初回ユーザー）

```
1. LINE → "こんにちは"
2. classify_intent → GREET (または CHAT)
3. dispatch → character_reply:
   → GetItem PROFILE: None → PROFILE 未登録
   → GetItem ONBOARDING_STATE: None → オンボーディング未開始
   → onboarding_flow.handle_onboarding(None):
      → PutItem ONBOARDING_STATE {step: WAITING_INCOME}
      → return "はじめまして〜！リワードちゃんだよ🎀 まずざっくり教えて〜。毎月の手取りってどれくらい？"
4. reply_message()
```

---

## 4. Deploy Round 3 の手順

```powershell
# 1. SAM ビルド（python3.13 Linux バイナリ）
sam build --profile share

# 2. SAM デプロイ
sam deploy --profile share

# 3. LINE から疎通確認
# 「疲れた」→ リワードちゃん口調の返答を確認
# ログ確認
aws logs tail "/aws/lambda/WebhookHandlerFunction" --profile share --since 5m
```
