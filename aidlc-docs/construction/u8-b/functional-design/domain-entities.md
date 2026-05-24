# U8-B: 音声チャット — ドメインエンティティ

> **⚠️ 方針変更 (2026-05-24)**: OpenAI Realtime API → Amazon Nova Sonic に移行済み

## 1. VoiceSession エンティティ

### DynamoDB 格納

| 属性 | 型 | 説明 |
|------|---|------|
| PK | S | `USER#{user_id}` |
| SK | S | `VOICE_SESSION#{session_id}` |
| status | S | `active` / `completed` / `aborted` |
| voice_provider | S | `bedrock_nova_sonic` |
| model | S | `amazon.nova-sonic-v1:0` |
| voice | S | `Kazuha` |
| connection_id | S | WebSocket connection ID |
| started_at | S | ISO8601 |
| ended_at | S | ISO8601 (終了時) |
| duration_sec | N | 会話時間（秒） |
| turn_count | N | 保存ターン数 |
| created_at | S | ISO8601 |
| updated_at | S | ISO8601 |

### ライフサイクル
```
create (status=active)
  → update (turn_count++)
  → complete (status=completed, ended_at, duration_sec)
  or
  → abort (status=aborted, reason)
```

---

## 2. ConversationTurn エンティティ

### DynamoDB 格納

| 属性 | 型 | 説明 |
|------|---|------|
| PK | S | `USER#{user_id}` |
| SK | S | `CONVERSATION_TURN#{timestamp}` |
| session_id | S | 所属セッションID |
| role | S | `user` / `assistant` |
| content | S | テキスト内容 |
| turn_index | N | セッション内連番 |
| created_at | S | ISO8601 |

### 注意
- timestamp はミリ秒精度のISO8601
- 同一セッション内の全ターンは session_id で紐づけ
- クエリ: `PK = USER#{user_id} AND SK begins_with CONVERSATION_TURN#` でセッション横断取得可

---

## 3. AnalysisJob エンティティ

### DynamoDB 格納

| 属性 | 型 | 説明 |
|------|---|------|
| PK | S | `ANALYSIS_JOB#{job_id}` |
| SK | S | `META#` |
| user_id | S | 対象ユーザー |
| session_id | S | 対象セッション |
| job_type | S | `conversation_analysis` |
| status | S | `queued` / `processing` / `completed` / `failed` |
| created_at | S | ISO8601 |
| started_at | S | 処理開始時刻 |
| completed_at | S | 処理完了時刻 |
| error | S | エラー時のメッセージ |
| retry_count | N | リトライ回数 |

### ステータス遷移
```
queued → processing → completed
                   → failed (retry_count < 3 → 再キュー)
```

---

## 4. 全SK一覧（U8-B追加分）

| SK パターン | Unit | エンティティ |
|------------|------|-------------|
| `VOICE_SESSION#{session_id}` | U8-B | VoiceSession |
| `CONVERSATION_TURN#{timestamp}` | U8-B | ConversationTurn |

| PK パターン (専用) | SK | Unit | エンティティ |
|-------------------|---|------|-------------|
| `ANALYSIS_JOB#{job_id}` | `META#` | U8-B | AnalysisJob |

---

## 5. SQS メッセージスキーマ

### analysis-queue メッセージ

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "job_type": "conversation_analysis",
  "created_at": "2026-05-24T10:30:00.000Z"
}
```
