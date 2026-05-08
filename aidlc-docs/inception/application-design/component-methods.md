# コンポーネントメソッド定義 — オートリワードサービス

> **注**: 詳細なビジネスロジック・バリデーションルールは Construction フェーズの Functional Design で定義します。
> 本ファイルはメソッドシグネチャ・入出力型・高レベルの目的を記載します。

---

## @ars/shared-clients

### StressClient

```typescript
// Stress Service へのHTTP呼び出しラッパー
triggerRewardFlow(userId: string, stressScore: number): Promise<void>
getCurrentScore(userId: string): Promise<StressScoreDto>
```

### FinanceClient

```typescript
// Finance Service へのHTTP呼び出しラッパー
getAvailableRewardBudget(userId: string): Promise<{ availableBudget: number }>
recordRewardSpending(userId: string, amount: number, category: RewardCategory): Promise<void>
```

### RewardClient

```typescript
// Reward Service へのHTTP呼び出しラッパー
triggerProposalGeneration(userId: string, stressScore: number): Promise<void>
getProposals(userId: string): Promise<RewardProposalDto[]>
```

### NotificationClient

```typescript
// Notification Service へのHTTP呼び出しラッパー
sendRewardProposalNotification(userId: string, proposals: RewardProposalDto[]): Promise<void>
```

---

## @ars/shared-ai

### TextSentimentAnalyzer

```typescript
// テキストから感情スコアを算出（0〜1: 0=ネガティブ, 1=ポジティブ）
analyze(text: string): Promise<{ sentimentScore: number; reasoning: string }>
```

### NotificationCopyGenerator

```typescript
// 共感的・ポジティブな通知コピーを生成
generate(params: {
  userName: string
  stressScore: number
  proposals: RewardProposalDto[]
  availableBudget: number
}): Promise<{ title: string; body: string }>
```

### InsightReportGenerator

```typescript
// 月次インサイトレポートを自然言語で生成
generate(params: {
  userId: string
  stressTrend: StressScoreDto[]
  rewardHistory: RewardProposalDto[]
  month: string // YYYY-MM
}): Promise<{ report: string }>
```

### TransactionCategoryClassifier

```typescript
// 銀行明細のカテゴリ自動分類
classify(description: string): Promise<{
  category: TransactionCategory
  confidence: number
}>
```

---

## Auth Service

### UserService

```typescript
// ユーザー情報の取得
findById(userId: string): Promise<UserDto>

// プロフィールの更新（名前・年齢・職種・ライフスタイル）
updateProfile(userId: string, data: UpdateProfileDto): Promise<UserDto>
```

### PreferencesService

```typescript
// 嗜好設定・予算上限・通知設定の取得
getPreferences(userId: string): Promise<UserPreferencesDto>

// 嗜好設定の更新（ご褒美カテゴリ・予算上限・通知時間帯）
updatePreferences(userId: string, data: UpdatePreferencesDto): Promise<UserPreferencesDto>
```

---

## Stress Service

### StressEntryService

```typescript
// ストレスエントリの作成（手動入力 or 自動）
createEntry(userId: string, data: CreateStressEntryDto): Promise<StressEntryDto>

// ストレス履歴の取得（ページネーション付き）
getHistory(userId: string, query: PaginationQuery): Promise<PaginatedResult<StressEntryDto>>
```

### StressScoringService（純粋関数 — PBT 対象）

```typescript
// 重み付き合成スコアを算出（0〜100）
// 入力: 各シグナルのスコア（0〜1）と重み
// 出力: 合成ストレススコア（0〜100）
calculateScore(inputs: {
  manualInput: number        // 0〜1（手動入力1〜5を正規化）
  calendarDensity?: number   // 0〜1
  textSentiment?: number     // 0〜1（低いほどストレス高）
  sleepQuality?: number      // 0〜1
  weights: ScoringWeights    // デフォルト: { manual: 0.4, calendar: 0.2, text: 0.3, sleep: 0.1 }
}): number
```

### StressThresholdService

```typescript
// 閾値超過の判定とリワードフローのトリガー
checkAndTrigger(userId: string, score: number, threshold: number): Promise<void>

// ストレス設定の取得（閾値・カレンダー連携フラグ）
getSettings(userId: string): Promise<StressSettingsDto>

// ストレス設定の更新
updateSettings(userId: string, data: UpdateStressSettingsDto): Promise<StressSettingsDto>
```

---

## Reward Service

### ProposalService

```typescript
// リワード提案フローのオーケストレーション
// FinanceClient → RuleBasedEngineService → (AiPersonalizationService) → NotificationClient
generateProposals(userId: string, stressScore: number): Promise<RewardProposalDto[]>

// ユーザーの現在の提案一覧取得
getActiveProposals(userId: string): Promise<RewardProposalDto[]>

// 採用済みリワード履歴の取得
getHistory(userId: string, query: PaginationQuery): Promise<PaginatedResult<RewardProposalDto>>
```

### RuleBasedEngineService（純粋関数 — PBT 対象）

```typescript
// ストレスレベル × 余裕額 → 提案候補フィルタリング
// 要件定義書 §10 の提案マトリクスを実装
filterByCriteria(params: {
  stressScore: number
  availableBudget: number
  preferredCategories: RewardCategory[]
  catalog: RewardCatalogItem[]
}): RewardCatalogItem[]
```

### FeedbackService

```typescript
// フィードバック（採用/却下/後で）の保存
// 採用時は FinanceClient.recordRewardSpending() を呼び出し
recordFeedback(userId: string, proposalId: string, data: FeedbackDto): Promise<void>
```

---

## Finance Service

### AvailableBudgetService（純粋関数 — PBT 対象）

```typescript
// 余裕額算出
// available = min(limit, (income - fixedExpenses) * 0.15) - currentMonthSpent
calculateAvailableBudget(params: {
  monthlyRewardLimit: number
  monthlyIncome: number
  monthlyFixedExpenses: number
  currentMonthRewardSpent: number
  safetyFactor?: number  // デフォルト: 0.15
}): number
```

### BudgetService

```typescript
// 月次予算・余裕額の取得（DB から月次集計 + AvailableBudgetService 呼び出し）
getMonthlyBudget(userId: string, month: string): Promise<BudgetSummaryDto>

// 予算設定の更新（月収・固定費・月次上限）
updateBudgetSettings(userId: string, data: UpdateBudgetDto): Promise<BudgetSettingsDto>
```

### TransactionService

```typescript
// 取引の取得（ページネーション付き）
getTransactions(userId: string, query: TransactionQuery): Promise<PaginatedResult<TransactionDto>>

// 手動取引追加
addTransaction(userId: string, data: CreateTransactionDto): Promise<TransactionDto>

// 取引カテゴリの手動修正
updateCategory(userId: string, transactionId: string, category: TransactionCategory): Promise<TransactionDto>
```

### CsvImportService

```typescript
// 銀行 CSV ファイルのパース・取り込み
// 対応フォーマット: 三菱UFJ / 三井住友 / ゆうちょ
importFromCsv(userId: string, file: Buffer, bankFormat: BankFormat): Promise<CsvImportResultDto>
```

---

## Notification Service

### NotificationService

```typescript
// リワード提案通知の送信（コピー生成 → スロットリング確認 → Web Push / FCM）
sendRewardProposalNotification(params: {
  userId: string
  proposals: RewardProposalDto[]
  availableBudget: number
}): Promise<void>

// 通知履歴の取得
getHistory(userId: string, query: PaginationQuery): Promise<PaginatedResult<NotificationLogDto>>
```

### ThrottleService

```typescript
// 送信可否を判定（1日上限・静寂時間帯チェック）
canSend(userId: string): Promise<{ allowed: boolean; reason?: string }>

// 送信記録（Redis カウンターをインクリメント）
recordSent(userId: string): Promise<void>
```

### DeviceTokenService

```typescript
// デバイストークンの登録
registerToken(userId: string, token: string, platform: 'web' | 'fcm'): Promise<void>

// デバイストークンの削除
removeToken(userId: string, token: string): Promise<void>

// ユーザーの全デバイストークン取得
getTokens(userId: string): Promise<DeviceTokenDto[]>
```

---

## Dashboard Service

### StressTrendService

```typescript
// ストレス推移データの取得（日次/週次/月次）
getTrend(userId: string, params: TrendQuery): Promise<StressTrendDto[]>
```

### RewardHistoryService

```typescript
// リワード履歴タイムラインの取得
getTimeline(userId: string, params: TimelineQuery): Promise<RewardTimelineDto[]>
```

### FinanceSummaryService

```typescript
// ご褒美支出の月次・年次集計
getSummary(userId: string, params: SummaryQuery): Promise<FinanceSummaryDto>
```

### InsightService

```typescript
// AI インサイトレポートの取得（月次キャッシュあり）
getMonthlyInsight(userId: string, month: string): Promise<InsightReportDto>
```
