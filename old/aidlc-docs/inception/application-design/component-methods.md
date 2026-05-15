# 繧ｳ繝ｳ繝昴・繝阪Φ繝医Γ繧ｽ繝・ラ螳夂ｾｩ 窶・繧ｪ繝ｼ繝医Μ繝ｯ繝ｼ繝峨し繝ｼ繝薙せ

> **豕ｨ**: 隧ｳ邏ｰ縺ｪ繝薙ず繝阪せ繝ｭ繧ｸ繝・け繝ｻ繝舌Μ繝・・繧ｷ繝ｧ繝ｳ繝ｫ繝ｼ繝ｫ縺ｯ Construction 繝輔ぉ繝ｼ繧ｺ縺ｮ Functional Design 縺ｧ螳夂ｾｩ縺励∪縺吶・
> 譛ｬ繝輔ぃ繧､繝ｫ縺ｯ繝｡繧ｽ繝・ラ繧ｷ繧ｰ繝阪メ繝｣繝ｻ蜈･蜃ｺ蜉帛梛繝ｻ鬮倥Ξ繝吶Ν縺ｮ逶ｮ逧・ｒ險倩ｼ峨＠縺ｾ縺吶・

---

## @ars/shared-clients

### StressClient

```typescript
// Stress Service 縺ｸ縺ｮHTTP蜻ｼ縺ｳ蜃ｺ縺励Λ繝・ヱ繝ｼ
triggerRewardFlow(userId: string, stressScore: number): Promise<void>
getCurrentScore(userId: string): Promise<StressScoreDto>
```

### FinanceClient

```typescript
// Finance Service 縺ｸ縺ｮHTTP蜻ｼ縺ｳ蜃ｺ縺励Λ繝・ヱ繝ｼ
getAvailableRewardBudget(userId: string): Promise<{ availableBudget: number }>
recordRewardSpending(userId: string, amount: number, category: RewardCategory): Promise<void>
```

### RewardClient

```typescript
// Reward Service 縺ｸ縺ｮHTTP蜻ｼ縺ｳ蜃ｺ縺励Λ繝・ヱ繝ｼ
triggerProposalGeneration(userId: string, stressScore: number): Promise<void>
getProposals(userId: string): Promise<RewardProposalDto[]>
```

### NotificationClient

```typescript
// Notification Service 縺ｸ縺ｮHTTP蜻ｼ縺ｳ蜃ｺ縺励Λ繝・ヱ繝ｼ
sendRewardProposalNotification(userId: string, proposals: RewardProposalDto[]): Promise<void>
```

---

## @ars/shared-ai

### TextSentimentAnalyzer

```typescript
// 繝・く繧ｹ繝医°繧画─諠・せ繧ｳ繧｢繧堤ｮ怜・・・縲・: 0=繝阪ぎ繝・ぅ繝・ 1=繝昴ず繝・ぅ繝厄ｼ・
analyze(text: string): Promise<{ sentimentScore: number; reasoning: string }>
```

### NotificationCopyGenerator

```typescript
// 蜈ｱ諢溽噪繝ｻ繝昴ず繝・ぅ繝悶↑騾夂衍繧ｳ繝斐・繧堤函謌・
generate(params: {
  userName: string
  stressScore: number
  proposals: RewardProposalDto[]
  availableBudget: number
}): Promise<{ title: string; body: string }>
```

### InsightReportGenerator

```typescript
// 譛域ｬ｡繧､繝ｳ繧ｵ繧､繝医Ξ繝昴・繝医ｒ閾ｪ辟ｶ險隱槭〒逕滓・
generate(params: {
  userId: string
  stressTrend: StressScoreDto[]
  rewardHistory: RewardProposalDto[]
  month: string // YYYY-MM
}): Promise<{ report: string }>
```

### TransactionCategoryClassifier

```typescript
// 驫陦梧・邏ｰ縺ｮ繧ｫ繝・ざ繝ｪ閾ｪ蜍募・鬘・
classify(description: string): Promise<{
  category: TransactionCategory
  confidence: number
}>
```

---

## Auth Service

### UserService

```typescript
// 繝ｦ繝ｼ繧ｶ繝ｼ諠・ｱ縺ｮ蜿門ｾ・
findById(userId: string): Promise<UserDto>

// 繝励Ο繝輔ぅ繝ｼ繝ｫ縺ｮ譖ｴ譁ｰ・亥錐蜑阪・蟷ｴ鮨｢繝ｻ閨ｷ遞ｮ繝ｻ繝ｩ繧､繝輔せ繧ｿ繧､繝ｫ・・
updateProfile(userId: string, data: UpdateProfileDto): Promise<UserDto>
```

### PreferencesService

```typescript
// 蝸懷･ｽ險ｭ螳壹・莠育ｮ嶺ｸ企剞繝ｻ騾夂衍險ｭ螳壹・蜿門ｾ・
getPreferences(userId: string): Promise<UserPreferencesDto>

// 蝸懷･ｽ險ｭ螳壹・譖ｴ譁ｰ・医＃隍堤ｾ弱き繝・ざ繝ｪ繝ｻ莠育ｮ嶺ｸ企剞繝ｻ騾夂衍譎る俣蟶ｯ・・
updatePreferences(userId: string, data: UpdatePreferencesDto): Promise<UserPreferencesDto>
```

---

## Stress Service

### StressEntryService

```typescript
// 繧ｹ繝医Ξ繧ｹ繧ｨ繝ｳ繝医Μ縺ｮ菴懈・・域焔蜍募・蜉・or 閾ｪ蜍包ｼ・
createEntry(userId: string, data: CreateStressEntryDto): Promise<StressEntryDto>

// 繧ｹ繝医Ξ繧ｹ螻･豁ｴ縺ｮ蜿門ｾ暦ｼ医・繝ｼ繧ｸ繝阪・繧ｷ繝ｧ繝ｳ莉倥″・・
getHistory(userId: string, query: PaginationQuery): Promise<PaginatedResult<StressEntryDto>>
```

### StressScoringService・育ｴ皮ｲ矩未謨ｰ 窶・PBT 蟇ｾ雎｡・・

```typescript
// 驥阪∩莉倥″蜷域・繧ｹ繧ｳ繧｢繧堤ｮ怜・・・縲・00・・
// 蜈･蜉・ 蜷・す繧ｰ繝翫Ν縺ｮ繧ｹ繧ｳ繧｢・・縲・・峨→驥阪∩
// 蜃ｺ蜉・ 蜷域・繧ｹ繝医Ξ繧ｹ繧ｹ繧ｳ繧｢・・縲・00・・
calculateScore(inputs: {
  manualInput: number        // 0縲・・域焔蜍募・蜉・縲・繧呈ｭ｣隕丞喧・・
  calendarDensity?: number   // 0縲・
  textSentiment?: number     // 0縲・・井ｽ弱＞縺ｻ縺ｩ繧ｹ繝医Ξ繧ｹ鬮假ｼ・
  sleepQuality?: number      // 0縲・
  weights: ScoringWeights    // 繝・ヵ繧ｩ繝ｫ繝・ { manual: 0.4, calendar: 0.2, text: 0.3, sleep: 0.1 }
}): number
```

### StressThresholdService

```typescript
// 髢ｾ蛟､雜・℃縺ｮ蛻､螳壹→繝ｪ繝ｯ繝ｼ繝峨ヵ繝ｭ繝ｼ縺ｮ繝医Μ繧ｬ繝ｼ
checkAndTrigger(userId: string, score: number, threshold: number): Promise<void>

// 繧ｹ繝医Ξ繧ｹ險ｭ螳壹・蜿門ｾ暦ｼ磯明蛟､繝ｻ繧ｫ繝ｬ繝ｳ繝繝ｼ騾｣謳ｺ繝輔Λ繧ｰ・・
getSettings(userId: string): Promise<StressSettingsDto>

// 繧ｹ繝医Ξ繧ｹ險ｭ螳壹・譖ｴ譁ｰ
updateSettings(userId: string, data: UpdateStressSettingsDto): Promise<StressSettingsDto>
```

---

## Reward Service

### ProposalService

```typescript
// 繝ｪ繝ｯ繝ｼ繝画署譯医ヵ繝ｭ繝ｼ縺ｮ繧ｪ繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｷ繝ｧ繝ｳ
// FinanceClient 竊・RuleBasedEngineService 竊・(AiPersonalizationService) 竊・NotificationClient
generateProposals(userId: string, stressScore: number): Promise<RewardProposalDto[]>

// 繝ｦ繝ｼ繧ｶ繝ｼ縺ｮ迴ｾ蝨ｨ縺ｮ謠先｡井ｸ隕ｧ蜿門ｾ・
getActiveProposals(userId: string): Promise<RewardProposalDto[]>

// 謗｡逕ｨ貂医∩繝ｪ繝ｯ繝ｼ繝牙ｱ･豁ｴ縺ｮ蜿門ｾ・
getHistory(userId: string, query: PaginationQuery): Promise<PaginatedResult<RewardProposalDto>>
```

### RuleBasedEngineService・育ｴ皮ｲ矩未謨ｰ 窶・PBT 蟇ｾ雎｡・・

```typescript
// 繧ｹ繝医Ξ繧ｹ繝ｬ繝吶Ν ﾃ・菴呵｣暮｡・竊・謠先｡亥呵｣懊ヵ繧｣繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ
// 隕∽ｻｶ螳夂ｾｩ譖ｸ ﾂｧ10 縺ｮ謠先｡医・繝医Μ繧ｯ繧ｹ繧貞ｮ溯｣・
filterByCriteria(params: {
  stressScore: number
  availableBudget: number
  preferredCategories: RewardCategory[]
  catalog: RewardCatalogItem[]
}): RewardCatalogItem[]
```

### FeedbackService

```typescript
// 繝輔ぅ繝ｼ繝峨ヰ繝・け・域治逕ｨ/蜊ｴ荳・蠕後〒・峨・菫晏ｭ・
// 謗｡逕ｨ譎ゅ・ FinanceClient.recordRewardSpending() 繧貞他縺ｳ蜃ｺ縺・
recordFeedback(userId: string, proposalId: string, data: FeedbackDto): Promise<void>
```

---

## Finance Service

### AvailableBudgetService・育ｴ皮ｲ矩未謨ｰ 窶・PBT 蟇ｾ雎｡・・

```typescript
// 菴呵｣暮｡咲ｮ怜・
// available = min(limit, (income - fixedExpenses) * 0.15) - currentMonthSpent
calculateAvailableBudget(params: {
  monthlyRewardLimit: number
  monthlyIncome: number
  monthlyFixedExpenses: number
  currentMonthRewardSpent: number
  safetyFactor?: number  // 繝・ヵ繧ｩ繝ｫ繝・ 0.15
}): number
```

### BudgetService

```typescript
// 譛域ｬ｡莠育ｮ励・菴呵｣暮｡阪・蜿門ｾ暦ｼ・B 縺九ｉ譛域ｬ｡髮・ｨ・+ AvailableBudgetService 蜻ｼ縺ｳ蜃ｺ縺暦ｼ・
getMonthlyBudget(userId: string, month: string): Promise<BudgetSummaryDto>

// 莠育ｮ苓ｨｭ螳壹・譖ｴ譁ｰ・域怦蜿弱・蝗ｺ螳夊ｲｻ繝ｻ譛域ｬ｡荳企剞・・
updateBudgetSettings(userId: string, data: UpdateBudgetDto): Promise<BudgetSettingsDto>
```

### TransactionService

```typescript
// 蜿門ｼ輔・蜿門ｾ暦ｼ医・繝ｼ繧ｸ繝阪・繧ｷ繝ｧ繝ｳ莉倥″・・
getTransactions(userId: string, query: TransactionQuery): Promise<PaginatedResult<TransactionDto>>

// 謇句虚蜿門ｼ戊ｿｽ蜉
addTransaction(userId: string, data: CreateTransactionDto): Promise<TransactionDto>

// 蜿門ｼ輔き繝・ざ繝ｪ縺ｮ謇句虚菫ｮ豁｣
updateCategory(userId: string, transactionId: string, category: TransactionCategory): Promise<TransactionDto>
```

### CsvImportService

```typescript
// 驫陦・CSV 繝輔ぃ繧､繝ｫ縺ｮ繝代・繧ｹ繝ｻ蜿悶ｊ霎ｼ縺ｿ
// 蟇ｾ蠢懊ヵ繧ｩ繝ｼ繝槭ャ繝・ 荳芽廠UFJ / 荳我ｺ穂ｽ丞暑 / 繧・≧縺｡繧・
importFromCsv(userId: string, file: Buffer, bankFormat: BankFormat): Promise<CsvImportResultDto>
```

---

## Notification Service

### NotificationService

```typescript
// 繝ｪ繝ｯ繝ｼ繝画署譯磯夂衍縺ｮ騾∽ｿ｡・医さ繝斐・逕滓・ 竊・繧ｹ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ遒ｺ隱・竊・Web Push / FCM・・
sendRewardProposalNotification(params: {
  userId: string
  proposals: RewardProposalDto[]
  availableBudget: number
}): Promise<void>

// 騾夂衍螻･豁ｴ縺ｮ蜿門ｾ・
getHistory(userId: string, query: PaginationQuery): Promise<PaginatedResult<NotificationLogDto>>
```

### ThrottleService

```typescript
// 騾∽ｿ｡蜿ｯ蜷ｦ繧貞愛螳夲ｼ・譌･荳企剞繝ｻ髱吝ｯよ凾髢灘ｸｯ繝√ぉ繝・け・・
canSend(userId: string): Promise<{ allowed: boolean; reason?: string }>

// 騾∽ｿ｡險倬鹸・・edis 繧ｫ繧ｦ繝ｳ繧ｿ繝ｼ繧偵う繝ｳ繧ｯ繝ｪ繝｡繝ｳ繝茨ｼ・
recordSent(userId: string): Promise<void>
```

### DeviceTokenService

```typescript
// 繝・ヰ繧､繧ｹ繝医・繧ｯ繝ｳ縺ｮ逋ｻ骭ｲ
registerToken(userId: string, token: string, platform: 'web' | 'fcm'): Promise<void>

// 繝・ヰ繧､繧ｹ繝医・繧ｯ繝ｳ縺ｮ蜑企勁
removeToken(userId: string, token: string): Promise<void>

// 繝ｦ繝ｼ繧ｶ繝ｼ縺ｮ蜈ｨ繝・ヰ繧､繧ｹ繝医・繧ｯ繝ｳ蜿門ｾ・
getTokens(userId: string): Promise<DeviceTokenDto[]>
```

---

## Dashboard Service

### StressTrendService

```typescript
// 繧ｹ繝医Ξ繧ｹ謗ｨ遘ｻ繝・・繧ｿ縺ｮ蜿門ｾ暦ｼ域律谺｡/騾ｱ谺｡/譛域ｬ｡・・
getTrend(userId: string, params: TrendQuery): Promise<StressTrendDto[]>
```

### RewardHistoryService

```typescript
// 繝ｪ繝ｯ繝ｼ繝牙ｱ･豁ｴ繧ｿ繧､繝繝ｩ繧､繝ｳ縺ｮ蜿門ｾ・
getTimeline(userId: string, params: TimelineQuery): Promise<RewardTimelineDto[]>
```

### FinanceSummaryService

```typescript
// 縺碑､堤ｾ取髪蜃ｺ縺ｮ譛域ｬ｡繝ｻ蟷ｴ谺｡髮・ｨ・
getSummary(userId: string, params: SummaryQuery): Promise<FinanceSummaryDto>
```

### InsightService

```typescript
// AI 繧､繝ｳ繧ｵ繧､繝医Ξ繝昴・繝医・蜿門ｾ暦ｼ域怦谺｡繧ｭ繝｣繝・す繝･縺ゅｊ・・
getMonthlyInsight(userId: string, month: string): Promise<InsightReportDto>
```
