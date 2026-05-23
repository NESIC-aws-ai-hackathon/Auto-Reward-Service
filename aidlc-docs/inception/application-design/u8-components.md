# Unit 8: コンポーネント定義

## コンポーネント一覧

| ID | コンポーネント名 | レイヤー | 責務 |
|----|----------------|---------|------|
| C01 | PWA Shell | Frontend | Vite+React SPA。ルーティング・レイアウト・Service Worker登録 |
| C02 | VoiceChat | Frontend | OpenAI Realtime WebRTC接続・音声UI・Transcript収集 |
| C03 | Dashboard | Frontend | 余剰金・支出推移・ストレスレベル表示 |
| C04 | DiaryView | Frontend | 日記サマリ表示・履歴一覧・読み上げ演出 |
| C05 | RecoveryView | Frontend | 回復案表示（0円回復 + 有料）・段階的誘導UI |
| C06 | AuthModule | Frontend | Cognito認証フロー・デモログイン・JWT管理 |
| C07 | ApiGateway | Backend | 同期API Lambda。認証・ルーティング・リクエスト処理 |
| C08 | VoiceSessionService | Backend | ephemeral key発行・セッション管理 |
| C09 | TranscriptService | Backend | Transcript保存・セッション終了検知 |
| C10 | AnalysisWorker | Backend | 非同期分析Lambda。ライフログ抽出・ストレス判定・日記生成 |
| C11 | PushService | Backend | Web Push通知送信・サブスクリプション管理 |
| C12 | RecoveryProvider | Backend | 回復案生成（0円回復+商品+サービス）|
| C13 | CognitoAuth | Infra | Cognito User Pool・JWT検証・デモユーザー |
| C14 | DataAccess | Layer | DynamoDB CRUD・エンティティマッピング |
| C15 | BedrockClient | Layer | Claude Sonnet呼び出し・プロンプト管理 |

---

## コンポーネント詳細

### C01: PWA Shell
- **技術**: Vite + React + React Router
- **責務**:
  - SPA ルーティング（/chat, /dashboard, /diary, /recovery, /settings）
  - ナビゲーションバー管理
  - Service Worker 登録（静的キャッシュ + Push受信）
  - グローバル状態管理（認証状態、ユーザー情報）
- **ホスティング**: S3 + CloudFront

### C02: VoiceChat
- **技術**: OpenAI Realtime API (WebRTC)
- **責務**:
  - ephemeral key取得（バックエンドAPI経由）
  - WebRTC セッション確立・維持・切断処理
  - VAD インジケーター表示
  - 音声波形アニメーション
  - Transcript 収集・ターンごとのバックエンド送信
  - ローカルキャッシュ（IndexedDB）による切断時バッファリング
  - テキストチャットモード切り替え
- **アバター**: 静止画表示 + 音声時軽微アニメ

### C03: Dashboard
- **責務**:
  - 余剰金残高・甘やかし枠残額表示
  - 支出推移グラフ（直近7日/30日）
  - カテゴリ別支出内訳
  - ストレスレベルインジケーター

### C04: DiaryView
- **責務**:
  - 今日の日記サマリ表示
  - 過去の日記一覧（カレンダー形式）
  - ふれまーるちゃん読み上げ演出（Web Speech API or TTS）
  - Push通知からのディープリンク受信

### C05: RecoveryView
- **責務**:
  - 「今日の甘やかし枠の使い道」画面
  - 回復案カード表示（0円回復・有料回復を並列）
  - 段階的誘導UI（共感→示唆→提案→外部確認）
  - 外部サイトリンク（将来拡張）

### C06: AuthModule
- **技術**: AWS Amplify Auth (Cognito)
- **責務**:
  - サインアップ/サインイン（メール）
  - デモログイン（ワンクリック体験）
  - JWT トークン管理（自動リフレッシュ）
  - 認証状態のReact Context提供

### C07: ApiGateway (同期API Lambda)
- **技術**: Python Lambda + API Gateway HTTP API
- **責務**:
  - Cognito JWT 検証
  - ルーティング（/api/voice-session, /api/transcript, /api/dashboard, /api/recovery, /api/push, /api/settings）
  - レスポンス整形・エラーハンドリング
- **エンドポイント一覧**: services.md参照

### C08: VoiceSessionService
- **責務**:
  - OpenAI API を使って ephemeral client secret 発行
  - セッション開始/終了の記録
  - セッションタイムアウト管理
  - ふれまーるちゃんのシステムプロンプト設定

### C09: TranscriptService
- **責務**:
  - Transcript ターン保存（`CONVERSATION_TURN#{timestamp}`）
  - セッション終了検知 → 分析ジョブ作成
  - 未送信Transcript の再送受付（切断復旧）

### C10: AnalysisWorker (非同期分析Lambda)
- **技術**: Python Lambda（EventBridge / SQS トリガー）
- **責務**:
  - ライフログ抽出（Claude Sonnet）
  - ストレス判定（Claude Sonnet）
  - 日記サマリ生成（Claude Sonnet）
  - 結果のDynamoDB保存
  - Push通知トリガー（日記完成時）
- **トリガー**:
  - セッション終了イベント → ライフログ抽出 + ストレス判定
  - EventBridge 日次（22:00）→ 日記サマリ生成
  - EventBridge 補助（5分ごと）→ 未処理Transcript再処理

### C11: PushService
- **責務**:
  - Web Push サブスクリプション登録/削除
  - VAPID鍵管理
  - 通知送信（日記サマリ完成、回復提案タイミング）

### C12: RecoveryProvider
- **責務**:
  - ストレスレベルに基づく回復案生成
  - 0円回復案（休息、散歩、深呼吸、入浴、動画、記事）
  - 有料回復案（既存Provider chain活用: 楽天、ホットペッパー等）
  - BedrockClientでふれまーるちゃん口調の提案文へ変換
  - 提案カードのフォーマット統一
- **処理フロー**:
  1. ルール/Provider chainで0円回復案・予算内回復案を生成
  2. BedrockClientでふれまーるちゃん口調の提案文に変換
  3. RecoveryViewにカード形式で返却

### C13: CognitoAuth (Infra)
- **技術**: Amazon Cognito User Pool
- **責務**:
  - User Pool 設定（メール認証、パスワードポリシー）
  - デモユーザー事前作成
  - JWT発行・検証
  - 内部ID連携（`IDENTITY#COGNITO#{sub}` → `USER#{id}`）

### C14: DataAccess (Layer)
- **技術**: boto3 DynamoDB
- **責務**:
  - エンティティ CRUD（統一命名 SK パターン）
  - クエリヘルパー（GSI, begins_with等）
  - バッチ書き込み

### C15: BedrockClient (Layer)
- **技術**: boto3 Bedrock Runtime
- **責務**:
  - Claude Sonnet 呼び出し（ライフログ/ストレス/日記）
  - プロンプトテンプレート管理
  - レスポンスパース
  - リトライ・タイムアウト制御
