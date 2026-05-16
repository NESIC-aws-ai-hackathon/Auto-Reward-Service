# サービス定義 — オートリワードサービス（v2）

**改訂日**: 2026-05-15 / コンセプト変更後版

---

## AWS SAM リソース一覧

| リソース名 | 種別 | Unit | 記述 |
|---------|------|------|---------|
| `WebhookHandlerFunction` | Lambda | Unit 1 | LINE Webhook受信・Router |
| `IntentClassifierFunction` | Lambda | Unit 2 | Intent分類（Nova Micro） |
| `CharacterReplyFunction` | Lambda | Unit 2 | リワードちゃんReply生成 |
| `OnboardingFlowFunction` | Lambda | Unit 2 | 初回登録フロー |
| `ExpenseExtractorFunction` | Lambda | Unit 3 | 支出抽出・確認フロー |
| `ReceiptAnalyzerFunction` | Lambda | Unit 3 | レシート画像解析（Nova Lite） |
| `RewardPoolUpdaterFunction` | Lambda | Unit 4 | 日次バッチ（楽天API→DynamoDB） |
| `RewardProposalFunction` | Lambda | Unit 5 | ご褒美候補マッチング |
| `PushNotifierFunction` | Lambda | Unit 6 | Push通知送信 |
| `LiffApiFunction` | Lambda | Unit 7 | LIFF用API |
| `WebhookApi` | API Gateway | Unit 1 | LINE Webhookエンドポイント |
| `LiffApi` | API Gateway | Unit 7 | LIFF用エンドポイント |
| `ArsTable` | DynamoDB | Unit 0 | シングルテーブル（全エンティティ） |
| `RewardPoolScheduler` | EventBridge Scheduler | Unit 4 | 日次候補プール更新 |
| `PushNotifierScheduler` | EventBridge Scheduler | Unit 6 | 1日1回Push送信 |

---

## Lambda 関数設定

| Lambda | メモリ | タイムアウト | 備考 |
|--------|-------|-----------|------|
| `WebhookHandlerFunction` | 256 MB | 10s | LINE応答3秒以内を目指すが、内部処理時間を含むためマージン確保 |
| `IntentClassifierFunction` | 256 MB | 10s | Bedrock呼び出し含む |
| `CharacterReplyFunction` | 256 MB | 10s | Bedrock呼び出し含む |
| `OnboardingFlowFunction` | 256 MB | 10s | Bedrock呼び出し含む |
| `ExpenseExtractorFunction` | 256 MB | 10s | Bedrock呼び出し含む |
| `ReceiptAnalyzerFunction` | 512 MB | 60s | 画像処理のためメモリ増。3秒超は非同期化 |
| `RewardPoolUpdaterFunction` | 512 MB | 300s | バッチ処理。全ユーザー分を処理 |
| `RewardProposalFunction` | 256 MB | 10s | Bedrock呼び出し含む |
| `PushNotifierFunction` | 256 MB | 300s | バッチ処理。複数ユーザーへPush |
| `LiffApiFunction` | 256 MB | 10s | DynamoDB読み書き + Google Calendar OAuth処理 |

---

## DynamoDB スキーマ（詳細）

### テーブル設計

| 項目 | 値 |
|------|-----|
| テーブル名 | `ArsTable` |
| 課金モード | PAY_PER_REQUEST（オンデマンド） |
| パーティションキー (PK) | `pk` (String) |
| ソートキー (SK) | `sk` (String) |
| 暗号化 | AWS管理キー（デフォルト） |
| TTL属性 | `expires_at`（CHAT・PENDING_EXPENSEの自動削除用） |

### GSI（グローバルセカンダリインデックス）

| GSI名 | PK | SK | 用途 |
|--------|-----|-----|------|
| `GSI1` | `gsi1pk` (String) | `gsi1sk` (String) | Push対象ユーザー検索（gsi1pk=`STATUS#ACTIVE`, gsi1sk=`PUSH_LAST#{date}`） |

### エンティティスキーマ

| PK | SK プレフィックス | 主な属性 | TTL |
|----|-----------|----------|-----|
| `USER#{lineUserId}` | `PROFILE#` | name, monthly_income, bonus, monthly_reward_limit, onboarding_done, onboarding_step, tone_style, created_at, updated_at | — |
| `USER#{lineUserId}` | `FIXED_COSTS#` | items: [{name, amount}], total, updated_at | — |
| `USER#{lineUserId}` | `CHAT#{isoTimestamp}` | role (user/assistant), text, intent, emotion | 30日 |
| `USER#{lineUserId}` | `LIFELOG#{isoTimestamp}` | emotion, fatigue_level, inferred_from, context | 90日 |
| `USER#{lineUserId}` | `PENDING_EXPENSE#` | item, amount, ars_category, confidence, message_id, status (pending/confirmed/rejected) | 24時間 |
| `USER#{lineUserId}` | `EXPENSE#{isoTimestamp}` | item, amount, ars_category, store, confirmed_at, source (chat/receipt) | — |
| `USER#{lineUserId}` | `PREF_MEMORY#` | preferred_categories[], liked_items[], avoided_items[], updated_at | — |
| `USER#{lineUserId}` | `REWARD_POOL#` | candidates: [{id, name, price, category, score, source_url, fetched_at}], updated_at | — |
| `USER#{lineUserId}` | `REWARD_SUGGESTION#{isoTimestamp}` | item_id, item_name, price, proposed_at, outcome (bought/skip/none), feedback_at | — |
| `USER#{lineUserId}` | `PUSH_LOG#{isoDate}` | sent_at, content_preview, message_count_today, message_count_month | — |
| `USER#{lineUserId}` | `GOOGLE_OAUTH#` | encrypted_refresh_token, connected_at, email_hint(masked) | — |

### ARSカテゴリ一覧

| カテゴリID | 表示名 | 説明 |
|-----------|--------|------|
| `emotional_stability` | 情緒安定費 | いつものルーティン（毎日のコーヒー等） |
| `recovery` | 回復費 | 自分へのご褒美（スイーツ、マッサージ等） |
| `emergency_recovery` | 緊急回復費 | 限界時の出費（衝動買い的だが許容範囲） |
| `investment` | 自己投資 | 本・セミナー等 |
| `social` | 社交費 | 飲み会・プレゼント等 |
| `daily` | 日常費 | 食料品・日用品等 |

---

## ルーティングマップ

### API Gateway（WebhookApi）

| パス | メソッド | Lambda | 認証方式 | 備考 |
|------|---------|--------|---------|------|
| `/webhook` | POST | `WebhookHandlerFunction` | なし（Lambda内で LINE署名検証） | LINE Platformからのコールバック |

### API Gateway（LiffApi）

| パス | メソッド | Lambda | 認証方式 | 備考 |
|------|---------|--------|---------|------|
| `/liff/history` | GET | `LiffApiFunction` | LIFFアクセストークン検証 | ご褒美提案履歴 + 支出サマリー |
| `/liff/settings` | GET | `LiffApiFunction` | LIFFアクセストークン検証 | 口調・ご褒美枠等の現在設定取得 |
| `/liff/settings` | PATCH | `LiffApiFunction` | LIFFアクセストークン検証 | 設定変更（口調・ご褒美枠） |
| `/liff/pool` | GET | `LiffApiFunction` | LIFFアクセストークン検証 | 現在の候補プール一覧 |
| `/liff/google/connect` | GET | `LiffApiFunction` | LIFFアクセストークン検証 | Google OAuth同意画面へのリダイレクトURL生成 |
| `/liff/google/callback` | GET | `LiffApiFunction` | stateパラメータ検証 | OAuthコールバック→token交換→refresh_token保存 |
| `/liff/google/disconnect` | POST | `LiffApiFunction` | LIFFアクセストークン検証 | Google連携解除（revoke + GOOGLE_OAUTH#削除） |
| `/liff/google/status` | GET | `LiffApiFunction` | LIFFアクセストークン検証 | Googleカレンダー連携状況取得 |

### EventBridge Scheduler

| スケジュール名 | cron式 | Lambda | 備考 |
|--------------|--------|--------|------|
| `RewardPoolScheduler` | `cron(0 3 * * ? *)` | `RewardPoolUpdaterFunction` | 毎日03:00 JST（深夜バッチ） |
| `PushNotifierScheduler` | `cron(0 12 * * ? *)` | `PushNotifierFunction` | 毎日12:00 JST（昼Push） |

---

## サービスオーケストレーションパターン

### パターン1: 同期チェーン（LINE Reply フロー）

```
LINE Platform --> API Gateway --> webhook_handler
                                      |
                   (署名検証 + Router) |
                                      v
                               intent_classifier
                                      |
                   (Intent判定)        |
                          +-----+-----+-----+-----+
                          |     |     |     |     |
                          v     v     v     v     v
                        EXPENSE REWARD GREET CHAT ONBOARDING
                          |     |     |           |
                          v     v     v           v
                        各ハンドラーが処理 + DynamoDB保存
                          |     |     |           |
                          v     v     v           v
                        line_service.reply_message()
                                      |
                                      v
                               LINE Platform (Reply)
```

> **制約**: webhook_handler受信〜Reply送信まで **3秒以内** （LINE Reply API制約）

### パターン2: 非同期バッチ（EventBridge → Lambda）

```
EventBridge Scheduler
        |
        v
  reward_pool_updater / push_notifier
        |
        +-- DynamoDB（読み取り）
        +-- 楽天API / Bedrock（外部呼び出し）
        +-- DynamoDB（書き込み）
        +-- line_service.push_message()（push_notifierのみ）
```

> **制約なし**: バッチ処理のため時間制約は緩い（Lambda タイムアウト 300s）

### パターン3: LIFF API（リクエスト/レスポンス）

```
LINEアプリ内ブラウザ (LIFF)
        |
        | LIFF SDK --> LIFFアクセストークン取得
        v
  API Gateway (LiffApi)
        |
        v
  liff_api (Lambda)
        |
        +-- LINE Platform API（トークン検証）
        +-- DynamoDB（読み書き）
        |
        v
  JSON レスポンス --> LIFF App 表示
```

---

## 環境変数・シークレット設定

### Lambda 環境変数（template.yaml で定義）

| 変数名 | 値 | 用途 |
|--------|-----|------|
| `TABLE_NAME` | `ArsTable` | DynamoDBテーブル名 |
| `BEDROCK_MODEL_TEXT` | `amazon.nova-micro-v1:0` | テキスト推論用モデルID |
| `BEDROCK_MODEL_MULTIMODAL` | `amazon.nova-lite-v1:0` | 画像解析用モデルID |
| `LOG_LEVEL` | `INFO` | ログレベル |
| `STAGE` | `dev` / `prod` | 環境識別 |

### Secrets Manager / SSM（実行時に取得）

| シークレット名 | 内容 | 利用Lambda |
|--------------|------|-----------|
| `ars/line/channel-secret` | LINE チャネルシークレット | webhook_handler |
| `ars/line/channel-access-token` | LINE チャネルアクセストークン | 全LINE通信Lambda |
| `ars/rakuten/app-id` | 楽天アプリイト（商品・トラベル共通） | reward_pool_updater |
| `ars/hotpepper/api-key` | ホットペッパーグルメAPIキー（Growth） | reward_pool_updater |
| `ars/google/client-id` | Google OAuth 2.0 Client ID | liff_api, google_calendar_service |
| `ars/google/client-secret` | Google OAuth 2.0 Client Secret | liff_api, google_calendar_service |
| `ars/liff/liff-id` | LIFF ID | liff_api |

---

## IAM ロール設計（最小権限）

| Lambda | DynamoDB | Bedrock | Secrets Manager | SSM | その他 |
|--------|----------|---------|----------------|-----|--------|
| webhook_handler | Read/Write | — | Read | — | — |
| intent_classifier | Read/Write | InvokeModel | Read | — | — |
| character_reply | Read/Write | InvokeModel | Read | — | — |
| onboarding_flow | Read/Write | InvokeModel | Read | — | — |
| expense_extractor | Read/Write | InvokeModel | Read | — | — |
| receipt_analyzer | Read/Write | InvokeModel | Read | — | — |
| reward_proposal | Read/Write | InvokeModel | Read | — | — |
| reward_pool_updater | Read/Write | — | Read | — | HTTPS外部（楽天API / ホットペッパーグルメAPI · Growth） |
| push_notifier | Read/Write | InvokeModel | Read | — | — |
| liff_api | Read/Write | — | Read | — | HTTPS外部（LINE検証API・Google Calendar API・Google OAuth） |
