# U8-B: 音声チャット — フロントエンドコンポーネント

> **⚠️ 方針変更 (2026-05-24)**: WebRTC/DataChannel → WebSocket + VAD に移行済み

## 1. ChatPage（メイン画面）

### 構成
```
ChatPage
├── AvatarDisplay          # ふれまーるちゃんアバター
├── TranscriptDisplay      # 会話履歴テキスト表示
├── VoiceControls          # マイクON/OFF、終了ボタン
│   ├── StartButton        # 会話開始
│   ├── EndButton          # 会話終了
│   └── VoiceIndicator     # 音声状態インジケーター
└── TextInput              # テキスト入力フォールバック
```

### 状態管理（useVoiceChat hook）

```typescript
interface VoiceChatState {
  status: 'idle' | 'connecting' | 'connected' | 'speaking' | 'listening' | 'ending';
  sessionId: string | null;
  transcripts: TranscriptTurn[];
  error: string | null;
  duration: number; // seconds
}

interface TranscriptTurn {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}
```

### アクション

| アクション | トリガー | 処理 |
|-----------|---------|------|
| startSession | 開始ボタン押下 | WebSocket接続 → startSession送信 |
| endSession | 終了ボタン / 終了キーワード | endSession送信 → WebSocket切断 |
| sendAudio | VAD発話終了検出 | audioChunk送信（base64 PCM） |
| sendText | テキスト入力送信 | textMessage送信 |
| addTranscript | サーバーからtranscript受信 | state更新 |

---

## 2. AvatarDisplay

### 仕様
- 表示: ふれまーるちゃんの静止画（将来3D化対応）
- サイズ: 画面幅 80%、最大 320px
- アニメーション:
  - idle: 微かな呼吸アニメーション (CSS)
  - listening (AI応答中): 軽いバウンス
  - ユーザー発話中: 静止（聞いてる）

### CSSアニメーション
```css
.avatar-idle { animation: breathe 3s ease-in-out infinite; }
.avatar-listening { animation: bounce 0.6s ease infinite; }
```

---

## 3. VoiceIndicator

### 状態表示

| 状態 | 表示 | 色 |
|------|------|---|
| idle | ○ マイクアイコン | グレー |
| connecting | ● 回転 | ピンク |
| speaking | ◉ 波形 | ピンク(濃) |
| listening | ◉ パルス | ピンク(薄) |

---

## 4. TranscriptDisplay

### 仕様
- チャットバブル形式（LINEライク）
- ユーザー: 右寄せ、ピンク背景
- ふれまーる: 左寄せ、白背景
- 自動スクロール（最新メッセージ）
- 最大表示: 直近50ターン（それ以上はスクロールで表示）

---

## 5. useVoiceChat フック

```typescript
function useVoiceChat() {
  // State
  const [state, dispatch] = useReducer(voiceChatReducer, initialState);
  
  // WebSocket connection ref
  const wsRef = useRef<WebSocket | null>(null);
  
  // Audio context for recording (16kHz) and playback (24kHz)
  const recordingCtxRef = useRef<AudioContext | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  
  // VAD state
  const isSpeakingRef = useRef(false);
  const silenceTimerRef = useRef<number | null>(null);
  const audioBufferRef = useRef<Float32Array[]>([]);
  
  // Actions
  const startSession = async () => {
    const token = await getIdToken();
    const ws = new WebSocket(`${VITE_VOICE_WS_URL}?token=${token}`);
    ws.onopen = () => ws.send(JSON.stringify({ action: "startSession" }));
    ws.onmessage = handleMessage;
    // ...
  };
  
  const endSession = async () => {
    wsRef.current?.send(JSON.stringify({ action: "endSession" }));
  };
  
  const sendTextMessage = (text: string) => {
    wsRef.current?.send(JSON.stringify({ action: "textMessage", text }));
  };
  
  // Cleanup on unmount
  useEffect(() => () => cleanup(), []);
  
  return { state, startSession, endSession, sendTextMessage };
}
```

### VAD (Voice Activity Detection)

```typescript
// ScriptProcessorNode (bufferSize: 4096, 16kHz)
// RMS threshold: 0.01
// Silence duration: 1500ms → 発話終了判定

processor.onaudioprocess = (e) => {
  const data = e.inputBuffer.getChannelData(0);
  const rms = Math.sqrt(data.reduce((sum, v) => sum + v * v, 0) / data.length);
  
  if (rms > THRESHOLD) {
    isSpeaking = true;
    resetSilenceTimer();
    audioBuffer.push(data.slice());
  } else if (isSpeaking) {
    audioBuffer.push(data.slice());
    startSilenceTimer(() => {
      // 発話終了 → audioChunk 送信
      const fullAudio = concatenateBuffers(audioBuffer);
      sendAudioChunk(fullAudio);
      audioBuffer = [];
      isSpeaking = false;
    }, 1500);
  }
};
```

---

## 6. TextInput（テキストフォールバック）

### 仕様
- チャット画面下部にテキスト入力フィールド
- 音声が使えない環境のフォールバック
- Enter で送信 → textMessage アクションとして WebSocket 送信
- レスポンスは transcript メッセージとして受信・表示

---

## 7. 音声再生

### AudioPlayback
```typescript
// サーバーからの audioResponse を再生
function playAudio(base64Data: string) {
  const binary = atob(base64Data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  
  const pcm16 = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(pcm16.length);
  for (let i = 0; i < pcm16.length; i++) float32[i] = pcm16[i] / 32768;
  
  const audioBuffer = playbackCtx.createBuffer(1, float32.length, 24000);
  audioBuffer.getChannelData(0).set(float32);
  
  const source = playbackCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(playbackCtx.destination);
  source.start();
}
```

---

## 8. PWA オフライン対応

- 音声機能はオンライン必須（WebSocket）
- オフライン時は「ネットワーク接続が必要です」表示
- テキスト入力もオンライン必須（WebSocket経由）
