# Infrastructure Design — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16  
**バージョン**: 1.0  
**ステータス**: レビュー待ち

---

## 1. インフラ決定事項サマリー

| 項目 | 決定値 | 根拠 |
|-----|--------|------|
| AWS リージョン | ap-northeast-1 | 要件定義書 §2 |
| VPC 配置 | VPC 外（デフォルト） | Cold Start 最小・MVP コスト最小 |
| S3 バケット | SAM 自動作成（`--resolve-s3`） | ハッカソン用途・運用コスト最小 |
| CloudWatch アラーム | なし（ログ目視確認） | ハッカソン用途 |
| 環境分離 | なし（prod のみ） | ハッカソン用途 |
| SAM スタック名 | `auto-reward-service` | — |

---

## 2. DynamoDB 設計

### 2.1 テーブル設定

| パラメータ | 値 |
|-----------|---|
| テーブル名 | `ArsTable` |
| 課金モード | PAY_PER_REQUEST（オンデマンド） |
| パーティションキー | `PK` (String) |
| ソートキー | `SK` (String) |
| サーバーサイド暗号化 | 有効（AWS マネージドキー） |
| PITR | 有効 |
| TTL 属性名 | `ttl` |

### 2.2 GSI 設計

| GSI 名 | GSI PK | GSI SK | 投影 | 対象エンティティ |
|--------|--------|--------|------|----------------|
| `entityType-index` | `entityType` (String) | `PK` (String) | ALL | PREF_MEMORY#, PROFILE# |

### 2.3 SAM リソース定義（抜粋）

```yaml
ArsTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: ArsTable
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - AttributeName: PK
        AttributeType: S
      - AttributeName: SK
        AttributeType: S
      - AttributeName: entityType
        AttributeType: S
    KeySchema:
      - AttributeName: PK
        KeyType: HASH
      - AttributeName: SK
        KeyType: RANGE
    GlobalSecondaryIndexes:
      - IndexName: entityType-index
        KeySchema:
          - AttributeName: entityType
            KeyType: HASH
          - AttributeName: PK
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
    SSESpecification:
      SSEEnabled: true
    PointInTimeRecoverySpecification:
      PointInTimeRecoveryEnabled: true
    TimeToLiveSpecification:
      AttributeName: ttl
      Enabled: true
    Tags:
      - Key: Project
        Value: auto-reward-service
      - Key: Stage
        Value: prod
```

---

## 3. Lambda Layer 設計

### 3.1 ArsCommonLayer 構成

| パラメータ | 値 |
|-----------|---|
| レイヤー名 | `ArsCommonLayer` |
| 対応ランタイム | `python3.14` |
| 格納パス | `src/` 以下の `services/`, `utils/`, `models/` |
| handlers | Layer に含めない（各 Lambda に直接配置） |
| boto3 / botocore | Layer に含めない（Lambda ランタイム組み込み） |

### 3.2 レイヤーディレクトリ構造

```
layer/
  python/
    services/
      __init__.py
      dynamodb_service.py
      bedrock_service.py
      line_service.py
      google_calendar_service.py
    utils/
      __init__.py
      secrets.py
      logger.py
      exceptions.py
    models/
      __init__.py
      schemas.py
```

### 3.3 SAM リソース定義（抜粋）

```yaml
ArsCommonLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: ArsCommonLayer
    ContentUri: layer/
    CompatibleRuntimes:
      - python3.14
    RetentionPolicy: Retain
  Metadata:
    BuildMethod: python3.14
```

---

## 4. Lambda 関数設定（全関数共通指針）

### 4.1 Globals 定義

```yaml
Globals:
  Function:
    Runtime: python3.14
    Architectures:
      - x86_64
    Environment:
      Variables:
        TABLE_NAME: !Ref ArsTable
        LINE_SECRET_NAME: ars/line
        GOOGLE_SECRET_NAME: ars/google
        RAKUTEN_SECRET_NAME: ars/rakuten
        LOG_LEVEL: INFO
        BEDROCK_TEXT_MODEL_ID: "amazon.nova-micro-v1:0"
        BEDROCK_IMAGE_MODEL_ID: "amazon.nova-lite-v1:0"
        BEDROCK_FALLBACK_MODEL_ID: "anthropic.claude-3-haiku-20240307-v1:0"
    Layers:
      - !Ref ArsCommonLayer
    Tracing: PassThrough
    Tags:
      Project: auto-reward-service
      Stage: prod
```

### 4.2 Lambda 関数別設定

| 関数名 | メモリ | タイムアウト | 用途 |
|--------|--------|-------------|------|
| WebhookHandler | 128 MB | 10 s | LINE Webhook 受信 |
| CharacterReply | 256 MB | 30 s | Bedrock テキスト生成 |
| ImageAnalysis | 512 MB | 60 s | Bedrock 画像解析 |
| BatchProcessor | 256 MB | 300 s | 日次バッチ処理 |
| LiffApi | 256 MB | 30 s | LIFF API エンドポイント |

### 4.3 Lambda 実行ロール権限（最小権限）

各 Lambda 関数の実行ロールに付与するポリシー：

| AWSサービス | アクション |
|------------|-----------|
| DynamoDB | `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:DeleteItem`, `dynamodb:Query`, `dynamodb:BatchWriteItem` |
| Bedrock | `bedrock:InvokeModel` |
| Secrets Manager | `secretsmanager:GetSecretValue`（ars/line, ars/google, ars/rakuten のみ） |
| CloudWatch Logs | `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` |

---

## 5. Secrets Manager 設計

### 5.1 シークレット構成

| シークレット名 | 格納キー | 参照 Lambda 環境変数 |
|--------------|---------|-------------------|
| `ars/line` | `LINE_CHANNEL_SECRET`, `LINE_ACCESS_TOKEN` | `LINE_SECRET_NAME` |
| `ars/google` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | `GOOGLE_SECRET_NAME` |
| `ars/rakuten` | `RAKUTEN_APP_ID` | `RAKUTEN_SECRET_NAME` |

### 5.2 アクセスパターン

- 初回呼び出し（コールドスタート時）に `GetSecretValue` を実行し、モジュールレベルでキャッシュ
- シークレットローテーション対応: MVP では未設定（手動更新）

---

## 6. API Gateway 設計

### 6.1 設定

| パラメータ | 値 |
|-----------|---|
| タイプ | HTTP API（API Gateway v2） |
| エンドポイント | `/webhook`（POST）/ `/liff/api/{proxy+}`（GET/POST） |
| 認証 | LINE 署名検証（Lambda 側で実装） |
| CORS | LIFF ドメインのみ許可 |
| スロットリング | デフォルト（バースト: 5000 req/s） |

---

## 7. EventBridge Scheduler 設計（ウォームアップ）

### 7.1 スケジュール設定

| スケジュール名 | 対象関数 | 実行間隔 | ペイロード |
|--------------|---------|---------|---------|
| `WarmupWebhook` | WebhookHandler | rate(5 minutes) | `{"source": "warmup"}` |
| `WarmupCharacterReply` | CharacterReply | rate(5 minutes) | `{"source": "warmup"}` |

### 7.2 SAM リソース定義（抜粋）

```yaml
# WebhookHandler の Events セクションに追記
WarmupSchedule:
  Type: Schedule
  Properties:
    Schedule: rate(5 minutes)
    Input: '{"source": "warmup"}'
    Enabled: true
```

---

## 8. CloudWatch Logs 設計

### 8.1 ログ設定

| 設定項目 | 値 |
|---------|---|
| 保持期間 | 30日（全 Lambda 関数） |
| 形式 | JSON 構造化ログ（aws-lambda-powertools Logger） |
| PII マスク | LINE userId, チャット内容, カレンダーデータ, トークン類 |

### 8.2 ログ保持期間 SAM 定義

```yaml
# 各 Lambda 関数のロググループ
WebhookHandlerLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub "/aws/lambda/${WebhookHandler}"
    RetentionInDays: 30
```

---

## 9. SAM テンプレート全体構造

```
template.yaml
├── AWSTemplateFormatVersion: '2010-09-09'
├── Transform: AWS::Serverless-2016-10-31
├── Description: Auto Reward Service
├── Parameters
│   └── Stage: prod（デフォルト）
├── Globals
│   └── Function（共通設定）
└── Resources
    ├── ArsTable（DynamoDB）
    ├── ArsCommonLayer（Lambda Layer）
    ├── ArsLambdaRole（IAM Role）
    ├── WebhookHandler（Lambda）
    ├── CharacterReply（Lambda）
    ├── ImageAnalysis（Lambda）
    ├── BatchProcessor（Lambda）
    ├── LiffApi（Lambda）
    ├── ArsHttpApi（API Gateway）
    ├── WebhookHandlerLogGroup（CloudWatch Logs）
    ├── CharacterReplyLogGroup（CloudWatch Logs）
    ├── ImageAnalysisLogGroup（CloudWatch Logs）
    ├── BatchProcessorLogGroup（CloudWatch Logs）
    └── LiffApiLogGroup（CloudWatch Logs）
```

---

## 10. samconfig.toml 設計

```toml
version = 0.1

[default]
[default.deploy]
[default.deploy.parameters]
stack_name = "auto-reward-service"
resolve_s3 = true
region = "ap-northeast-1"
confirm_changeset = false
capabilities = "CAPABILITY_IAM"

[default.build]
[default.build.parameters]
use_container = false
```

---

## 11. リソース命名規則

| リソース種別 | 命名パターン | 例 |
|------------|-----------|---|
| DynamoDB テーブル | `ArsTable` | `ArsTable` |
| Lambda 関数 | `{FunctionName}` | `WebhookHandler` |
| Lambda Layer | `ArsCommonLayer` | `ArsCommonLayer` |
| IAM ロール | `ArsLambdaRole` | `ArsLambdaRole` |
| Log Group | `/aws/lambda/{FunctionName}` | `/aws/lambda/WebhookHandler` |
| Secrets Manager | `ars/{service}` | `ars/line` |
| SAM スタック | `auto-reward-service` | `auto-reward-service` |

---

## 12. インフラ設計の制約事項

1. **VPC なし**: DynamoDB / Bedrock / Secrets Manager はすべてパブリックエンドポイント経由（HTTPS）
2. **CloudWatch アラームなし**: MVP 期間はログ目視確認のみ。問題発生時は手動対応
3. **環境分離なし**: prod 単一環境。ハッカソン終了後に複数環境対応が必要な場合は `Stage` パラメータを活用
4. **DLQ なし**: EventBridge トリガー Lambda は Lambda 標準リトライ（最大2回）のみ
5. **X-Ray 無効**: Tracing: PassThrough（コスト削減）
6. **WAF なし**: SEC-07 に定義の API Gateway WAF はハッカソン用途のため省略。本番移行時は AWS WAF WebACL の適用を推奨
