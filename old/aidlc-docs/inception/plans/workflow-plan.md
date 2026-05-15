# 繝ｯ繝ｼ繧ｯ繝輔Ο繝ｼ螳溯｡瑚ｨ育判 窶・繧ｪ繝ｼ繝医Μ繝ｯ繝ｼ繝峨し繝ｼ繝薙せ

**菴懈・譌･**: 2026-05-08  
**繝励Ο繧ｸ繧ｧ繧ｯ繝医ち繧､繝・*: Greenfield  
**隍・尅蠎ｦ**: Complex・・ Unit縲√・繧､繧ｯ繝ｭ繧ｵ繝ｼ繝薙せ縲、I 騾｣謳ｺ・・

---

## 繧ｹ繧ｳ繝ｼ繝励・蠖ｱ髻ｿ蛻・梵

### 螟画峩蠖ｱ髻ｿ遽・峇

| 蠖ｱ髻ｿ鬆伜沺 | 隧ｳ邏ｰ |
|----------|------|
| 繝ｦ繝ｼ繧ｶ繝ｼ蠖ｱ髻ｿ | 繧ｨ繝ｳ繝峨Θ繝ｼ繧ｶ繝ｼ蜷代￠譁ｰ隕上し繝ｼ繝薙せ蜈ｨ菴・|
| 繧｢繝ｼ繧ｭ繝・け繝√Ε蠖ｱ髻ｿ | 繝槭う繧ｯ繝ｭ繧ｵ繝ｼ繝薙せ・・ 繧ｵ繝ｼ繝薙せ・・ React 繝輔Ο繝ｳ繝医お繝ｳ繝・|
| 繝・・繧ｿ繝｢繝・Ν蠖ｱ髻ｿ | PostgreSQL / TimescaleDB / Redis / ClickHouse |
| API 蠖ｱ髻ｿ | 譁ｰ隕・REST API・亥・ Unit・・|
| NFR 蠖ｱ髻ｿ | 繧ｻ繧ｭ繝･繝ｪ繝・ぅ・亥ｿ・茨ｼ峨・繝代ヵ繧ｩ繝ｼ繝槭Φ繧ｹ繝ｻ繝・せ繝域姶逡･ |

### 繝ｪ繧ｹ繧ｯ隧穂ｾ｡

| 繝ｪ繧ｹ繧ｯ | 繝ｬ繝吶Ν | 逅・罰 |
|--------|--------|------|
| 邱丞粋繝ｪ繧ｹ繧ｯ | **High** | 6 繧ｵ繝ｼ繝薙せ譁ｰ隕乗ｧ狗ｯ峨´LM 騾｣謳ｺ縲、uth 繝槭ロ繝ｼ繧ｸ繝峨し繝ｼ繝薙せ縲；rowth 諡｡蠑ｵ諤ｧ險ｭ險医′蠢・ｦ・|
| 謚陦鍋噪荳咲｢ｺ螳滓ｧ | Medium | NestJS + TypeScript 邨ｱ荳讒区・縺ｯ讓呎ｺ也噪縺縺後ゝimescaleDB / ClickHouse 縺ｯ蟆る摩諤ｧ縺悟ｿ・ｦ・|
| 繧ｹ繧ｳ繝ｼ繝励Μ繧ｹ繧ｯ | Medium | MVP 縺ｫ邨槭▲縺溘′縲；rowth 隕区紺縺医・險ｭ險亥愛譁ｭ縺瑚､・尅 |

---

## 螳溯｡後ヵ繧ｧ繝ｼ繧ｺ蛻､螳・

### INCEPTION PHASE

| 繧ｹ繝・・繧ｸ | 螳溯｡悟愛螳・| 逅・罰 |
|----------|----------|------|
| Workspace Detection | 笨・螳御ｺ・| 窶・|
| Reverse Engineering | 竢ｭ・・繧ｹ繧ｭ繝・・ | Greenfield 縺ｮ縺溘ａ荳崎ｦ・|
| Requirements Analysis | 笨・螳御ｺ・| 窶・|
| **User Stories** | 竢ｭ・・繧ｹ繧ｭ繝・・ | `隕∽ｻｶ螳夂ｾｩ譖ｸ.md` ﾂｧ9 縺ｫ US-01縲弑S-13 縺悟ｮ悟・螳夂ｾｩ貂医∩縲よ眠隕丈ｽ懈・荳崎ｦ・|
| **Workflow Planning** | 笨・螳溯｡御ｸｭ | 蟶ｸ縺ｫ螳溯｡・|
| **Application Design** | 笨・螳溯｡後☆繧・| 6 繧ｵ繝ｼ繝薙せ ﾃ・繧ｳ繝ｳ繝昴・繝阪Φ繝郁ｨｭ險医′蠢・ｦ・|
| **Units Generation** | 笨・螳溯｡後☆繧・| 7 Unit 縺ｮ蛻・ｧ｣繝ｻ萓晏ｭ倬未菫ゅ・繧ｹ繝医・繝ｪ繝ｼ繝槭ャ繝励′蠢・ｦ・|

### CONSTRUCTION PHASE・・nit 縺斐→縺ｫ繝ｫ繝ｼ繝暦ｼ・

螳溯｣・・ｺ上・隕∽ｻｶ遒ｺ隱阪・蝗樒ｭ費ｼ・2=C縲後さ繧｢繝舌Μ繝･繝ｼ蜆ｪ蜈医搾ｼ峨↓蠕薙＞莉･荳九・鬆・→縺吶ｋ・・

| 鬆・ｺ・| Unit | 繧ｵ繝ｼ繝薙せ蜷・| 險ｭ險医せ繝・・繧ｸ |
|------|------|----------|------------|
| 1 | U1 | Auth Service | Functional Design + NFR Design + Infrastructure Design + Code Generation |
| 2 | U2 | Stress Service | Functional Design + NFR Design + Infrastructure Design + Code Generation |
| 3 | U4 | Reward Service | Functional Design + NFR Design + Infrastructure Design + Code Generation |
| 4 | U3 | Finance Service | Functional Design + NFR Design + Infrastructure Design + Code Generation |
| 5 | U5 | Notification Service | Functional Design + NFR Design + Code Generation |
| 6 | U7 | Dashboard Service | Functional Design + NFR Design + Code Generation |

> **豕ｨ**: U1・・uth Service・峨・ U2/U4 縺ｮ萓晏ｭ伜燕謠舌・縺溘ａ譛蛻昴↓螳溯｣・☆繧・

### NFR 險ｭ險医・驕ｩ逕ｨ

| NFR | 驕ｩ逕ｨ蟇ｾ雎｡ | 蛻､螳・|
|-----|----------|------|
| 繧ｻ繧ｭ繝･繝ｪ繝・ぅ・・ecurity Baseline・・| 蜈ｨ Unit | 笨・蠢・茨ｼ亥・繝ｫ繝ｼ繝ｫ・・|
| 繝代ヵ繧ｩ繝ｼ繝槭Φ繧ｹ・・95 < 500ms・・| 蜈ｨ API | 笨・蜷・Unit 縺ｮ NFR Design 縺ｧ螳夂ｾｩ |
| 繝・せ繝茨ｼ・nit + 邨ｱ蜷医ユ繧ｹ繝茨ｼ・| 蜈ｨ Unit | 笨・Code Generation 縺ｫ蜷ｫ繧√ｋ |
| PBT・・artial 繝｢繝ｼ繝会ｼ・| U2繝ｻU3繝ｻU4 縺ｮ邏皮ｲ矩未謨ｰ | 笨・蟇ｾ雎｡ Unit 縺ｮ Functional Design 縺ｧ迚ｹ螳・|

### 繧､繝ｳ繝輔Λ險ｭ險医・驕ｩ逕ｨ

| 繧ｹ繝・・繧ｸ | 蛻､螳・| 蜀・ｮｹ |
|----------|------|------|
| Infrastructure Design・・ocker Compose・・| 笨・螳溯｡後☆繧・| 繝ｭ繝ｼ繧ｫ繝ｫ髢狗匱迺ｰ蠅・・ Docker Compose 險ｭ險茨ｼ亥・繧ｵ繝ｼ繝薙せ邨ｱ蜷茨ｼ・|
| Infrastructure Design・・loud・・| 竢ｭ・・蟆・擂 | 繝ｭ繝ｼ繧ｫ繝ｫ蜍穂ｽ懷ｾ後↓繧ｯ繝ｩ繧ｦ繝臥ｧｻ陦鯉ｼ域悽險育判螟厄ｼ・|

---

## 謌先棡迚ｩ荳隕ｧ

### INCEPTION 繝輔ぉ繝ｼ繧ｺ謌先棡迚ｩ

```
aidlc-docs/
笏懌楳笏 aidlc-state.md
笏懌楳笏 audit.md
笏披楳笏 inception/
    笏懌楳笏 requirements/
    笏・  笏懌楳笏 requirement-verification-questions.md 笨・
    笏・  笏披楳笏 requirements.md 笨・
    笏懌楳笏 plans/
    笏・  笏懌楳笏 workflow-plan.md・域悽繝輔ぃ繧､繝ｫ・俄怛
    笏・  笏懌楳笏 application-design-plan.md・域ｬ｡繧ｹ繝・ャ繝励〒菴懈・・・
    笏・  笏披楳笏 unit-of-work-plan.md・・nits Generation 縺ｧ菴懈・・・
    笏披楳笏 application-design/
        笏懌楳笏 components.md
        笏懌楳笏 component-methods.md
        笏懌楳笏 services.md
        笏懌楳笏 component-dependency.md
        笏懌楳笏 application-design.md
        笏懌楳笏 unit-of-work.md
        笏懌楳笏 unit-of-work-dependency.md
        笏披楳笏 unit-of-work-story-map.md
```

### CONSTRUCTION 繝輔ぉ繝ｼ繧ｺ謌先棡迚ｩ・・nit 縺斐→・・

```
aidlc-docs/construction/
笏披楳笏 {unit-name}/
    笏懌楳笏 functional-design.md
    笏懌楳笏 nfr-requirements.md
    笏懌楳笏 nfr-design.md
    笏披楳笏 infrastructure-design.md

{project-root}/
笏懌楳笏 docker-compose.yml
笏懌楳笏 apps/
笏・  笏懌楳笏 auth-service/
笏・  笏懌楳笏 stress-service/
笏・  笏懌楳笏 reward-service/
笏・  笏懌楳笏 finance-service/
笏・  笏懌楳笏 notification-service/
笏・  笏披楳笏 dashboard-service/
笏披楳笏 frontend/
    笏披楳笏 web/
```

---

## 谺｡縺ｮ繧ｹ繝・ャ繝・

1. **Application Design** 窶・繧ｳ繝ｳ繝昴・繝阪Φ繝医・繧ｵ繝ｼ繝薙せ繝ｻ萓晏ｭ倬未菫ゅ・險ｭ險・
2. **Units Generation** 窶・Unit 蠅・阜繝ｻ萓晏ｭ倥・繝医Μ繧ｯ繧ｹ繝ｻ繧ｹ繝医・繝ｪ繝ｼ繝槭ャ繝励・逕滓・
3. **Construction Phase・・1 縺九ｉ鬆・ｬ｡・・* 窶・險ｭ險・竊・繧ｳ繝ｼ繝臥函謌・竊・繝・せ繝・
