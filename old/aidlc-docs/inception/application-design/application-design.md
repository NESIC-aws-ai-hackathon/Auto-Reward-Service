# Application Design・育ｵｱ蜷育沿・・窶・繧ｪ繝ｼ繝医Μ繝ｯ繝ｼ繝峨し繝ｼ繝薙せ

**菴懈・譌･**: 2026-05-08  
**繧ｹ繝・・繧ｿ繧ｹ**: 繝ｬ繝薙Η繝ｼ蠕・■

---

## 1. 繧｢繝ｼ繧ｭ繝・け繝√Ε讎りｦ・

### 險ｭ險域婿驥昴∪縺ｨ繧・

| 鬆・岼 | 豎ｺ螳壼・螳ｹ |
|------|---------|
| 繝｢繝弱Ξ繝晉ｮ｡逅・| **Turborepo**・・pm workspaces + 繝薙Ν繝峨く繝｣繝・す繝･・・|
| 繝舌ャ繧ｯ繧ｨ繝ｳ繝峨ヵ繝ｬ繝ｼ繝繝ｯ繝ｼ繧ｯ | **NestJS・・ypeScript・・* 蜈ｨ繧ｵ繝ｼ繝薙せ邨ｱ荳 |
| 繝｢繧ｸ繝･繝ｼ繝ｫ蠅・阜 | **繝上う繝悶Μ繝・ラ**・医さ繧｢繝峨Γ繧､繝ｳ縺ｯ繝峨Γ繧､繝ｳ蛻・牡縲∝・騾壽ｩ溯・縺ｯ繝ｬ繧､繝､繝ｼ蛻・牡・・|
| 繧ｵ繝ｼ繝薙せ髢馴壻ｿ｡ | **蜈ｱ譛峨け繝ｩ繧､繧｢繝ｳ繝医ヱ繝・こ繝ｼ繧ｸ**・・ars/shared-clients縲？TTP 蜷梧悄・・|
| API Gateway | **Nginx**・・WT 讀懆ｨｼ荳蜈・喧縲々-User-Id 繝倥ャ繝繝ｼ霆｢騾・ｼ・|
| OpenAI 邨ｱ蜷・| **蜈ｱ譛・AI 繧ｯ繝ｩ繧､繧｢繝ｳ繝・*・・ars/shared-ai・・|
| 繝輔Ο繝ｳ繝医お繝ｳ繝臥憾諷狗ｮ｡逅・| **Zustand**・医げ繝ｭ繝ｼ繝舌Ν・・ **TanStack Query**・医し繝ｼ繝舌・繧ｹ繝・・繝茨ｼ・|
| 繝輔Ο繝ｳ繝医お繝ｳ繝峨さ繝ｳ繝昴・繝阪Φ繝・| **Feature-based**・・eatures/ 驟堺ｸ九↓讖溯・蜊倅ｽ搾ｼ・|

---

## 2. 繧ｷ繧ｹ繝・Β讒区・蝗ｳ

```
[繝悶Λ繧ｦ繧ｶ: React App・・ite・云
        |
        | HTTPS
        v
[Nginx API Gateway]
  JWT 讀懆ｨｼ・・uth0/Cognito JWKS・・
  繝ｫ繝ｼ繝・ぅ繝ｳ繧ｰ
        |
        +笏笏笏 /api/v1/users/        竊・auth-service:3001
        +笏笏笏 /api/v1/stress/       竊・stress-service:3002
        +笏笏笏 /api/v1/rewards/      竊・reward-service:3003
        +笏笏笏 /api/v1/finance/      竊・finance-service:3004
        +笏笏笏 /api/v1/notifications/竊・notification-service:3005
        +笏笏笏 /api/v1/dashboard/    竊・dashboard-service:3006


繧ｵ繝ｼ繝薙せ髢馴壻ｿ｡・・ars/shared-clients 邨檎罰縲？TTP 蜷梧悄・・

stress-service 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏竊・reward-service
                                              笏・
                             笏娯楳笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏､
                             笏・               笏・
                             v                v
                      finance-service  notification-service
                             
reward-service 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏竊・finance-service
reward-service 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏竊・notification-service
dashboard-service 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏竊・stress-service
dashboard-service 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏竊・reward-service
dashboard-service 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏竊・finance-service


蜈ｱ譛峨ヱ繝・こ繝ｼ繧ｸ・・ars/*・・

@ars/shared-types   竊・蜈ｨ繧ｵ繝ｼ繝薙せ繝ｻ繝輔Ο繝ｳ繝医お繝ｳ繝・
@ars/shared-clients 竊・stress / reward / finance / notification / dashboard service
@ars/shared-ai      竊・stress / reward / finance / notification / dashboard service
@ars/shared-config  竊・蜈ｨ繝舌ャ繧ｯ繧ｨ繝ｳ繝峨し繝ｼ繝薙せ


螟夜Κ繧ｵ繝ｼ繝薙せ:

Auth0/Cognito 竊・Nginx・・WT JWKS 讀懆ｨｼ・・
OpenAI API    竊・@ars/shared-ai 邨檎罰
Web Push/FCM  竊・notification-service
```

---

## 3. 繝ｪ繝昴ず繝医Μ讒区・

```
auto-reward-service/
笏懌楳笏 apps/
笏・  笏懌楳笏 auth-service/          # NestJS・・ostgreSQL・・
笏・  笏懌楳笏 stress-service/        # NestJS・・imescaleDB・・
笏・  笏懌楳笏 reward-service/        # NestJS・・ostgreSQL + Redis・・
笏・  笏懌楳笏 finance-service/       # NestJS・・ostgreSQL・・
笏・  笏懌楳笏 notification-service/  # NestJS・・ostgreSQL + Redis・・
笏・  笏懌楳笏 dashboard-service/     # NestJS・・lickHouse・・
笏・  笏披楳笏 web/                   # React + Vite・・ypeScript・・
笏懌楳笏 packages/
笏・  笏懌楳笏 shared-types/          # @ars/shared-types
笏・  笏懌楳笏 shared-clients/        # @ars/shared-clients
笏・  笏懌楳笏 shared-ai/             # @ars/shared-ai
笏・  笏披楳笏 shared-config/         # @ars/shared-config
笏懌楳笏 infrastructure/
笏・  笏懌楳笏 docker-compose.yml
笏・  笏披楳笏 nginx/
笏・      笏披楳笏 nginx.conf
笏懌楳笏 turbo.json
笏披楳笏 package.json
```

---

## 4. 繧ｵ繝ｼ繝薙せ繧ｵ繝槭Μ繝ｼ

| 繧ｵ繝ｼ繝薙せ | Unit | 繝昴・繝・| DB | 荳ｻ縺ｪ雋ｬ蜍・|
|---------|------|--------|----|---------| 
| auth-service | U1 | 3001 | PostgreSQL | 繝ｦ繝ｼ繧ｶ繝ｼ繝ｻ蝸懷･ｽ繝ｻ莠育ｮ励・騾夂衍險ｭ螳夂ｮ｡逅・|
| stress-service | U2 | 3002 | TimescaleDB | 繧ｹ繝医Ξ繧ｹ蜿朱寔繝ｻ繧ｹ繧ｳ繧｢繝ｪ繝ｳ繧ｰ繝ｻ髢ｾ蛟､蛻､螳壹・繝ｪ繝ｯ繝ｼ繝峨ヵ繝ｭ繝ｼ繝医Μ繧ｬ繝ｼ |
| reward-service | U4 | 3003 | PostgreSQL + Redis | 謠先｡育函謌舌・繧ｫ繧ｿ繝ｭ繧ｰ繝ｻ繝輔ぅ繝ｼ繝峨ヰ繝・け繝ｻ繝ｪ繝ｯ繝ｼ繝峨ヵ繝ｭ繝ｼ繧ｪ繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｿ繝ｼ |
| finance-service | U3 | 3004 | PostgreSQL | 蜿取髪邂｡逅・・菴呵｣暮｡咲ｮ怜・繝ｻCSV 繧､繝ｳ繝昴・繝・|
| notification-service | U5 | 3005 | PostgreSQL + Redis | 繝励ャ繧ｷ繝･騾夂衍逕滓・繝ｻ騾∽ｿ｡繝ｻ繧ｹ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ |
| dashboard-service | U7 | 3006 | ClickHouse | 繝・・繧ｿ髮・ｨ医・繧ｰ繝ｩ繝輔・AI 繧､繝ｳ繧ｵ繧､繝・|

---

## 5. 荳ｻ隕√が繝ｼ繧ｱ繧ｹ繝医Ξ繝ｼ繧ｷ繝ｧ繝ｳ繝輔Ο繝ｼ

### 繧ｹ繝医Ξ繧ｹ髢ｾ蛟､雜・℃ 竊・繝ｪ繝ｯ繝ｼ繝蛾夂衍

```
1. 繝ｦ繝ｼ繧ｶ繝ｼ縺後せ繝医Ξ繧ｹ繧貞・蜉・
2. stress-service: 繧ｹ繧ｳ繧｢邂怜・ 竊・髢ｾ蛟､繝√ぉ繝・け
3. [髢ｾ蛟､雜・℃] 竊・reward-service: generateProposals()
4. reward-service 竊・finance-service: getAvailableRewardBudget()
5. reward-service: RuleBasedEngine 縺ｧ謠先｡育函謌・
6. reward-service 竊・notification-service: sendRewardProposalNotification()
7. notification-service: LLM 縺ｧ繧ｳ繝斐・逕滓・ 竊・繧ｹ繝ｭ繝・ヨ繝ｪ繝ｳ繧ｰ繝√ぉ繝・け 竊・Push 騾∽ｿ｡
```

---

## 6. PBT・医・繝ｭ繝代ユ繧｣繝吶・繧ｹ繝・せ繝茨ｼ牙ｯｾ雎｡繧ｳ繝ｳ繝昴・繝阪Φ繝・

| 繧ｳ繝ｳ繝昴・繝阪Φ繝・| 繧ｵ繝ｼ繝薙せ | 蟇ｾ雎｡繝励Ο繝代ユ繧｣ |
|-------------|---------|--------------|
| `StressScoringService.calculateScore()` | stress-service | 繧ｹ繧ｳ繧｢縺悟ｸｸ縺ｫ 0縲・00 縺ｮ遽・峇蜀・・㍾縺ｿ縺ｮ蜷郁ｨ医′ 1.0 縺ｮ縺ｨ縺榊・蜉帛､牙喧縺ｫ蜊倩ｪｿ蠢懃ｭ・|
| `RuleBasedEngineService.filterByCriteria()` | reward-service | 繝輔ぅ繝ｫ繧ｿ邨先棡縺御ｽ呵｣暮｡阪・繧ｹ繝医Ξ繧ｹ繝ｬ繝吶Ν縺ｮ譚｡莉ｶ繧貞ｿ・★貅縺溘☆縲∫ｩｺ縺ｧ縺ｪ縺・・蜉帙↓蟇ｾ縺玲署譯医′霑斐ｋ |
| `AvailableBudgetService.calculateAvailableBudget()` | finance-service | 邨先棡縺悟ｸｸ縺ｫ 0 莉･荳翫〕imit 縺ｮ荳企剞繧定ｶ・∴縺ｪ縺・|

---

## 7. 繧ｻ繧ｭ繝･繝ｪ繝・ぅ險ｭ險医・繧､繝ｳ繝茨ｼ・ecurity Baseline・・

| 繝ｫ繝ｼ繝ｫ | 螳溯｣・婿驥・|
|--------|---------|
| SECURITY-01・域囓蜿ｷ蛹厄ｼ・| DB 謗･邯壹↓ TLS 蠢・医￣ostgreSQL / Redis / ClickHouse 證怜捷蛹冶ｨｭ螳・|
| SECURITY-02・医い繧ｯ繧ｻ繧ｹ繝ｭ繧ｰ・・| Nginx 繧｢繧ｯ繧ｻ繧ｹ繝ｭ繧ｰ繧・JSON 蠖｢蠑上〒蜃ｺ蜉帙√Ο繧ｰ髮・ｴ・|
| SECURITY-03・医い繝励Μ繝ｭ繧ｰ・・| 讒矩蛹悶Ο繧ｰ・・ars/shared-config/LoggerModule・峨￣II繝ｻ繝医・繧ｯ繝ｳ縺ｯ繝ｭ繧ｰ蜃ｺ蜉帷ｦ∵ｭ｢ |

---

## 8. 隧ｳ邏ｰ繝峨く繝･繝｡繝ｳ繝医∈縺ｮ蜿ら・

| 繝峨く繝･繝｡繝ｳ繝・| 繝代せ |
|------------|------|
| 繧ｳ繝ｳ繝昴・繝阪Φ繝亥ｮ夂ｾｩ | [components.md](./components.md) |
| 繝｡繧ｽ繝・ラ繧ｷ繧ｰ繝阪メ繝｣ | [component-methods.md](./component-methods.md) |
| 繧ｵ繝ｼ繝薙せ隧ｳ邏ｰ | [services.md](./services.md) |
| 萓晏ｭ倬未菫ゅ・繝医Μ繧ｯ繧ｹ | [component-dependency.md](./component-dependency.md) |
