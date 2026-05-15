# Unit of Work 萓晏ｭ倥・繝医Μ繧ｯ繧ｹ 窶・繧ｪ繝ｼ繝医Μ繝ｯ繝ｼ繝峨し繝ｼ繝薙せ

## 萓晏ｭ倥・繝医Μ繧ｯ繧ｹ

`笨・ = 萓晏ｭ倥≠繧奇ｼ亥ｮ溯｣・燕縺ｫ萓晏ｭ伜・縺悟ｿ・ｦ・ｼ・ 
`窶覗 = 萓晏ｭ倥↑縺・

窶ｻ Unit逡ｪ蜿ｷ縺ｯ隕∽ｻｶ螳夂ｾｩ譖ｸ縺ｮ Unit 逡ｪ蜿ｷ縺ｨ荳閾ｴ縺輔○縺ｦ縺・∪縺呻ｼ・4=Reward Service縲ゞ3=Finance Service縲ゞ7=Dashboard Service・峨・
螳溯｣・し繧､繧ｯ繝ｫ鬆・・縲梧耳螂ｨ螳溯｣・・ｺ上阪そ繧ｯ繧ｷ繝ｧ繝ｳ繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

| Unit | U0 蝓ｺ逶､ | U1 Auth | U2 Stress | U4 Reward | U3 Finance | U5 Notif | U7 Dashboard |
|------|--------|---------|----------|----------|-----------|---------|------------|
| **U0 蝓ｺ逶､** | 窶・| 窶・| 窶・| 窶・| 窶・| 窶・| 窶・|
| **U1 Auth** | 笨・| 窶・| 窶・| 窶・| 窶・| 窶・| 窶・|
| **U2 Stress** | 笨・| 笨・| 窶・| 笨・ｼ・lient・・| 窶・| 窶・| 窶・|
| **U4 Reward** | 笨・| 笨・| 笨・ｼ亥女菫｡蛛ｴ・・| 窶・| 笨・ｼ・lient・・| 笨・ｼ・lient・・| 窶・|
| **U3 Finance** | 笨・| 笨・| 窶・| 窶・| 窶・| 窶・| 窶・|
| **U5 Notif** | 笨・| 笨・| 窶・| 笨・ｼ亥女菫｡蛛ｴ・・| 窶・| 窶・| 窶・|
| **U7 Dashboard** | 笨・| 笨・| 笨・ｼ・lient・・| 笨・ｼ・lient・・| 笨・ｼ・lient・・| 窶・| 窶・|
| **Web** | 笨・ｼ・ypes・・| 笨・ｼ・PI・・| 笨・ｼ・PI・・| 笨・ｼ・PI・・| 笨・ｼ・PI・・| 笨・ｼ・PI・・| 笨・ｼ・PI・・|

---

## 螳溯｣・・ｺ上げ繝ｩ繝・

```
Unit 0・亥渕逶､・・
    笏・
    笏懌楳笏笆ｺ Unit 1・・uth Service・・
    笏・        笏・
    笏・   笏娯楳笏笏笏笏､
    笏・   笏・   笏・
    笏・   笆ｼ    笆ｼ
    笏懌楳笏笆ｺ Unit 2・・tress Service・俄楳笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏・
    笏・             笏・                                      笏・
    笏・             笏・RewardClient 蜻ｼ縺ｳ蜃ｺ縺・                 笏・
    笏・             笆ｼ                                       笏・
    笏懌楳笏笆ｺ Unit 3・・eward Service・俄淀笏笏 FinanceClient 笏笏笏笏笏笏笏笏､
    笏・             笏・                                      笏・
    笏・             笏・NotificationClient 蜻ｼ縺ｳ蜃ｺ縺・           笏・
    笏・             笆ｼ                                       笏・
    笏懌楳笏笆ｺ Unit 5・・otification Service・・                   笏・
    笏・                                                     笏・
    笏懌楳笏笆ｺ Unit 4・・inance Service・俄楳笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏・
    笏・
    笏披楳笏笆ｺ Unit 6・・ashboard Service・・
              笏・蜈ｨ Client 萓晏ｭ・
              笆ｼ
         ・亥・ Unit 螳御ｺ・ｾ後↓螳溯｣・耳螂ｨ・・

Unit 7・・eb Frontend・・
    笏披楳笏 蜈ｨ繝舌ャ繧ｯ繧ｨ繝ｳ繝・Unit 螳御ｺ・ｾ鯉ｼ医∪縺溘・荳ｦ陦後＠縺ｦ API 繝｢繝・け縺ｧ髢狗匱・・
```

---

## 謗ｨ螂ｨ螳溯｣・・ｺ・

```
[1] Unit 0  窶・蝓ｺ逶､・・urborepo + 蜈ｱ譛峨ヱ繝・こ繝ｼ繧ｸ + Docker Compose 鬪ｨ譬ｼ・・
[2] Unit 1  窶・Auth Service
[3] Unit 2  窶・Stress Service・・ewardClient 縺ｯ繧ｹ繧ｿ繝門他縺ｳ蜃ｺ縺暦ｼ・
[4] Unit 3  窶・Reward Service・・inanceClient, NotifClient 縺ｯ繧ｹ繧ｿ繝門他縺ｳ蜃ｺ縺暦ｼ・
[5] Unit 4  窶・Finance Service・・inanceClient 縺ｮ螳溯｣・ｒ螳梧・・・
[6] Unit 5  窶・Notification Service・・otifClient 縺ｮ螳溯｣・ｒ螳梧・・・
[7] Unit 6  窶・Dashboard Service
[8] Unit 7  窶・Web Frontend・医ヰ繝・け繧ｨ繝ｳ繝牙ｮ梧・蠕・or MSW 繝｢繝・け荳ｦ陦碁幕逋ｺ・・
```

---

## shared-clients 螳溯｣・せ繧ｱ繧ｸ繝･繝ｼ繝ｫ

| Client | 繧ｹ繧ｿ繝紋ｽ懈・ | 螳溯｣・ｮ梧・ |
|--------|----------|---------|
| `RewardClient` | Unit 0 | Unit 3・医せ繝ｩ繧､繧ｹ 3-8・・|
| `FinanceClient` | Unit 0 | Unit 4・医せ繝ｩ繧､繧ｹ 4-9・・|
| `NotificationClient` | Unit 0 | Unit 5・医せ繝ｩ繧､繧ｹ 5-8・・|
| `StressClient` | Unit 0 | Unit 7 Dashboard Service・医せ繝ｩ繧､繧ｹ 6-1 蜀・〒蜈・ｮ滂ｼ・|
| `DashboardClient` | Unit 0 | Unit 6・亥ｿ・ｦ√↓蠢懊§縺ｦ・・|

---

## 繝悶Ο繝・く繝ｳ繧ｰ萓晏ｭ假ｼ亥ｮ溯｣・幕蟋九・蜑肴署・・

| 螳溯｣・・| 繧ｵ繝ｼ繝薙せ | 髢句ｧ句燕縺ｫ蠢・ｦ√↑縺薙→ |
|--------|---------|------------------|
| 隨ｬ1 | U1 Auth Service | Unit 0 螳御ｺ・|
| 隨ｬ2 | U2 Stress Service | Unit 0 螳御ｺ・ U1 Auth 縺ｮ users 繝・・繝悶Ν縺悟ｭ伜惠縺吶ｋ |
| 隨ｬ3 | U4 Reward Service | Unit 0 螳御ｺ・ U1 Auth 螳御ｺ・ｼ遺ｻStress Service縺ｯ蜻ｼ縺ｳ蜃ｺ縺怜・縺ｪ縺ｮ縺ｧ螳御ｺ・ｸ崎ｦ√３ewardClient繧ｹ繧ｿ繝悶′螳夂ｾｩ貂医∩縺ｧ縺ゅｌ縺ｰ髢句ｧ句庄閭ｽ・・|
| 隨ｬ4 | U3 Finance Service | Unit 0 螳御ｺ・ U1 Auth 螳御ｺ・|
| 隨ｬ5 | U5 Notification Service | Unit 0 螳御ｺ・ U1 Auth 螳御ｺ・ U4 Reward 縺ｮ RewardProposalDto 縺檎｢ｺ螳壹＠縺ｦ縺・ｋ |
| 隨ｬ6 | U7 Dashboard Service | Unit 0 螳御ｺ・ U1 Auth 螳御ｺ・ U2縲弑5 縺ｮ API 縺悟虚菴懊☆繧・|
| 隨ｬ7 | Web Frontend | Unit 0 縺ｮ shared-types 縺檎｢ｺ螳壹＠縺ｦ縺・ｋ・・SW 縺ｧ荳ｦ陦碁幕逋ｺ蜿ｯ・・|
