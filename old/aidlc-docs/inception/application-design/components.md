# 繧ｳ繝ｳ繝昴・繝阪Φ繝亥ｮ夂ｾｩ 窶・繧ｪ繝ｼ繝医Μ繝ｯ繝ｼ繝峨し繝ｼ繝薙せ

**繧｢繝ｼ繧ｭ繝・け繝√Ε譁ｹ驥晢ｼ亥屓遲斐∪縺ｨ繧・ｼ・**
- 繝｢繝弱Ξ繝・ **Turborepo**・・pm workspaces + 繝薙Ν繝峨く繝｣繝・す繝･・・
- 繝｢繧ｸ繝･繝ｼ繝ｫ蠅・阜: **繝上う繝悶Μ繝・ラ**・医さ繧｢繝峨Γ繧､繝ｳ縺ｯ繝峨Γ繧､繝ｳ蛻・牡縲∝・騾壽ｩ溯・縺ｯ繝ｬ繧､繝､繝ｼ蛻・牡・・
- 繧ｵ繝ｼ繝薙せ髢馴壻ｿ｡: **蜈ｱ譛峨け繝ｩ繧､繧｢繝ｳ繝医ヱ繝・こ繝ｼ繧ｸ**・・ars/shared-clients・・
- JWT 讀懆ｨｼ: **API Gateway・・ginx・峨〒荳蜈・､懆ｨｼ**・・-User-Id 繝倥ャ繝繝ｼ貂｡縺暦ｼ・
- OpenAI 蜻ｼ縺ｳ蜃ｺ縺・ **蜈ｱ譛・AI 繧ｯ繝ｩ繧､繧｢繝ｳ繝医Δ繧ｸ繝･繝ｼ繝ｫ**・・ars/shared-ai・・

---

## 繝ｪ繝昴ず繝医Μ讒区・

```
auto-reward-service/           # Turborepo 繝ｫ繝ｼ繝・
笏懌楳笏 apps/
笏・  笏懌楳笏 auth-service/          # U1: NestJS
笏・  笏懌楳笏 stress-service/        # U2: NestJS
笏・  笏懌楳笏 reward-service/        # U4: NestJS
笏・  笏懌楳笏 finance-service/       # U3: NestJS
笏・  笏懌楳笏 notification-service/  # U5: NestJS
笏・  笏懌楳笏 dashboard-service/     # U7: NestJS
笏・  笏披楳笏 web/                   # React (Vite + TypeScript)
笏懌楳笏 packages/
笏・  笏懌楳笏 shared-types/          # @ars/shared-types
笏・  笏懌楳笏 shared-clients/        # @ars/shared-clients
笏・  笏懌楳笏 shared-ai/             # @ars/shared-ai
笏・  笏披楳笏 shared-config/         # @ars/shared-config
笏懌楳笏 infrastructure/
笏・  笏懌楳笏 docker-compose.yml
笏・  笏披楳笏 nginx/
笏・      笏披楳笏 nginx.conf         # API Gateway + JWT 讀懆ｨｼ
笏懌楳笏 turbo.json
笏披楳笏 package.json
```

---

## 蜈ｱ譛峨ヱ繝・こ繝ｼ繧ｸ・・ackages/・・

### @ars/shared-types

**雋ｬ蜍・*: 蜈ｨ繧ｵ繝ｼ繝薙せ蜈ｱ騾壹・ TypeScript 蝙句ｮ夂ｾｩ繝ｻDTO繝ｻ蛻玲嫌蝙・

| 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|--------------|------|
| `UserDto` | 繝ｦ繝ｼ繧ｶ繝ｼ諠・ｱ DTO |
| `StressEntryDto` | 繧ｹ繝医Ξ繧ｹ繧ｨ繝ｳ繝医Μ DTO |
| `StressScoreDto` | 繧ｹ繝医Ξ繧ｹ繧ｹ繧ｳ繧｢ DTO |
| `RewardProposalDto` | 繝ｪ繝ｯ繝ｼ繝画署譯・DTO |
| `FinanceBudgetDto` | 雋｡蜍吩ｺ育ｮ・DTO |
| `NotificationDto` | 騾夂衍 DTO |
| `RewardCategory` | 繝ｪ繝ｯ繝ｼ繝峨き繝・ざ繝ｪ蛻玲嫌蝙具ｼ・OOD / EXPERIENCE / ITEM / SERVICE・・|
| `StressLevel` | 繧ｹ繝医Ξ繧ｹ繝ｬ繝吶Ν蛻玲嫌蝙具ｼ・OW / MEDIUM / HIGH・・|

---

### @ars/shared-clients

**雋ｬ蜍・*: 繧ｵ繝ｼ繝薙せ髢・HTTP 騾壻ｿ｡縺ｮ繧ｯ繝ｩ繧､繧｢繝ｳ繝医Λ繝・ヱ繝ｼ・・estJS HttpModule 繝吶・繧ｹ・・

| 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|--------------|------|
| `StressClient` | Stress Service 縺ｸ縺ｮ HTTP 蜻ｼ縺ｳ蜃ｺ縺励Λ繝・ヱ繝ｼ |
| `FinanceClient` | Finance Service 縺ｸ縺ｮ HTTP 蜻ｼ縺ｳ蜃ｺ縺励Λ繝・ヱ繝ｼ |
| `RewardClient` | Reward Service 縺ｸ縺ｮ HTTP 蜻ｼ縺ｳ蜃ｺ縺励Λ繝・ヱ繝ｼ |
| `NotificationClient` | Notification Service 縺ｸ縺ｮ HTTP 蜻ｼ縺ｳ蜃ｺ縺励Λ繝・ヱ繝ｼ |
| `DashboardClient` | Dashboard Service 縺ｸ縺ｮ HTTP 蜻ｼ縺ｳ蜃ｺ縺励Λ繝・ヱ繝ｼ |

---

### @ars/shared-ai

**雋ｬ蜍・*: OpenAI API 蜻ｼ縺ｳ蜃ｺ縺励・蜈ｱ譛峨け繝ｩ繧､繧｢繝ｳ繝医Δ繧ｸ繝･繝ｼ繝ｫ

| 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|--------------|------|
| `AiModule` | NestJS 繝｢繧ｸ繝･繝ｼ繝ｫ・・penAI SDK 蛻晄悄蛹悶・DI・・|
| `TextSentimentAnalyzer` | 繝・く繧ｹ繝医°繧画─諠・せ繧ｳ繧｢繧堤ｮ怜・・・tress Service 逕ｨ・・|
| `NotificationCopyGenerator` | 蜈ｱ諢溽噪騾夂衍繧ｳ繝斐・繧堤函謌撰ｼ・otification Service 逕ｨ・・|
| `InsightReportGenerator` | 譛域ｬ｡繧､繝ｳ繧ｵ繧､繝医Ξ繝昴・繝医ｒ逕滓・・・ashboard Service 逕ｨ・・|
| `TransactionCategoryClassifier` | 譏守ｴｰ繧定・蜍輔き繝・ざ繝ｪ蛻・｡橸ｼ・inance Service 逕ｨ・・|

---

### @ars/shared-config

**雋ｬ蜍・*: NestJS 險ｭ螳壹Δ繧ｸ繝･繝ｼ繝ｫ縺ｮ蜈ｱ騾壼ｮ溯｣・

| 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|--------------|------|
| `AppConfigModule` | 迺ｰ蠅・､画焚隱ｭ縺ｿ霎ｼ縺ｿ・・estJS ConfigModule 繝ｩ繝・ヱ繝ｼ・・|
| `LoggerModule` | 讒矩蛹悶Ο繧ｰ・・SON 蠖｢蠑上…orrelation ID 莉倥″・榎
| `HealthModule` | `/health` 繧ｨ繝ｳ繝峨・繧､繝ｳ繝亥・騾壼ｮ溯｣・|

---

## 繝舌ャ繧ｯ繧ｨ繝ｳ繝峨し繝ｼ繝薙せ・・pps/・・

### Auth Service・・1・・

**雋ｬ蜍・*: 繝ｦ繝ｼ繧ｶ繝ｼ繧｢繧ｫ繧ｦ繝ｳ繝医・繝励Ο繝輔ぅ繝ｼ繝ｫ繝ｻ險ｭ螳夂ｮ｡逅・・uth0/Cognito 縺ｨ縺ｮ邨ｱ蜷医・

| 繝｢繧ｸ繝･繝ｼ繝ｫ | 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|----------|--------------|------|
| `UserModule` | `UserController` | 繝励Ο繝輔ぅ繝ｼ繝ｫ CRUD 繧ｨ繝ｳ繝峨・繧､繝ｳ繝茨ｼ・ET/PATCH /users/me・・|
| | `UserService` | 繝ｦ繝ｼ繧ｶ繝ｼ諠・ｱ縺ｮ蜿門ｾ励・譖ｴ譁ｰ繝薙ず繝阪せ繝ｭ繧ｸ繝・け |
| | `UserRepository` | users 繝・・繝悶Ν縺ｮ CRUD・・ostgreSQL・・|
| `PreferencesModule` | `PreferencesController` | 蝸懷･ｽ險ｭ螳壹・莠育ｮ嶺ｸ企剞繝ｻ騾夂衍險ｭ螳壹お繝ｳ繝峨・繧､繝ｳ繝・|
| | `PreferencesService` | 險ｭ螳壼､縺ｮ讀懆ｨｼ繝ｻ菫晏ｭ倥Ο繧ｸ繝・け |
| | `PreferencesRepository` | user_preferences 繝・・繝悶Ν縺ｮ CRUD |
| `AuthModule`・亥・騾夲ｼ・| `JwtStrategy` | API Gateway 縺九ｉ貂｡縺輔ｌ縺・X-User-Id 繝倥ャ繝繝ｼ繧呈､懆ｨｼ繝ｻ繝ｪ繧ｯ繧ｨ繧ｹ繝医さ繝ｳ繝・く繧ｹ繝医↓豕ｨ蜈･ |
| | `CurrentUserDecorator` | 繧ｳ繝ｳ繝医Ο繝ｼ繝ｩ繝ｼ縺ｧ繝ｭ繧ｰ繧､繝ｳ繝ｦ繝ｼ繧ｶ繝ｼ繧貞叙繧雁・縺吶ョ繧ｳ繝ｬ繝ｼ繧ｿ |

---

### Stress Service・・2・・

**雋ｬ蜍・*: 繧ｹ繝医Ξ繧ｹ蠎ｦ縺ｮ蜿朱寔繝ｻ繧ｹ繧ｳ繧｢繝ｪ繝ｳ繧ｰ繝ｻ髢ｾ蛟､蛻､螳壹ゅせ繝医Ξ繧ｹ髢ｾ蛟､雜・℃譎ゅ↓繝ｪ繝ｯ繝ｼ繝峨ヵ繝ｭ繝ｼ繧偵ヨ繝ｪ繧ｬ繝ｼ縲・

| 繝｢繧ｸ繝･繝ｼ繝ｫ | 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|----------|--------------|------|
| `StressEntryModule` | `StressEntryController` | 繧ｹ繝医Ξ繧ｹ繧ｨ繝ｳ繝医Μ菴懈・繝ｻ螻･豁ｴ蜿門ｾ励お繝ｳ繝峨・繧､繝ｳ繝・|
| | `StressEntryService` | 繧ｨ繝ｳ繝医Μ菫晏ｭ倥・繧ｹ繧ｳ繧｢蜀崎ｨ育ｮ励・繧ｪ繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｷ繝ｧ繝ｳ |
| | `StressEntryRepository` | stress_entries 繝・・繝悶Ν縺ｮ CRUD・・imescaleDB・・|
| `StressScoringModule` | `StressScoringService` | 驥阪∩莉倥″蜷域・繧ｹ繧ｳ繧｢邂怜・・育ｴ皮ｲ矩未謨ｰ 窶・**PBT 蟇ｾ雎｡**・・|
| | `TextSentimentAdapter` | @ars/shared-ai 縺ｮ TextSentimentAnalyzer 繝ｩ繝・ヱ繝ｼ |
| `StressThresholdModule` | `StressThresholdService` | 髢ｾ蛟､蛻､螳壹・繝ｪ繝ｯ繝ｼ繝峨ヵ繝ｭ繝ｼ繝医Μ繧ｬ繝ｼ・・ewardClient 蜻ｼ縺ｳ蜃ｺ縺暦ｼ・|
| | `StressSettingsController` | 髢ｾ蛟､繝ｻ繧ｫ繝ｬ繝ｳ繝繝ｼ騾｣謳ｺ險ｭ螳壹お繝ｳ繝峨・繧､繝ｳ繝・|
| | `StressSettingsRepository` | stress_settings 繝・・繝悶Ν縺ｮ CRUD |

---

### Reward Service・・4・・

**雋ｬ蜍・*: 繧ｹ繝医Ξ繧ｹ繧ｹ繧ｳ繧｢縺ｨ雋｡蜍吩ｽ呵｣暮｡阪°繧峨ヱ繝ｼ繧ｽ繝翫Λ繧､繧ｺ縺輔ｌ縺溘Μ繝ｯ繝ｼ繝画署譯医ｒ逕滓・縲る夂衍繝医Μ繧ｬ繝ｼ縺ｾ縺ｧ諡・ｽ難ｼ医Μ繝ｯ繝ｼ繝峨ヵ繝ｭ繝ｼ繧ｪ繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｿ繝ｼ・峨・

| 繝｢繧ｸ繝･繝ｼ繝ｫ | 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|----------|--------------|------|
| `CatalogModule` | `CatalogController` | 繝ｪ繝ｯ繝ｼ繝峨き繧ｿ繝ｭ繧ｰ讀懃ｴ｢繧ｨ繝ｳ繝峨・繧､繝ｳ繝・|
| | `CatalogService` | 繧ｫ繧ｿ繝ｭ繧ｰ讀懃ｴ｢繝ｻ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ |
| | `CatalogRepository` | reward_catalog 繝・・繝悶Ν縺ｮ CRUD・・ostgreSQL・・|
| `ProposalModule` | `ProposalController` | 謠先｡井ｸ隕ｧ蜿門ｾ励・謗｡逕ｨ螻･豁ｴ繧ｨ繝ｳ繝峨・繧､繝ｳ繝・|
| | `ProposalService` | 謠先｡育函謌舌ヵ繝ｭ繝ｼ縺ｮ繧ｪ繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｷ繝ｧ繝ｳ・・inanceClient 竊・ProposalEngineService 竊・NotificationClient・・|
| | `ProposalRepository` | reward_proposals 繝・・繝悶Ν縺ｮ CRUD |
| `ProposalEngineModule` | `RuleBasedEngineService` | 繧ｹ繝医Ξ繧ｹ繝ｬ繝吶Ν ﾃ・菴呵｣暮｡・竊・謠先｡医Μ繧ｹ繝育函謌撰ｼ育ｴ皮ｲ矩未謨ｰ 窶・**PBT 蟇ｾ雎｡**・・|
| | `AiPersonalizationService` | 驕主悉繝輔ぅ繝ｼ繝峨ヰ繝・け繧貞渕縺ｫ謠先｡医せ繧ｳ繧｢繝ｪ繝ｳ繧ｰ・亥ｰ・擂繝輔ぉ繝ｼ繧ｺ・・|
| `FeedbackModule` | `FeedbackController` | 謗｡逕ｨ/蜊ｴ荳・蠕後〒繝輔ぅ繝ｼ繝峨ヰ繝・け繧ｨ繝ｳ繝峨・繧､繝ｳ繝・|
| | `FeedbackService` | 繝輔ぅ繝ｼ繝峨ヰ繝・け菫晏ｭ倥・謾ｯ蜃ｺ閾ｪ蜍戊ｨ倬鹸・・inanceClient 蜻ｼ縺ｳ蜃ｺ縺暦ｼ・|
| | `FeedbackRepository` | reward_feedbacks 繝・・繝悶Ν縺ｮ CRUD |

---

### Finance Service・・3・・

**雋ｬ蜍・*: 蜿取髪邂｡逅・・菴呵｣暮｡咲ｮ怜・繝ｻCSV 繧､繝ｳ繝昴・繝医・AI 繧ｫ繝・ざ繝ｪ蛻・｡槭・

| 繝｢繧ｸ繝･繝ｼ繝ｫ | 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|----------|--------------|------|
| `BudgetModule` | `BudgetController` | 譛域ｬ｡莠育ｮ励・菴呵｣暮｡阪お繝ｳ繝峨・繧､繝ｳ繝・|
| | `BudgetService` | 莠育ｮ苓ｨｭ螳夂ｮ｡逅・|
| | `BudgetRepository` | budgets 繝・・繝悶Ν縺ｮ CRUD |
| `AvailableBudgetModule` | `AvailableBudgetController` | GET /finance/available-reward-budget |
| | `AvailableBudgetService` | 菴呵｣暮｡咲ｮ怜・繝ｭ繧ｸ繝・け・育ｴ皮ｲ矩未謨ｰ 窶・**PBT 蟇ｾ雎｡**・・|
| `TransactionModule` | `TransactionController` | 蜿門ｼ募ｱ･豁ｴ蜿門ｾ励・謇句虚霑ｽ蜉繧ｨ繝ｳ繝峨・繧､繝ｳ繝・|
| | `TransactionService` | 蜿門ｼ輔・菫晏ｭ倥・繧ｫ繝・ざ繝ｪ蛻・｡槭が繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｷ繝ｧ繝ｳ |
| | `TransactionRepository` | transactions 繝・・繝悶Ν縺ｮ CRUD |
| `CsvImportModule` | `CsvImportController` | POST /finance/import/csv |
| | `CsvImportService` | CSV 繝代・繧ｹ繝ｻ繝輔か繝ｼ繝槭ャ繝亥､画鋤・井ｸ芽廠UFJ / 荳我ｺ穂ｽ丞暑 / 繧・≧縺｡繧・ｼ・|
| | `CategoryClassifierAdapter` | @ars/shared-ai 縺ｮ TransactionCategoryClassifier 繝ｩ繝・ヱ繝ｼ |

---

### Notification Service・・5・・

**雋ｬ蜍・*: 繝ｪ繝ｯ繝ｼ繝画署譯磯夂衍縺ｮ逕滓・繝ｻ騾∽ｿ｡繝ｻ繧ｹ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ邂｡逅・・

| 繝｢繧ｸ繝･繝ｼ繝ｫ | 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|----------|--------------|------|
| `DeviceTokenModule` | `DeviceTokenController` | 繝・ヰ繧､繧ｹ繝医・繧ｯ繝ｳ逋ｻ骭ｲ繝ｻ蜑企勁繧ｨ繝ｳ繝峨・繧､繝ｳ繝・|
| | `DeviceTokenService` | 繝医・繧ｯ繝ｳ邂｡逅・|
| | `DeviceTokenRepository` | device_tokens 繝・・繝悶Ν縺ｮ CRUD |
| `NotificationModule` | `NotificationController` | 騾夂衍騾∽ｿ｡繝ｻ螻･豁ｴ蜿門ｾ励お繝ｳ繝峨・繧､繝ｳ繝・|
| | `NotificationService` | 騾夂衍繧ｳ繝斐・逕滓・ 竊・繧ｹ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ遒ｺ隱・竊・Web Push / FCM 騾∽ｿ｡縺ｮ繧ｪ繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｷ繝ｧ繝ｳ |
| | `NotificationRepository` | notification_logs 繝・・繝悶Ν縺ｮ CRUD |
| `ThrottleModule` | `ThrottleService` | 1譌･譛螟ｧ騾夂衍謨ｰ繝ｻ髱吝ｯよ凾髢灘ｸｯ・・2:00縲・:00・峨メ繧ｧ繝・け・・edis・・|
| `CopyGeneratorAdapter` | 窶・| @ars/shared-ai 縺ｮ NotificationCopyGenerator 繝ｩ繝・ヱ繝ｼ |

---

### Dashboard Service・・7・・

**雋ｬ蜍・*: 繧ｹ繝医Ξ繧ｹ繝ｻ繝ｪ繝ｯ繝ｼ繝峨・雋｡蜍吶ョ繝ｼ繧ｿ縺ｮ髮・ｨ医・蜿ｯ隕門喧繝ｻAI 繧､繝ｳ繧ｵ繧､繝育函謌舌・

| 繝｢繧ｸ繝･繝ｼ繝ｫ | 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 雋ｬ蜍・|
|----------|--------------|------|
| `StressTrendModule` | `StressTrendController` | 繧ｹ繝医Ξ繧ｹ謗ｨ遘ｻ繝・・繧ｿ繧ｨ繝ｳ繝峨・繧､繝ｳ繝・|
| | `StressTrendService` | TimescaleDB / ClickHouse 縺九ｉ髮・ｨ茨ｼ・tressClient 邨檎罰・・|
| `RewardHistoryModule` | `RewardHistoryController` | 繝ｪ繝ｯ繝ｼ繝牙ｱ･豁ｴ繧ｿ繧､繝繝ｩ繧､繝ｳ繧ｨ繝ｳ繝峨・繧､繝ｳ繝・|
| | `RewardHistoryService` | RewardClient 邨檎罰縺ｧ繝・・繧ｿ蜿門ｾ励・髮・ｨ・|
| `FinanceSummaryModule` | `FinanceSummaryController` | 雋｡蜍吝ｽｱ髻ｿ繧ｵ繝槭Μ繝ｼ繧ｨ繝ｳ繝峨・繧､繝ｳ繝・|
| | `FinanceSummaryService` | FinanceClient 邨檎罰縺ｧ繝・・繧ｿ蜿門ｾ励・髮・ｨ・|
| `InsightModule` | `InsightController` | AI 繧､繝ｳ繧ｵ繧､繝医Ξ繝昴・繝医お繝ｳ繝峨・繧､繝ｳ繝・|
| | `InsightService` | 譛域ｬ｡繧､繝ｳ繧ｵ繧､繝医Ξ繝昴・繝育函謌撰ｼ・nsightReportGeneratorAdapter 邨檎罰・・|
| | `InsightReportGeneratorAdapter` | @ars/shared-ai 縺ｮ InsightReportGenerator 繝ｩ繝・ヱ繝ｼ |

---

## 繝輔Ο繝ｳ繝医お繝ｳ繝会ｼ・pps/web・・

**謚陦・*: React + TypeScript + Vite  
**迥ｶ諷狗ｮ｡逅・*: Zustand・医げ繝ｭ繝ｼ繝舌Ν・・ TanStack Query・医し繝ｼ繝舌・繧ｹ繝・・繝茨ｼ・ 
**繧ｳ繝ｳ繝昴・繝阪Φ繝郁ｨｭ險・*: Feature-based

```
apps/web/src/
笏懌楳笏 features/
笏・  笏懌楳笏 auth/              # 繝ｭ繧ｰ繧､繝ｳ繝ｻ逋ｻ骭ｲ繝ｻ蛻晄悄險ｭ螳壹え繧｣繧ｶ繝ｼ繝・
笏・  笏懌楳笏 stress/            # 繧ｹ繝医Ξ繧ｹ蜈･蜉帙・繝繝・す繝･繝懊・繝・
笏・  笏懌楳笏 rewards/           # 繝ｪ繝ｯ繝ｼ繝画署譯井ｸ隕ｧ繝ｻ繝輔ぅ繝ｼ繝峨ヰ繝・け
笏・  笏懌楳笏 finance/           # 蜿取髪險ｭ螳壹・CSV 繧､繝ｳ繝昴・繝・
笏・  笏懌楳笏 dashboard/         # 謖ｯ繧願ｿ斐ｊ繧ｰ繝ｩ繝輔・繧､繝ｳ繧ｵ繧､繝・
笏・  笏披楳笏 notifications/     # 騾夂衍險ｭ螳壹・螻･豁ｴ
笏懌楳笏 shared/
笏・  笏懌楳笏 components/        # 蜈ｱ騾・UI 繧ｳ繝ｳ繝昴・繝阪Φ繝茨ｼ・utton, Modal 遲会ｼ・
笏・  笏懌楳笏 hooks/             # 蜈ｱ騾壹き繧ｹ繧ｿ繝繝輔ャ繧ｯ
笏・  笏懌楳笏 stores/            # Zustand 繧ｹ繝医い・・uth, ui・・
笏・  笏披楳笏 api/               # API 繧ｯ繝ｩ繧､繧｢繝ｳ繝茨ｼ・xios 繧､繝ｳ繧ｹ繧ｿ繝ｳ繧ｹ・・
笏披楳笏 app/
    笏懌楳笏 App.tsx
    笏懌楳笏 router.tsx          # React Router v6
    笏披楳笏 providers.tsx       # QueryClient, Zustand, AuthProvider
```

| 繧ｳ繝ｳ繝昴・繝阪Φ繝育ｾ､ | 雋ｬ蜍・|
|----------------|------|
| `features/auth/` | 繝ｭ繧ｰ繧､繝ｳ繝輔か繝ｼ繝繝ｻGoogle OAuth 繝懊ち繝ｳ繝ｻ蛻晄悄險ｭ螳壹え繧｣繧ｶ繝ｼ繝会ｼ医き繝・ざ繝ｪ驕ｸ謚槭・莠育ｮ苓ｨｭ螳夲ｼ・|
| `features/stress/` | 繧ｹ繝医Ξ繧ｹ蜈･蜉帙え繧｣繧ｸ繧ｧ繝・ヨ・・繧ｿ繝・・蜈･蜉幢ｼ峨・繧ｹ繝医Ξ繧ｹ螻･豁ｴ繧ｫ繝ｼ繝・|
| `features/rewards/` | 繝ｪ繝ｯ繝ｼ繝画署譯医き繝ｼ繝我ｸ隕ｧ繝ｻ謗｡逕ｨ/蜊ｴ荳・蠕後〒繝懊ち繝ｳ繝ｻ謗｡逕ｨ貂医∩螻･豁ｴ |
| `features/finance/` | 蜿取髪蜈･蜉帙ヵ繧ｩ繝ｼ繝繝ｻ菴呵｣暮｡阪え繧｣繧ｸ繧ｧ繝・ヨ繝ｻCSV 繧｢繝・・繝ｭ繝ｼ繝峨・蜿門ｼ輔き繝・ざ繝ｪ菫ｮ豁｣ |
| `features/dashboard/` | 繧ｹ繝医Ξ繧ｹ謗ｨ遘ｻ繧ｰ繝ｩ繝輔・縺碑､堤ｾ取髪蜃ｺ譽偵げ繝ｩ繝輔・AI 繧､繝ｳ繧ｵ繧､繝医き繝ｼ繝・|
| `features/notifications/` | 騾夂衍險ｭ螳壹ヵ繧ｩ繝ｼ繝繝ｻ騾夂衍螻･豁ｴ繝ｪ繧ｹ繝・|
| `shared/stores/authStore` | Zustand: 隱崎ｨｼ迥ｶ諷具ｼ・ser, token, isAuthenticated・・|
| `shared/stores/uiStore` | Zustand: 繧ｰ繝ｭ繝ｼ繝舌Ν UI 迥ｶ諷具ｼ医Δ繝ｼ繝繝ｫ陦ｨ遉ｺ縲√Ο繝ｼ繝・ぅ繝ｳ繧ｰ・・|
