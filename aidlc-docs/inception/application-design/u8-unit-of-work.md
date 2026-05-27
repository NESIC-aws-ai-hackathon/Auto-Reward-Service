# Unit 8: Unit of Work 定義

## デプロイ方針

| 項目 | 決定 |
|------|------|
| **SAMスタック** | 新規 `ars-u8-pwa`（既存 `auto-reward-service` とは独立） |
| **DynamoDB** | 既存 `ArsTable` を参照（パラメータでARN/名前を受け取る） |
| **既存コード** | 完全分離。`liff_api.py` は変更しない |
| **Layer** | 新規 Layer を作成（既存 ArsCommonLayer は使用しない） |

## コード構成

```
Auto-Reward-Service/
├── src/                          # 既存コード（変更なし）
├── layer/                        # 既存Layer（変更なし）
├── u8/                           # ★ Unit 8 新規ディレクトリ
│   ├── frontend/                 # Vite + React SPA
│   │   ├── src/
│   │   │   ├── components/       # React コンポーネント
│   │   │   ├── hooks/            # カスタムフック
│   │   │   ├── lib/              # APIクライアント、ユーティリティ
│   │   │   ├── pages/            # ページコンポーネント
│   │   │   └── App.tsx
│   │   ├── public/
│   │   │   ├── manifest.json     # PWA マニフェスト
│   │   │   └── sw.js             # Service Worker
│   │   ├── index.html
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── vite.config.ts
│   ├── backend/
│   │   ├── handlers/
│   │   │   ├── api_handler.py    # SyncApiService (ars-u8-api)
│   │   │   └── analysis_handler.py  # AnalysisService (ars-u8-analysis)
│   │   ├── services/
│   │   │   ├── voice_session.py  # C08 VoiceSessionService
│   │   │   ├── transcript.py     # C09 TranscriptService
│   │   │   ├── analysis.py       # C10 AnalysisWorker logic
│   │   │   ├── push_service.py   # C11 PushService
│   │   │   └── recovery.py       # C12 RecoveryProvider
│   │   └── shared/
│   │       ├── data_access.py    # C14 DataAccess
│   │       ├── bedrock_client.py # C15 BedrockClient
│   │       ├── auth.py           # JWT検証ユーティリティ
│   │       └── config.py         # 環境変数・設定
│   ├── template.yaml             # SAM テンプレート (ars-u8-pwa)
│   ├── samconfig.toml
│   └── tests/
│       ├── unit/
│       └── integration/
└── aidlc-docs/                   # ドキュメント
```

---

## Unit 一覧

| Unit | 名称 | スコープ | デプロイ対象 |
|------|------|---------|------------|
| U8-A | PWA基盤 + Cognito認証 | C01, C06, C07(骨格), C13, C14 | SAMスタック初期構築 + React SPA + CloudFront + Cognito |
| U8-B | 音声チャット | C02, C08, C09 | WebRTC接続 + ephemeral key API + Transcript保存 |
| U8-C | ライフログ + 日記サマリ | C10(LifeLog/Diary), C11, C15 | AnalysisService Lambda + EventBridge + Push |
| U8-D | ストレス判定 + 回復提案 | C10(Stress), C12, C05 | ストレス分析 + 回復案生成 + RecoveryView |
| U8-E | ダッシュボード統合 | C03, C04 | Dashboard + DiaryView + ナビゲーション統合 |

---

## U8-A: PWA基盤 + Cognito認証

### 目的
Unit 8 全体の土台を構築する。認証付きPWAが動作する最小構成。

### スコープ
| コンポーネント | 内容 |
|--------------|------|
| C01 PWA Shell | Vite + React プロジェクト初期化、React Router、Service Worker登録 |
| C06 AuthModule | Cognito認証フロー（サインイン/デモログイン）、JWT管理 |
| C07 ApiGateway（骨格） | Lambda ハンドラー骨格、JWT検証、ルーティング基盤 |
| C13 CognitoAuth | Cognito User Pool + App Client (SAMリソース) |
| C14 DataAccess | DynamoDB アクセスLayer（既存ArsTable参照） |

### 成果物
- `u8/frontend/` — React SPA 初期構成（ルーティング + 認証画面）
- `u8/backend/handlers/api_handler.py` — 骨格（/api/settings のみ）
- `u8/backend/shared/data_access.py` — DynamoDB CRUD
- `u8/backend/shared/auth.py` — JWT検証
- `u8/template.yaml` — Cognito, Lambda, API Gateway, S3, CloudFront

### デプロイ確認
- `sam deploy` 成功
- CloudFront URL でPWA表示
- デモログイン → JWT取得 → /api/settings 呼び出し成功

---

## U8-B: 音声チャット

### 目的
ふれまーるちゃんとの音声会話ができるコア体験を実装する。

### スコープ
| コンポーネント | 内容 |
|--------------|------|
| C02 VoiceChat | WebRTC接続UI、VADインジケーター、Transcript収集、IndexedDBキャッシュ |
| C08 VoiceSessionService | ephemeral key発行、VOICE_SESSION管理 |
| C09 TranscriptService | ターン保存、バルク保存、セッション終了 → ANALYSIS_JOB作成 |

### 成果物
- `u8/frontend/src/pages/ChatPage.tsx` — 音声チャット画面
- `u8/frontend/src/components/VoiceChat/` — WebRTC接続コンポーネント
- `u8/backend/services/voice_session.py`
- `u8/backend/services/transcript.py`
- API: `/api/voice-session/start`, `/api/voice-session/end`, `/api/transcript/turn`, `/api/transcript/bulk`

### デプロイ確認
- PWAで音声会話開始 → ふれまーるちゃんが応答
- Transcript がDynamoDBに保存されている
- セッション終了 → VOICE_SESSION# completed + ANALYSIS_JOB# queued

---

## U8-C: ライフログ + 日記サマリ

### 目的
会話Transcriptから自動的にライフログを抽出し、日記サマリを生成する。

### スコープ
| コンポーネント | 内容 |
|--------------|------|
| C10 AnalysisWorker（LifeLog/Diary） | ライフログ抽出 + 日記サマリ生成（Claude Sonnet） |
| C11 PushService | Web Push サブスクリプション + 通知送信 |
| C15 BedrockClient | Claude Sonnet 呼び出し基盤 |

### 成果物
- `u8/backend/handlers/analysis_handler.py` — 非同期Lambda
- `u8/backend/services/analysis.py` — extract_life_log(), generate_diary_summary()
- `u8/backend/services/push_service.py` — Web Push送信
- `u8/backend/shared/bedrock_client.py` — Claude Sonnet呼び出し
- SAM: SQS キュー, EventBridge (22:00 日記生成 + 5min reprocess)
- API: `/api/push/subscribe`, `/api/push/unsubscribe`

### デプロイ確認
- 音声会話終了 → SQS → AnalysisService → LIFE_LOG# 作成
- EventBridge 22:00 → DAILY_FUREMARU_SUMMARY# 作成 → Push通知受信
- ANALYSIS_JOB# が completed に更新

---

## U8-D: ストレス判定 + 回復提案

### 目的
ストレス判定ロジックと段階的回復提案を実装する。

### スコープ
| コンポーネント | 内容 |
|--------------|------|
| C10 AnalysisWorker（Stress） | ストレス判定（Claude Sonnet）|
| C12 RecoveryProvider | 0円/有料回復案生成 + ふれまーるちゃん口調変換 |
| C05 RecoveryView | 回復案カードUI、段階的誘導 |

### 成果物
- `u8/backend/services/analysis.py` に `assess_stress()` 追加
- `u8/backend/services/recovery.py` — 回復案生成
- `u8/frontend/src/pages/RecoveryPage.tsx` — 回復案画面
- API: `/api/recovery`, `/api/recovery/permit`, `/api/recovery/skip`

### デプロイ確認
- 会話終了 → STRESS_SUMMARY# 作成（レベル1〜5）
- /api/recovery → 0円回復案 + 有料回復案がふれまーるちゃん口調で返却
- permit/skip → REWARD_PERMIT# / REWARD_SKIP# 作成

---

## U8-E: ダッシュボード統合

### 目的
全機能をダッシュボードUIに統合し、完成形のPWAにする。

### スコープ
| コンポーネント | 内容 |
|--------------|------|
| C03 Dashboard | 余剰金・支出推移・ストレスレベル表示 |
| C04 DiaryView | 日記サマリ表示・履歴・読み上げ演出 |
| ナビゲーション統合 | 5タブナビ完成（チャット/ダッシュボード/日記/ご褒美/設定） |

### 成果物
- `u8/frontend/src/pages/DashboardPage.tsx`
- `u8/frontend/src/pages/DiaryPage.tsx`
- `u8/frontend/src/components/Navigation/`
- API: `/api/dashboard`, `/api/diary`, `/api/diary/{date}`

### デプロイ確認
- 全5タブが機能する
- ダッシュボード: 余剰金・支出推移表示
- 日記: 過去日記一覧 + 読み上げ演出
- E2E: 音声会話 → ライフログ → ストレス判定 → 回復提案 → 日記生成
