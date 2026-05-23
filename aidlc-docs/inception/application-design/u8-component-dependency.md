# Unit 8: コンポーネント依存関係

---

## 依存マトリクス

| From ↓ / To → | C07 Api | C08 Voice | C09 Transcript | C10 Analysis | C11 Push | C12 Recovery | C13 Cognito | C14 Data | C15 Bedrock |
|----------------|---------|-----------|---------------|-------------|----------|-------------|-------------|----------|-------------|
| **C02 VoiceChat** | ● | | | | | | | | |
| **C03 Dashboard** | ● | | | | | | | | |
| **C04 DiaryView** | ● | | | | | | | | |
| **C05 RecoveryView** | ● | | | | | | | | |
| **C06 AuthModule** | | | | | | | ● | | |
| **C07 ApiGateway** | — | ● | ● | | ● | ● | ● | ● | |
| **C08 VoiceSession** | | — | | | | | | ● | |
| **C09 Transcript** | | | — | | | | | ● | |
| **C10 Analysis** | | | ● | — | ● | | | ● | ● |
| **C11 Push** | | | | | — | | | ● | |
| **C12 Recovery** | | | | | | — | | ● | ● |

● = 依存あり、— = 自身

---

## 通信パターン

### Frontend → Backend（同期）

```
┌─────────────────────────────────────────────┐
│  PWA (React SPA)                            │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐   │
│  │Voice │ │Dash  │ │Diary │ │Recovery  │   │
│  │Chat  │ │board │ │View  │ │View      │   │
│  └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘   │
│     │        │        │          │          │
│  ┌──┴────────┴────────┴──────────┴───┐      │
│  │        AuthModule (Cognito)       │      │
│  └──────────────┬────────────────────┘      │
└─────────────────┼───────────────────────────┘
                  │ HTTPS + JWT
                  ▼
┌─────────────────────────────────────────────┐
│  API Gateway (HTTP API + JWT Authorizer)    │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  SyncApiService (Lambda: ars-u8-api)        │
│  ┌───────┐ ┌──────────┐ ┌────────────┐     │
│  │Voice  │ │Transcript│ │Recovery    │     │
│  │Session│ │Service   │ │Provider    │     │
│  └───┬───┘ └────┬─────┘ └─────┬──────┘     │
│      │          │              │            │
│  ┌───┴──────────┴──────────────┴──────┐     │
│  │         DataAccess (Layer)         │     │
│  └────────────────┬───────────────────┘     │
└───────────────────┼─────────────────────────┘
                    │
                    ▼
            ┌──────────────┐
            │  DynamoDB    │
            │  (ArsTable)  │
            └──────────────┘
```

### Backend → Backend（非同期）

```
SyncApiService                     AnalysisService
┌──────────────┐                  ┌──────────────────┐
│ session_end  │                  │ AnalysisWorker   │
│   handler    │── SQS Queue ──▶│                  │
└──────────────┘                  │ ┌────────────┐   │
                                  │ │LifeLog     │   │
EventBridge                       │ │Extractor   │   │
┌──────────────┐                  │ └─────┬──────┘   │
│ cron 22:00   │── invoke ──────▶│       │          │
│ rate 5min    │                  │ ┌─────▼──────┐   │
└──────────────┘                  │ │Stress      │   │
                                  │ │Assessor    │   │
                                  │ └─────┬──────┘   │
                                  │       │          │
                                  │ ┌─────▼──────┐   │
                                  │ │Diary       │   │
                                  │ │Generator   │   │
                                  │ └─────┬──────┘   │
                                  │       │          │
                                  │ ┌─────▼──────┐   │
                                  │ │PushService │   │
                                  │ └────────────┘   │
                                  └──────────────────┘
                                         │
                                    ┌────┴────┐
                                    ▼         ▼
                              DynamoDB    Bedrock
                                       (Claude Sonnet)
```

### PWA → OpenAI（WebRTC直接）

```
PWA                    Backend              OpenAI Realtime
 │                       │                       │
 │── GET ephemeral key ─▶│                       │
 │                       │── create session ────▶│
 │                       │◀── client_secret ─────│
 │◀── client_secret ─────│                       │
 │                                               │
 │══════════ WebRTC (音声直接通信) ══════════════▶│
 │◀════════════════════════════════════════════════│
 │                                               │
 │   [transcript callbacks]                      │
 │── POST /transcript/turn ─▶ Backend            │
```

---

## データフロー

### 会話〜日記生成の完全フロー

```
1. ユーザーがPWAで音声会話を開始
   PWA → Backend: POST /api/voice-session/start
   Backend → OpenAI: create ephemeral session
   PWA ← Backend: client_secret
   PWA → OpenAI: WebRTC接続

2. 会話中（ターンごと）
   OpenAI → PWA: transcript callback
   PWA → Backend: POST /api/transcript/turn
   Backend → DynamoDB: CONVERSATION_TURN#{timestamp}

3. 会話終了
   PWA → Backend: POST /api/voice-session/end
   Backend → SQS: {type: "session_ended", user_id, session_id}

4. 非同期分析（AnalysisService）
   SQS → AnalysisService: session_ended
   AnalysisService → DynamoDB: query CONVERSATION_TURN#*
   AnalysisService → Bedrock: ライフログ抽出プロンプト
   AnalysisService → DynamoDB: LIFE_LOG#{date}#{seq}
   AnalysisService → Bedrock: ストレス判定プロンプト
   AnalysisService → DynamoDB: STRESS_SUMMARY#{date}

5. 日記生成（EventBridge 22:00）
   EventBridge → AnalysisService: generate_diary
   AnalysisService → DynamoDB: query LIFE_LOG#{today}#*
   AnalysisService → Bedrock: 日記サマリ生成プロンプト
   AnalysisService → DynamoDB: DAILY_FUREMARU_SUMMARY#{date}
   AnalysisService → PushService: 通知送信
   PushService → ユーザーブラウザ: Web Push

6. ユーザーが日記を閲覧
   PWA → Backend: GET /api/diary/{date}
   Backend → DynamoDB: query DAILY_FUREMARU_SUMMARY#{date}
   PWA: ふれまーるちゃん読み上げ演出
```

---

## 外部サービス依存

| 外部サービス | 使用コンポーネント | 通信方式 | フォールバック |
|-------------|-----------------|---------|-------------|
| OpenAI Realtime API | C02 (WebRTC), C08 (REST) | WebRTC + REST | テキストチャット（Bedrock） |
| Amazon Cognito | C06, C07, C13 | SDK / JWT | なし（認証必須） |
| Amazon Bedrock | C10, C12, C15 | boto3 | リトライ + タイムアウト |
| Web Push (VAPID) | C11 | HTTP | 通知失敗はサイレント |
| 楽天/ホットペッパー | C12 | REST API | 0円回復案のみ表示 |
