# Unit 8: アプリケーション設計書（統合）

## 1. 設計概要

| 項目 | 決定 |
|------|------|
| **フロントエンド** | Vite + React SPA（TypeScript） |
| **ホスティング** | S3 + CloudFront |
| **同期API** | API Gateway HTTP API + Lambda (`ars-u8-api`) |
| **非同期分析** | SQS + Lambda (`ars-u8-analysis`) |
| **認証** | Amazon Cognito User Pool + JWT Authorizer |
| **音声** | OpenAI Realtime API (WebRTC, ephemeral key) |
| **分析LLM** | Claude 3.5 Sonnet via Bedrock |
| **Push** | Web Push API (VAPID) |
| **DB** | DynamoDB (既存ArsTable拡張) |
| **定期ジョブ** | EventBridge → Lambda |

---

## 2. アーキテクチャ全体図

```
                    ┌─────────────────────────────┐
                    │   CloudFront + S3           │
                    │   (PWA Static Hosting)      │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │   Vite + React SPA (PWA)    │
                    │   ┌─────┐ ┌────┐ ┌─────┐   │
                    │   │Voice│ │Dash│ │Diary│   │
                    │   │Chat │ │    │ │     │   │
                    │   └──┬──┘ └─┬──┘ └──┬──┘   │
                    │      │      │       │      │
                    │   ┌──┴──────┴───────┴──┐   │
                    │   │  Auth (Cognito)    │   │
                    │   └─────────┬──────────┘   │
                    └─────────────┼───────────────┘
                                  │
              ┌───────────────────┼────────────────────┐
              │                   │                    │
              ▼                   ▼                    ▼
    ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐
    │ OpenAI       │   │ API Gateway      │   │ Cognito      │
    │ Realtime API │   │ (HTTP API)       │   │ User Pool    │
    │ (WebRTC)     │   │ + JWT Authorizer │   │              │
    └──────────────┘   └────────┬─────────┘   └──────────────┘
                                │
                    ┌───────────▼────────────┐
                    │ Lambda: ars-u8-api     │
                    │ (SyncApiService)       │
                    │ ┌────────────────────┐ │
                    │ │VoiceSession│Trans- │ │
                    │ │Service     │cript  │ │
                    │ │            │Service│ │
                    │ ├────────────┼───────┤ │
                    │ │Recovery    │Push   │ │
                    │ │Provider    │Service│ │
                    │ └─────┬──────┴───┬───┘ │
                    │       │          │     │
                    │  ┌────┴──────────┴──┐  │
                    │  │DataAccess (Layer)│  │
                    │  └────────┬─────────┘  │
                    └───────────┼─────────────┘
                       │        │
                       │        ▼
                       │  ┌──────────┐
                       │  │DynamoDB  │
                       │  │(ArsTable)│
                       │  └──────────┘
                       │
                       ▼ SQS
              ┌────────────────────────┐
              │ Lambda: ars-u8-analysis │
              │ (AnalysisService)       │
              │                         │
              │ LifeLog → Stress →      │
              │ Diary → Push            │
              │         │               │
              │    ┌────▼────┐          │
              │    │Bedrock  │          │
              │    │(Claude) │          │
              │    └─────────┘          │
              └────────────────────────┘
                       ▲
                       │
              ┌────────┴───────┐
              │  EventBridge   │
              │  - cron 22:00  │
              │  - rate 5min   │
              └────────────────┘
```

---

## 3. コンポーネント構成サマリ

### Frontend（6コンポーネント）

| ID | 名称 | 責務 |
|----|------|------|
| C01 | PWA Shell | Viteビルド、React Router、Service Worker、グローバル状態 |
| C02 | VoiceChat | WebRTC接続、Transcript収集、VAD表示、アバター |
| C03 | Dashboard | 余剰金・支出・ストレス表示 |
| C04 | DiaryView | 日記表示・履歴・読み上げ |
| C05 | RecoveryView | 回復案カード・段階的誘導 |
| C06 | AuthModule | Cognito認証・JWT管理・デモログイン |

### Backend（6コンポーネント）

| ID | 名称 | 実行環境 | 責務 |
|----|------|---------|------|
| C07 | ApiGateway | Lambda (sync) | ルーティング・認証・リクエスト処理 |
| C08 | VoiceSessionService | Lambda内 | ephemeral key発行・セッション管理 |
| C09 | TranscriptService | Lambda内 | Transcript保存・セッション終了検知 |
| C10 | AnalysisWorker | Lambda (async) | LLM分析（ライフログ・ストレス・日記） |
| C11 | PushService | Lambda内 | Web Push送信・購読管理 |
| C12 | RecoveryProvider | Lambda内 | 回復案生成（0円+有料）+ LLMで提案文変換 |

### Infrastructure / Layer（3コンポーネント）

| ID | 名称 | 責務 |
|----|------|------|
| C13 | CognitoAuth | User Pool・JWT検証・デモユーザー |
| C14 | DataAccess | DynamoDB CRUD・ID解決 |
| C15 | BedrockClient | Claude Sonnet呼び出し・プロンプト管理 |

---

## 4. Lambda構成

| Lambda名 | タイプ | トリガー | タイムアウト | メモリ |
|----------|--------|---------|------------|--------|
| `ars-u8-api` | 同期 | API Gateway HTTP API | 29s | 256MB |
| `ars-u8-analysis` | 非同期 | SQS + EventBridge | 300s | 512MB |

---

## 5. API設計サマリ

| グループ | エンドポイント数 | 主要操作 |
|---------|---------------|---------|
| Voice Session | 2 | start, end |
| Transcript | 2 | turn, bulk |
| Dashboard | 1 | get |
| Diary | 2 | list, detail |
| Recovery | 3 | get, permit, skip |
| Push | 2 | subscribe, unsubscribe |
| Settings | 2 | get, update |
| **合計** | **14** | |

---

## 6. データモデル（確定）

SK統一命名規則（`UPPER_SNAKE_CASE#{パラメータ}`）：

| SK | 用途 | 書込元 |
|----|------|--------|
| `PROFILE#` | ユーザー設定 | SyncApiService |
| `CONVERSATION_TURN#{timestamp}` | 会話ターン | SyncApiService |
| `LIFE_LOG#{date}#{seq}` | ライフログ | AnalysisService |
| `DAILY_FUREMARU_SUMMARY#{date}` | 日記サマリ | AnalysisService |
| `STRESS_SUMMARY#{date}` | ストレス判定 | AnalysisService |
| `EXPENSE#{timestamp}` | 支出記録 | SyncApiService / AnalysisService |
| `REWARD_PERMIT#{timestamp}` | 回復実行 | SyncApiService |
| `REWARD_SKIP#{timestamp}` | 回復スキップ | SyncApiService |
| `MONTHLY_SUMMARY#{yyyy-mm}` | 月次集計 | AnalysisService |
| `PUSH_SUBSCRIPTION#` | Push購読 | SyncApiService |
| `VOICE_SESSION#{sessionId}` | 音声セッション管理 | SyncApiService |
| `ANALYSIS_JOB#{jobId}` (PK: ANALYSIS_JOB#{jobId}, SK: META#) | 非同期分析ジョブ管理 | SyncApiService / AnalysisService |

---

## 7. 技術スタック確定

| 層 | 技術 | バージョン |
|----|------|-----------|
| Frontend Build | Vite | 6.x |
| Frontend Framework | React | 19.x |
| Frontend Language | TypeScript | 5.x |
| CSS | TailwindCSS or CSS Modules | TBD |
| State Management | React Context + useReducer | — |
| Backend Runtime | Python | 3.13 |
| IaC | AWS SAM | — |
| DB | DynamoDB | — |
| Auth | Amazon Cognito | — |
| LLM (Voice) | OpenAI Realtime API | gpt-4o-realtime |
| LLM (Analysis) | Claude 3.5 Sonnet | Bedrock |
| Push | pywebpush (VAPID) | — |
| CDN | CloudFront | — |
| Static Hosting | S3 | — |
| Queue | SQS | — |
| Scheduler | EventBridge | — |

---

## 8. 詳細設計ドキュメント参照

- コンポーネント定義: `u8-components.md`
- メソッドシグネチャ: `u8-component-methods.md`
- サービス・オーケストレーション: `u8-services.md`
- 依存関係・通信パターン: `u8-component-dependency.md`
