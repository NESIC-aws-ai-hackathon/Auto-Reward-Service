# Deployment Architecture — Unit 4: ご褒美候補プール

**作成日**: 2026-05-16

---

## デプロイアーキテクチャ概要

```
AWS Cloud (ap-northeast-1)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  EventBridge Scheduler (RewardPoolScheduler)                │
│  cron(0 17 * * ? *)  →  JST 02:00 毎日                      │
│         │                                                   │
│         ▼                                                   │
│  Lambda: RewardPoolUpdaterFunction                          │
│  - Runtime: python3.13                                      │
│  - Memory: 256MB                                            │
│  - Timeout: 300秒                                           │
│  - Layer: ArsCommonLayer                                    │
│         │                                                   │
│    ┌────┤                                                   │
│    │    │                                                   │
│    ▼    ▼                                                   │
│  DynamoDB (ArsTable)   Secrets Manager (ars/rakuten)        │
│  - PROFILE# (Read)     - RAKUTEN_APP_ID (Read, キャッシュ)  │
│  - PREF_MEMORY# (R)                                         │
│  - REWARD_POOL# (R/W)                                       │
│    │                                                        │
│    ▼                                                        │
│  External: Rakuten Web Service API                          │
│  (HTTPS: app.rakuten.co.jp)                                 │
│  Rate Limit: 1 req/sec                                      │
│                                                             │
│  CloudWatch Logs: /aws/lambda/RewardPoolUpdaterFunction     │
│  - PoolUpdateResult（バッチ完了サマリー）                    │
│  - ERROR/WARNING ログ（楽天API失敗）                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## デプロイラウンド

Unit 4 は **デプロイラウンド 4（Unit 0〜5 まとめて）** でデプロイする。  
（AGENTS.md: U0〜U5 まとめてデプロイ → E2E チェーン確認）

| ラウンド | 対象 | Unit 4 での確認内容 |
|---------|------|-----------------|
| Round 4 | U0〜U5 | EventBridge 手動実行 → `PoolUpdateResult` ログ確認 → DynamoDB に REWARD_POOL# 生成確認 |

---

## Unit 4 デプロイ後の動作確認手順

1. **AWS コンソール → EventBridge Scheduler → RewardPoolScheduler → 「Test」実行**
2. **CloudWatch Logs → /aws/lambda/RewardPoolUpdaterFunction** で以下を確認:
   - `pool_update_complete` ログに `success_count > 0` が出力されること
3. **DynamoDB → ArsTable → アイテムエクスプローラ** で `SK = REWARD_POOL#` のアイテムが生成されていること
4. `items` 配列に楽天API由来の商品が含まれていること

---

## Outputs 追加

```yaml
Outputs:
  RewardPoolUpdaterFunctionArn:
    Description: Reward pool batch updater Lambda ARN
    Value: !GetAtt RewardPoolUpdaterFunction.Arn
```
