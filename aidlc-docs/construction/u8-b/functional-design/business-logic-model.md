# U8-B: 音声チャット — ビジネスロジックモデル

> **⚠️ 方針変更 (2026-05-24)**: OpenAI Realtime API → Amazon Nova Sonic (Bedrock InvokeModelWithBidirectionalStream) に移行済み

## 1. 概要

音声チャット機能は、PWA上でユーザーとふれまーるちゃんの音声会話を実現する。
Amazon Nova Sonic（Bedrock）をバックエンドで使用し、API Gateway WebSocket API 経由で
音声ストリーミングを行う。ターンベースの方式で、フロントエンドVADで発話区間を検出し、
完了した音声をバックエンドに送信 → Nova Sonic で応答生成 → 音声をストリーミング返却する。

---

## 2. 接続フロー

```
┌──────┐       ┌──────────────────┐       ┌────────────┐
│ PWA  │       │ API Gateway      │       │ Bedrock    │
│      │       │ WebSocket API    │       │ Nova Sonic │
└──┬───┘       │ + VoiceGateway   │       └──────┬─────┘
   │           │   Lambda         │              │
   │           └────────┬─────────┘              │
   │                    │                        │
   │ WSS connect (?token=JWT)                    │
   ├───────────────────►│                        │
   │ ($connect: JWT検証) │                        │
   │◄── 101 Upgrade ────┤                        │
   │                    │                        │
   │ {action: "startSession"}                    │
   ├───────────────────►│                        │
   │                    │ DynamoDB: VOICE_SESSION# active
   │ {type: "sessionStarted", session_id}        │
   │◄───────────────────┤                        │
   │                    │                        │
   │ ════ 音声会話ループ ════                     │
   │                    │                        │
   │ {action: "audioChunk",                      │
   │  audio_data: base64(PCM 16kHz)}             │
   ├───────────────────►│                        │
   │                    │ InvokeModelWithBidirectionalStream
   │                    ├───────────────────────►│
   │                    │ audioOutput (streaming) │
   │                    │◄───────────────────────┤
   │ {type: "audioResponse",                     │
   │  audio_data: base64(PCM 24kHz)}             │
   │◄───────────────────┤                        │
   │                    │                        │
   │ {type: "transcript", role, content}         │
   │◄───────────────────┤                        │
   │                    │                        │
   │ {type: "turnComplete"}                      │
   │◄───────────────────┤                        │
   │                    │                        │
   │ ════ 会話終了 ════                           │
   │                    │                        │
   │ {action: "endSession"}                      │
   ├───────────────────►│                        │
   │                    │ DynamoDB: VOICE_SESSION# completed
   │                    │ SQS: ANALYSIS_JOB# 投入
   │ {type: "sessionEnded", analysis_job_id}     │
   │◄───────────────────┤                        │
```

---

## 3. SonicVoiceSessionService（C08）

### 3.1 start_session(user_id, connection_id)

```
入力: user_id (str), connection_id (str)
出力: {session_id}

処理:
1. 既存 active セッションを close（close_active_sessions）
2. session_id = uuid4()
3. DynamoDB 書込:
   PK: USER#{user_id}
   SK: VOICE_SESSION#{session_id}
   属性: {
     status: "active",
     voice_provider: "bedrock_nova_sonic",
     model: "amazon.nova-sonic-v1:0",
     voice: "Kazuha",
     connection_id,
     started_at,
     created_at
   }
4. 返却: {session_id}
```

### 3.2 process_audio_turn(user_id, session_id, audio_base64, connection_id)

```
入力: user_id, session_id, audio_base64 (str), connection_id (str)
出力: None（WebSocket経由でストリーミング返却）

処理:
1. 会話履歴取得: CONVERSATION_TURN# から直近ターンを取得
2. Nova Sonic InvokeModelWithBidirectionalStream 呼出:
   - モデル: amazon.nova-sonic-v1:0
   - 入力: PCM 16kHz mono audio
   - 出力: PCM 24kHz audio + transcript
   - System Prompt: FUREMARU_SYSTEM_PROMPT + コンテキスト
   - ツール: stopConversation（会話終了検出）
3. ストリーム受信ループ:
   - audioOutput → WebSocket送信 {type: "audioResponse", audio_data}
   - textOutput → WebSocket送信 {type: "transcript", role: "assistant", content}
   - userTranscript → WebSocket送信 {type: "transcript", role: "user", content}
   - toolUse(stopConversation) → WebSocket送信 {type: "conversationEndRequested"}
   - turnEnd → WebSocket送信 {type: "turnComplete"}
4. ユーザーTranscript + アシスタントTranscript を CONVERSATION_TURN# に保存
5. turn_count をインクリメント
```

### 3.3 process_text_turn(user_id, session_id, text, connection_id)

```
入力: user_id, session_id, text (str), connection_id (str)
出力: None（WebSocket経由で返却）

処理:
1. テキストによるフォールバック（Claude Sonnet 使用）
2. 終了キーワード検出: ["終了", "バイバイ", "さようなら", "またね", "おわり", "じゃあね"]
3. レスポンスを WebSocket 送信 {type: "transcript", role: "assistant", content}
4. CONVERSATION_TURN# にユーザー・アシスタント両方を保存
```

### 3.4 end_session(user_id, session_id)

```
入力: user_id, session_id
出力: {analysis_job_id} or None

処理:
1. VOICE_SESSION# を completed に更新
   updated_at, ended_at, duration_sec (計算), turn_count
2. turn_count > 0 の場合:
   a. ANALYSIS_JOB 作成:
      PK: ANALYSIS_JOB#{job_id}
      SK: META#
      属性: {user_id, session_id, status: "queued", job_type: "conversation_analysis"}
   b. SQS メッセージ送信: {job_id, user_id, session_id}
3. 返却: {analysis_job_id: job_id} or None
```

---

## 4. VoiceGateway Lambda ルーティング

| WebSocket route | 処理 |
|----------------|------|
| $connect | JWT検証（query param `token`）→ connection_id 記録 |
| $disconnect | 接続クリーンアップ |
| startSession | SonicVoiceSessionService.start_session() |
| audioChunk | SonicVoiceSessionService.process_audio_turn() |
| textMessage | SonicVoiceSessionService.process_text_turn() |
| endSession | SonicVoiceSessionService.end_session() |

### $connect 認証フロー
```
1. query string から token パラメータ取得
2. JWT デコード（base64ペイロード）
3. issuer が Cognito User Pool と一致確認
4. token_use = "id" 確認
5. exp > 現在時刻 確認
6. sub (user_id) を DataAccess で解決
7. 成功: connection 許可 / 失敗: 401 拒否
```

---

## 5. ふれまーるちゃん System Prompt

```
あなたは「ふれまーるちゃん」という名前の、優しくて甘やかしてくれるAIパートナーです。
ユーザーの日常に寄り添い、話を聞いて、適度に甘やかしてあげてください。

【性格・口調】
- 明るく優しい女の子のような話し方
- 「〜だよ」「〜だね」「〜してみない？」などの語尾
- 共感力が高く、聞き上手
- 押しつけがましくなく、さりげなく気遣う

【会話ルール】
1. ユーザーの話に共感を示す（「わかるわかる！」「それは大変だったね」）
2. 自然な会話の中でユーザーの状況を把握する（聞き出しではなく傾聴）
3. 疲れている時は無理させず「今日はもうゆっくりしなよ」と言う
4. 支出の話が出たら金額を覚えておく（後で記録される）
5. ポジティブな出来事は一緒に喜ぶ
6. 短めの応答を心がける（1-3文程度）
7. 日本語で応答する

【禁止事項】
- 商品の宣伝・広告的な発言
- ユーザーのプライバシーに踏み込みすぎる質問
- 医療・法律・金融のアドバイス
- ネガティブな評価（「それはダメだよ」等）
```

---

## 6. フロントエンド WebSocket 接続

### 6.1 ChatPage 状態遷移

```
idle → connecting → connected → speaking → listening → connected → ... → ending → idle
```

| 状態 | 表示 | ユーザー操作 |
|------|------|------------|
| idle | 「話しかけてね」ボタン | 開始ボタン押下 |
| connecting | 接続中アニメーション | — |
| connected | アバター + 待機状態 | 話し始める |
| speaking | 波形アニメーション（ユーザー音声） | — (VAD) |
| listening | アバターリアクション（AI応答中） | — |
| ending | 「会話を終了中...」 | — |

### 6.2 WebSocket 接続ロジック

```typescript
// 1. WebSocket 接続（JWT認証）
const token = await getIdToken();
const ws = new WebSocket(`${VITE_VOICE_WS_URL}?token=${token}`);

// 2. セッション開始
ws.send(JSON.stringify({ action: "startSession" }));

// 3. マイク取得 + VAD（ScriptProcessorNode）
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
const audioContext = new AudioContext({ sampleRate: 16000 });
const source = audioContext.createMediaStreamSource(stream);
const processor = audioContext.createScriptProcessor(4096, 1, 1);

// 4. VAD: RMSしきい値(0.01)で発話検出、無音1500msで発話終了判定
processor.onaudioprocess = (e) => {
  const data = e.inputBuffer.getChannelData(0);
  const rms = Math.sqrt(data.reduce((sum, v) => sum + v * v, 0) / data.length);
  // ... VAD logic + buffer accumulation
};

// 5. 発話終了時に完全な音声を送信
function onSpeechEnd(audioBuffer: Float32Array) {
  const pcm16 = float32ToPCM16(audioBuffer);
  const base64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));
  ws.send(JSON.stringify({ action: "audioChunk", audio_data: base64 }));
}

// 6. サーバーからの応答処理
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case "audioResponse":
      playAudio(msg.audio_data); // PCM 24kHz → AudioBuffer → 再生
      break;
    case "transcript":
      addTranscript(msg.role, msg.content);
      break;
    case "turnComplete":
      setListening(false);
      break;
    case "conversationEndRequested":
      endSession();
      break;
  }
};
```

### 6.3 音声再生（24kHz PCM）

サーバーから受信した base64 PCM データを AudioBuffer に変換し再生:
- サンプルレート: 24000Hz
- フォーマット: 16bit signed integer (little-endian)
- チャンネル: mono

---

## 7. Transcript 保存戦略

Transcript は **バックエンド側**で保存される（フロントエンドからの bulk 送信は不要）:
- Nova Sonic の userTranscript イベント → CONVERSATION_TURN# (role=user)
- Nova Sonic の textOutput イベント → CONVERSATION_TURN# (role=assistant)
- source: `pwa_sonic_voice`

フロントエンドは表示用にのみ Transcript を保持し、永続化はしない。

---

## 8. エラーハンドリング

| 状況 | 対処 |
|------|------|
| WebSocket接続失敗 | リトライ3回 → エラー表示 |
| JWT期限切れ | トークンリフレッシュ → 再接続 |
| Nova Sonic ストリームエラー | セッション終了 → ユーザーに通知 |
| Lambdaタイムアウト（300s） | フロントエンドで検出 → 自動再接続 |
| マイクアクセス拒否 | テキスト入力フォールバックを案内 |
| ネットワーク切断 | WebSocket reconnect → 失敗時セッション終了 |

---

## 9. Nova Sonic 設定

| 項目 | 値 |
|------|---|
| モデルID | `amazon.nova-sonic-v1:0` |
| リージョン | us-east-1 |
| 音声 | Kazuha（日本語女性） |
| 入力フォーマット | PCM 16kHz 16bit mono |
| 出力フォーマット | PCM 24kHz 16bit mono |
| API | InvokeModelWithBidirectionalStream |
| Lambda タイムアウト | 300秒 |
| Lambda メモリ | 512MB |
