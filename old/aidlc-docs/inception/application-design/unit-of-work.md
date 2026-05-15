# Unit of Work 螳夂ｾｩ 窶・繧ｪ繝ｼ繝医Μ繝ｯ繝ｼ繝峨し繝ｼ繝薙せ

**菴懈・譌･**: 2026-05-08

## 螳溯｣・し繧､繧ｯ繝ｫ譁ｹ驥晢ｼ育｢ｺ螳夲ｼ・

| 鬆・岼 | 豎ｺ螳壼・螳ｹ |
|------|---------|
| 螳溯｣・ｲ貞ｺｦ | **讖溯・繧ｹ繝ｩ繧､繧ｹ蜊倅ｽ・*・亥推 Unit 縺ｮ荳ｭ縺ｮ讖溯・繧貞ｰ上＆縺丞玄蛻・▲縺ｦ螳溯｣・ｼ・|
| 蜈ｱ譛峨ヱ繝・こ繝ｼ繧ｸ | **Unit 0 縺ｨ縺励※譛蛻昴・繧ｵ繧､繧ｯ繝ｫ縺ｧ螳溯｣・* |
| 繝・せ繝・| **繧ｳ繝ｼ繝臥函謌舌→蜷後§繧ｵ繧､繧ｯ繝ｫ**・・nit 繝・せ繝・+ 邨ｱ蜷医ユ繧ｹ繝医ｒ蜷ｫ繧√ｋ・・|
| Docker Compose | **蜷・Unit 縺ｮ螳溯｣・↓荳ｦ陦・*縺励※縲√◎縺ｮ繧ｵ繝ｼ繝薙せ縺ｮ繧ｳ繝ｳ繝・リ螳夂ｾｩ繧定ｿｽ蜉 |

---

## 繝｢繝弱Ξ繝・繧ｳ繝ｼ繝画ｧ区・譁ｹ驥・

```
auto-reward-service/                  竊・Turborepo 繝ｫ繝ｼ繝・
笏懌楳笏 apps/
笏・  笏懌楳笏 auth-service/                 # Unit 1
笏・  笏懌楳笏 stress-service/               # Unit 2
笏・  笏懌楳笏 reward-service/               # Unit 3
笏・  笏懌楳笏 finance-service/              # Unit 4
笏・  笏懌楳笏 notification-service/         # Unit 5
笏・  笏懌楳笏 dashboard-service/            # Unit 6
笏・  笏披楳笏 web/                          # Unit 7
笏懌楳笏 packages/
笏・  笏懌楳笏 shared-types/                 # Unit 0
笏・  笏懌楳笏 shared-clients/               # Unit 0
笏・  笏懌楳笏 shared-ai/                    # Unit 0
笏・  笏披楳笏 shared-config/                # Unit 0
笏懌楳笏 infrastructure/
笏・  笏懌楳笏 docker-compose.yml
笏・  笏披楳笏 nginx/
笏懌楳笏 turbo.json
笏披楳笏 package.json
```

---

## Unit 荳隕ｧ

### Unit 0: 蜈ｱ譛牙渕逶､・・hared Infrastructure・・

**譛蛻昴・繧ｵ繧､繧ｯ繝ｫ縺ｧ螳溯｣・ｼ亥・陦悟ｿ・茨ｼ・*

| 蜀・ｮｹ | 隧ｳ邏ｰ |
|------|------|
| **繧ｹ繧ｳ繝ｼ繝・* | Turborepo 蛻晄悄蛹悶∝・譛峨ヱ繝・こ繝ｼ繧ｸ 4 譛ｬ縲．ocker Compose 鬪ｨ譬ｼ縲¨ginx 險ｭ螳夐ｪｨ譬ｼ |
| **謌先棡迚ｩ** | `packages/shared-types/`, `packages/shared-clients/`・医せ繧ｿ繝厄ｼ・ `packages/shared-ai/`・医せ繧ｿ繝厄ｼ・ `packages/shared-config/`, `infrastructure/docker-compose.yml`・磯ｪｨ譬ｼ・・ `infrastructure/nginx/nginx.conf` |
| **螳御ｺ・擅莉ｶ** | 蜈ｨ繧ｵ繝ｼ繝薙せ縺悟・譛峨ヱ繝・こ繝ｼ繧ｸ繧・import 縺ｧ縺阪ｋ; Docker Compose 縺ｧ繧､繝ｳ繝輔Λ・・B繝ｻRedis・峨′襍ｷ蜍輔〒縺阪ｋ |

**讖溯・繧ｹ繝ｩ繧､繧ｹ:**
| 繧ｹ繝ｩ繧､繧ｹ | 蜀・ｮｹ |
|---------|------|
| 0-1 | Turborepo + npm workspaces 繧ｻ繝・ヨ繧｢繝・・縲～package.json` 險ｭ螳・|
| 0-2 | `@ars/shared-types`: DTO繝ｻ蛻玲嫌蝙句ｮ夂ｾｩ |
| 0-3 | `@ars/shared-config`: AppConfigModule, LoggerModule, HealthModule |
| 0-4 | `@ars/shared-clients`: 繧ｯ繝ｩ繧､繧｢繝ｳ繝医せ繧ｿ繝厄ｼ亥梛縺ｮ縺ｿ縲∝ｮ溯｣・・蠕檎ｶ・Unit 縺ｧ蜈・ｮ滂ｼ・|
| 0-5 | `@ars/shared-ai`: AiModule 繧ｹ繧ｿ繝厄ｼ・penAI SDK 繧ｻ繝・ヨ繧｢繝・・縺ｮ縺ｿ・・|
| 0-6 | `infrastructure/`: Docker Compose 鬪ｨ譬ｼ・・B繝ｻRedis繝ｻClickHouse 繧ｳ繝ｳ繝・リ・峨¨ginx 鬪ｨ譬ｼ |

---

### Unit 1: Auth Service・・1 蟇ｾ蠢懶ｼ・

**蟇ｾ蠢懆ｦ∽ｻｶ**: U1-01縲弑1-05 / US-01, US-02

| 蜀・ｮｹ | 隧ｳ邏ｰ |
|------|------|
| **繧ｹ繧ｳ繝ｼ繝・* | 繝ｦ繝ｼ繧ｶ繝ｼ邂｡逅・・繝励Ο繝輔ぅ繝ｼ繝ｫ繝ｻ蝸懷･ｽ險ｭ螳壹・莠育ｮ嶺ｸ企剞繝ｻ騾夂衍險ｭ螳・|
| **DB** | PostgreSQL・・ars_auth`・・|
| **萓晏ｭ・* | Unit 0・・hared-config, shared-types・・|
| **螳御ｺ・擅莉ｶ** | `/users/me` GET/PATCH 縺悟虚菴懊☆繧・ Docker Compose 縺ｧ auth-service 縺瑚ｵｷ蜍輔☆繧・|

**讖溯・繧ｹ繝ｩ繧､繧ｹ:**
| 繧ｹ繝ｩ繧､繧ｹ | 讖溯・ | 蟇ｾ蠢・US |
|---------|------|---------|
| 1-1 | NestJS 繝励Ο繧ｸ繧ｧ繧ｯ繝亥・譛溷喧 + PostgreSQL 謗･邯・+ HealthModule | 窶・|
| 1-2 | UserModule: 繝励Ο繝輔ぅ繝ｼ繝ｫ CRUD・・ET/PATCH /users/me・・+ Unit 繝・せ繝・| US-01 |
| 1-3 | PreferencesModule: 蝸懷･ｽ繝ｻ莠育ｮ嶺ｸ企剞繝ｻ騾夂衍險ｭ螳・CRUD + Unit 繝・せ繝・| US-02 |
| 1-4 | AuthModule: JwtStrategy・・-User-Id 繝倥ャ繝繝ｼ讀懆ｨｼ・・ CurrentUserDecorator | 窶・|
| 1-5 | 邨ｱ蜷医ユ繧ｹ繝茨ｼ・ocker Compose 荳翫〒縺ｮ E2E・・| 窶・|
| 1-6 | Docker Compose 縺ｫ auth-service + postgres-auth 繧ｳ繝ｳ繝・リ繧定ｿｽ蜉 | 窶・|

---

### Unit 2: Stress Service・・2 蟇ｾ蠢懶ｼ・

**蟇ｾ蠢懆ｦ∽ｻｶ**: U2-01, U2-05, U2-06, U2-07・・VP・・ US-03, US-04・井ｸ驛ｨ・・ US-05

| 蜀・ｮｹ | 隧ｳ邏ｰ |
|------|------|
| **繧ｹ繧ｳ繝ｼ繝・* | 謇句虚繧ｹ繝医Ξ繧ｹ蜈･蜉帙・繧ｹ繧ｳ繧｢邂怜・繝ｻ髢ｾ蛟､蛻､螳壹・繝ｪ繝ｯ繝ｼ繝峨ヵ繝ｭ繝ｼ繝医Μ繧ｬ繝ｼ繝ｻ螻･豁ｴ菫晏ｭ・|
| **DB** | TimescaleDB・・ars_stress`・・|
| **萓晏ｭ・* | Unit 0・・hared-config, shared-types, shared-clients/RewardClient 繧ｹ繧ｿ繝厄ｼ・ Unit 1・・uth・・|
| **螳御ｺ・擅莉ｶ** | 繧ｹ繝医Ξ繧ｹ蜈･蜉帚・繧ｹ繧ｳ繧｢邂怜・竊帝明蛟､蛻､螳壺・RewardClient 蜻ｼ縺ｳ蜃ｺ縺励′蜍穂ｽ懊☆繧・|

**讖溯・繧ｹ繝ｩ繧､繧ｹ:**
| 繧ｹ繝ｩ繧､繧ｹ | 讖溯・ | 蟇ｾ蠢・US |
|---------|------|---------|
| 2-1 | NestJS 繝励Ο繧ｸ繧ｧ繧ｯ繝亥・譛溷喧 + TimescaleDB 謗･邯・+ HealthModule | 窶・|
| 2-2 | StressEntryModule: 謇句虚蜈･蜉帙お繝ｳ繝峨・繧､繝ｳ繝・+ Unit 繝・せ繝・| US-03 |
| 2-3 | StressScoringModule: 繧ｹ繧ｳ繧｢邂怜・邏皮ｲ矩未謨ｰ + Unit 繝・せ繝・+ **PBT** | 窶・|
| 2-4 | StressThresholdModule: 髢ｾ蛟､蛻､螳・+ RewardClient 蜻ｼ縺ｳ蜃ｺ縺・+ Unit 繝・せ繝・| US-05 |
| 2-5 | 邨ｱ蜷医ユ繧ｹ繝茨ｼ・tress 蜈･蜉帚・髢ｾ蛟､蛻､螳壹ヵ繝ｭ繝ｼ・・| 窶・|
| 2-6 | Docker Compose 縺ｫ stress-service + timescaledb 繧ｳ繝ｳ繝・リ繧定ｿｽ蜉 | 窶・|
| 2-7 | ・亥ｰ・擂・欝extSentimentAdapter: shared-ai 騾｣謳ｺ | US-04 荳驛ｨ |

---

### Unit 3: Reward Service・・4 蟇ｾ蠢懶ｼ・

**蟇ｾ蠢懆ｦ∽ｻｶ**: U4-01, U4-02, U4-05・・VP・・ US-08, US-10, US-11

| 蜀・ｮｹ | 隧ｳ邏ｰ |
|------|------|
| **繧ｹ繧ｳ繝ｼ繝・* | 繝ｪ繝ｯ繝ｼ繝峨き繧ｿ繝ｭ繧ｰ繝ｻ繝ｫ繝ｼ繝ｫ繝吶・繧ｹ謠先｡医・繝輔ぅ繝ｼ繝峨ヰ繝・け蜿朱寔繝ｻ騾夂衍繝医Μ繧ｬ繝ｼ |
| **DB** | PostgreSQL・・ars_reward`・・ Redis・域署譯医く繝｣繝・す繝･・・|
| **萓晏ｭ・* | Unit 0, Unit 1, Unit 2・・ewardClient 繧貞女縺大叙繧句・・峨：inance Client 繧ｹ繧ｿ繝悶¨otification Client 繧ｹ繧ｿ繝・|
| **螳御ｺ・擅莉ｶ** | Stress Service 縺九ｉ縺ｮ繝医Μ繧ｬ繝ｼ縺ｧ謠先｡医′逕滓・縺輔ｌ縲¨otification Service 縺ｫ霆｢騾√〒縺阪ｋ |

**讖溯・繧ｹ繝ｩ繧､繧ｹ:**
| 繧ｹ繝ｩ繧､繧ｹ | 讖溯・ | 蟇ｾ蠢・US |
|---------|------|---------|
| 3-1 | NestJS 繝励Ο繧ｸ繧ｧ繧ｯ繝亥・譛溷喧 + PostgreSQL + Redis 謗･邯・| 窶・|
| 3-2 | CatalogModule: 繧ｫ繧ｿ繝ｭ繧ｰ CRUD + 繧ｷ繝ｼ繝峨ョ繝ｼ繧ｿ + Unit 繝・せ繝・| US-08 蜑肴署 |
| 3-3 | RuleBasedEngineModule: 謠先｡医・繝医Μ繧ｯ繧ｹ邏皮ｲ矩未謨ｰ + Unit 繝・せ繝・+ **PBT** | US-08 |
| 3-4 | ProposalModule: 謠先｡育函謌舌ヵ繝ｭ繝ｼ・・inanceClient 竊・Engine 竊・菫晏ｭ・竊・NotifClient・・| US-08 |
| 3-5 | FeedbackModule: 謗｡逕ｨ/蜊ｴ荳・蠕後〒 + 謾ｯ蜃ｺ險倬鹸・・inanceClient・・+ Unit 繝・せ繝・| US-10, US-11 |
| 3-6 | 邨ｱ蜷医ユ繧ｹ繝茨ｼ域署譯育函謌舌懊ヵ繧｣繝ｼ繝峨ヰ繝・け繝輔Ο繝ｼ・・| 窶・|
| 3-7 | Docker Compose 縺ｫ reward-service + postgres-reward + redis 繧ｳ繝ｳ繝・リ繧定ｿｽ蜉 | 窶・|
| 3-8 | @ars/shared-clients 縺ｮ RewardClient 繧貞ｮ溯｣・ｼ医せ繧ｿ繝・竊・螳溯｣・ｼ・| 窶・|

---

### Unit 4: Finance Service・・3 蟇ｾ蠢懶ｼ・

**蟇ｾ蠢懆ｦ∽ｻｶ**: U3-01, U3-04, U3-05・・VP・・ U3-02, U3-06・・hould・・ US-06, US-07

| 蜀・ｮｹ | 隧ｳ邏ｰ |
|------|------|
| **繧ｹ繧ｳ繝ｼ繝・* | 蜿取髪邂｡逅・・菴呵｣暮｡咲ｮ怜・繝ｻCSV 繧､繝ｳ繝昴・繝医・AI 繧ｫ繝・ざ繝ｪ蛻・｡・|
| **DB** | PostgreSQL・・ars_finance`・・|
| **萓晏ｭ・* | Unit 0, Unit 1 |
| **螳御ｺ・擅莉ｶ** | 菴呵｣暮｡咲ｮ怜・ API 縺悟虚菴懊☆繧・ Reward Service 縺ｮ FinanceClient 縺悟ｮ滄圀縺ｫ蜻ｼ縺ｳ蜃ｺ縺帙ｋ |

**讖溯・繧ｹ繝ｩ繧､繧ｹ:**
| 繧ｹ繝ｩ繧､繧ｹ | 讖溯・ | 蟇ｾ蠢・US |
|---------|------|---------|
| 4-1 | NestJS 繝励Ο繧ｸ繧ｧ繧ｯ繝亥・譛溷喧 + PostgreSQL 謗･邯・| 窶・|
| 4-2 | BudgetModule: 譛域ｬ｡莠育ｮ苓ｨｭ螳・CRUD + Unit 繝・せ繝・| US-06 |
| 4-3 | AvailableBudgetModule: 菴呵｣暮｡咲ｮ怜・邏皮ｲ矩未謨ｰ + Unit 繝・せ繝・+ **PBT** | US-06, US-08 蜑肴署 |
| 4-4 | TransactionModule: 蜿門ｼ・CRUD + Unit 繝・せ繝・| US-07 |
| 4-5 | CsvImportModule: CSV 繝代・繧ｹ・井ｸ芽廠UFJ / 荳我ｺ穂ｽ丞暑 / 繧・≧縺｡繧・ｼ・ Unit 繝・せ繝・| US-07 |
| 4-6 | CategoryClassifierAdapter: shared-ai 騾｣謳ｺ + Unit 繝・せ繝・| US-07 |
| 4-7 | 邨ｱ蜷医ユ繧ｹ繝・| 窶・|
| 4-8 | Docker Compose 縺ｫ finance-service + postgres-finance 繧ｳ繝ｳ繝・リ繧定ｿｽ蜉 | 窶・|
| 4-9 | @ars/shared-clients 縺ｮ FinanceClient 繧貞ｮ溯｣・ｼ医せ繧ｿ繝・竊・螳溯｣・ｼ・| 窶・|

---

### Unit 5: Notification Service・・5 蟇ｾ蠢懶ｼ・

**蟇ｾ蠢懆ｦ∽ｻｶ**: U5-01, U5-02, U5-03・・VP・・ US-05・磯夂衍騾∽ｿ｡驛ｨ蛻・ｼ・

| 蜀・ｮｹ | 隧ｳ邏ｰ |
|------|------|
| **繧ｹ繧ｳ繝ｼ繝・* | 繝励ャ繧ｷ繝･騾夂衍逕滓・繝ｻ騾∽ｿ｡繝ｻ繧ｹ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ繝ｻ繝・ヰ繧､繧ｹ繝医・繧ｯ繝ｳ邂｡逅・|
| **DB** | PostgreSQL・・ars_notification`・・ Redis・医せ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ繧ｫ繧ｦ繝ｳ繧ｿ繝ｼ・・|
| **萓晏ｭ・* | Unit 0, Unit 1, Unit 3・・otifClient 繧貞女縺大叙繧句・・・|
| **螳御ｺ・擅莉ｶ** | Reward Service 縺九ｉ縺ｮ繝医Μ繧ｬ繝ｼ縺ｧ Web Push 騾夂衍縺碁∽ｿ｡縺ｧ縺阪ｋ |

**讖溯・繧ｹ繝ｩ繧､繧ｹ:**
| 繧ｹ繝ｩ繧､繧ｹ | 讖溯・ | 蟇ｾ蠢・US |
|---------|------|---------|
| 5-1 | NestJS 繝励Ο繧ｸ繧ｧ繧ｯ繝亥・譛溷喧 + PostgreSQL + Redis 謗･邯・| 窶・|
| 5-2 | DeviceTokenModule: 繝医・繧ｯ繝ｳ逋ｻ骭ｲ繝ｻ蜑企勁 + Unit 繝・せ繝・| 窶・|
| 5-3 | ThrottleModule: 1譌･荳企剞繝ｻ髱吝ｯよ凾髢灘ｸｯ繝√ぉ繝・け・・edis・・ Unit 繝・せ繝・| US-05 |
| 5-4 | CopyGeneratorAdapter: shared-ai 騾｣謳ｺ・磯夂衍繧ｳ繝斐・逕滓・・・ Unit 繝・せ繝・| 窶・|
| 5-5 | NotificationModule: 騾∽ｿ｡繝輔Ο繝ｼ邨ｱ蜷・+ Web Push / FCM 騾∽ｿ｡ + Unit 繝・せ繝・| US-05 |
| 5-6 | 邨ｱ蜷医ユ繧ｹ繝・| 窶・|
| 5-7 | Docker Compose 縺ｫ notification-service + postgres-notif 繧ｳ繝ｳ繝・リ繧定ｿｽ蜉 | 窶・|
| 5-8 | @ars/shared-clients 縺ｮ NotificationClient 繧貞ｮ溯｣・ｼ医せ繧ｿ繝・竊・螳溯｣・ｼ・| 窶・|

---

### Unit 6: Dashboard Service・・7 蟇ｾ蠢懶ｼ・

**蟇ｾ蠢懆ｦ∽ｻｶ**: U7-01, U7-02, U7-03・・VP・・ U7-04・・hould・・ US-12, US-13

| 蜀・ｮｹ | 隧ｳ邏ｰ |
|------|------|
| **繧ｹ繧ｳ繝ｼ繝・* | 繧ｹ繝医Ξ繧ｹ謗ｨ遘ｻ繝ｻ繝ｪ繝ｯ繝ｼ繝牙ｱ･豁ｴ繝ｻ雋｡蜍吶し繝槭Μ繝ｼ繝ｻAI 繧､繝ｳ繧ｵ繧､繝・|
| **DB** | ClickHouse |
| **萓晏ｭ・* | Unit 0, Unit 1, Unit 2, Unit 3, Unit 4・亥推 Client 邨檎罰・・|
| **螳御ｺ・擅莉ｶ** | 繝繝・す繝･繝懊・繝牙・ API 縺悟虚菴懊☆繧・|

**讖溯・繧ｹ繝ｩ繧､繧ｹ:**
| 繧ｹ繝ｩ繧､繧ｹ | 讖溯・ | 蟇ｾ蠢・US |
|---------|------|---------|
| 6-1 | NestJS 繝励Ο繧ｸ繧ｧ繧ｯ繝亥・譛溷喧 + ClickHouse 謗･邯・| 窶・|
| 6-2 | StressTrendModule: 繧ｹ繝医Ξ繧ｹ謗ｨ遘ｻ繝・・繧ｿ API + Unit 繝・せ繝・| US-12 |
| 6-3 | RewardHistoryModule: 繝ｪ繝ｯ繝ｼ繝牙ｱ･豁ｴ API + Unit 繝・せ繝・| US-12 |
| 6-4 | FinanceSummaryModule: 雋｡蜍吶し繝槭Μ繝ｼ API + Unit 繝・せ繝・| US-12 |
| 6-5 | InsightModule: AI 繧､繝ｳ繧ｵ繧､繝医Ξ繝昴・繝育函謌・+ 譛域ｬ｡繧ｭ繝｣繝・す繝･ + Unit 繝・せ繝・| US-13 |
| 6-6 | 邨ｱ蜷医ユ繧ｹ繝・| 窶・|
| 6-7 | Docker Compose 縺ｫ dashboard-service + clickhouse 繧ｳ繝ｳ繝・リ繧定ｿｽ蜉 | 窶・|

---

### Unit 7: Web 繝輔Ο繝ｳ繝医お繝ｳ繝・

**蟇ｾ蠢懆ｦ∽ｻｶ**: 蜈ｨ US・・S-01縲弑S-13・峨・繝輔Ο繝ｳ繝医お繝ｳ繝牙ｮ溯｣・

| 蜀・ｮｹ | 隧ｳ邏ｰ |
|------|------|
| **繧ｹ繧ｳ繝ｼ繝・* | React + Vite 繧｢繝励Μ縲∝・ Feature |
| **萓晏ｭ・* | Unit 0・・hared-types・・ Unit 1縲・・・PI 邨檎罰・・|
| **螳御ｺ・擅莉ｶ** | 蜈ｨ Feature 縺悟虚菴懊＠縲√ヰ繝・け繧ｨ繝ｳ繝峨→ E2E 縺ｧ謗･邯壹〒縺阪ｋ |

**讖溯・繧ｹ繝ｩ繧､繧ｹ:**
| 繧ｹ繝ｩ繧､繧ｹ | 讖溯・ | 蟇ｾ蠢・US |
|---------|------|---------|
| 7-1 | Vite + React + TypeScript 蛻晄悄蛹悶ヽouter縲￣rovider 險ｭ螳・| 窶・|
| 7-2 | `features/auth/`: 繝ｭ繧ｰ繧､繝ｳ繝ｻ蛻晄悄險ｭ螳壹え繧｣繧ｶ繝ｼ繝・| US-01, US-02 |
| 7-3 | `features/stress/`: 繧ｹ繝医Ξ繧ｹ蜈･蜉帙え繧｣繧ｸ繧ｧ繝・ヨ繝ｻ螻･豁ｴ | US-03 |
| 7-4 | `features/rewards/`: 謠先｡医き繝ｼ繝峨・繝輔ぅ繝ｼ繝峨ヰ繝・け繝懊ち繝ｳ繝ｻ螻･豁ｴ | US-08, US-09, US-10, US-11 |
| 7-5 | `features/finance/`: 蜿取髪蜈･蜉帙・菴呵｣暮｡阪え繧｣繧ｸ繧ｧ繝・ヨ繝ｻCSV 繧｢繝・・繝ｭ繝ｼ繝・| US-06, US-07 |
| 7-6 | `features/dashboard/`: 繧ｹ繝医Ξ繧ｹ繧ｰ繝ｩ繝輔・謾ｯ蜃ｺ繧ｰ繝ｩ繝輔・AI 繧､繝ｳ繧ｵ繧､繝医き繝ｼ繝・| US-12, US-13 |
| 7-7 | `features/notifications/`: 騾夂衍險ｭ螳壹・螻･豁ｴ | US-05 |
| 7-8 | 邨ｱ蜷医ユ繧ｹ繝茨ｼ・SW 繝｢繝・け + Testing Library・・| 窶・|
| 7-9 | Docker Compose 縺ｫ web 繧ｳ繝ｳ繝・リ繧定ｿｽ蜉 | 窶・|
