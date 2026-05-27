## Unit 4 Infrastructure Design Plan

- [x] 既存 template.yaml の精査（Unit 0/1/2 定義済みリソース確認）
- [x] Unit 4 新規インフラリソースの特定
  - [x] 新規 Lambda: RewardPoolUpdaterFunction (300秒タイムアウト、256MB)
  - [x] 新規 EventBridge Scheduler: RewardPoolScheduler (cron UTC 17:00)
  - [x] SchedulerExecutionRole 更新: RewardPoolUpdaterFunction への InvokeFunction 権限追加
  - [x] CloudWatch Logs: RewardPoolUpdaterFunctionLogGroup (30日保持)
  - [x] 環境変数追加: RAKUTEN_DEFAULT_KEYWORDS, RAKUTEN_MAX_ITEMS_PER_POOL, RAKUTEN_HITS_PER_KEYWORD
  - [x] IAM 権限追加: なし（ArsLambdaRole の既存権限で賄える。ArsSecretsManagerPolicy に ars/rakuten* は既に含まれている）
- [x] template.yaml 差分の確定
- [x] infrastructure-design.md 生成
- [x] deployment-architecture.md 生成
