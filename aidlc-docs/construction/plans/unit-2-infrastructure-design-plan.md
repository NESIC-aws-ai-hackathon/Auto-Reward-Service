## Unit 2 Infrastructure Design Plan

- [x] 既存 template.yaml の精査（Unit 0/1 定義済みリソース確認）
- [x] Unit 2 新規インフラリソースの特定
  - [x] 新規 Lambda: なし（WebhookHandlerFunction に統合）
  - [x] 新規 API Gateway: なし（WebhookApi 継続）
  - [x] IAM 権限追加: Bedrock / DynamoDB は Unit 0 で既に定義済み → 追加なし
  - [x] 環境変数追加: `DAILY_CHAT_LIMIT` のみ
- [x] template.yaml 差分の確定（Globals への環境変数追加 1 件のみ）
- [x] infrastructure-design.md 生成
- [x] deployment-architecture.md 生成
