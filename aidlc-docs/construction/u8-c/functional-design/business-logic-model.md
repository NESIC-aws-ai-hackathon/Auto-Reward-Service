# U8-C: ライフログ + 日記サマリ — ビジネスロジックモデル

## 1. 概要

会話Transcriptから自動的にライフログを抽出し、1日の終わりに日記サマリを生成する。
非同期Lambda（`ars-u8-analysis`）がSQS/EventBridgeで起動され、Bedrock Claude Sonnetで分析する。

---

## 2. 処理フロー

```
┌──────────────┐     ┌─────────┐     ┌───────────────────┐
│ VoiceSession │     │  SQS    │     │ ars-u8-analysis   │
│ end_session  │────►│ Queue   │────►│ (analysis_handler)│
└──────────────┘     └─────────┘     └────────┬──────────┘
                                               │
                     ┌─────────────────────────┼──────────┐
                     │                         │          │
                     ▼                         ▼          ▼
              extract_life_log()      assess_stress()  generate_diary()
                     │                    (U8-D)          │
                     ▼                                    ▼
              LIFE_LOG#{date}#{seq}            DAILY_FUREMARU_SUMMARY#{date}
              EXPENSE#{timestamp}                        │
                                                        ▼
                                                  Push通知送信
```

### EventBridge トリガー
- **cron(0 13 * * ? *)** = 毎日22:00 JST → 日記サマリ生成
- **rate(5 minutes)** = 未処理ジョブの再処理

---

## 3. AnalysisHandler（Lambda エントリポイント）

### 3.1 SQS トリガー処理

```python
def lambda_handler(event, context):
    for record in event["Records"]:
        body = json.loads(record["body"])
        job_type = body.get("job_type")

        if job_type == "conversation_analysis":
            process_conversation(body)
        elif job_type == "daily_diary":
            process_daily_diary(body)
```

### 3.2 EventBridge トリガー処理

```python
# EventBridge → Lambda (22:00 JST)
# 全ユーザーの日記サマリを生成する
def handle_scheduled_diary(event):
    # 当日分のライフログがあるユーザーを検索
    # 各ユーザーに対して generate_diary_summary() を実行
```

---

## 4. AnalysisService

### 4.1 process_conversation(job)

```
入力: {job_id, user_id, session_id}

処理:
1. ANALYSIS_JOB# を processing に更新
2. CONVERSATION_TURN# をセッションIDで取得
3. Claude Sonnet でライフログ抽出:
   - extract_life_log(turns) → LifeLog[]
4. ライフログ保存: LIFE_LOG#{date}#{seq}
5. 支出検出保存: EXPENSE#{timestamp}
6. ANALYSIS_JOB# を completed に更新
```

### 4.2 extract_life_log(turns) → LifeLog[]

```
プロンプト:
「以下の会話から、ユーザーの生活に関する事実を抽出してください。
推測や補完はせず、会話に明示的に言及された情報のみを記録してください。」

出力JSON:
[
  {
    "category": "食事|活動|睡眠|運動|対人|気分|支出|場所|ご褒美",
    "content": "記述",
    "confidence": 0.0-1.0,
    "timestamp_hint": "午前|午後|夕方|夜|不明",
    "amount": null | 数値 (支出カテゴリのみ)
  }
]
```

### 4.3 generate_diary_summary(user_id, date)

```
入力: user_id, date (YYYY-MM-DD)

処理:
1. 当日のLIFE_LOG# を全取得
2. 当日のEXPENSE# を全取得
3. Claude Sonnet で日記生成:
   - ふれまーるちゃん視点の日記テキスト
4. DAILY_FUREMARU_SUMMARY#{date} に保存
5. Push通知送信（ユーザーの通知有効時）
```

### 4.4 日記サマリ生成プロンプト

```
あなたは「ふれまーるちゃん」です。
ユーザーの今日一日を振り返る短い日記を書いてください。

【ルール】
- ふれまーるちゃんの視点で「今日の〇〇ちゃんは...」と書く
- 200-400文字程度
- 温かい言葉で一日を締めくくる
- 明日への一言を添える
- 事実に基づく（推測しない）
- 何もイベントがない場合は「今日はゆっくりだったね」で締める
```

---

## 5. BedrockClient

### 5.1 インターフェース

```python
class BedrockClient:
    def invoke(self, prompt: str, system: str = None, max_tokens: int = 2000) -> str:
        """Claude Sonnet を呼び出してテキストを返す"""

    def invoke_json(self, prompt: str, system: str = None) -> dict | list:
        """Claude Sonnet を呼び出してJSON解析済み結果を返す"""
```

### 5.2 モデル設定
- Model ID: `anthropic.claude-3-5-sonnet-20241022-v2:0`
- Region: `us-east-1`（Bedrock利用可能リージョン）
- Max Tokens: 2000（ライフログ抽出）/ 1000（日記サマリ）
- Temperature: 0.3（事実抽出）/ 0.7（日記生成）

---

## 6. PushService

### 6.1 subscribe(user_id, subscription)

```
入力: user_id, subscription: {endpoint, keys: {p256dh, auth}}
処理: PUSH_SUBSCRIPTION# に保存
```

### 6.2 unsubscribe(user_id)

```
処理: PUSH_SUBSCRIPTION# を削除
```

### 6.3 send_notification(user_id, title, body)

```
処理:
1. PUSH_SUBSCRIPTION# 取得
2. pywebpush で送信
3. 失敗時: 購読削除（410 Gone）
```

---

## 7. エラーハンドリング

| 状況 | 対処 |
|------|------|
| Bedrock throttling | リトライ3回（exponential backoff） |
| ジョブ失敗 | retry_count++ → 3回まで再キュー |
| Push送信失敗(410) | 購読自動削除 |
| ライフログ抽出がJSON不正 | フォールバック：空リスト + ログ出力 |
