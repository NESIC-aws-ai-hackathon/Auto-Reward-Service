# Tech Stack Decisions — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16

---

## 確定技術スタック決定一覧

| 決定項目 | 採用技術・設定 | 選択理由 |
|---------|--------------|---------|
| **AWS リージョン** | ap-northeast-1（東京） | Bedrock Nova 対応、LINE ユーザーへの低レイテンシ |
| **Python ランタイム** | Python 3.14 | 最新 GA 版（2025年10月リリース）。パフォーマンス最適化・型システム改善 |
| **DynamoDB キャパシティ** | オンデマンド（PAY_PER_REQUEST） | MVP 段階のユーザー数不確実性に対応。スケーリング管理不要 |
| **Lambda Layer** | services/ + utils/ + models/ のみ | ハンドラコードと共通ライブラリを分離。boto3 は Lambda 内蔵を利用 |
| **Cold Start 対策** | EventBridge ウォームアップ ping（5分毎） | Provisioned Concurrency コスト不要。MVPコスト最適 |
| **X-Ray トレーシング** | 無効（SAM `Tracing: PassThrough`） | MVP 段階は CloudWatch Logs で十分 |
| **CloudWatch Logs 保持期間** | 30日（全関数統一） | デバッグに十分・コスト最適 |
| **ロギングライブラリ** | aws-lambda-powertools Logger | JSON 構造化 + PII マスク + correlation ID 自動付与 |
| **Pydantic バージョン** | v2 | 型安全・高速バリデーション |
| **LINE SDK** | line-bot-sdk v3（薄いラッパー） | 公式サポート。4メソッドのみ公開 |

---

## Lambda 関数別設定一覧

| 関数名 | ユニット | メモリ | タイムアウト | ウォームアップ |
|--------|---------|--------|------------|--------------|
| WebhookHandler | Unit 1 | 128MB | 10秒 | ✅ 5分毎 |
| IntentClassifier | Unit 2 | 256MB | 30秒 | — |
| CharacterReply | Unit 2 | 256MB | 30秒 | ✅ 5分毎（代表） |
| OnboardingFlow | Unit 2 | 256MB | 30秒 | — |
| ExpenseExtractor | Unit 3 | 256MB | 30秒 | — |
| ReceiptImageAnalyzer | Unit 3 | 512MB | 60秒 | — |
| RewardPoolUpdater | Unit 4 | 256MB | 300秒 | — |
| RewardProposal | Unit 5 | 256MB | 30秒 | — |
| PushNotifier | Unit 6 | 256MB | 300秒 | — |
| LiffApi | Unit 7 | 256MB | 30秒 | — |

> **注意**: Unit 0 はハンドラ関数を持たない。上記は全ユニットの基準値として定義。

---

## SAM template.yaml 設定指針

### Globals セクション

```yaml
Globals:
  Function:
    Runtime: python3.14
    Architectures:
      - x86_64
    Tracing: PassThrough
    Environment:
      Variables:
        DYNAMODB_TABLE_NAME: !Ref ArsTable
        SECRET_NAME: !Ref SecretName
        BEDROCK_TEXT_MODEL_ID: !Ref BedrockTextModelId
        BEDROCK_IMAGE_MODEL_ID: !Ref BedrockImageModelId
        AWS_ACCOUNT_ID: !Ref AWS::AccountId
    Layers:
      - !Ref ArsCommonLayer
    LoggingConfig:
      LogFormat: JSON
      ApplicationLogLevel: INFO
      SystemLogLevel: WARN
```

### DynamoDB テーブル定義要点

```yaml
ArsTable:
  Type: AWS::DynamoDB::Table
  Properties:
    BillingMode: PAY_PER_REQUEST       # Q1: オンデマンド
    TableName: !Sub "ArsTable-${StageName}"
    TimeToLiveSpecification:            # R1-5: TTL 有効化
      AttributeName: ttl
      Enabled: true
    PointInTimeRecoverySpecification:
      PointInTimeRecoveryEnabled: true
    SSESpecification:
      SSEEnabled: true                  # SEC-03: 暗号化
    GlobalSecondaryIndexes:             # Q1-C: entityType-index
      - IndexName: entityType-index
        KeySchema:
          - AttributeName: entityType
            KeyType: HASH
          - AttributeName: PK
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
```

### CloudWatch Logs 保持期間（SAM）

```yaml
# 各 Lambda Function リソースに追加
LogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub "/aws/lambda/${FunctionName}"
    RetentionInDays: 30                # Q6: 30日
```

---

## Python 3.14 対応確認事項

> ⚠️ **Lambda ランタイム確認**: Python 3.14（GA: 2025年10月）の AWS Lambda サポートは  
> `sam deploy` 実行前に [AWS Lambda サポートランタイム一覧](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html) で確認すること。  
> 未サポートの場合は Python 3.13 にフォールバックする。

---

## ウォームアップ ping 設計

### EventBridge Scheduler ルール

```yaml
WarmupWebhookScheduler:
  Type: AWS::Scheduler::Schedule
  Properties:
    ScheduleExpression: "rate(5 minutes)"
    Target:
      Arn: !GetAtt WebhookHandlerFunction.Arn
      RoleArn: !GetAtt SchedulerRole.Arn
      Input: '{"source": "warmup"}'

WarmupBedrockScheduler:
  Type: AWS::Scheduler::Schedule
  Properties:
    ScheduleExpression: "rate(5 minutes)"
    Target:
      Arn: !GetAtt CharacterReplyFunction.Arn
      RoleArn: !GetAtt SchedulerRole.Arn
      Input: '{"source": "warmup"}'
```

### ハンドラ側の warmup 検出パターン

```python
def lambda_handler(event, context):
    # ウォームアップ ping の検出（全ハンドラ共通）
    if event.get("source") == "warmup":
        logger.debug("Warmup ping received")
        return {"statusCode": 200, "body": "warm"}
    # ... 通常処理
```

---

## 依存ライブラリ一覧

### requirements.txt（Lambda Layer 同梱）

```
pydantic>=2.0.0
line-bot-sdk>=3.0.0
aws-lambda-powertools>=3.0.0
requests>=2.31.0
```

### requirements-dev.txt（ローカル開発・テスト用のみ）

```
boto3>=1.34.0
botocore>=1.34.0
pytest>=8.0.0
pytest-mock>=3.12.0
moto[dynamodb,secretsmanager,bedrock-runtime]>=5.0.0
```
