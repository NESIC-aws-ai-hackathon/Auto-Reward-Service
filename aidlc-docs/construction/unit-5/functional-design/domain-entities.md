# ドメインエンティティ — Unit 5: ご褒美提案 + 繰り越し機能

**Unit**: Unit 5 — ご褒美提案（F6 対応）+ 繰り越し機能（F2-07）  
**作成日**: 2026-05-16

---

## 1. エンティティ一覧

### UserProfile（既存 + carryover_rate 追加）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| pk | str | — | USER#{line_user_id} |
| sk | str | PROFILE# | SK 固定 |
| reward_budget_monthly | Decimal | None | 月次ご褒美予算（円） |
| bonus_months | list[int] | None | ボーナス月リスト（例: [6, 12]） |
| bonus_amount | int | None | ボーナス概算額（円、1回分） |
| **carryover_rate** | **float** | **0.5** | **繰り越し率（F2-07 追加）** |
| tone | str | friendly | 口調 |

### MonthlyExpenseSummary（既存 + 繰り越しフィールド追加）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| pk | str | — | USER#{line_user_id} |
| sk | str | — | MONTHLY_SUMMARY#YYYY-MM |
| total_amount | Decimal | 0 | 当月支出合計 |
| expense_count | int | 0 | 支出件数 |
| reward_budget | Decimal | 0 | 基本ご褒美予算（コピー） |
| **carryover_amount** | **int** | **0** | **繰り越し額（F2-07 追加）** |
| **bonus_amount** | **int** | **0** | **ボーナス加算額（F2-07 追加）** |
| **total_budget** | **int** | **0** | **総予算（base+carryover+bonus）（F2-07 追加）** |
| **remaining** | **int** | **0** | **残額（total_budget - total_amount）（F2-07 追加）** |
| updated_at | str | None | 最終更新日時（ISO8601） |

### RewardPoolItem（既存・変更なし）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| id | str | — | 楽天 itemCode など一意 ID |
| name | str | — | 商品・施設・店舗名 |
| price | Decimal | — | 価格（円） |
| category | str | — | カテゴリ |
| score | float | 0.0 | スコア（0.0〜1.0） |
| type | str | product | product / travel / restaurant |
| source_url | str | None | 詳細 URL |
| image_url | str | None | 画像 URL |

### RewardSuggestion（既存・変更なし）

| フィールド | 型 | 説明 |
|---|---|---|
| pk | str | USER#{id} |
| sk | str | REWARD_SUGGESTION#{ISO8601} |
| entity_type | str | REWARD_SUGGESTION |
| item_id | str | 提案したアイテム ID（停止時は None） |
| item_name | str | 提案したアイテム名 |
| price | Decimal | 提案価格 |
| proposed_at | str | 提案日時 |
| outcome | str | bought / skip / None |

---

## 2. 値オブジェクト

### MonthlyBudgetResult（一時オブジェクト、DDB 保存なし）

`calculate_monthly_budget()` の返却値として使用する dict:

```python
{
    "base_budget":      int,   # プロファイルの基本予算
    "carryover_amount": int,   # 繰り越し額（0以上）
    "bonus_amount":     int,   # ボーナス加算額（0以上）
    "total_budget":     int,   # 総予算 = base + carryover + bonus
}
```

---

## 3. DynamoDB アクセスパターン

| 操作 | PK | SK | 用途 |
|---|---|---|---|
| GetItem | USER#{id} | PROFILE# | プロファイル取得（budget, tone, bonus_months 等） |
| GetItem | USER#{id} | REWARD_POOL# | ご褒美候補プール取得 |
| GetItem | USER#{id} | MONTHLY_SUMMARY#{先月YYYY-MM} | 先月残額取得（繰り越し計算） |
| GetItem | USER#{id} | MONTHLY_SUMMARY#{今月YYYY-MM} | 今月サマリー取得（既存チェック） |
| Query | USER#{id} | EXPENSE#{今月YYYY-MM}...で前方一致 | 今月の支出合計集計 |
| PutItem | USER#{id} | REWARD_SUGGESTION#{ISO8601} | 提案履歴保存 |
| UpdateItem | USER#{id} | REWARD_POOL# | スコア調整後の候補プール更新 |
