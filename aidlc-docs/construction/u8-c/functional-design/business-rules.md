# U8-C: ライフログ + 日記サマリ — ビジネスルール

## 1. ライフログ抽出ルール

### LOG-01: 抽出対象カテゴリ
- 食事、活動、睡眠、運動、対人、気分、支出、場所、ご褒美

### LOG-02: 事実のみ原則
- LLMが推測・補完しない
- 会話で明示的に言及された情報のみ
- confidence < 0.5 のエントリは保存しない

### LOG-03: 支出の二重書き込み
- カテゴリ "支出" のログは LIFE_LOG# と EXPENSE# の両方に書き込む
- EXPENSE# は既存の支出記録体系と互換

### LOG-04: 日付推定
- 会話日のライフログとして記録
- 「昨日」「一昨日」の言及は該当日付に記録
- 日付が不明な場合は会話日として記録

---

## 2. 日記サマリルール

### DIARY-01: 生成タイミング
- ユーザー設定の diary_time（デフォルト 22:00 JST）
- EventBridge cron で起動

### DIARY-02: 生成条件
- 当日のLIFE_LOG# が1件以上存在すること
- 0件の場合は「今日はゆっくりだったね」のデフォルト日記

### DIARY-03: 文字数
- 200-400文字
- 超過時はLLMに再生成指示

### DIARY-04: 冪等性
- 同日の DAILY_FUREMARU_SUMMARY# は上書き（再生成可能）
- 再生成時は updated_at を更新

---

## 3. Push通知ルール

### PUSH-01: 通知タイミング（U8-Cスコープ）
- 日記サマリ完成時のみ

### PUSH-02: 通知条件
- ユーザーの notification_enabled が true
- PUSH_SUBSCRIPTION# が存在する

### PUSH-03: 購読管理
- 1ユーザー1購読（最新で上書き）
- 410 Gone レスポンスで自動削除
- ブラウザ通知許可がない場合はAPI側で拒否しない（PWA側で制御）

### PUSH-04: VAPID鍵管理
- 環境変数で管理: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT
- デプロイ時に生成、Parameter Store に保管

---

## 4. AnalysisJob ルール（U8-C拡張）

### JOB-04: 処理フロー
```
queued → processing → [extract_life_log] → completed
                   → failed (retry_count < 3 → SQS re-queue)
```

### JOB-05: タイムアウト
- 1ジョブの処理上限: 240秒（Lambda 300秒 - バッファ）
- Bedrock呼び出し1回のタイムアウト: 60秒

### JOB-06: 並行処理
- SQS の MaxConcurrency: 5（Lambda同時実行数制限）
- VisibilityTimeout: 360秒

---

## 5. EventBridge ルール

### SCHED-01: 日記生成スケジュール
- `cron(0 13 * * ? *)` = 毎日 22:00 JST (UTC 13:00)
- Lambda に `{"trigger": "scheduled_diary"}` を渡す

### SCHED-02: リプロセススケジュール
- `rate(5 minutes)`
- Lambda に `{"trigger": "reprocess"}` を渡す
- ANALYSIS_JOB# status=queued かつ created_at > 10分前 のジョブを再処理

---

## 6. バリデーション

### VAL-05: Push subscribe
```json
{
  "subscription": {
    "endpoint": "required, https:// URL",
    "keys": {
      "p256dh": "required, base64 string",
      "auth": "required, base64 string"
    }
  }
}
```

### VAL-06: Push unsubscribe
- 認証済みユーザーなら即実行（ボディ不要）
