# Unit 6: Push 通知 — NFR 要件 + NFR 設計 + インフラ設計

## 非機能要件

| ID | カテゴリ | 要件 | 目標値 |
|----|---------|------|--------|
| NFR-6-01 | パフォーマンス | PushScheduler 実行時間 | 60 秒以内（全ユーザーキュー登録） |
| NFR-6-02 | パフォーマンス | PushDispatcher 実行時間 | 120 秒以内 |
| NFR-6-03 | コスト | LINE Push 月間通数 | 190 通以下（200 通上限の 95%） |
| NFR-6-04 | 信頼性 | Push 送信失敗時 | ログ記録して続行、リトライなし |
| NFR-6-05 | セキュリティ | user_id ログ出力 | 先頭 6 字 + *** |
| NFR-6-06 | 運用 | PUSH_QUEUE TTL | 翌日自動削除 |
| NFR-6-07 | 運用 | PUSH_LOG TTL | 30 日自動削除 |

---

## NFR 設計

### パフォーマンス設計

- **PushScheduler**: GSI クエリで全ユーザー取得 → BatchWriteItem で PUSH_QUEUE 書き込み
  - 25 件ずつバッチ処理（DynamoDB BatchWriteItem 上限）
- **PushDispatcher**: PUSH_QUEUE から Query → 直列で Push 送信
  - 10 分間隔のため、1 回あたり最大数件の処理で十分
  - Timeout: 120 秒

### コスト管理設計

- PROFILE.push_count_this_month で月間通数を追跡
- MonthlyPushFunction 実行時に全ユーザーの push_count_this_month を 0 リセット
- Dispatcher 送信前に `push_count_this_month >= 190` チェック → スキップ

### エラーハンドリング設計

- Push 送信失敗: WARNING ログ + status = "failed" → 次ユーザーへ続行
- DynamoDB エラー: Lambda 全体を失敗させない（try/except per user）
- メッセージ生成失敗: デフォルトの either_or テンプレートにフォールバック

---

## インフラ設計

### Lambda 関数定義

```yaml
PushSchedulerFunction:
  Runtime: python3.13
  MemorySize: 256
  Timeout: 60
  Trigger: EventBridge cron(0 1 ? * * *)  # UTC 01:00 = JST 10:00

PushDispatcherFunction:
  Runtime: python3.13
  MemorySize: 256
  Timeout: 120
  Trigger: EventBridge rate(10 minutes)

MonthlyPushFunction:
  Runtime: python3.13
  MemorySize: 256
  Timeout: 120
  Trigger: EventBridge cron(0 0 1 * ? *)  # UTC 00:00 = JST 09:00
```

### IAM 追加権限

- SchedulerExecutionRole に新 Lambda ARN を追加

### EventBridge Scheduler

- PushSchedulerSchedule: 毎日 UTC 01:00
- PushDispatcherSchedule: 10 分間隔
- MonthlyPushSchedule: 毎月 1 日 UTC 00:00

### DynamoDB 追加アクセスパターン

| パターン | PK | SK | 操作 |
|---------|-----|-----|------|
| キュー書き込み | PUSH_QUEUE#{date} | USER#{user_id} | PutItem (BatchWrite) |
| キュー読み込み | PUSH_QUEUE#{date} | begins_with("USER#") | Query + Filter |
| キュー更新 | PUSH_QUEUE#{date} | USER#{user_id} | UpdateItem |
| 設定読み込み | USER#{user_id} | PUSH_SETTINGS# | GetItem |
| 設定書き込み | USER#{user_id} | PUSH_SETTINGS# | PutItem |
| ログ書き込み | USER#{user_id} | PUSH_LOG#{datetime} | PutItem |
| ログ読み込み | USER#{user_id} | begins_with("PUSH_LOG#") | Query (7日分) |
