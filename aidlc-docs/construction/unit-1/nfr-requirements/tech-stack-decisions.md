# テックスタック決定 — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**Unit**: Unit 1 — LINE Bot基盤

---

## 確定テックスタック

Unit 1 は Unit 0 で確立したスタックを継承し、以下の構成で実装する。

---

## 1. API エンドポイント

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **API Gateway 種別** | HTTP API v2 | Unit 0 設計で確定済み。REST API より低コスト・低レイテンシ |
| **エンドポイント** | `POST /webhook` | LINE Platform の Webhook URL として登録 |
| **認証方式** | なし（Lambda 内署名検証） | LINE Signature 検証で十分。API Gateway レベルの認証は不要 |
| **スロットリング** | 定常 100 req/s、バースト 200 req/s | ハッカソン規模の誤爆防止 |
| **CORS** | 不要 | LINE Platform は CORS 不使用。ブラウザから直接呼ばれない |

---

## 2. Lambda 関数

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **ランタイム** | python3.14 | Unit 0 Globals で設定済み |
| **アーキテクチャ** | x86_64 | Unit 0 Globals で設定済み |
| **メモリ** | 256 MB | Unit 2 以降の Bedrock 追加を見越して変更不要な値を採用 |
| **タイムアウト** | 10 秒 | PERF-05 より。LINE 応答 3 秒目標 + バッファ |
| **Handler** | `webhook_handler.handler` | `src/handlers/webhook_handler.py` 内の `handler` 関数 |
| **Lambda Layer** | `ArsCommonLayer` (Unit 0) | line-bot-sdk v3, aws-lambda-powertools, pydantic 等 |

---

## 3. セキュリティ・シークレット

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **チャネルシークレット** | Secrets Manager `ars/line` | Unit 0 SEC-02 で確定 |
| **アクセストークン** | Secrets Manager `ars/line` | 同上 |
| **IAM 権限（Unit 1 追加）** | `secretsmanager:GetSecretValue` (ars/line) | 最小権限原則。DynamoDB は Unit 2 で追加 |

---

## 4. 観測性・ロギング

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **ロガー** | aws-lambda-powertools `PIIMaskingLogger` | Unit 0 実装済み |
| **X-Ray** | 無効 | ハッカソン期間中は不要 |
| **ログ保持** | 30 日 | デバッグに十分 |
| **ログレベル** | INFO（環境変数） | Unit 0 Globals で設定済み |

---

## 5. ウォームアップ

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **ウォームアップ方式** | EventBridge Scheduler → Lambda invoke | Unit 0 PERF-03 で確定 |
| **スケジュール** | 5 分毎 | Unit 0 SCAL-03 で確定 |
| **Scheduler 名** | `WarmupWebhookScheduler` | Unit 0 SCAL-03 で確定 |
| **ペイロード** | `{"source": "warmup"}` | Unit 0 PERF-03 で確定 |

---

## 6. template.yaml 追加差分サマリー

Unit 1 で `template.yaml` に追加する SAM リソース:

| リソース名 | 種別 | 内容 |
|---------|------|------|
| `WebhookHandlerFunction` | `AWS::Serverless::Function` | Webhook ハンドラ Lambda |
| `WebhookApi` | `AWS::Serverless::HttpApi` | HTTP API v2 エンドポイント |
| `WarmupWebhookScheduler` | `AWS::Scheduler::Schedule` | 5 分毎ウォームアップ |

> ※ `WebhookHandlerFunction` の Policies には `ArsLambdaRole` ではなく SAM inline policy で `ars/line` への GetSecretValue 権限を付与する。
