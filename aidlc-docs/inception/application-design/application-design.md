# Application Design（統合版） — オートリワードサービス

**作成日**: 2026-05-08  
**ステータス**: レビュー待ち

---

## 1. アーキテクチャ概要

### 設計方針まとめ

| 項目 | 決定内容 |
|------|---------|
| モノレポ管理 | **Turborepo**（npm workspaces + ビルドキャッシュ） |
| バックエンドフレームワーク | **NestJS（TypeScript）** 全サービス統一 |
| モジュール境界 | **ハイブリッド**（コアドメインはドメイン分割、共通機能はレイヤー分割） |
| サービス間通信 | **共有クライアントパッケージ**（@ars/shared-clients、HTTP 同期） |
| API Gateway | **Nginx**（JWT 検証一元化、X-User-Id ヘッダー転送） |
| OpenAI 統合 | **共有 AI クライアント**（@ars/shared-ai） |
| フロントエンド状態管理 | **Zustand**（グローバル）+ **TanStack Query**（サーバーステート） |
| フロントエンドコンポーネント | **Feature-based**（features/ 配下に機能単位） |

---

## 2. システム構成図

```
[ブラウザ: React App（Vite）]
        |
        | HTTPS
        v
[Nginx API Gateway]
  JWT 検証（Auth0/Cognito JWKS）
  ルーティング
        |
        +─── /api/v1/users/        → auth-service:3001
        +─── /api/v1/stress/       → stress-service:3002
        +─── /api/v1/rewards/      → reward-service:3003
        +─── /api/v1/finance/      → finance-service:3004
        +─── /api/v1/notifications/→ notification-service:3005
        +─── /api/v1/dashboard/    → dashboard-service:3006


サービス間通信（@ars/shared-clients 経由、HTTP 同期）:

stress-service ─────────────────────→ reward-service
                                              │
                             ┌────────────────┤
                             │                │
                             v                v
                      finance-service  notification-service
                             
reward-service ──────────────────────→ finance-service
reward-service ──────────────────────→ notification-service
dashboard-service ───────────────────→ stress-service
dashboard-service ───────────────────→ reward-service
dashboard-service ───────────────────→ finance-service


共有パッケージ（@ars/*）:

@ars/shared-types   ← 全サービス・フロントエンド
@ars/shared-clients ← stress / reward / finance / notification / dashboard service
@ars/shared-ai      ← stress / reward / finance / notification / dashboard service
@ars/shared-config  ← 全バックエンドサービス


外部サービス:

Auth0/Cognito ← Nginx（JWT JWKS 検証）
OpenAI API    ← @ars/shared-ai 経由
Web Push/FCM  ← notification-service
```

---

## 3. リポジトリ構成

```
auto-reward-service/
├── apps/
│   ├── auth-service/          # NestJS（PostgreSQL）
│   ├── stress-service/        # NestJS（TimescaleDB）
│   ├── reward-service/        # NestJS（PostgreSQL + Redis）
│   ├── finance-service/       # NestJS（PostgreSQL）
│   ├── notification-service/  # NestJS（PostgreSQL + Redis）
│   ├── dashboard-service/     # NestJS（ClickHouse）
│   └── web/                   # React + Vite（TypeScript）
├── packages/
│   ├── shared-types/          # @ars/shared-types
│   ├── shared-clients/        # @ars/shared-clients
│   ├── shared-ai/             # @ars/shared-ai
│   └── shared-config/         # @ars/shared-config
├── infrastructure/
│   ├── docker-compose.yml
│   └── nginx/
│       └── nginx.conf
├── turbo.json
└── package.json
```

---

## 4. サービスサマリー

| サービス | Unit | ポート | DB | 主な責務 |
|---------|------|--------|----|---------| 
| auth-service | U1 | 3001 | PostgreSQL | ユーザー・嗜好・予算・通知設定管理 |
| stress-service | U2 | 3002 | TimescaleDB | ストレス収集・スコアリング・閾値判定・リワードフロートリガー |
| reward-service | U4 | 3003 | PostgreSQL + Redis | 提案生成・カタログ・フィードバック・リワードフローオーケストレーター |
| finance-service | U3 | 3004 | PostgreSQL | 収支管理・余裕額算出・CSV インポート |
| notification-service | U5 | 3005 | PostgreSQL + Redis | プッシュ通知生成・送信・スロットリング |
| dashboard-service | U7 | 3006 | ClickHouse | データ集計・グラフ・AI インサイト |

---

## 5. 主要オーケストレーションフロー

### ストレス閾値超過 → リワード通知

```
1. ユーザーがストレスを入力
2. stress-service: スコア算出 → 閾値チェック
3. [閾値超過] → reward-service: generateProposals()
4. reward-service → finance-service: getAvailableRewardBudget()
5. reward-service: RuleBasedEngine で提案生成
6. reward-service → notification-service: sendRewardProposalNotification()
7. notification-service: LLM でコピー生成 → スロットリングチェック → Push 送信
```

---

## 6. PBT（プロパティベーステスト）対象コンポーネント

| コンポーネント | サービス | 対象プロパティ |
|-------------|---------|--------------|
| `StressScoringService.calculateScore()` | stress-service | スコアが常に 0〜100 の範囲内、重みの合計が 1.0 のとき入力変化に単調応答 |
| `RuleBasedEngineService.filterByCriteria()` | reward-service | フィルタ結果が余裕額・ストレスレベルの条件を必ず満たす、空でない入力に対し提案が返る |
| `AvailableBudgetService.calculateAvailableBudget()` | finance-service | 結果が常に 0 以上、limit の上限を超えない |

---

## 7. セキュリティ設計ポイント（Security Baseline）

| ルール | 実装方針 |
|--------|---------|
| SECURITY-01（暗号化） | DB 接続に TLS 必須、PostgreSQL / Redis / ClickHouse 暗号化設定 |
| SECURITY-02（アクセスログ） | Nginx アクセスログを JSON 形式で出力、ログ集約 |
| SECURITY-03（アプリログ） | 構造化ログ（@ars/shared-config/LoggerModule）、PII・トークンはログ出力禁止 |

---

## 8. 詳細ドキュメントへの参照

| ドキュメント | パス |
|------------|------|
| コンポーネント定義 | [components.md](./components.md) |
| メソッドシグネチャ | [component-methods.md](./component-methods.md) |
| サービス詳細 | [services.md](./services.md) |
| 依存関係マトリクス | [component-dependency.md](./component-dependency.md) |
