## Unit 4 NFR Design Plan

- [x] Unit 4 NFR Requirements 成果物確認（nfr-requirements.md / tech-stack-decisions.md）
- [x] 適用NFRデザインパターン特定
  - [x] Retry with Exponential Backoff（楽天API失敗時）
  - [x] Module-Level Cache（Secrets Manager AppID）
  - [x] Rate Limiter（楽天API 1req/秒制限）
  - [x] Fail-Safe Default（楽天API全失敗時の既存プール維持）
  - [x] Circuit Breaker 不要（バッチはユーザー単位でスキップで十分）
- [x] 論理コンポーネント設計
  - [x] RewardPoolUpdaterFunction（新規Lambda）
  - [x] rakuten_service（HTTP クライアント + リトライ）
  - [x] reward_pool_service（スコアリング + 差分マージ）
  - [x] EventBridge Scheduler（RewardPoolScheduler）
- [x] nfr-design-patterns.md 生成
- [x] logical-components.md 生成
