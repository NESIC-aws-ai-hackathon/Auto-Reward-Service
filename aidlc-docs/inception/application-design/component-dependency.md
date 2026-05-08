# コンポーネント依存関係 — オートリワードサービス

## 依存マトリクス

凡例: **呼び出す（→）** / **依存なし（—）**

| 呼び出し元 ↓ / 呼び出し先 → | auth | stress | reward | finance | notification | dashboard | shared-clients | shared-ai | shared-types | shared-config |
|---|---|---|---|---|---|---|---|---|---|---|
| **auth-service** | — | — | — | — | — | — | — | — | ✅ | ✅ |
| **stress-service** | — | — | ✅ RewardClient | — | — | — | ✅ | ✅ TextSentiment | ✅ | ✅ |
| **reward-service** | — | — | — | ✅ FinanceClient | ✅ NotificationClient | — | ✅ | ✅ AiPersonalize（将来） | ✅ | ✅ |
| **finance-service** | — | — | — | — | — | — | — | ✅ CategoryClassifier | ✅ | ✅ |
| **notification-service** | — | — | — | — | — | — | — | ✅ CopyGenerator | ✅ | ✅ |
| **dashboard-service** | — | ✅ StressClient | ✅ RewardClient | ✅ FinanceClient | — | — | ✅ | ✅ InsightReport | ✅ | ✅ |
| **web（frontend）** | — | — | — | — | — | — | — | — | ✅ | — |
| **nginx（API GW）** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — |

---

## サービス間通信フロー

### フロー 1：ストレス登録 → リワード提案 → 通知（メインフロー）

```
[Web フロントエンド]
    |
    | POST /api/v1/stress/entries
    v
[Nginx API Gateway]  ← JWT 検証（Auth0/Cognito JWKS）
    |
    | X-User-Id ヘッダー付きでルーティング
    v
[stress-service]
    | StressEntryService.createEntry()
    | → StressScoringService.calculateScore()
    | → StressThresholdService.checkAndTrigger()
    |       ↓ 閾値超過時のみ
    |   RewardClient.triggerProposalGeneration()
    |       |
    v       v
[reward-service]
    | ProposalService.generateProposals()
    | → FinanceClient.getAvailableRewardBudget()
    |       |
    |       v
    |   [finance-service]
    |   AvailableBudgetService.calculateAvailableBudget()
    |       |
    |   (余裕額を返す)
    |       |
    | ← 余裕額受信
    | → RuleBasedEngineService.filterByCriteria()
    | → ProposalRepository.save(proposals)
    | → NotificationClient.sendRewardProposalNotification()
    |       |
    v       v
[notification-service]
    | NotificationService.sendRewardProposalNotification()
    | → ThrottleService.canSend()          ← Redis
    | → NotificationCopyGenerator.generate() ← OpenAI API
    | → DeviceTokenService.getTokens()
    | → Web Push API / FCM
    | → NotificationRepository.save(log)
    | → ThrottleService.recordSent()       ← Redis
```

### フロー 2：リワード採用 → 支出自動記録

```
[Web フロントエンド]
    |
    | POST /api/v1/rewards/proposals/:id/feedback  { action: "ACCEPT" }
    v
[Nginx API Gateway]
    |
    v
[reward-service]
    | FeedbackService.recordFeedback()
    | → FeedbackRepository.save()
    | → FinanceClient.recordRewardSpending()  ← 採用時のみ
    |       |
    v       v
[finance-service]
    | TransactionService.addTransaction()
    | → TransactionRepository.save()
```

### フロー 3：ダッシュボード表示

```
[Web フロントエンド]
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
    | StressTrendService    → StressClient  → [stress-service]
    | RewardHistoryService  → RewardClient  → [reward-service]
    | FinanceSummaryService → FinanceClient → [finance-service]
    | InsightService        → InsightReportGenerator ← OpenAI API
```

---

## 外部依存関係

| 外部サービス | 利用サービス | 用途 |
|------------|------------|------|
| Auth0 / AWS Cognito | Nginx（API Gateway） | JWT 発行・JWKS 提供 |
| OpenAI API（GPT-4o） | shared-ai | テキスト感情分析・通知コピー・インサイト・カテゴリ分類 |
| Web Push API | notification-service | Web ブラウザへのプッシュ通知 |
| FCM（Firebase Cloud Messaging） | notification-service | Android / PWA へのプッシュ通知（将来） |

---

## インフラ依存関係（Docker Compose）

```
postgres-auth      ← auth-service
timescaledb        ← stress-service
postgres-reward    ← reward-service
redis              ← reward-service（キャッシュ）、notification-service（スロットリング）
postgres-finance   ← finance-service
postgres-notif     ← notification-service
clickhouse         ← dashboard-service
```

---

## 依存関係ルール

1. **フロントエンド → Nginx のみ**: Web フロントエンドはバックエンドサービスを直接呼び出さない
2. **サービス間は shared-clients 経由**: サービス間の HTTP 呼び出しは必ず @ars/shared-clients のクライアントクラスを使用する
3. **OpenAI は shared-ai 経由のみ**: 各サービスが OpenAI SDK を直接 import しない
4. **auth-service は他サービスを呼び出さない**: ユーザー管理サービスは依存の末端
5. **循環依存禁止**: サービス間の循環参照（A→B→A）は設計上起こさない
