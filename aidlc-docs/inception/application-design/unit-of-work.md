# Unit of Work 定義 — オートリワードサービス

**作成日**: 2026-05-08

## 実装サイクル方針（確定）

| 項目 | 決定内容 |
|------|---------|
| 実装粒度 | **機能スライス単位**（各 Unit の中の機能を小さく区切って実装） |
| 共有パッケージ | **Unit 0 として最初のサイクルで実装** |
| テスト | **コード生成と同じサイクル**（Unit テスト + 統合テストを含める） |
| Docker Compose | **各 Unit の実装に並行**して、そのサービスのコンテナ定義を追加 |

---

## モノレポ コード構成方針

```
auto-reward-service/                  ← Turborepo ルート
├── apps/
│   ├── auth-service/                 # Unit 1
│   ├── stress-service/               # Unit 2
│   ├── reward-service/               # Unit 3
│   ├── finance-service/              # Unit 4
│   ├── notification-service/         # Unit 5
│   ├── dashboard-service/            # Unit 6
│   └── web/                          # Unit 7
├── packages/
│   ├── shared-types/                 # Unit 0
│   ├── shared-clients/               # Unit 0
│   ├── shared-ai/                    # Unit 0
│   └── shared-config/                # Unit 0
├── infrastructure/
│   ├── docker-compose.yml
│   └── nginx/
├── turbo.json
└── package.json
```

---

## Unit 一覧

### Unit 0: 共有基盤（Shared Infrastructure）

**最初のサイクルで実装（先行必須）**

| 内容 | 詳細 |
|------|------|
| **スコープ** | Turborepo 初期化、共有パッケージ 4 本、Docker Compose 骨格、Nginx 設定骨格 |
| **成果物** | `packages/shared-types/`, `packages/shared-clients/`（スタブ）, `packages/shared-ai/`（スタブ）, `packages/shared-config/`, `infrastructure/docker-compose.yml`（骨格）, `infrastructure/nginx/nginx.conf` |
| **完了条件** | 全サービスが共有パッケージを import できる; Docker Compose でインフラ（DB・Redis）が起動できる |

**機能スライス:**
| スライス | 内容 |
|---------|------|
| 0-1 | Turborepo + npm workspaces セットアップ、`package.json` 設定 |
| 0-2 | `@ars/shared-types`: DTO・列挙型定義 |
| 0-3 | `@ars/shared-config`: AppConfigModule, LoggerModule, HealthModule |
| 0-4 | `@ars/shared-clients`: クライアントスタブ（型のみ、実装は後続 Unit で充実） |
| 0-5 | `@ars/shared-ai`: AiModule スタブ（OpenAI SDK セットアップのみ） |
| 0-6 | `infrastructure/`: Docker Compose 骨格（DB・Redis・ClickHouse コンテナ）、Nginx 骨格 |

---

### Unit 1: Auth Service（U1 対応）

**対応要件**: U1-01〜U1-05 / US-01, US-02

| 内容 | 詳細 |
|------|------|
| **スコープ** | ユーザー管理・プロフィール・嗜好設定・予算上限・通知設定 |
| **DB** | PostgreSQL（`ars_auth`） |
| **依存** | Unit 0（shared-config, shared-types） |
| **完了条件** | `/users/me` GET/PATCH が動作する; Docker Compose で auth-service が起動する |

**機能スライス:**
| スライス | 機能 | 対応 US |
|---------|------|---------|
| 1-1 | NestJS プロジェクト初期化 + PostgreSQL 接続 + HealthModule | — |
| 1-2 | UserModule: プロフィール CRUD（GET/PATCH /users/me） + Unit テスト | US-01 |
| 1-3 | PreferencesModule: 嗜好・予算上限・通知設定 CRUD + Unit テスト | US-02 |
| 1-4 | AuthModule: JwtStrategy（X-User-Id ヘッダー検証）+ CurrentUserDecorator | — |
| 1-5 | 統合テスト（Docker Compose 上での E2E） | — |
| 1-6 | Docker Compose に auth-service + postgres-auth コンテナを追加 | — |

---

### Unit 2: Stress Service（U2 対応）

**対応要件**: U2-01, U2-05, U2-06, U2-07（MVP）/ US-03, US-04（一部）, US-05

| 内容 | 詳細 |
|------|------|
| **スコープ** | 手動ストレス入力・スコア算出・閾値判定・リワードフロートリガー・履歴保存 |
| **DB** | TimescaleDB（`ars_stress`） |
| **依存** | Unit 0（shared-config, shared-types, shared-clients/RewardClient スタブ）, Unit 1（Auth） |
| **完了条件** | ストレス入力→スコア算出→閾値判定→RewardClient 呼び出しが動作する |

**機能スライス:**
| スライス | 機能 | 対応 US |
|---------|------|---------|
| 2-1 | NestJS プロジェクト初期化 + TimescaleDB 接続 + HealthModule | — |
| 2-2 | StressEntryModule: 手動入力エンドポイント + Unit テスト | US-03 |
| 2-3 | StressScoringModule: スコア算出純粋関数 + Unit テスト + **PBT** | — |
| 2-4 | StressThresholdModule: 閾値判定 + RewardClient 呼び出し + Unit テスト | US-05 |
| 2-5 | 統合テスト（Stress 入力→閾値判定フロー） | — |
| 2-6 | Docker Compose に stress-service + timescaledb コンテナを追加 | — |
| 2-7 | （将来）TextSentimentAdapter: shared-ai 連携 | US-04 一部 |

---

### Unit 3: Reward Service（U4 対応）

**対応要件**: U4-01, U4-02, U4-05（MVP）/ US-08, US-10, US-11

| 内容 | 詳細 |
|------|------|
| **スコープ** | リワードカタログ・ルールベース提案・フィードバック収集・通知トリガー |
| **DB** | PostgreSQL（`ars_reward`）+ Redis（提案キャッシュ） |
| **依存** | Unit 0, Unit 1, Unit 2（RewardClient を受け取る側）、Finance Client スタブ、Notification Client スタブ |
| **完了条件** | Stress Service からのトリガーで提案が生成され、Notification Service に転送できる |

**機能スライス:**
| スライス | 機能 | 対応 US |
|---------|------|---------|
| 3-1 | NestJS プロジェクト初期化 + PostgreSQL + Redis 接続 | — |
| 3-2 | CatalogModule: カタログ CRUD + シードデータ + Unit テスト | US-08 前提 |
| 3-3 | RuleBasedEngineModule: 提案マトリクス純粋関数 + Unit テスト + **PBT** | US-08 |
| 3-4 | ProposalModule: 提案生成フロー（FinanceClient → Engine → 保存 → NotifClient） | US-08 |
| 3-5 | FeedbackModule: 採用/却下/後で + 支出記録（FinanceClient） + Unit テスト | US-10, US-11 |
| 3-6 | 統合テスト（提案生成〜フィードバックフロー） | — |
| 3-7 | Docker Compose に reward-service + postgres-reward + redis コンテナを追加 | — |
| 3-8 | @ars/shared-clients の RewardClient を実装（スタブ → 実装） | — |

---

### Unit 4: Finance Service（U3 対応）

**対応要件**: U3-01, U3-04, U3-05（MVP）, U3-02, U3-06（Should）/ US-06, US-07

| 内容 | 詳細 |
|------|------|
| **スコープ** | 収支管理・余裕額算出・CSV インポート・AI カテゴリ分類 |
| **DB** | PostgreSQL（`ars_finance`） |
| **依存** | Unit 0, Unit 1 |
| **完了条件** | 余裕額算出 API が動作する; Reward Service の FinanceClient が実際に呼び出せる |

**機能スライス:**
| スライス | 機能 | 対応 US |
|---------|------|---------|
| 4-1 | NestJS プロジェクト初期化 + PostgreSQL 接続 | — |
| 4-2 | BudgetModule: 月次予算設定 CRUD + Unit テスト | US-06 |
| 4-3 | AvailableBudgetModule: 余裕額算出純粋関数 + Unit テスト + **PBT** | US-06, US-08 前提 |
| 4-4 | TransactionModule: 取引 CRUD + Unit テスト | US-07 |
| 4-5 | CsvImportModule: CSV パース（三菱UFJ / 三井住友 / ゆうちょ）+ Unit テスト | US-07 |
| 4-6 | CategoryClassifierAdapter: shared-ai 連携 + Unit テスト | US-07 |
| 4-7 | 統合テスト | — |
| 4-8 | Docker Compose に finance-service + postgres-finance コンテナを追加 | — |
| 4-9 | @ars/shared-clients の FinanceClient を実装（スタブ → 実装） | — |

---

### Unit 5: Notification Service（U5 対応）

**対応要件**: U5-01, U5-02, U5-03（MVP）/ US-05（通知送信部分）

| 内容 | 詳細 |
|------|------|
| **スコープ** | プッシュ通知生成・送信・スロットリング・デバイストークン管理 |
| **DB** | PostgreSQL（`ars_notification`）+ Redis（スロットリングカウンター） |
| **依存** | Unit 0, Unit 1, Unit 3（NotifClient を受け取る側） |
| **完了条件** | Reward Service からのトリガーで Web Push 通知が送信できる |

**機能スライス:**
| スライス | 機能 | 対応 US |
|---------|------|---------|
| 5-1 | NestJS プロジェクト初期化 + PostgreSQL + Redis 接続 | — |
| 5-2 | DeviceTokenModule: トークン登録・削除 + Unit テスト | — |
| 5-3 | ThrottleModule: 1日上限・静寂時間帯チェック（Redis）+ Unit テスト | US-05 |
| 5-4 | CopyGeneratorAdapter: shared-ai 連携（通知コピー生成）+ Unit テスト | — |
| 5-5 | NotificationModule: 送信フロー統合 + Web Push / FCM 送信 + Unit テスト | US-05 |
| 5-6 | 統合テスト | — |
| 5-7 | Docker Compose に notification-service + postgres-notif コンテナを追加 | — |
| 5-8 | @ars/shared-clients の NotificationClient を実装（スタブ → 実装） | — |

---

### Unit 6: Dashboard Service（U7 対応）

**対応要件**: U7-01, U7-02, U7-03（MVP）, U7-04（Should）/ US-12, US-13

| 内容 | 詳細 |
|------|------|
| **スコープ** | ストレス推移・リワード履歴・財務サマリー・AI インサイト |
| **DB** | ClickHouse |
| **依存** | Unit 0, Unit 1, Unit 2, Unit 3, Unit 4（各 Client 経由） |
| **完了条件** | ダッシュボード全 API が動作する |

**機能スライス:**
| スライス | 機能 | 対応 US |
|---------|------|---------|
| 6-1 | NestJS プロジェクト初期化 + ClickHouse 接続 | — |
| 6-2 | StressTrendModule: ストレス推移データ API + Unit テスト | US-12 |
| 6-3 | RewardHistoryModule: リワード履歴 API + Unit テスト | US-12 |
| 6-4 | FinanceSummaryModule: 財務サマリー API + Unit テスト | US-12 |
| 6-5 | InsightModule: AI インサイトレポート生成 + 月次キャッシュ + Unit テスト | US-13 |
| 6-6 | 統合テスト | — |
| 6-7 | Docker Compose に dashboard-service + clickhouse コンテナを追加 | — |

---

### Unit 7: Web フロントエンド

**対応要件**: 全 US（US-01〜US-13）のフロントエンド実装

| 内容 | 詳細 |
|------|------|
| **スコープ** | React + Vite アプリ、全 Feature |
| **依存** | Unit 0（shared-types）, Unit 1〜6（API 経由） |
| **完了条件** | 全 Feature が動作し、バックエンドと E2E で接続できる |

**機能スライス:**
| スライス | 機能 | 対応 US |
|---------|------|---------|
| 7-1 | Vite + React + TypeScript 初期化、Router、Provider 設定 | — |
| 7-2 | `features/auth/`: ログイン・初期設定ウィザード | US-01, US-02 |
| 7-3 | `features/stress/`: ストレス入力ウィジェット・履歴 | US-03 |
| 7-4 | `features/rewards/`: 提案カード・フィードバックボタン・履歴 | US-08, US-09, US-10, US-11 |
| 7-5 | `features/finance/`: 収支入力・余裕額ウィジェット・CSV アップロード | US-06, US-07 |
| 7-6 | `features/dashboard/`: ストレスグラフ・支出グラフ・AI インサイトカード | US-12, US-13 |
| 7-7 | `features/notifications/`: 通知設定・履歴 | US-05 |
| 7-8 | 統合テスト（MSW モック + Testing Library） | — |
| 7-9 | Docker Compose に web コンテナを追加 | — |
