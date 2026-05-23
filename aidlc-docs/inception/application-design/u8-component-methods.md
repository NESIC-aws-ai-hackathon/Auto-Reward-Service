# Unit 8: コンポーネントメソッド定義

> **Note**: 詳細なビジネスルール・バリデーションロジックは Functional Design (per-unit) で定義する。
> ここではメソッドシグネチャと高レベルの目的のみ記載。

---

## C02: VoiceChat (Frontend)

```typescript
// セッション管理
startSession(): Promise<void>
  // → バックエンドからephemeral key取得 → WebRTC接続確立
endSession(): Promise<void>
  // → WebRTC切断 → 未送信Transcript flush → セッション終了API呼び出し

// Transcript管理
sendTranscriptTurn(turn: TranscriptTurn): Promise<void>
  // → ターンをバックエンドに送信。失敗時IndexedDBにキャッシュ
flushCachedTranscripts(): Promise<void>
  // → IndexedDBの未送信Transcriptをバックエンドに再送

// UI制御
toggleTextMode(): void
  // → 音声/テキストモード切り替え
```

---

## C06: AuthModule (Frontend)

```typescript
signIn(email: string, password: string): Promise<AuthSession>
signUp(email: string, password: string): Promise<void>
demoLogin(): Promise<AuthSession>
  // → 事前作成済みデモユーザーで即時ログイン
signOut(): Promise<void>
getAccessToken(): Promise<string>
  // → 有効なJWTを返す（期限切れなら自動リフレッシュ）
getCurrentUser(): AuthUser | null
```

---

## C07: ApiGateway (同期API Lambda)

```python
def handler(event, context) -> dict:
    """API Gateway HTTP API ハンドラー。ルーティング + JWT検証"""

# ルート定義
POST /api/voice-session/start    → _handle_voice_session_start()
POST /api/voice-session/end      → _handle_voice_session_end()
POST /api/transcript/turn        → _handle_transcript_turn()
POST /api/transcript/bulk        → _handle_transcript_bulk()  # 再送用
GET  /api/dashboard              → _handle_get_dashboard()
GET  /api/diary                  → _handle_get_diary_list()
GET  /api/diary/{date}           → _handle_get_diary_detail()
GET  /api/recovery               → _handle_get_recovery_suggestions()
POST /api/recovery/permit        → _handle_recovery_permit()
POST /api/recovery/skip          → _handle_recovery_skip()
POST /api/push/subscribe         → _handle_push_subscribe()
DELETE /api/push/subscribe       → _handle_push_unsubscribe()
GET  /api/settings               → _handle_get_settings()
PUT  /api/settings               → _handle_update_settings()
```

---

## C08: VoiceSessionService

```python
def create_session(user_id: str, system_prompt: str) -> dict:
    """OpenAI Realtime API で ephemeral client secret を発行、VOICE_SESSIONエンティティ作成"""
    # VOICE_SESSION#{sessionId} を active 状態で作成
    # Returns: {"client_secret": "...", "session_id": "...", "expires_at": ...}

def end_session(user_id: str, session_id: str) -> dict:
    """セッション終了を記録し、ANALYSIS_JOB作成、分析ジョブをSQSに投入"""
    # VOICE_SESSION#{sessionId} を completed に更新
    # ANALYSIS_JOB#{jobId} (PK: ANALYSIS_JOB#{jobId}, SK: META#) を queued で作成
    # Returns: {"status": "ended", "analysis_job_id": "..."}

def get_system_prompt() -> str:
    """ふれまーるちゃんのキャラクター設定プロンプトを返す"""
```

---

## C09: TranscriptService

```python
def save_turn(user_id: str, session_id: str, turn: dict) -> None:
    """1ターン（ユーザー発話+AI応答）をDynamoDBに保存"""
    # SK: CONVERSATION_TURN#{timestamp}

def save_bulk(user_id: str, session_id: str, turns: list[dict]) -> None:
    """複数ターンをバッチ保存（切断復旧時の再送用）"""

def get_session_transcript(user_id: str, session_id: str) -> list[dict]:
    """セッション内の全ターンを取得"""

def mark_session_ended(user_id: str, session_id: str) -> None:
    """セッション終了マーク → 分析ジョブ作成トリガー"""
```

---

## C10: AnalysisWorker (非同期Lambda)

```python
def handler(event, context) -> None:
    """SQS/EventBridge トリガー。イベントタイプに応じて分岐"""

def extract_life_log(user_id: str, session_id: str) -> list[dict]:
    """Transcript → ライフログエントリ抽出（Claude Sonnet）"""
    # Output: [{category, content, confidence, timestamp}, ...]
    # SK: LIFE_LOG#{date}#{seq}

def assess_stress(user_id: str, date: str) -> dict:
    """会話+余剰金+ライフログからストレス判定（Claude Sonnet）"""
    # Output: {level: 1-5, signals: [...], recommended_actions: [...]}
    # SK: STRESS_SUMMARY#{date}

def generate_diary_summary(user_id: str, date: str) -> dict:
    """ライフログから日記調サマリを生成（Claude Sonnet）"""
    # Output: {summary_text, highlights: [...], mood_emoji}
    # SK: DAILY_FUREMARU_SUMMARY#{date}

def handle_missed_sessions() -> None:
    """EventBridge補助: 未処理セッションを検出して再処理"""
```

---

## C11: PushService

```python
def subscribe(user_id: str, subscription: dict) -> None:
    """Web Push サブスクリプション登録"""
    # SK: PUSH_SUBSCRIPTION#

def unsubscribe(user_id: str) -> None:
    """サブスクリプション削除"""

def send_notification(user_id: str, title: str, body: str, url: str = None) -> bool:
    """Web Push 通知送信"""
```

---

## C12: RecoveryProvider

```python
def get_recovery_suggestions(user_id: str, stress_level: int, budget: int) -> list[dict]:
    """ストレスレベルと予算に応じた回復案を生成"""
    # Returns: [{type: "free"|"paid", title, description, category, action_url?}, ...]

def get_free_recovery_options(stress_level: int) -> list[dict]:
    """０円回復案をルールベースで生成（休息、散歩、深呼吸、入浴、動画、記事等）"""

def get_paid_recovery_options(budget: int, user_context: dict) -> list[dict]:
    """有料回復案を既存Provider chainから取得"""

def format_as_furemaru_message(suggestions: list[dict]) -> list[dict]:
    """回復案をふれまーるちゃん口調の提案文に変換（BedrockClient使用）"""

def record_permit(user_id: str, recovery_item: dict) -> None:
    """回復実行記録（REWARD_PERMIT#{timestamp}）"""

def record_skip(user_id: str, recovery_item: dict) -> None:
    """回復スキップ記録（REWARD_SKIP#{timestamp}）"""
```

---

## C14: DataAccess (Layer)

```python
def put_item(pk: str, sk: str, data: dict) -> None:
def get_item(pk: str, sk: str) -> dict | None:
def query_items(pk: str, sk_prefix: str, limit: int = 50) -> list[dict]:
def query_items_between(pk: str, sk_start: str, sk_end: str) -> list[dict]:
def batch_put_items(items: list[dict]) -> None:
def delete_item(pk: str, sk: str) -> None:
def update_item(pk: str, sk: str, updates: dict) -> None:

# ユーザーID解決
def resolve_user_id(cognito_sub: str) -> str:
    """IDENTITY#COGNITO#{sub} → USER#{id} を解決。なければ新規作成"""
```

---

## C15: BedrockClient (Layer)

```python
def invoke_claude_sonnet(prompt: str, system: str = None, max_tokens: int = 4096) -> str:
    """Claude 3.5 Sonnet を呼び出し、テキストレスポンスを返す"""

def invoke_with_json_output(prompt: str, system: str = None) -> dict:
    """JSON形式のレスポンスを期待する呼び出し"""
```
