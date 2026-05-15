# 繧ｵ繝ｼ繝薙せ螳夂ｾｩ 窶・繧ｪ繝ｼ繝医Μ繝ｯ繝ｼ繝峨し繝ｼ繝薙せ

## 繧ｵ繝ｼ繝薙せ荳隕ｧ

| 繧ｵ繝ｼ繝薙せ蜷・| 繝昴・繝・| Unit | DB |
|----------|--------|------|----|
| nginx・・PI Gateway・・| 80 / 443 | 窶・| 窶・|
| auth-service | 3001 | U1 | PostgreSQL |
| stress-service | 3002 | U2 | TimescaleDB・・ostgreSQL 諡｡蠑ｵ・・|
| reward-service | 3003 | U4 | PostgreSQL + Redis |
| finance-service | 3004 | U3 | PostgreSQL |
| notification-service | 3005 | U5 | PostgreSQL + Redis |
| dashboard-service | 3006 | U7 | ClickHouse + ・井ｻ悶し繝ｼ繝薙せ邨檎罰・・|
| web・医ヵ繝ｭ繝ｳ繝医お繝ｳ繝会ｼ・| 5173 | 窶・| 窶・|

---

## API Gateway・・ginx・・

**雋ｬ蜍・*: 蜈ｨ繧ｵ繝ｼ繝薙せ縺ｸ縺ｮ繝ｪ繝舌・繧ｹ繝励Ο繧ｭ繧ｷ縲・WT 讀懆ｨｼ・・uth0/Cognito JWKS・峨ｒ荳蜈・球蠖薙・ 
讀懆ｨｼ謌仙粥蠕後∽ｻ･荳九・繝倥ャ繝繝ｼ繧偵ヰ繝・け繧ｨ繝ｳ繝峨し繝ｼ繝薙せ縺ｫ霆｢騾√☆繧具ｼ・

```
X-User-Id: <sub claim>
X-User-Email: <email claim>
```

**繝ｫ繝ｼ繝・ぅ繝ｳ繧ｰ:**

| 繝代せ繝励Ξ繝輔ぅ繝・け繧ｹ | 霆｢騾∝・ |
|-----------------|--------|
| `/api/v1/users/` | auth-service:3001 |
| `/api/v1/stress/` | stress-service:3002 |
| `/api/v1/rewards/` | reward-service:3003 |
| `/api/v1/finance/` | finance-service:3004 |
| `/api/v1/notifications/` | notification-service:3005 |
| `/api/v1/dashboard/` | dashboard-service:3006 |

---

## auth-service・・1・・

**繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ**: NestJS + TypeScript  
**DB**: PostgreSQL・・ars_auth` 繝・・繧ｿ繝吶・繧ｹ・・ 
**蠖ｹ蜑ｲ**: 繝ｦ繝ｼ繧ｶ繝ｼ繝励Ο繝輔ぅ繝ｼ繝ｫ繝ｻ蝸懷･ｽ險ｭ螳壹・莠育ｮ嶺ｸ企剞繝ｻ騾夂衍險ｭ螳壹・豌ｸ邯夂ｮ｡逅・

**繝｢繧ｸ繝･繝ｼ繝ｫ讒区・:**
```
AppModule
笏懌楳笏 UserModule        # /users/me
笏懌楳笏 PreferencesModule # /users/me/preferences・亥梨螂ｽ繝ｻ莠育ｮ励・騾夂衍險ｭ螳夲ｼ・
笏懌楳笏 AuthModule        # JwtStrategy・・-User-Id 繝倥ャ繝繝ｼ讀懆ｨｼ・・
笏懌楳笏 AppConfigModule   # @ars/shared-config
笏懌楳笏 LoggerModule      # @ars/shared-config
笏披楳笏 HealthModule      # /health
```

**螟夜Κ萓晏ｭ・*: Auth0 / AWS Cognito・・WKS 繧ｨ繝ｳ繝峨・繧､繝ｳ繝医¨ginx 縺ｧ菴ｿ逕ｨ・・

---

## stress-service・・2・・

**繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ**: NestJS + TypeScript  
**DB**: TimescaleDB・・ars_stress` 繝・・繧ｿ繝吶・繧ｹ・・ 
**蠖ｹ蜑ｲ**: 繧ｹ繝医Ξ繧ｹ繧ｨ繝ｳ繝医Μ蜿朱寔繝ｻ繧ｹ繧ｳ繧｢繝ｪ繝ｳ繧ｰ繝ｻ髢ｾ蛟､蛻､螳壹・繝ｪ繝ｯ繝ｼ繝峨ヵ繝ｭ繝ｼ繝医Μ繧ｬ繝ｼ

**繝｢繧ｸ繝･繝ｼ繝ｫ讒区・:**
```
AppModule
笏懌楳笏 StressEntryModule    # /stress/entries
笏懌楳笏 StressScoringModule  # 蜀・Κ繝｢繧ｸ繝･繝ｼ繝ｫ・育峩謗･繧ｨ繝ｳ繝峨・繧､繝ｳ繝医↑縺暦ｼ・
笏懌楳笏 StressThresholdModule # /stress/score/current, /stress/settings
笏懌楳笏 AiModule             # @ars/shared-ai・・extSentimentAnalyzer・・
笏懌楳笏 SharedClientsModule  # @ars/shared-clients・・ewardClient・・
笏懌楳笏 AppConfigModule
笏懌楳笏 LoggerModule
笏披楳笏 HealthModule
```

**繧ｪ繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｷ繝ｧ繝ｳ繝輔Ο繝ｼ・磯明蛟､雜・℃譎ゑｼ・**
```
StressEntryService.createEntry()
  竊・StressScoringService.calculateScore()
  竊・StressThresholdService.checkAndTrigger()
    竊・RewardClient.triggerProposalGeneration()   竊・reward-service 繧貞他縺ｳ蜃ｺ縺・
```

---

## reward-service・・4・・

**繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ**: NestJS + TypeScript  
**DB**: PostgreSQL・・ars_reward`・・ Redis・域署譯医く繝｣繝・す繝･・・ 
**蠖ｹ蜑ｲ**: 繝ｪ繝ｯ繝ｼ繝画署譯育函謌舌・繧ｫ繧ｿ繝ｭ繧ｰ邂｡逅・・繝輔ぅ繝ｼ繝峨ヰ繝・け蜿朱寔  
**繝ｪ繝ｯ繝ｼ繝峨ヵ繝ｭ繝ｼ繧ｪ繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｿ繝ｼ**: Finance Service 縺九ｉ菴呵｣暮｡阪ｒ蜿門ｾ励＠縲∵署譯医ｒ逕滓・縲¨otification Service 縺ｫ騾夂衍繧呈欠遉ｺ

**繝｢繧ｸ繝･繝ｼ繝ｫ讒区・:**
```
AppModule
笏懌楳笏 CatalogModule         # /rewards/catalog
笏懌楳笏 ProposalModule        # /rewards/proposals, /rewards/history
笏懌楳笏 ProposalEngineModule  # 蜀・Κ繝｢繧ｸ繝･繝ｼ繝ｫ・・uleBasedEngine, AiPersonalization・・
笏懌楳笏 FeedbackModule        # /rewards/proposals/:id/feedback
笏懌楳笏 AiModule              # @ars/shared-ai・・iPersonalizationService - 蟆・擂・・
笏懌楳笏 SharedClientsModule   # @ars/shared-clients・・inanceClient, NotificationClient・・
笏懌楳笏 AppConfigModule
笏懌楳笏 LoggerModule
笏披楳笏 HealthModule
```

**繧ｪ繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｷ繝ｧ繝ｳ繝輔Ο繝ｼ・域署譯育函謌先凾・・**
```
ProposalService.generateProposals(userId, stressScore)
  竊・FinanceClient.getAvailableRewardBudget(userId)
  竊・RuleBasedEngineService.filterByCriteria(...)
  竊・ProposalRepository.save(proposals)
  竊・NotificationClient.sendRewardProposalNotification(userId, proposals)
```

---

## finance-service・・3・・

**繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ**: NestJS + TypeScript  
**DB**: PostgreSQL・・ars_finance`・・ 
**蠖ｹ蜑ｲ**: 蜿取髪邂｡逅・・菴呵｣暮｡咲ｮ怜・繝ｻCSV 繧､繝ｳ繝昴・繝医・AI 繧ｫ繝・ざ繝ｪ蛻・｡・

**繝｢繧ｸ繝･繝ｼ繝ｫ讒区・:**
```
AppModule
笏懌楳笏 BudgetModule          # /finance/budget
笏懌楳笏 AvailableBudgetModule # /finance/available-reward-budget
笏懌楳笏 TransactionModule     # /finance/transactions
笏懌楳笏 CsvImportModule       # /finance/import/csv
笏懌楳笏 AiModule              # @ars/shared-ai・・ransactionCategoryClassifier・・
笏懌楳笏 AppConfigModule
笏懌楳笏 LoggerModule
笏披楳笏 HealthModule
```

---

## notification-service・・5・・

**繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ**: NestJS + TypeScript  
**DB**: PostgreSQL・・ars_notification`・・ Redis・医せ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ繧ｫ繧ｦ繝ｳ繧ｿ繝ｼ・・ 
**蠖ｹ蜑ｲ**: 繝励ャ繧ｷ繝･騾夂衍逕滓・繝ｻ騾∽ｿ｡繝ｻ繧ｹ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ繝ｻ繝・ヰ繧､繧ｹ繝医・繧ｯ繝ｳ邂｡逅・

**繝｢繧ｸ繝･繝ｼ繝ｫ讒区・:**
```
AppModule
笏懌楳笏 DeviceTokenModule  # /notifications/device-tokens
笏懌楳笏 NotificationModule # /notifications/history
笏懌楳笏 ThrottleModule     # 蜀・Κ繝｢繧ｸ繝･繝ｼ繝ｫ・・edis・・
笏懌楳笏 AiModule           # @ars/shared-ai・・otificationCopyGenerator・・
笏懌楳笏 AppConfigModule
笏懌楳笏 LoggerModule
笏披楳笏 HealthModule
```

**騾夂衍繝輔Ο繝ｼ:**
```
NotificationService.sendRewardProposalNotification(params)
  竊・ThrottleService.canSend(userId)            竊・騾∽ｿ｡蜿ｯ蜷ｦ繝√ぉ繝・け
  竊・NotificationCopyGenerator.generate(...)    竊・LLM 縺ｧ繧ｳ繝斐・逕滓・
  竊・DeviceTokenService.getTokens(userId)       竊・繝・ヰ繧､繧ｹ繝医・繧ｯ繝ｳ蜿門ｾ・
  竊・Web Push API / FCM 騾∽ｿ｡
  竊・NotificationRepository.save(log)           竊・騾∽ｿ｡繝ｭ繧ｰ菫晏ｭ・
  竊・ThrottleService.recordSent(userId)         竊・繧ｫ繧ｦ繝ｳ繧ｿ繝ｼ譖ｴ譁ｰ
```

---

## dashboard-service・・7・・

**繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ**: NestJS + TypeScript  
**DB**: ClickHouse・磯寔險医ョ繝ｼ繧ｿ・・ 莉悶し繝ｼ繝薙せ縺ｸ縺ｮ HTTP 蜻ｼ縺ｳ蜃ｺ縺・ 
**蠖ｹ蜑ｲ**: 繧ｹ繝医Ξ繧ｹ繝ｻ繝ｪ繝ｯ繝ｼ繝峨・雋｡蜍吶ョ繝ｼ繧ｿ縺ｮ髮・ｨ医・蜿ｯ隕門喧繝ｻAI 繧､繝ｳ繧ｵ繧､繝・

**繝｢繧ｸ繝･繝ｼ繝ｫ讒区・:**
```
AppModule
笏懌楳笏 StressTrendModule     # /dashboard/stress-trends
笏懌楳笏 RewardHistoryModule   # /dashboard/reward-history
笏懌楳笏 FinanceSummaryModule  # /dashboard/finance-summary
笏懌楳笏 InsightModule         # /dashboard/insights
笏懌楳笏 AiModule              # @ars/shared-ai・・nsightReportGenerator・・
笏懌楳笏 SharedClientsModule   # @ars/shared-clients・・tressClient, RewardClient, FinanceClient・・
笏懌楳笏 AppConfigModule
笏懌楳笏 LoggerModule
笏披楳笏 HealthModule
```

---

## 繝輔Ο繝ｳ繝医お繝ｳ繝会ｼ・pps/web・・

**繝輔Ξ繝ｼ繝繝ｯ繝ｼ繧ｯ**: React 18 + TypeScript + Vite  
**迥ｶ諷狗ｮ｡逅・*: Zustand・医げ繝ｭ繝ｼ繝舌Ν UI/隱崎ｨｼ迥ｶ諷具ｼ・ TanStack Query v5・医し繝ｼ繝舌・繧ｹ繝・・繝茨ｼ・ 
**繝ｫ繝ｼ繝・ぅ繝ｳ繧ｰ**: React Router v6  
**HTTP 繧ｯ繝ｩ繧､繧｢繝ｳ繝・*: axios・・/api/v1` 縺ｸ縺ｮ繝ｪ繧ｯ繧ｨ繧ｹ繝医、PI Gateway 邨檎罰・・

**荳ｻ隕√・繝ｭ繝舌う繝繝ｼ讒区・:**
```tsx
<QueryClientProvider>        // TanStack Query
  <BrowserRouter>            // React Router
    <AuthProvider>           // Zustand authStore
      <App />
    </AuthProvider>
  </BrowserRouter>
</QueryClientProvider>
```
