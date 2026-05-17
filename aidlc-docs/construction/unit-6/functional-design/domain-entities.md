# Unit 6: Push 通知 — ドメインエンティティ

## DynamoDB スキーマ

### PUSH_QUEUE#{date}（日次配信キュー）

| キー | 形式 | 例 |
|------|------|-----|
| PK | `PUSH_QUEUE#{YYYY-MM-DD}` | `PUSH_QUEUE#2026-05-17` |
| SK | `USER#{user_id}` | `USER#Uabc123` |

| 属性 | 型 | 説明 |
|------|-----|------|
| scheduled_at | String (ISO8601) | 配信予定時刻 |
| status | String | `pending` / `sent` / `failed` / `skipped` |
| category | String | 送信後に選択されたカテゴリを記録 |
| ttl | Number | 翌日 00:00 UTC（自動削除） |

---

### PUSH_LOG#{datetime}（送信記録）

| キー | 形式 | 例 |
|------|------|-----|
| PK | `USER#{user_id}` | `USER#Uabc123` |
| SK | `PUSH_LOG#{ISO8601}` | `PUSH_LOG#2026-05-17T14:37:00` |

| 属性 | 型 | 説明 |
|------|-----|------|
| category | String | メッセージカテゴリ |
| template_id | String | 使用テンプレートのインデックス |
| message_preview | String | 送信メッセージの先頭 50 文字 |
| created_at | String (ISO8601) | 送信日時 |
| ttl | Number | 30 日後（自動削除） |

---

### PUSH_SETTINGS#（通知設定）

| キー | 形式 | 例 |
|------|------|-----|
| PK | `USER#{user_id}` | `USER#Uabc123` |
| SK | `PUSH_SETTINGS#` | `PUSH_SETTINGS#` |

| 属性 | 型 | デフォルト | 説明 |
|------|-----|----------|------|
| all_enabled | Boolean | true | 全通知の ON/OFF |
| daily_message | Boolean | true | 日次メッセージ |
| push_time_start | String | "10:00" | 配信開始時刻 |
| push_time_end | String | "21:00" | 配信終了時刻 |
| budget_nudge | Boolean | true | 予算ナッジ |
| recommendation | Boolean | true | おすすめ提案 |
| anniversary | Boolean | true | 記念日リマインダー |
| monthly_report | Boolean | true | 月初レポート |
| streak | Boolean | true | 連続記録の応援 |
| updated_at | String (ISO8601) | - | 最終更新日時 |

---

## SK プレフィックス追加

```python
SK_PUSH_SETTINGS = "PUSH_SETTINGS#"
SK_PREFIX_PUSH_QUEUE = "PUSH_QUEUE#"
```

---

## Lambda 関数

| 関数 | トリガー | 役割 |
|------|---------|------|
| PushSchedulerFunction | EventBridge cron 毎日 10:00 JST | ランダム時刻生成 + PUSH_QUEUE 書き込み |
| PushDispatcherFunction | EventBridge rate(10 minutes) | 予定時刻到達分の Push 送信 |
| MonthlyPushFunction | EventBridge cron 毎月 1 日 9:00 JST | 月初レポート Push |

---

## サービスクラス

| サービス | ファイル | 責務 |
|---------|---------|------|
| DailyPushService | `layer/python/services/daily_push.py` | メッセージ生成（カテゴリ選択 + テンプレート埋め） |
| MonthlyPushService | `layer/python/services/monthly_push.py` | 月初レポートメッセージ生成 |
| PushManager | `layer/python/services/push_manager.py` | Push 送信 + 通数管理 + ログ |
| PreferenceExtractor | `layer/python/services/preference_extractor.py` | 会話からの嗜好自動抽出 |
