# Unit 8: サービス定義とオーケストレーション

---

## サービス一覧

| サービス名 | 実行環境 | トリガー | 責務 |
|-----------|---------|---------|------|
| SyncApiService | Lambda (Python) | API Gateway HTTP API | 同期リクエスト処理（認証・データ取得・セッション管理） |
| AnalysisService | Lambda (Python) | SQS + EventBridge | 非同期LLM分析（ライフログ・ストレス・日記） |
| PushNotificationService | Lambda内モジュール | AnalysisService から呼び出し | Web Push 送信 |

---

## SyncApiService

### 概要
- **Lambda名**: `ars-u8-api`
- **ランタイム**: Python 3.13
- **トリガー**: API Gateway HTTP API（Cognito JWT Authorizer）
- **メモリ**: 256MB
- **タイムアウト**: 29秒

### エンドポイント一覧

| メソッド | パス | 機能 | 使用コンポーネント |
|---------|------|------|-----------------|
| POST | /api/voice-session/start | ephemeral key発行 + VOICE_SESSION作成 | C08 VoiceSessionService |
| POST | /api/voice-session/end | セッション終了 + ANALYSIS_JOB作成 + SQS投入 | C08, C09 |
| POST | /api/transcript/turn | Transcript 1ターン保存 | C09 TranscriptService |
| POST | /api/transcript/bulk | Transcript バッチ保存（再送） | C09 |
| GET | /api/dashboard | ダッシュボードデータ取得 | C14 DataAccess |
| GET | /api/diary | 日記一覧取得 | C14 |
| GET | /api/diary/{date} | 日記詳細取得 | C14 |
| GET | /api/recovery | 回復案取得 | C12 RecoveryProvider |
| POST | /api/recovery/permit | 回復実行記録 | C12 |
| POST | /api/recovery/skip | 回復スキップ記録 | C12 |
| POST | /api/push/subscribe | Push購読登録 | C11 PushService |
| DELETE | /api/push/subscribe | Push購読解除 | C11 |
| GET | /api/settings | 設定取得 | C14 |
| PUT | /api/settings | 設定更新 | C14 |

### 認証フロー
1. クライアント: Authorization ヘッダーに Cognito Access Token を付与
2. API Gateway: Cognito JWT Authorizer で検証
3. Lambda: `event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]` からユーザー特定
4. DataAccess: `resolve_user_id(cognito_sub)` で内部IDに変換

---

## AnalysisService

### 概要
- **Lambda名**: `ars-u8-analysis`
- **ランタイム**: Python 3.13
- **トリガー**: SQS キュー (`ars-u8-analysis-queue`) + EventBridge
- **メモリ**: 512MB（LLM呼び出しのレスポンス処理用）
- **タイムアウト**: 300秒（5分）

### イベントタイプ

| イベント | ソース | 処理内容 |
|---------|--------|---------|
| `session_ended` | SQS（SyncApiServiceから投入） | ライフログ抽出 + ストレス判定 |
| `generate_diary` | EventBridge（日次22:00） | 日記サマリ生成 + Push通知 |
| `reprocess_missed` | EventBridge（5分ごと） | 未処理セッション検出・再処理 |

### オーケストレーションフロー

#### フロー1: セッション終了 → ライフログ + ストレス判定

```
SyncApiService                    SQS                    AnalysisService
     |                             |                          |
     |-- session_ended event ----->|                          |
     |                             |-- deliver message ------>|
     |                             |                          |
     |                             |      1. get_session_transcript()
     |                             |      2. extract_life_log()
     |                             |         → Claude Sonnet
     |                             |      3. save LIFE_LOG#{date}#{seq}
     |                             |      4. assess_stress()
     |                             |         → Claude Sonnet
     |                             |      5. save STRESS_SUMMARY#{date}
     |                             |      6. (if stress >= 4) trigger recovery suggestion
```

#### フロー2: 日次日記サマリ生成

```
EventBridge (22:00)              AnalysisService              PushService
     |                                |                          |
     |-- generate_diary event ------->|                          |
     |                                |                          |
     |                     1. query LIFE_LOG#{today}#*           |
     |                     2. query STRESS_SUMMARY#{today}       |
     |                     3. generate_diary_summary()           |
     |                        → Claude Sonnet                    |
     |                     4. save DAILY_FUREMARU_SUMMARY#{date} |
     |                     5. send_notification() ------------->|
     |                                                          |-- Web Push
```

#### フロー3: 未処理セッション再処理

```
EventBridge (5min)               AnalysisService
     |                                |
     |-- reprocess_missed event ----->|
     |                                |
     |                     1. scan sessions without analysis
     |                     2. for each: extract_life_log() + assess_stress()
```

---

## フロントエンド → バックエンド通信

### API クライアント設計（React）

```typescript
// src/lib/api.ts
const API_BASE = import.meta.env.VITE_API_URL; // API Gateway URL

async function apiClient<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getAccessToken(); // Cognito JWT
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...options?.headers,
    },
  });
  if (!res.ok) throw new ApiError(res.status, await res.json());
  return res.json();
}
```

### WebRTC セッションフロー

```
PWA (React)                  SyncApiService              OpenAI Realtime
     |                            |                           |
     |-- POST /voice-session/start -->|                       |
     |                            |-- create ephemeral key -->|
     |                            |<-- client_secret ---------|
     |<-- {client_secret} --------|                           |
     |                                                        |
     |-- WebRTC SDP offer (using client_secret) ------------->|
     |<-- WebRTC SDP answer -----------------------------------|
     |                                                        |
     |<========== 音声ストリーム（双方向）====================>|
     |                                                        |
     |-- POST /transcript/turn -->|  (ターンごとに非同期送信)  |
     |                            |                           |
     |-- POST /voice-session/end ->|                          |
     |                            |-- SQS: session_ended ---->| (→ AnalysisService)
```

---

## インフラ構成（概要）

```
CloudFront
  └── S3 Bucket (PWA静的ファイル)

API Gateway (HTTP API)
  ├── Cognito JWT Authorizer
  └── Lambda: ars-u8-api (SyncApiService)
        ├── → DynamoDB (ArsTable)
        ├── → OpenAI API (ephemeral key)
        └── → SQS (analysis-queue)

SQS: ars-u8-analysis-queue
  └── Lambda: ars-u8-analysis (AnalysisService)
        ├── → DynamoDB (ArsTable)
        ├── → Bedrock (Claude Sonnet)
        └── → Web Push (pywebpush)

EventBridge
  ├── Rule: diary-generation (cron 22:00 JST daily)
  └── Rule: reprocess-missed (rate 5 min)
        └── → Lambda: ars-u8-analysis

Cognito User Pool: ars-u8-users
  └── App Client → PWA
```
