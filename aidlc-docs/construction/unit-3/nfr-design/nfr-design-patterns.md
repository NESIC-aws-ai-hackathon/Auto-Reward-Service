# Unit 3: 支出記録 — NFR Design

**作成日**: 2026-05-16

---

## PERF-3-01/02: Bedrock 呼び出し設計

### テキスト抽出（Nova Lite 1回呼び出し）
- `expense_extractor.extract()` 内で支出 JSON 抽出 + カテゴリ分類を 1プロンプトで実施
- `system_prompt` にキャラクター口調は含めない（抽出専用プロンプト）
- 返答形式: JSON のみ（`{"items": [...], "is_expense": true}`）
- `bedrock_service.invoke_text()` の `temperature=0.1`（抽出タスクは低温度）

### レシート解析（Nova Lite マルチモーダル）
- Converse API の `content` に `image` block + `text` block を含める
- 画像フォーマット: `image/jpeg` or `image/png`（LINE Content API から取得）
- Lambda タイムアウト: **29秒**（template.yaml の `Timeout` を変更）
- `parse_failed` 判定: JSON パース失敗 または `items` が空配列

---

## PERF-3-03: Reply-First / Post-Reply パターン（Unit 2 と同一）

```
1. LINE Reply（記録確認メッセージ + 今月累計）
2. Post-Reply:
   - Expense 保存（DynamoDB put_item）
   - MonthlyExpenseSummary 更新（increment_atomic_counter）
   - PendingExpense 削除（確認フロー経由の場合）
```

---

## REL-3-01/02: エラーハンドリング設計

| エラー種別 | 検出方法 | 対応 |
|---|---|---|
| Bedrock ValidationException | `e.response["Error"]["Code"]` | `parse_failed = True` としてフォールバックメッセージ |
| Bedrock ThrottlingException | `e.response["Error"]["Code"]` | `_invoke_with_retry` でリトライ（Unit 2 流用） |
| JSON パース失敗 | `json.JSONDecodeError` | `parse_failed = True` でフォールバック |
| DynamoDB WriteError | `ClientError` | 「記録できなかった、もう一度試してみて」返信。リトライなし |
| LINE Content API 失敗 | `LineApiError` | 「画像取得失敗」フォールバックメッセージ |

---

## 設計パターン一覧

| パターン | 新規/流用 | 実装箇所 |
|---|---|---|
| Reply-First / Post-Reply | 流用（Unit 2） | `webhook_handler._handle_expense()` |
| Bedrock フォールバックチェーン | 流用（Unit 2） | `bedrock_service._invoke_with_retry()` |
| アトミックカウンタ | 流用（Unit 0） | `dynamodb_service.increment_atomic_counter()` で `total_amount` を ADD |
| TTL 自動削除 | 流用（Unit 0） | PendingExpense（24h）/ PENDING_CLARIFICATION（10分） |
| JSON 強制出力プロンプト | **新規** | `expense_prompt.py` / `receipt_prompt.py` — LLM に純 JSON のみ返させる |
| PENDING_CLARIFICATION セッション | **新規** | `expense_extractor.py` — 追加質問の複数ターン状態管理 |

---

## template.yaml への変更点

| 変更対象 | 変更内容 | 理由 |
|---|---|---|
| `WebhookHandlerFunction.Timeout` | 10秒 → **29秒** | レシート画像解析の同期処理（PERF-3-02） |

Lambda タイムアウト以外の新規 AWS リソースは Unit 3 では追加しない（SQS 非同期化は Deploy Round 4 実測後に判断）。

---

## PENDING_CLARIFICATION セッション設計

```
DynamoDB SK: PENDING_CLARIFICATION#{timestamp}
Item:
  {
    "waiting_for": "amount",              # "amount" | "item_name_and_amount"
    "partial_items": [...],               # 現時点で判明している情報
    "retry_count": 0,                     # 最大2（BR-3-02）
    "created_at": "ISO 8601",
    "ttl": <10分後 Unix timestamp>        # DynamoDB TTL で自動削除
  }
```

フロー:
1. `amount` が null → PENDING_CLARIFICATION を保存 → 追加質問メッセージを Reply
2. 次の Webhook 受信時 → PENDING_CLARIFICATION があれば clarification 回答として処理
3. `retry_count >= 2` → 入力ガイドメッセージ → PENDING_CLARIFICATION 削除

---

## MonthlyExpenseSummary 設計

```
DynamoDB PK: USER#{line_user_id}
DynamoDB SK: MONTHLY_SUMMARY#{YYYY-MM}
Item:
  {
    "total_amount": 0,          # ADD で加算（アトミック）
    "expense_count": 0,         # ADD で加算（アトミック）
    "reward_budget": 20000,     # PROFILE.reward_budget からコピー（初回作成時）
  }
```

`remaining_budget` は DynamoDB には保存せず、取得時に `reward_budget - total_amount` で計算する（BR-3-09: マイナス許容）。
