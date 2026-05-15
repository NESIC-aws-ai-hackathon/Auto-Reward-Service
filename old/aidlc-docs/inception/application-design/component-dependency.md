# 繧ｳ繝ｳ繝昴・繝阪Φ繝井ｾ晏ｭ倬未菫・窶・繧ｪ繝ｼ繝医Μ繝ｯ繝ｼ繝峨し繝ｼ繝薙せ

## 萓晏ｭ倥・繝医Μ繧ｯ繧ｹ

蜃｡萓・ **蜻ｼ縺ｳ蜃ｺ縺呻ｼ遺・・・* / **萓晏ｭ倥↑縺暦ｼ遺費ｼ・*

| 蜻ｼ縺ｳ蜃ｺ縺怜・ 竊・/ 蜻ｼ縺ｳ蜃ｺ縺怜・ 竊・| auth | stress | reward | finance | notification | dashboard | shared-clients | shared-ai | shared-types | shared-config |
|---|---|---|---|---|---|---|---|---|---|---|
| **auth-service** | 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 笨・| 笨・|
| **stress-service** | 窶・| 窶・| 笨・RewardClient | 窶・| 窶・| 窶・| 笨・| 笨・TextSentiment | 笨・| 笨・|
| **reward-service** | 窶・| 窶・| 窶・| 笨・FinanceClient | 笨・NotificationClient | 窶・| 笨・| 笨・AiPersonalize・亥ｰ・擂・・| 笨・| 笨・|
| **finance-service** | 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 笨・CategoryClassifier | 笨・| 笨・|
| **notification-service** | 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 笨・CopyGenerator | 笨・| 笨・|
| **dashboard-service** | 窶・| 笨・StressClient | 笨・RewardClient | 笨・FinanceClient | 窶・| 窶・| 笨・| 笨・InsightReport | 笨・| 笨・|
| **web・・rontend・・* | 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 笨・| 窶・|
| **nginx・・PI GW・・* | 笨・| 笨・| 笨・| 笨・| 笨・| 笨・| 窶・| 窶・| 窶・| 窶・|

---

## 繧ｵ繝ｼ繝薙せ髢馴壻ｿ｡繝輔Ο繝ｼ

### 繝輔Ο繝ｼ 1・壹せ繝医Ξ繧ｹ逋ｻ骭ｲ 竊・繝ｪ繝ｯ繝ｼ繝画署譯・竊・騾夂衍・医Γ繧､繝ｳ繝輔Ο繝ｼ・・

```
[Web 繝輔Ο繝ｳ繝医お繝ｳ繝云
    |
    | POST /api/v1/stress/entries
    v
[Nginx API Gateway]  竊・JWT 讀懆ｨｼ・・uth0/Cognito JWKS・・
    |
    | X-User-Id 繝倥ャ繝繝ｼ莉倥″縺ｧ繝ｫ繝ｼ繝・ぅ繝ｳ繧ｰ
    v
[stress-service]
    | StressEntryService.createEntry()
    | 竊・StressScoringService.calculateScore()
    | 竊・StressThresholdService.checkAndTrigger()
    |       竊・髢ｾ蛟､雜・℃譎ゅ・縺ｿ
    |   RewardClient.triggerProposalGeneration()
    |       |
    v       v
[reward-service]
    | ProposalService.generateProposals()
    | 竊・FinanceClient.getAvailableRewardBudget()
    |       |
    |       v
    |   [finance-service]
    |   AvailableBudgetService.calculateAvailableBudget()
    |       |
    |   (菴呵｣暮｡阪ｒ霑斐☆)
    |       |
    | 竊・菴呵｣暮｡榊女菫｡
    | 竊・RuleBasedEngineService.filterByCriteria()
    | 竊・ProposalRepository.save(proposals)
    | 竊・NotificationClient.sendRewardProposalNotification()
    |       |
    v       v
[notification-service]
    | NotificationService.sendRewardProposalNotification()
    | 竊・ThrottleService.canSend()          竊・Redis
    | 竊・NotificationCopyGenerator.generate() 竊・OpenAI API
    | 竊・DeviceTokenService.getTokens()
    | 竊・Web Push API / FCM
    | 竊・NotificationRepository.save(log)
    | 竊・ThrottleService.recordSent()       竊・Redis
```

### 繝輔Ο繝ｼ 2・壹Μ繝ｯ繝ｼ繝画治逕ｨ 竊・謾ｯ蜃ｺ閾ｪ蜍戊ｨ倬鹸

```
[Web 繝輔Ο繝ｳ繝医お繝ｳ繝云
    |
    | POST /api/v1/rewards/proposals/:id/feedback  { action: "ACCEPT" }
    v
[Nginx API Gateway]
    |
    v
[reward-service]
    | FeedbackService.recordFeedback()
    | 竊・FeedbackRepository.save()
    | 竊・FinanceClient.recordRewardSpending()  竊・謗｡逕ｨ譎ゅ・縺ｿ
    |       |
    v       v
[finance-service]
    | TransactionService.addTransaction()
    | 竊・TransactionRepository.save()
```

### 繝輔Ο繝ｼ 3・壹ム繝・す繝･繝懊・繝芽｡ｨ遉ｺ

```
[Web 繝輔Ο繝ｳ繝医お繝ｳ繝云
    |
    | GET /api/v1/dashboard/stress-trends
    | GET /api/v1/dashboard/reward-history
    | GET /api/v1/dashboard/finance-summary
    | GET /api/v1/dashboard/insights
    v
[Nginx API Gateway]
    |
    v
[dashboard-service]
    | StressTrendService    竊・StressClient  竊・[stress-service]
    | RewardHistoryService  竊・RewardClient  竊・[reward-service]
    | FinanceSummaryService 竊・FinanceClient 竊・[finance-service]
    | InsightService        竊・InsightReportGenerator 竊・OpenAI API
```

---

## 螟夜Κ萓晏ｭ倬未菫・

| 螟夜Κ繧ｵ繝ｼ繝薙せ | 蛻ｩ逕ｨ繧ｵ繝ｼ繝薙せ | 逕ｨ騾・|
|------------|------------|------|
| Auth0 / AWS Cognito | Nginx・・PI Gateway・・| JWT 逋ｺ陦後・JWKS 謠蝉ｾ・|
| OpenAI API・・PT-4o・・| shared-ai | 繝・く繧ｹ繝域─諠・・譫舌・騾夂衍繧ｳ繝斐・繝ｻ繧､繝ｳ繧ｵ繧､繝医・繧ｫ繝・ざ繝ｪ蛻・｡・|
| Web Push API | notification-service | Web 繝悶Λ繧ｦ繧ｶ縺ｸ縺ｮ繝励ャ繧ｷ繝･騾夂衍 |
| FCM・・irebase Cloud Messaging・・| notification-service | Android / PWA 縺ｸ縺ｮ繝励ャ繧ｷ繝･騾夂衍・亥ｰ・擂・・|

---

## 繧､繝ｳ繝輔Λ萓晏ｭ倬未菫ゑｼ・ocker Compose・・

```
postgres-auth      竊・auth-service
timescaledb        竊・stress-service
postgres-reward    竊・reward-service
redis              竊・reward-service・医く繝｣繝・す繝･・峨］otification-service・医せ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ・・
postgres-finance   竊・finance-service
postgres-notif     竊・notification-service
clickhouse         竊・dashboard-service
```

---

## 萓晏ｭ倬未菫ゅΝ繝ｼ繝ｫ

1. **繝輔Ο繝ｳ繝医お繝ｳ繝・竊・Nginx 縺ｮ縺ｿ**: Web 繝輔Ο繝ｳ繝医お繝ｳ繝峨・繝舌ャ繧ｯ繧ｨ繝ｳ繝峨し繝ｼ繝薙せ繧堤峩謗･蜻ｼ縺ｳ蜃ｺ縺輔↑縺・
2. **繧ｵ繝ｼ繝薙せ髢薙・ shared-clients 邨檎罰**: 繧ｵ繝ｼ繝薙せ髢薙・ HTTP 蜻ｼ縺ｳ蜃ｺ縺励・蠢・★ @ars/shared-clients 縺ｮ繧ｯ繝ｩ繧､繧｢繝ｳ繝医け繝ｩ繧ｹ繧剃ｽｿ逕ｨ縺吶ｋ
3. **OpenAI 縺ｯ shared-ai 邨檎罰縺ｮ縺ｿ**: 蜷・し繝ｼ繝薙せ縺・OpenAI SDK 繧堤峩謗･ import 縺励↑縺・
4. **auth-service 縺ｯ莉悶し繝ｼ繝薙せ繧貞他縺ｳ蜃ｺ縺輔↑縺・*: 繝ｦ繝ｼ繧ｶ繝ｼ邂｡逅・し繝ｼ繝薙せ縺ｯ萓晏ｭ倥・譛ｫ遶ｯ
5. **蠕ｪ迺ｰ萓晏ｭ倡ｦ∵ｭ｢**: 繧ｵ繝ｼ繝薙せ髢薙・蠕ｪ迺ｰ蜿ら・・・竊達竊但・峨・險ｭ險井ｸ願ｵｷ縺薙＆縺ｪ縺・
