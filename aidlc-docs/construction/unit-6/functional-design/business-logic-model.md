# Unit 6: Push 通知 — ビジネスロジックモデル

## 概要

Unit 6 はリワードちゃんからの自発的な LINE Push 通知を実装する。
ユーザーの入力がなくてもリワードちゃんが「友達のように」話しかける体験を提供する。

---

## ビジネスロジック構成

### BL-6-01: 日次プッシュスケジューリング

```
毎日 JST 10:00 に EventBridge → PushSchedulerFunction が起動
  1. entityType-index GSI で全 ACTIVE ユーザーを取得
  2. 各ユーザーの PUSH_SETTINGS を確認
     - all_enabled = false → スキップ
     - daily_message = false → スキップ
  3. 10:00〜21:00 のランダム時刻を生成
  4. PUSH_QUEUE#{date}  SK=USER#{user_id} に書き込み
     - scheduled_at: ランダム時刻
     - status: "pending"
     - ttl: 翌日 00:00（自動削除）
```

### BL-6-02: プッシュディスパッチ

```
10 分おきに EventBridge → PushDispatcherFunction が起動
  1. PUSH_QUEUE#{today} から scheduled_at <= now AND status = "pending" を取得
  2. 各ユーザーについて:
     a. monthly_push_count チェック（200 通上限）
     b. daily_push.generate_daily_push() でメッセージ生成
     c. line_service.push_message() で送信
     d. status を "sent" に更新
     e. PUSH_LOG#{datetime} に送信記録を保存
     f. PROFILE.push_count_this_month を +1
  3. エラー時: status を "failed" に更新、次回リトライなし
```

### BL-6-03: メッセージ生成ロジック

```
generate_daily_push(user_id):
  1. ユーザー情報取得
     - PROFILE（nickname, budget, bonus, birthday, anniversaries）
     - PREF_MEMORY#（嗜好データ）
     - MONTHLY_SUMMARY#（予算残高）
     - 過去14日の EXPENSE#（最近の支出）
     - PUSH_LOG#（重複回避）
  2. カテゴリ選択
     - 記念日7日前 → anniversary_approach 優先
     - 嗜好データ < 5 件 → deep_dive_preference の重み UP
     - 嗜好データ >= 5 件 → specific_recommendation の重み UP
     - 最近の支出なし → past_reference 無効
     - 重み付きランダム選択
  3. テンプレート + 変数埋め
     - 時間帯トーン（10-12, 12-14, 14-17, 17-19, 19-21）
     - ユーザー固有変数（name, food_pref, remaining, etc.）
  4. 重複チェック（過去7日の PUSH_LOG と同テンプレート → 再選択）
```

### BL-6-04: 月初レポート Push

```
毎月1日 JST 9:00 に EventBridge → MonthlyPushFunction が起動
  1. 全 ACTIVE ユーザーを取得
  2. 各ユーザーの先月 MONTHLY_SUMMARY# を取得
  3. 繰り越し計算（finance_engine.calculate_monthly_budget）
  4. レポートメッセージ生成
  5. Push 送信 + PUSH_LOG に記録
```

### BL-6-05: 嗜好自動抽出（preference_extractor）

```
Push 後のユーザー返信で:
  1. webhook_handler → character_reply（通常の会話処理）
  2. 同時に preference_extractor.extract()
     - Bedrock で { category, items, sentiment, context } を抽出
  3. items があれば PREF_MEMORY# を更新（重複排除、追加）
```

### BL-6-06: PUSH 設定管理

```
LIFF API:
  GET  /api/push-settings → 現在の設定を返す
  PUT  /api/push-settings → 設定を更新

チャットからの変更:
  「静かにして」→ all_enabled = false
  「また連絡して」→ all_enabled = true
```

---

## データフロー

```
EventBridge (10:00 JST)
  → PushSchedulerFunction
    → DynamoDB PUSH_QUEUE#{date} 書き込み

EventBridge (rate 10min)
  → PushDispatcherFunction
    → DynamoDB PUSH_QUEUE 読み込み
    → daily_push.generate_daily_push()
      → DynamoDB (PROFILE / PREF_MEMORY / MONTHLY_SUMMARY / EXPENSE / PUSH_LOG)
    → line_service.push_message()
    → DynamoDB PUSH_LOG 書き込み

EventBridge (月初 9:00 JST)
  → MonthlyPushFunction
    → DynamoDB MONTHLY_SUMMARY 読み込み
    → finance_engine.calculate_monthly_budget()
    → line_service.push_message()
```

---

## メッセージカテゴリ & 重み

| カテゴリ | 基本重み | 条件変動 |
|---------|---------|---------|
| food_discovery | 3 | - |
| budget_nudge | 2 | - |
| specific_recommendation | 3 | 嗜好データ >= 5件 → 5 |
| either_or | 2 | - |
| past_reference | 2 | 最近の支出なし → 0 |
| deep_dive_preference | 3 | 嗜好データ < 5件 → 5, >= 5件 → 1 |
| anniversary_approach | 2 | 7日前に記念日あり → 最優先 |
| streak_challenge | 1 | - |
