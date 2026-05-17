# Logical Components — Unit 2: リワードちゃんキャラクター

**作成日**: 2026-05-16  
**Unit**: Unit 2 — LINE Bot会話

---

## 1. コンポーネント構成図

```
LINE Platform
    │  POST /webhook
    ▼
┌───────────────────────────────────────────┐
│  API Gateway HTTP API v2 (WebhookApi)     │
│  POST /webhook / Throttle: 100 req/s      │
└───────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Lambda: WebhookHandlerFunction (256 MB / 10s)                      │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  handler()                                                  │    │
│  │   ├─ [1] warmup check → 即 200                              │    │
│  │   ├─ [2] Signature Guard → 失敗 403                         │    │
│  │   └─ [3] イベントループ（Error Containment）                  │    │
│  │          │                                                  │    │
│  │          └─ _route_message()                                │    │
│  │               │                                             │    │
│  │          ┌────▼──── [A] 入力長ガード（> 1000文字）            │    │
│  │          │    │      └─ 固定文言 reply → return              │    │
│  │          │    │                                             │    │
│  │          │    ├── [B] DAILY_COUNT チェック（BR-2-12）         │    │
│  │          │    │      └─ 上限超過 → 退場演出 reply → return    │    │
│  │          │    │                                             │    │
│  │          │    ├── [C] intent_classifier.classify()          │    │
│  │          │    │      └─ Nova Micro 呼び出し → IntentResult   │    │
│  │          │    │                                             │    │
│  │          │    ├── [D] Intent ディスパッチ                    │    │
│  │          │    │      ├─ ONBOARD  → onboarding_flow          │    │
│  │          │    │      ├─ EXPENSE  → (Unit 3 stub)            │    │
│  │          │    │      ├─ REWARD   → (Unit 5 stub)            │    │
│  │          │    │      └─ その他   → character_reply          │    │
│  │          │    │                                             │    │
│  │          │    ├── [E] reply_message() ← ここまで 3 秒以内    │    │
│  │          │    │                                             │    │
│  │          │    └── [F] Post-Reply 操作（失敗は WARNING のみ）  │    │
│  │          │           ├─ _save_chat_log()                    │    │
│  │          │           ├─ _update_daily_count()               │    │
│  │          │           └─ _detect_preferences()               │    │
│  └──────────┴───────────────────────────────────────────────── ┘    │
│                                                                     │
│  Module-Level Singletons:                                           │
│   _line_service: LineService                                        │
│   _dynamodb_service: DynamoDBService                                │
│   _bedrock_service: BedrockService                                  │
└─────────────────────────────────────────────────────────────────────┘
         │              │                   │
         ▼              ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌───────────────────────────────┐
│ Secrets Mgr  │  │ LINE API     │  │ Amazon Bedrock                │
│ ars/line     │  │ reply_msg    │  │ amazon.nova-micro-v1:0        │
└──────────────┘  └──────────────┘  │  ├─ Intent 分類               │
                                    │  └─ キャラクター応答生成        │
         │                          └───────────────────────────────┘
         ▼
┌────────────────────────────────────────────────────────────┐
│ DynamoDB ArsTable (PAY_PER_REQUEST)                        │
│                                                            │
│  PK=USER#{id}  SK=PROFILE          ← GetItem              │
│  PK=USER#{id}  SK=ONBOARDING_STATE ← Get/Put/Delete       │
│  PK=USER#{id}  SK=DAILY_COUNT#{d}  ← UpdateItem (ADD 1)   │
│  PK=USER#{id}  SK=CHAT#{timestamp} ← PutItem (TTL 30日)   │
│  PK=USER#{id}  SK=PREF_MEMORY#*    ← PutItem              │
└────────────────────────────────────────────────────────────┘

EventBridge Scheduler (5分毎)
    │  {"source": "warmup"}
    └─► WebhookHandlerFunction
```

---

## 2. 新規ハンドラーコンポーネント

### 2.1 intent_classifier.py

| 項目 | 内容 |
|------|------|
| **責務** | テキストメッセージを Intent 種別に分類する |
| **入力** | `str`（ユーザーメッセージ）|
| **出力** | `IntentClassificationResult`（intent, confidence） |
| **依存** | `bedrock_service.invoke_text()`, `intent_prompt.py` |
| **フォールバック** | Bedrock 失敗時 → `intent="UNKNOWN", confidence=0.0` |

```
classify_intent(text: str) -> IntentClassificationResult
    │
    ├── build_intent_prompt(text)  ← intent_prompt.py
    ├── bedrock_service.invoke_text(prompt, system_prompt)
    │      └── BedrockServiceError → return UNKNOWN
    └── _parse_intent_response(raw_json)
           └── JSON パース失敗 → return UNKNOWN
```

### 2.2 character_reply.py

| 項目 | 内容 |
|------|------|
| **責務** | Intent と会話コンテキストに基づいてキャラクター応答を生成する |
| **入力** | `CharacterReplyContext`（intent, user_message, recent_chat_logs, emotion_state 等） |
| **出力** | `str`（リワードちゃんの返答テキスト） |
| **依存** | `bedrock_service.invoke_text()`, `character_prompts.py` |
| **フォールバック** | 2.1 節のフォールバックチェーンパターンを適用 |

```
generate_reply(ctx: CharacterReplyContext) -> str
    │
    ├── _infer_emotion(ctx.user_message)  ← ルールベース感情推定
    ├── _load_recent_chat_logs(ctx.user_id, limit=5)  ← DynamoDB Query
    ├── build_character_prompt(ctx)  ← character_prompts.py
    ├── bedrock_service.invoke_text(prompt, system_prompt)
    │      └── BedrockServiceError → FALLBACK_MESSAGES[ctx.intent]
    └── reply_text
```

### 2.3 onboarding_flow.py

| 項目 | 内容 |
|------|------|
| **責務** | 初回登録の状態機械。月収→固定費→ご褒美枠→ボーナス→誕生日の順で会話を進める |
| **入力** | `user_id: str`, `message_text: str`, `current_state: OnboardingState | None` |
| **出力** | `str`（次のステップの質問文または完了メッセージ）|
| **依存** | `dynamodb_service`（ONBOARDING_STATE/PROFILE/FIXED_COSTS の get/put/delete） |
| **状態遷移** | WAITING_INCOME → WAITING_FIXED_COSTS → CONFIRM_REWARD_BUDGET → WAITING_BONUS → WAITING_BIRTHDAY → COMPLETED |

```
handle_onboarding(user_id, text, state) -> str
    │
    ├── state is None → 初回 → 月収質問文を返す + PutItem ONBOARDING_STATE
    ├── WAITING_INCOME → 月収を解析 → 次ステップへ
    ├── WAITING_FIXED_COSTS → 固定費を解析 → ご褒美枠算出 → 確認質問
    ├── CONFIRM_REWARD_BUDGET → WAITING_BONUS へ
    ├── WAITING_BONUS → ボーナス解析（スキップ可） → WAITING_BIRTHDAY へ
    ├── WAITING_BIRTHDAY → 誕生日解析（スキップ可） → COMPLETED へ
    └── COMPLETED → DeleteItem ONBOARDING_STATE + PutItem PROFILE → 完了メッセージ
```

---

## 3. 新規プロンプトコンポーネント

### 3.1 intent_prompt.py

| 項目 | 内容 |
|------|------|
| **責務** | Intent 分類プロンプトのテンプレートを提供する |
| **定数** | `INTENT_SYSTEM_PROMPT`（Intent 種別定義 + プロンプトインジェクション防御） |
| **関数** | `build_intent_prompt(user_message: str) -> str`（`<user_message>` タグで囲む） |
| **Intent 種別** | EXPENSE / REWARD / GREET / CHAT / ONBOARDING / CONFIRM_YES / CONFIRM_NO / UNKNOWN |

### 3.2 character_prompts.py

| 項目 | 内容 |
|------|------|
| **責務** | キャラクター応答生成プロンプトのテンプレートを提供する |
| **定数** | `CHARACTER_SYSTEM_PROMPTS`（口調別: friendly / polite / devilish） |
| **関数** | `build_character_prompt(ctx: CharacterReplyContext) -> str` |
| **コンテキスト注入** | 直近 5 件の CHAT ログ / 感情状態 / Intent / オンボーディングステップ |

---

## 4. 新規 DynamoDB アクセスパターン（Unit 2）

| # | アクセスパターン | 操作 | Key | 呼び出し元 |
|---|---|---|---|---|
| 1 | プロファイル取得 | GetItem | PK=USER#{id}, SK=PROFILE | `onboarding_flow.py`, `character_reply.py` |
| 2 | オンボーディング状態取得 | GetItem | PK=USER#{id}, SK=ONBOARDING_STATE | `webhook_handler.py` |
| 3 | オンボーディング状態更新 | PutItem | PK=USER#{id}, SK=ONBOARDING_STATE | `onboarding_flow.py` |
| 4 | オンボーディング状態削除 | DeleteItem | PK=USER#{id}, SK=ONBOARDING_STATE | `onboarding_flow.py`（完了時） |
| 5 | 日次カウント増加 | UpdateItem (ADD) | PK=USER#{id}, SK=DAILY_COUNT#{d} | `webhook_handler.py` |
| 6 | CHAT ログ保存 | PutItem | PK=USER#{id}, SK=CHAT#{ISO8601} | `webhook_handler.py`（Reply 後） |
| 7 | 直近 CHAT ログ取得 | Query (begins_with CHAT, Limit=5) | PK=USER#{id} | `character_reply.py` |
| 8 | 嗜好メモリ保存 | PutItem | PK=USER#{id}, SK=PREF_MEMORY#{cat}#{kw} | `webhook_handler.py`（Reply 後） |

---

## 5. セキュリティコンポーネント

| コンポーネント | 実装箇所 | 機能 |
|---|---|---|
| 入力長ガード | `webhook_handler._route_message()` 入口 | 1,000 文字超で即 return |
| プロンプトサンドボックス | `intent_prompt.py`, `character_prompts.py` | `<user_message>` タグ境界 |
| 署名検証 | `webhook_handler.handler()` 先頭（Unit 1 継承） | 不正リクエスト 403 |
| PII フィルタ | `logger.py`（Unit 0 継承） | ユーザーメッセージ本文のログ出力禁止 |
