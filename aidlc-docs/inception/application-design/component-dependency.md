# コンポーネント依存関係 — オートリワードサービス（v2）

**改訂日**: 2026-05-15 / コンセプト変更後版

---

## Lambda 関数間の呼び出し関係

```
webhook_handler
  ├──→ intent_classifier
  │         ├──→ expense_extractor
  │         │       └──→ dynamodb_service（PENDING_EXPENSE保存）
  │         ├──→ reward_proposal
  │         │       ├──→ finance_engine（余裕額算出）
  │         │       ├──→ reward_pool_service（候補選択）
  │         │       └──→ character_reply（キャラ口調で提案）
  │         ├──→ character_reply
  │         │       └──→ bedrock_service（Nova Micro）
  │         ├──→ onboarding_flow
  │         │       └──→ dynamodb_service（PROFILE保存）
  │         └──→ dynamodb_service（CHATログ保存）
  └──→ receipt_analyzer（画像メッセージ時）
          ├──→ line_service.get_content
          ├──→ bedrock_service（Nova Lite）
          └──→ dynamodb_service（PENDING_EXPENSE保存）

reward_pool_updater（EventBridge）
  ├──→ dynamodb_service（PREF_MEMORY取得）
  ├──→ rakuten_service（商品検索）
  └──→ dynamodb_service（REWARD_POOL更新）

push_notifier（EventBridge）
  ├──→ dynamodb_service（対象ユーザー取得）
  ├──→ bedrock_service（Nova Micro）
  └──→ line_service.push（Push送信）

liff_api（API Gateway）
  └──→ dynamodb_service（履歴・設定取得 / 設定更新）
```

---

## 共通サービス依存マトリクス

| Lambda / コンポーネント | dynamodb_service | bedrock_service | line_service | rakuten_service | finance_engine | reward_pool_service | secrets | logger |
|--------------------------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| webhook_handler | ✔ | — | ✔ | — | — | — | ✔ | ✔ |
| intent_classifier | ✔ | ✔ | — | — | — | — | ✔ | ✔ |
| expense_extractor | ✔ | ✔ | ✔ | — | — | — | ✔ | ✔ |
| receipt_analyzer | ✔ | ✔ | ✔ | — | — | — | ✔ | ✔ |
| character_reply | ✔ | ✔ | ✔ | — | — | — | ✔ | ✔ |
| onboarding_flow | ✔ | ✔ | ✔ | — | — | — | ✔ | ✔ |
| reward_proposal | ✔ | ✔ | ✔ | — | ✔ | ✔ | ✔ | ✔ |
| reward_pool_updater | ✔ | — | — | ✔ | — | ✔ | ✔ | ✔ |
| push_notifier | ✔ | ✔ | ✔ | — | — | — | ✔ | ✔ |
| liff_api | ✔ | — | — | — | ✔ | ✔ | ✔ | ✔ |

---

## データフロー図

### フロー1: チャット支出入力 → 確認 → DynamoDB保存（メインフロー）

```
[LINEユーザー]
    |
    | "セブンでプリン買った 320円"
    v
[LINE Messaging API]
    |
    | Webhook POST
    v
[API Gateway] --> [webhook_handler]
                       |
                       | X-Line-Signature検証OK
                       | message.type = "text"
                       v
                  [intent_classifier]
                       |
                       | bedrock_service.invoke_model(intent_prompt)
                       | -> Intent = "EXPENSE", confidence = 0.92
                       v
                  [expense_extractor]
                       |
                       | bedrock_service.invoke_model(expense_prompt)
                       | -> {"item": "プリン", "amount": 320, "ars_category": "emotional_stability"}
                       | confidence >= 0.8 -> needs_confirm = false
                       |
                       +-- dynamodb_service.put_item(EXPENSE#{timestamp})
                       |
                       +-- line_service.reply_message("覚えた〜。たまご系プリン...")
                       |
                       v
                  [LINE Reply API] --> ユーザーに応答
```

### フロー2: ご褒美提案（感情把握 → マッチング → 提案）

```
[LINEユーザー]
    |
    | "今日疲れた"
    v
[webhook_handler] --> [intent_classifier]
                           |
                           | Intent = "REWARD", confidence = 0.85
                           v
                      [reward_proposal]
                           |
                           +-- finance_engine.calculate_available_budget()
                           |     |
                           |     +-- dynamodb_service.get_item(PROFILE#)
                           |     +-- dynamodb_service.query(EXPENSE#{今月})
                           |     -> budget = 3200円
                           |
                           +-- reward_pool_service.select_candidates(state, budget)
                           |     |
                           |     +-- dynamodb_service.get_item(REWARD_POOL#)
                           |     -> [{"name": "抹茶プリン", "price": 320, ...}]
                           |
                           +-- character_reply.generate_reply(提案コンテキスト)
                           |     |
                           |     +-- bedrock_service.invoke_model(character_prompt)
                           |     -> "前に抹茶好きって言ってたよね〜..."
                           |
                           +-- dynamodb_service.put_item(REWARD_SUGGESTION#{timestamp})
                           +-- line_service.reply_message(提案メッセージ)
                           v
                      [LINE Reply API] --> ユーザーに応答
```

### フロー3: 日次バッチ（候補プール更新）

```
[EventBridge Scheduler] -- cron(0 3 * * ? *) --> [reward_pool_updater]
                                                       |
                                                       | _get_all_active_users()
                                                       |   +-- dynamodb_service.query_gsi(GSI1)
                                                       |   -> ["user_001", "user_002", ...]
                                                       |
                                                       | for each user:
                                                       |   +-- dynamodb_service.get_item(PREF_MEMORY#)
                                                       |   |   -> preferred_categories, liked_items
                                                       |   |
                                                       |   +-- rakuten_service.search_items(categories)
                                                       |   |   -> [商品リスト]
                                                       |   |
                                                       |   +-- _adjust_scores(candidates, history)
                                                       |   |   -> スルー品スコア↓、購入系スコア↑
                                                       |   |
                                                       |   +-- _remove_stale_candidates(14日超)
                                                       |   |
                                                       |   +-- dynamodb_service.put_item(REWARD_POOL#)
                                                       v
                                                  [完了（ログ出力）]
```

### フロー4: Push通知（1日1回バッチ）

```
[EventBridge Scheduler] -- cron(0 12 * * ? *) --> [push_notifier]
                                                       |
                                                       | _get_push_targets()
                                                       |   +-- dynamodb_service.query_gsi(GSI1)
                                                       |   +-- 月200通未達 & 今日未Push フィルタ
                                                       |   -> [対象ユーザーリスト]
                                                       |
                                                       | for each user:
                                                       |   +-- _check_monthly_limit(user_id)
                                                       |   |   -> True（送信可）
                                                       |   |
                                                       |   +-- bedrock_service.invoke_model(push_prompt)
                                                       |   |   -> "今日ちょっとだけ話したいことある〜"
                                                       |   |
                                                       |   +-- line_service.push_message(user_id, content)
                                                       |   +-- dynamodb_service.put_item(PUSH_LOG#{today})
                                                       v
                                                  [完了（ログ出力）]
```

---

## 外部依存関係

| 外部サービス | 利用コンポーネント | 用途 | 認証方法 |
|------------|-----------------|------|---------|
| LINE Messaging API | line_service | Webhook受信・Reply・Push・Content取得 | チャネルアクセストークン |
| LINE Platform API | liff_api | LIFFアクセストークン検証 | なし（公開API） |
| Amazon Bedrock | bedrock_service | テキスト推論（Nova Micro）・画像解析（Nova Lite） | IAM Role |
| 楽天ウェブサービスAPI | rakuten_service | 商品検索 | アプリID |
| AWS Secrets Manager | secrets | シークレット取得 | IAM Role |
| AWS SSM Parameter Store | secrets | パラメータ取得 | IAM Role |
| Amazon DynamoDB | dynamodb_service | 全データ読み書き | IAM Role |
| Amazon EventBridge | （インフラ） | スケジュール実行 | IAM Role |
| Amazon CloudWatch Logs | logger | ログ出力 | IAM Role（自動） |

---

## インフラ依存関係（AWS SAM template.yaml）

```
ArsTable (DynamoDB)         <-- 全Lambda関数
Secrets Manager             <-- 全Lambda関数（起動時にシークレット取得）
WebhookApi (API Gateway)    <-- WebhookHandlerFunction
LiffApi (API Gateway)       <-- LiffApiFunction
RewardPoolScheduler         <-- RewardPoolUpdaterFunction
PushNotifierScheduler       <-- PushNotifierFunction
Bedrock Runtime             <-- intent_classifier, character_reply, onboarding_flow,
                                expense_extractor, receipt_analyzer, reward_proposal,
                                push_notifier
```

---

## 依存関係ルール

1. **ハンドラー → 共通サービスのみ**: Lambda ハンドラーは `services/` のモジュールのみimportする。ハンドラー同士を直接importしない
2. **共通サービスは外部依存を隠蔽**: `bedrock_service`, `line_service`, `rakuten_service` が外部APIの詳細を隠蔽し、ハンドラーはAWS SDKを直接呼ばない
3. **secrets経由のみ**: シークレット値（トークン・APIキー）は `secrets` モジュール経由でのみ取得。環境変数にシークレットを直接格納しない
4. **DynamoDBアクセスは dynamodb_service 経由のみ**: 各ハンドラーが boto3.client('dynamodb') を直接呼ばない
5. **循環依存禁止**: services/ 内のモジュール間に循環importを作らない（finance_engine ↔ reward_pool_service 等）
6. **prompts/ は純粋テンプレート**: プロンプトモジュールは外部依存を持たない純粋な文字列テンプレート関数のみ
