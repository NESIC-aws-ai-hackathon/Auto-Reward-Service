# サービス定義 — オートリワードサービス

## サービス一覧

| サービス名 | ポート | Unit | DB |
|----------|--------|------|----|
| nginx（API Gateway） | 80 / 443 | — | — |
| auth-service | 3001 | U1 | PostgreSQL |
| stress-service | 3002 | U2 | TimescaleDB（PostgreSQL 拡張） |
| reward-service | 3003 | U4 | PostgreSQL + Redis |
| finance-service | 3004 | U3 | PostgreSQL |
| notification-service | 3005 | U5 | PostgreSQL + Redis |
| dashboard-service | 3006 | U7 | ClickHouse + （他サービス経由） |
| web（フロントエンド） | 5173 | — | — |

---

## API Gateway（Nginx）

**責務**: 全サービスへのリバースプロキシ。JWT 検証（Auth0/Cognito JWKS）を一元担当。  
検証成功後、以下のヘッダーをバックエンドサービスに転送する：

```
X-User-Id: <sub claim>
X-User-Email: <email claim>
```

**ルーティング:**

| パスプレフィックス | 転送先 |
|-----------------|--------|
| `/api/v1/users/` | auth-service:3001 |
| `/api/v1/stress/` | stress-service:3002 |
| `/api/v1/rewards/` | reward-service:3003 |
| `/api/v1/finance/` | finance-service:3004 |
| `/api/v1/notifications/` | notification-service:3005 |
| `/api/v1/dashboard/` | dashboard-service:3006 |

---

## auth-service（U1）

**フレームワーク**: NestJS + TypeScript  
**DB**: PostgreSQL（`ars_auth` データベース）  
**役割**: ユーザープロフィール・嗜好設定・予算上限・通知設定の永続管理

**モジュール構成:**
```
AppModule
├── UserModule        # /users/me
├── PreferencesModule # /users/me/preferences（嗜好・予算・通知設定）
├── AuthModule        # JwtStrategy（X-User-Id ヘッダー検証）
├── AppConfigModule   # @ars/shared-config
├── LoggerModule      # @ars/shared-config
└── HealthModule      # /health
```

**外部依存**: Auth0 / AWS Cognito（JWKS エンドポイント、Nginx で使用）

---

## stress-service（U2）

**フレームワーク**: NestJS + TypeScript  
**DB**: TimescaleDB（`ars_stress` データベース）  
**役割**: ストレスエントリ収集・スコアリング・閾値判定・リワードフロートリガー

**モジュール構成:**
```
AppModule
├── StressEntryModule    # /stress/entries
├── StressScoringModule  # 内部モジュール（直接エンドポイントなし）
├── StressThresholdModule # /stress/score/current, /stress/settings
├── AiModule             # @ars/shared-ai（TextSentimentAnalyzer）
├── SharedClientsModule  # @ars/shared-clients（RewardClient）
├── AppConfigModule
├── LoggerModule
└── HealthModule
```

**オーケストレーションフロー（閾値超過時）:**
```
StressEntryService.createEntry()
  → StressScoringService.calculateScore()
  → StressThresholdService.checkAndTrigger()
    → RewardClient.triggerProposalGeneration()   ← reward-service を呼び出し
```

---

## reward-service（U4）

**フレームワーク**: NestJS + TypeScript  
**DB**: PostgreSQL（`ars_reward`）+ Redis（提案キャッシュ）  
**役割**: リワード提案生成・カタログ管理・フィードバック収集  
**リワードフローオーケストレーター**: Finance Service から余裕額を取得し、提案を生成、Notification Service に通知を指示

**モジュール構成:**
```
AppModule
├── CatalogModule         # /rewards/catalog
├── ProposalModule        # /rewards/proposals, /rewards/history
├── ProposalEngineModule  # 内部モジュール（RuleBasedEngine, AiPersonalization）
├── FeedbackModule        # /rewards/proposals/:id/feedback
├── AiModule              # @ars/shared-ai（AiPersonalizationService - 将来）
├── SharedClientsModule   # @ars/shared-clients（FinanceClient, NotificationClient）
├── AppConfigModule
├── LoggerModule
└── HealthModule
```

**オーケストレーションフロー（提案生成時）:**
```
ProposalService.generateProposals(userId, stressScore)
  → FinanceClient.getAvailableRewardBudget(userId)
  → RuleBasedEngineService.filterByCriteria(...)
  → ProposalRepository.save(proposals)
  → NotificationClient.sendRewardProposalNotification(userId, proposals)
```

---

## finance-service（U3）

**フレームワーク**: NestJS + TypeScript  
**DB**: PostgreSQL（`ars_finance`）  
**役割**: 収支管理・余裕額算出・CSV インポート・AI カテゴリ分類

**モジュール構成:**
```
AppModule
├── BudgetModule          # /finance/budget
├── AvailableBudgetModule # /finance/available-reward-budget
├── TransactionModule     # /finance/transactions
├── CsvImportModule       # /finance/import/csv
├── AiModule              # @ars/shared-ai（TransactionCategoryClassifier）
├── AppConfigModule
├── LoggerModule
└── HealthModule
```

---

## notification-service（U5）

**フレームワーク**: NestJS + TypeScript  
**DB**: PostgreSQL（`ars_notification`）+ Redis（スロットリングカウンター）  
**役割**: プッシュ通知生成・送信・スロットリング・デバイストークン管理

**モジュール構成:**
```
AppModule
├── DeviceTokenModule  # /notifications/device-tokens
├── NotificationModule # /notifications/history
├── ThrottleModule     # 内部モジュール（Redis）
├── AiModule           # @ars/shared-ai（NotificationCopyGenerator）
├── AppConfigModule
├── LoggerModule
└── HealthModule
```

**通知フロー:**
```
NotificationService.sendRewardProposalNotification(params)
  → ThrottleService.canSend(userId)            ← 送信可否チェック
  → NotificationCopyGenerator.generate(...)    ← LLM でコピー生成
  → DeviceTokenService.getTokens(userId)       ← デバイストークン取得
  → Web Push API / FCM 送信
  → NotificationRepository.save(log)           ← 送信ログ保存
  → ThrottleService.recordSent(userId)         ← カウンター更新
```

---

## dashboard-service（U7）

**フレームワーク**: NestJS + TypeScript  
**DB**: ClickHouse（集計データ）+ 他サービスへの HTTP 呼び出し  
**役割**: ストレス・リワード・財務データの集計・可視化・AI インサイト

**モジュール構成:**
```
AppModule
├── StressTrendModule     # /dashboard/stress-trends
├── RewardHistoryModule   # /dashboard/reward-history
├── FinanceSummaryModule  # /dashboard/finance-summary
├── InsightModule         # /dashboard/insights
├── AiModule              # @ars/shared-ai（InsightReportGenerator）
├── SharedClientsModule   # @ars/shared-clients（StressClient, RewardClient, FinanceClient）
├── AppConfigModule
├── LoggerModule
└── HealthModule
```

---

## フロントエンド（apps/web）

**フレームワーク**: React 18 + TypeScript + Vite  
**状態管理**: Zustand（グローバル UI/認証状態）+ TanStack Query v5（サーバーステート）  
**ルーティング**: React Router v6  
**HTTP クライアント**: axios（`/api/v1` へのリクエスト、API Gateway 経由）

**主要プロバイダー構成:**
```tsx
<QueryClientProvider>        // TanStack Query
  <BrowserRouter>            // React Router
    <AuthProvider>           // Zustand authStore
      <App />
    </AuthProvider>
  </BrowserRouter>
</QueryClientProvider>
```
