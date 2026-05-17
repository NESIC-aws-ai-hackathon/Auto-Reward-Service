# ドメインエンティティ — Unit 7: LIFFダッシュボード

**Unit**: Unit 7 — LIFFダッシュボード（F8 対応）+ カレンダー連携UI（F9-02）  
**作成日**: 2026-05-16

---

## 1. エンティティ（全て既存・変更なし）

Unit 7 は新規エンティティを追加せず、既存のエンティティを Read / Update する。

| エンティティ | PK | SK | Read | Write |
|---|---|---|---|---|
| UserProfile | USER#{id} | PROFILE# | ✅ 設定取得 | ✅ 設定更新 |
| MonthlyExpenseSummary | USER#{id} | MONTHLY_SUMMARY#{YYYY-MM} | ✅ サマリー表示 | — |
| Expense | USER#{id} | EXPENSE#{ISO8601} | ✅ 支出履歴表示 | — |
| RewardPool | USER#{id} | REWARD_POOL# | ✅ 候補一覧表示 | — |
| RewardSuggestion | USER#{id} | REWARD_SUGGESTION#{ISO8601} | ✅ 提案履歴表示 | — |
| GoogleOAuth | USER#{id} | GOOGLE_OAUTH# | ✅ 連携状態確認 | ✅ 連携解除（Delete） |

---

## 2. API レスポンススキーマ

### GET /api/dashboard

```json
{
  "nickname": "ともちゃん",
  "tone": "friendly",
  "monthly_summary": {
    "total_budget": 24000,
    "total_spent": 8320,
    "remaining": 15680,
    "carryover_amount": 4000,
    "expense_count": 12
  },
  "recent_suggestions": [
    {
      "item_name": "プレミアム入浴剤セット",
      "price": 1980,
      "proposed_at": "2026-05-16T14:30:00+09:00",
      "outcome": "bought"
    }
  ]
}
```

### GET /api/expenses?month=2026-05

```json
{
  "month": "2026-05",
  "expenses": [
    {
      "item_name": "プリン",
      "amount": 320,
      "ars_category": "情緒安定費",
      "created_at": "2026-05-16T12:00:00+09:00"
    }
  ]
}
```

### GET /api/history

```json
{
  "suggestions": [
    {
      "item_name": "プレミアム入浴剤セット",
      "price": 1980,
      "proposed_at": "2026-05-16T14:30:00+09:00",
      "outcome": "bought"
    }
  ]
}
```

### GET /api/pool

```json
{
  "items": [
    {
      "name": "バスソルト ギフトセット",
      "price": 2480,
      "category": "入浴剤",
      "score": 0.85,
      "type": "product",
      "image_url": "https://...",
      "source_url": "https://..."
    }
  ]
}
```

### GET /api/settings

```json
{
  "tone": "friendly",
  "reward_budget_monthly": 20000,
  "bonus_months": [6, 12],
  "bonus_amount": 400000,
  "carryover_rate": 0.5,
  "nickname": "ともちゃん"
}
```

### PUT /api/settings

リクエスト:
```json
{
  "tone": "devilish",
  "reward_budget_monthly": 25000
}
```

レスポンス:
```json
{
  "updated": true
}
```

### GET /api/calendar/status

```json
{
  "connected": true,
  "connected_at": "2026-05-10T09:00:00+09:00"
}
```

---

## 3. DynamoDB アクセスパターン

| 操作 | API | PK | SK | メソッド |
|---|---|---|---|---|
| GetItem | dashboard, settings | USER#{id} | PROFILE# | get_item |
| GetItem | dashboard | USER#{id} | MONTHLY_SUMMARY#{YYYY-MM} | get_item |
| Query | expenses | USER#{id} | EXPENSE#{YYYY-MM}... | query_by_pk |
| Query | history, dashboard | USER#{id} | REWARD_SUGGESTION# | query_by_pk |
| GetItem | pool | USER#{id} | REWARD_POOL# | get_item |
| UpdateItem | settings | USER#{id} | PROFILE# | update_item |
| GetItem | calendar/status | USER#{id} | GOOGLE_OAUTH# | get_item |
| DeleteItem | calendar/disconnect | USER#{id} | GOOGLE_OAUTH# | delete_item |
