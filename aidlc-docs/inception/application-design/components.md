# コンポーネント定義 — オートリワードサービス

**アーキテクチャ方針（回答まとめ）:**
- モノレポ: **Turborepo**（npm workspaces + ビルドキャッシュ）
- モジュール境界: **ハイブリッド**（コアドメインはドメイン分割、共通機能はレイヤー分割）
- サービス間通信: **共有クライアントパッケージ**（@ars/shared-clients）
- JWT 検証: **API Gateway（Nginx）で一元検証**（X-User-Id ヘッダー渡し）
- OpenAI 呼び出し: **共有 AI クライアントモジュール**（@ars/shared-ai）

---

## リポジトリ構成

```
auto-reward-service/           # Turborepo ルート
├── apps/
│   ├── auth-service/          # U1: NestJS
│   ├── stress-service/        # U2: NestJS
│   ├── reward-service/        # U4: NestJS
│   ├── finance-service/       # U3: NestJS
│   ├── notification-service/  # U5: NestJS
│   ├── dashboard-service/     # U7: NestJS
│   └── web/                   # React (Vite + TypeScript)
├── packages/
│   ├── shared-types/          # @ars/shared-types
│   ├── shared-clients/        # @ars/shared-clients
│   ├── shared-ai/             # @ars/shared-ai
│   └── shared-config/         # @ars/shared-config
├── infrastructure/
│   ├── docker-compose.yml
│   └── nginx/
│       └── nginx.conf         # API Gateway + JWT 検証
├── turbo.json
└── package.json
```

---

## 共有パッケージ（packages/）

### @ars/shared-types

**責務**: 全サービス共通の TypeScript 型定義・DTO・列挙型

| コンポーネント | 責務 |
|--------------|------|
| `UserDto` | ユーザー情報 DTO |
| `StressEntryDto` | ストレスエントリ DTO |
| `StressScoreDto` | ストレススコア DTO |
| `RewardProposalDto` | リワード提案 DTO |
| `FinanceBudgetDto` | 財務予算 DTO |
| `NotificationDto` | 通知 DTO |
| `RewardCategory` | リワードカテゴリ列挙型（FOOD / EXPERIENCE / ITEM / SERVICE） |
| `StressLevel` | ストレスレベル列挙型（LOW / MEDIUM / HIGH） |

---

### @ars/shared-clients

**責務**: サービス間 HTTP 通信のクライアントラッパー（NestJS HttpModule ベース）

| コンポーネント | 責務 |
|--------------|------|
| `StressClient` | Stress Service への HTTP 呼び出しラッパー |
| `FinanceClient` | Finance Service への HTTP 呼び出しラッパー |
| `RewardClient` | Reward Service への HTTP 呼び出しラッパー |
| `NotificationClient` | Notification Service への HTTP 呼び出しラッパー |
| `DashboardClient` | Dashboard Service への HTTP 呼び出しラッパー |

---

### @ars/shared-ai

**責務**: OpenAI API 呼び出しの共有クライアントモジュール

| コンポーネント | 責務 |
|--------------|------|
| `AiModule` | NestJS モジュール（OpenAI SDK 初期化・DI） |
| `TextSentimentAnalyzer` | テキストから感情スコアを算出（Stress Service 用） |
| `NotificationCopyGenerator` | 共感的通知コピーを生成（Notification Service 用） |
| `InsightReportGenerator` | 月次インサイトレポートを生成（Dashboard Service 用） |
| `TransactionCategoryClassifier` | 明細を自動カテゴリ分類（Finance Service 用） |

---

### @ars/shared-config

**責務**: NestJS 設定モジュールの共通実装

| コンポーネント | 責務 |
|--------------|------|
| `AppConfigModule` | 環境変数読み込み（NestJS ConfigModule ラッパー） |
| `LoggerModule` | 構造化ログ（JSON 形式、correlation ID 付き）|
| `HealthModule` | `/health` エンドポイント共通実装 |

---

## バックエンドサービス（apps/）

### Auth Service（U1）

**責務**: ユーザーアカウント・プロフィール・設定管理。Auth0/Cognito との統合。

| モジュール | コンポーネント | 責務 |
|----------|--------------|------|
| `UserModule` | `UserController` | プロフィール CRUD エンドポイント（GET/PATCH /users/me） |
| | `UserService` | ユーザー情報の取得・更新ビジネスロジック |
| | `UserRepository` | users テーブルの CRUD（PostgreSQL） |
| `PreferencesModule` | `PreferencesController` | 嗜好設定・予算上限・通知設定エンドポイント |
| | `PreferencesService` | 設定値の検証・保存ロジック |
| | `PreferencesRepository` | user_preferences テーブルの CRUD |
| `AuthModule`（共通） | `JwtStrategy` | API Gateway から渡された X-User-Id ヘッダーを検証・リクエストコンテキストに注入 |
| | `CurrentUserDecorator` | コントローラーでログインユーザーを取り出すデコレータ |

---

### Stress Service（U2）

**責務**: ストレス度の収集・スコアリング・閾値判定。ストレス閾値超過時にリワードフローをトリガー。

| モジュール | コンポーネント | 責務 |
|----------|--------------|------|
| `StressEntryModule` | `StressEntryController` | ストレスエントリ作成・履歴取得エンドポイント |
| | `StressEntryService` | エントリ保存・スコア再計算のオーケストレーション |
| | `StressEntryRepository` | stress_entries テーブルの CRUD（TimescaleDB） |
| `StressScoringModule` | `StressScoringService` | 重み付き合成スコア算出（純粋関数 — **PBT 対象**） |
| | `TextSentimentAdapter` | @ars/shared-ai の TextSentimentAnalyzer ラッパー |
| `StressThresholdModule` | `StressThresholdService` | 閾値判定・リワードフロートリガー（RewardClient 呼び出し） |
| | `StressSettingsController` | 閾値・カレンダー連携設定エンドポイント |
| | `StressSettingsRepository` | stress_settings テーブルの CRUD |

---

### Reward Service（U4）

**責務**: ストレススコアと財務余裕額からパーソナライズされたリワード提案を生成。通知トリガーまで担当（リワードフローオーケストレーター）。

| モジュール | コンポーネント | 責務 |
|----------|--------------|------|
| `CatalogModule` | `CatalogController` | リワードカタログ検索エンドポイント |
| | `CatalogService` | カタログ検索・フィルタリング |
| | `CatalogRepository` | reward_catalog テーブルの CRUD（PostgreSQL） |
| `ProposalModule` | `ProposalController` | 提案一覧取得・採用履歴エンドポイント |
| | `ProposalService` | 提案生成フローのオーケストレーション（FinanceClient → ProposalEngineService → NotificationClient） |
| | `ProposalRepository` | reward_proposals テーブルの CRUD |
| `ProposalEngineModule` | `RuleBasedEngineService` | ストレスレベル × 余裕額 → 提案リスト生成（純粋関数 — **PBT 対象**） |
| | `AiPersonalizationService` | 過去フィードバックを基に提案スコアリング（将来フェーズ） |
| `FeedbackModule` | `FeedbackController` | 採用/却下/後でフィードバックエンドポイント |
| | `FeedbackService` | フィードバック保存・支出自動記録（FinanceClient 呼び出し） |
| | `FeedbackRepository` | reward_feedbacks テーブルの CRUD |

---

### Finance Service（U3）

**責務**: 収支管理・余裕額算出・CSV インポート・AI カテゴリ分類。

| モジュール | コンポーネント | 責務 |
|----------|--------------|------|
| `BudgetModule` | `BudgetController` | 月次予算・余裕額エンドポイント |
| | `BudgetService` | 予算設定管理 |
| | `BudgetRepository` | budgets テーブルの CRUD |
| `AvailableBudgetModule` | `AvailableBudgetController` | GET /finance/available-reward-budget |
| | `AvailableBudgetService` | 余裕額算出ロジック（純粋関数 — **PBT 対象**） |
| `TransactionModule` | `TransactionController` | 取引履歴取得・手動追加エンドポイント |
| | `TransactionService` | 取引の保存・カテゴリ分類オーケストレーション |
| | `TransactionRepository` | transactions テーブルの CRUD |
| `CsvImportModule` | `CsvImportController` | POST /finance/import/csv |
| | `CsvImportService` | CSV パース・フォーマット変換（三菱UFJ / 三井住友 / ゆうちょ） |
| | `CategoryClassifierAdapter` | @ars/shared-ai の TransactionCategoryClassifier ラッパー |

---

### Notification Service（U5）

**責務**: リワード提案通知の生成・送信・スロットリング管理。

| モジュール | コンポーネント | 責務 |
|----------|--------------|------|
| `DeviceTokenModule` | `DeviceTokenController` | デバイストークン登録・削除エンドポイント |
| | `DeviceTokenService` | トークン管理 |
| | `DeviceTokenRepository` | device_tokens テーブルの CRUD |
| `NotificationModule` | `NotificationController` | 通知送信・履歴取得エンドポイント |
| | `NotificationService` | 通知コピー生成 → スロットリング確認 → Web Push / FCM 送信のオーケストレーション |
| | `NotificationRepository` | notification_logs テーブルの CRUD |
| `ThrottleModule` | `ThrottleService` | 1日最大通知数・静寂時間帯（22:00〜7:00）チェック（Redis） |
| `CopyGeneratorAdapter` | — | @ars/shared-ai の NotificationCopyGenerator ラッパー |

---

### Dashboard Service（U7）

**責務**: ストレス・リワード・財務データの集計・可視化・AI インサイト生成。

| モジュール | コンポーネント | 責務 |
|----------|--------------|------|
| `StressTrendModule` | `StressTrendController` | ストレス推移データエンドポイント |
| | `StressTrendService` | TimescaleDB / ClickHouse から集計（StressClient 経由） |
| `RewardHistoryModule` | `RewardHistoryController` | リワード履歴タイムラインエンドポイント |
| | `RewardHistoryService` | RewardClient 経由でデータ取得・集計 |
| `FinanceSummaryModule` | `FinanceSummaryController` | 財務影響サマリーエンドポイント |
| | `FinanceSummaryService` | FinanceClient 経由でデータ取得・集計 |
| `InsightModule` | `InsightController` | AI インサイトレポートエンドポイント |
| | `InsightService` | 月次インサイトレポート生成（InsightReportGeneratorAdapter 経由） |
| | `InsightReportGeneratorAdapter` | @ars/shared-ai の InsightReportGenerator ラッパー |

---

## フロントエンド（apps/web）

**技術**: React + TypeScript + Vite  
**状態管理**: Zustand（グローバル）+ TanStack Query（サーバーステート）  
**コンポーネント設計**: Feature-based

```
apps/web/src/
├── features/
│   ├── auth/              # ログイン・登録・初期設定ウィザード
│   ├── stress/            # ストレス入力・ダッシュボード
│   ├── rewards/           # リワード提案一覧・フィードバック
│   ├── finance/           # 収支設定・CSV インポート
│   ├── dashboard/         # 振り返りグラフ・インサイト
│   └── notifications/     # 通知設定・履歴
├── shared/
│   ├── components/        # 共通 UI コンポーネント（Button, Modal 等）
│   ├── hooks/             # 共通カスタムフック
│   ├── stores/            # Zustand ストア（auth, ui）
│   └── api/               # API クライアント（axios インスタンス）
└── app/
    ├── App.tsx
    ├── router.tsx          # React Router v6
    └── providers.tsx       # QueryClient, Zustand, AuthProvider
```

| コンポーネント群 | 責務 |
|----------------|------|
| `features/auth/` | ログインフォーム・Google OAuth ボタン・初期設定ウィザード（カテゴリ選択・予算設定） |
| `features/stress/` | ストレス入力ウィジェット（2タップ入力）・ストレス履歴カード |
| `features/rewards/` | リワード提案カード一覧・採用/却下/後でボタン・採用済み履歴 |
| `features/finance/` | 収支入力フォーム・余裕額ウィジェット・CSV アップロード・取引カテゴリ修正 |
| `features/dashboard/` | ストレス推移グラフ・ご褒美支出棒グラフ・AI インサイトカード |
| `features/notifications/` | 通知設定フォーム・通知履歴リスト |
| `shared/stores/authStore` | Zustand: 認証状態（user, token, isAuthenticated） |
| `shared/stores/uiStore` | Zustand: グローバル UI 状態（モーダル表示、ローディング） |
