# Unit 3: 支出記録 — Infrastructure Design

**作成日**: 2026-05-16

---

## template.yaml 変更差分

### 変更: WebhookHandlerFunction タイムアウト延長

```yaml
# Globals セクション（既存）
Globals:
  Function:
    Timeout: 29          # 変更: 10 → 29（レシート画像解析の同期処理対応）
    MemorySize: 256
    Runtime: python3.13
    Architectures:
      - x86_64
    Layers:
      - !Ref ArsCommonLayer
    Environment:
      Variables:
        TABLE_NAME: !Ref ArsTable
        LINE_CHANNEL_SECRET: !Sub "{{resolve:secretsmanager:ars/line:SecretString:channel_secret}}"
        LINE_CHANNEL_ACCESS_TOKEN: !Sub "{{resolve:secretsmanager:ars/line:SecretString:channel_access_token}}"
        BEDROCK_TEXT_MODEL_ID: "amazon.nova-lite-v1:0"
        BEDROCK_IMAGE_MODEL_ID: "amazon.nova-lite-v1:0"
        BEDROCK_FALLBACK_MODEL_ID: "amazon.nova-lite-v1:0"
        DAILY_CHAT_LIMIT: "50"
```

新規 AWS リソース（SQS / EventBridge 等）の追加なし。

---

## 新規ファイル一覧

| ファイル | 配置 | 役割 |
|---|---|---|
| `src/prompts/expense_prompt.py` | WebhookHandlerFunction コンテキスト | テキスト支出抽出プロンプト（JSON 強制出力） |
| `src/prompts/receipt_prompt.py` | WebhookHandlerFunction コンテキスト | レシート画像解析プロンプト（JSON 強制出力） |
| `src/handlers/expense_extractor.py` | WebhookHandlerFunction コンテキスト | テキスト→支出JSON化 + 追加質問フロー + ARSカテゴリ分類 |
| `src/handlers/receipt_analyzer.py` | WebhookHandlerFunction コンテキスト | 画像→支出JSON化（Nova Lite マルチモーダル） |

---

## 更新ファイル一覧

| ファイル | 更新内容 |
|---|---|
| `layer/python/models/schemas.py` | `Expense` / `PendingExpense` / `ExtractedItem` / `ExpenseExtractResult` / `ReceiptAnalysisResult` / `MonthlyExpenseSummary` モデル追加 |
| `layer/python/services/dynamodb_service.py` | `get_pending_clarification()` / `save_pending_clarification()` / `delete_pending_clarification()` / `get_monthly_summary()` / `save_monthly_summary()` 追加 |
| `src/handlers/webhook_handler.py` | EXPENSE Intent ルーティング追加（`_handle_expense()`）/ 画像メッセージルーティング追加（`_handle_image()`） |

---

## DynamoDB スキーマ追加

| PK | SK | エンティティ | TTL |
|---|---|---|---|
| `USER#{line_user_id}` | `EXPENSE#{ISO8601}` | 確定済み支出 | なし |
| `USER#{line_user_id}` | `PENDING_EXPENSE#{ISO8601}` | 確認待ち支出 | 24時間 |
| `USER#{line_user_id}` | `PENDING_CLARIFICATION#{ISO8601}` | 追加質問セッション | 10分 |
| `USER#{line_user_id}` | `MONTHLY_SUMMARY#{YYYY-MM}` | 月次累計 | なし |
