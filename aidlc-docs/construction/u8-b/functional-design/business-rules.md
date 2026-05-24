# U8-B: 音声チャット — ビジネスルール

> **⚠️ 方針変更 (2026-05-24)**: OpenAI Realtime API → Amazon Nova Sonic に移行済み

## 1. 音声セッション管理ルール

### VOICE-01: セッション開始条件
- ユーザーが認証済み（JWT有効）であること
- WebSocket $connect で JWT 検証に成功していること
- 同時アクティブセッションは1ユーザー1つまで
- 既にactiveセッションがある場合は先に自動終了させる

### VOICE-02: セッション最大時間
- 1セッションの最大時間: Lambda タイムアウト 300秒（5分）
- 各ターンは独立した Bedrock ストリームで処理
- Lambda タイムアウトは1ターンあたりの制限（セッション全体はフロントエンドで管理）

### VOICE-03: セッション終了条件
- ユーザーが明示的に終了ボタンを押す（endSession アクション）
- Nova Sonic が stopConversation ツールを呼出（終了キーワード検出）
- WebSocket 切断（$disconnect → クリーンアップ）
- ブラウザ/タブを閉じた場合

### VOICE-04: 終了キーワード
以下のキーワードをテキスト入力で検出した場合、会話を終了する:
- "終了", "バイバイ", "さようなら", "またね", "おわり", "じゃあね"

---

## 2. WebSocket 通信ルール

### WS-01: 認証
- $connect 時に query parameter `token` で JWT を検証
- JWT の issuer が Cognito User Pool ID と一致すること
- token_use = "id" であること
- exp が現在時刻より未来であること

### WS-02: メッセージフォーマット（クライアント → サーバー）
```json
{ "action": "startSession" }
{ "action": "audioChunk", "audio_data": "<base64 PCM 16kHz>" }
{ "action": "textMessage", "text": "<テキスト>" }
{ "action": "endSession" }
```

### WS-03: メッセージフォーマット（サーバー → クライアント）
```json
{ "type": "sessionStarted", "session_id": "uuid" }
{ "type": "audioResponse", "audio_data": "<base64 PCM 24kHz>" }
{ "type": "transcript", "role": "user|assistant", "content": "text" }
{ "type": "turnComplete" }
{ "type": "conversationEndRequested" }
{ "type": "sessionEnded", "analysis_job_id": "uuid" }
{ "type": "error", "message": "..." }
```

---

## 3. Transcript ルール

### TRANS-01: ターン保存フォーマット
```json
{
  "role": "user" | "assistant",
  "content": "テキスト内容",
  "timestamp": "2026-05-24T10:30:00.000Z"
}
```

### TRANS-02: 保存タイミング
- バックエンドで保存（Nova Sonic の transcript イベント受信時）
- フロントエンドからの bulk 送信は不要

### TRANS-03: source 属性
- 音声会話ターン: `source = "pwa_sonic_voice"`
- テキストフォールバック: `source = "pwa_sonic_voice"`（同一）

---

## 4. ANALYSIS_JOB ルール

### JOB-01: ジョブ作成条件
- セッション終了時（end_session）に自動作成
- turn_count > 0 の場合のみ（空セッションはジョブ作成しない）

### JOB-02: ジョブステータス遷移
```
queued → processing → completed
                   → failed (リトライ対象)
```

### JOB-03: SQS メッセージ形式
```json
{
  "job_id": "uuid",
  "user_id": "uuid",
  "session_id": "uuid",
  "job_type": "conversation_analysis"
}
```

---

## 5. Nova Sonic 設定ルール

### SONIC-01: モデル設定
- Model: `amazon.nova-sonic-v1:0`
- Voice: `Kazuha`（日本語女性）
- 入力: PCM 16kHz 16bit mono
- 出力: PCM 24kHz 16bit mono
- リージョン: us-east-1

### SONIC-02: ターンベース設計
- 1ユーザー発話 = 1 InvokeModelWithBidirectionalStream コール
- 会話履歴はコンテキストとして各ターンに渡す
- Nova Sonic はストリーミングで音声 + テキストを返却

### SONIC-03: ツール定義
- `stopConversation`: Nova Sonic がユーザーの会話終了意図を検出した場合に呼出

---

## 6. バリデーションルール

### VAL-01: $connect
- token query param: 必須、有効な JWT

### VAL-02: startSession
- 認証済み接続であること（$connect 成功済み）

### VAL-03: audioChunk
- audio_data: 必須、base64エンコードされたPCMデータ
- セッションがactive状態であること

### VAL-04: textMessage
- text: 必須、1-10000文字
- セッションがactive状態であること

### VAL-05: endSession
- セッションがactive状態であること

---

## 7. セキュリティルール

### SEC-01: 認証
- WebSocket 接続に JWT 必須（query param）
- Lambda 内で JWT ペイロードをデコード・検証
- Cognito User Pool の issuer チェック

### SEC-02: セッション所有権
- 各 WebSocket 接続は 1 ユーザーに紐づく
- connection_id と user_id のマッピングはセッション内で管理
- 他ユーザーのセッションには操作不可

### SEC-03: API Gateway 設定
- WebSocket API にはカスタムオーソライザーなし（Lambda $connect で検証）
- @connections API で応答をプッシュ
