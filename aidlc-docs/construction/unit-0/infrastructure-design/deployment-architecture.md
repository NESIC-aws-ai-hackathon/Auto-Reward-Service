# Deployment Architecture — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16  
**バージョン**: 1.0  
**ステータス**: レビュー待ち

---

## 1. システム全体アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────────┐
│ 外部サービス                                                          │
│  LINE Platform  Google Calendar API  楽天カード（将来）               │
└────────┬─────────────────┬──────────────────────────────────────────┘
         │ HTTPS           │ HTTPS (OAuth2)
         ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ AWS (ap-northeast-1)                                                 │
│                                                                      │
│  ┌─────────────────┐    ┌───────────────────────────────────────┐   │
│  │  API Gateway     │    │  EventBridge Scheduler                │   │
│  │  (HTTP API v2)   │    │  rate(5min) × 2                      │   │
│  │  /webhook POST   │    └──────────┬────────────────┬──────────┘   │
│  │  /liff/api/*     │               │                │              │
│  └──┬───────────────┘               │                │              │
│     │                               ▼                ▼              │
│     │              ┌─────────────────────┐  ┌──────────────────┐   │
│     │              │  WebhookHandler      │  │  CharacterReply  │   │
│     │              │  128MB / 10s         │  │  256MB / 30s     │   │
│     ▼              └─────────────────────┘  └──────────────────┘   │
│  ┌──────────────┐  ┌─────────────────────┐  ┌──────────────────┐   │
│  │  LiffApi     │  │  ImageAnalysis       │  │  BatchProcessor  │   │
│  │  256MB / 30s │  │  512MB / 60s         │  │  256MB / 300s    │   │
│  └──────────────┘  └─────────────────────┘  └──────────────────┘   │
│     │ 全 Lambda 共通                                                  │
│     ├──────────────────────────────────────────────────────────┐    │
│     │                                                           │    │
│     ▼                                                           ▼    │
│  ┌────────────────────────┐         ┌──────────────────────────┐   │
│  │  ArsCommonLayer         │         │  Amazon DynamoDB          │   │
│  │  (services/utils/models)│         │  ArsTable                 │   │
│  └────────────────────────┘         │  GSI: entityType-index    │   │
│                                      │  TTL / SSE / PITR         │   │
│                                      └──────────────────────────┘   │
│                                                                      │
│  ┌────────────────────────┐         ┌──────────────────────────┐   │
│  │  AWS Secrets Manager    │         │  Amazon Bedrock           │   │
│  │  ars/line               │         │  Nova Micro / Nova Lite   │   │
│  │  ars/google             │         └──────────────────────────┘   │
│  │  ars/rakuten            │                                         │
│  └────────────────────────┘         ┌──────────────────────────┐   │
│                                      │  CloudWatch Logs          │   │
│  ┌────────────────────────┐         │  /aws/lambda/* (30日)     │   │
│  │  S3 (SAM 自動管理)      │         └──────────────────────────┘   │
│  │  アーティファクト格納    │                                         │
│  └────────────────────────┘                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. SAM デプロイフロー

```
開発者 PC
    │
    ├─ sam build
    │   └─ layer/ を zip → ArsCommonLayer
    │   └─ src/handlers/ を zip → 各 Lambda 関数
    │
    ├─ sam deploy --config-env default
    │   ├─ アーティファクトを S3（自動作成バケット）へアップロード
    │   ├─ CloudFormation スタック "auto-reward-service" を作成/更新
    │   └─ 全リソースをデプロイ
    │
    └─ デプロイ完了
        ├─ API Gateway エンドポイント URL 出力
        └─ Lambda ARN 出力
```

### 2.1 ビルドコマンド

```bash
# 依存関係インストール
pip install -r requirements.txt -t layer/python/

# SAM ビルド
sam build

# SAM デプロイ
sam deploy
```

---

## 3. ディレクトリ構成（デプロイ対象）

```
Auto-Reward-Service/
├── template.yaml              # SAM テンプレート（IaC 本体）
├── samconfig.toml             # デプロイ設定（prod のみ）
├── Makefile                   # ショートカットコマンド
├── requirements.txt           # Lambda Layer 依存パッケージ
├── requirements-dev.txt       # 開発用パッケージ（boto3, pytest等）
│
├── layer/                     # Lambda Layer ソース
│   └── python/
│       ├── services/          # ビジネスロジック層
│       │   ├── __init__.py
│       │   ├── dynamodb_service.py
│       │   ├── bedrock_service.py
│       │   ├── line_service.py
│       │   └── google_calendar_service.py
│       ├── utils/             # ユーティリティ層
│       │   ├── __init__.py
│       │   ├── secrets.py
│       │   ├── logger.py
│       │   └── exceptions.py
│       └── models/            # データモデル層
│           ├── __init__.py
│           └── schemas.py
│
├── src/
│   └── handlers/              # Lambda ハンドラー（Layer 非対象）
│       ├── webhook_handler.py
│       ├── character_reply.py
│       ├── image_analysis.py
│       ├── batch_processor.py
│       └── liff_api.py
│
└── tests/
    └── unit/                  # ユニットテスト
```

---

## 4. 環境変数設計（Lambda 共通）

| 環境変数名 | 値 | 設定箇所 |
|-----------|---|---------|
| `TABLE_NAME` | `ArsTable` | SAM Globals |
| `LINE_SECRET_NAME` | `ars/line` | SAM Globals |
| `GOOGLE_SECRET_NAME` | `ars/google` | SAM Globals |
| `RAKUTEN_SECRET_NAME` | `ars/rakuten` | SAM Globals |
| `LOG_LEVEL` | `INFO` | SAM Globals |
| `BEDROCK_TEXT_MODEL_ID` | `amazon.nova-micro-v1:0` | SAM Globals |
| `BEDROCK_IMAGE_MODEL_ID` | `amazon.nova-lite-v1:0` | SAM Globals |
| `BEDROCK_FALLBACK_MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` | SAM Globals |

---

## 5. IAM ロール設計

### 5.1 ArsLambdaRole

すべての Lambda 関数が共有する実行ロール（最小権限原則）。

```yaml
ArsLambdaRole:
  Type: AWS::IAM::Role
  Properties:
    RoleName: ArsLambdaRole
    AssumeRolePolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Service: lambda.amazonaws.com
          Action: sts:AssumeRole
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    Policies:
      - PolicyName: ArsDynamoDBPolicy
        PolicyDocument:
          Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - dynamodb:GetItem
                - dynamodb:PutItem
                - dynamodb:UpdateItem
                - dynamodb:DeleteItem
                - dynamodb:Query
                - dynamodb:BatchWriteItem
              Resource:
                - !GetAtt ArsTable.Arn
                - !Sub "${ArsTable.Arn}/index/*"
      - PolicyName: ArsBedrockPolicy
        PolicyDocument:
          Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
              Resource: "*"
      - PolicyName: ArsSecretsManagerPolicy
        PolicyDocument:
          Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - secretsmanager:GetSecretValue
              Resource:
                - !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:ars/line*"
                - !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:ars/google*"
                - !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:ars/rakuten*"
```

---

## 6. ネットワーク設計

| 項目 | 設定 |
|------|------|
| VPC | なし（Lambda デフォルト） |
| インターネットアクセス | あり（LINE API / Google Calendar API / Bedrock エンドポイント） |
| セキュリティグループ | なし（VPC 外のため不要） |
| DynamoDB アクセス | HTTPS パブリックエンドポイント（ap-northeast-1） |
| Secrets Manager アクセス | HTTPS パブリックエンドポイント（ap-northeast-1） |

> **注意**: VPC 外配置のため、通信はすべて HTTPS で暗号化されているが、VPC エンドポイントは使用しない。本番グレードに移行する場合は VPC + エンドポイント配置を推奨。

---

## 7. コスト概算（ハッカソン想定）

| サービス | 想定使用量 | 月額概算 |
|---------|-----------|---------|
| Lambda | ~10,000 呼び出し/月 | 無料枠内 |
| DynamoDB | ~1 GB / 100万 RCU+WCU | ~$1 |
| Bedrock (Nova Micro) | ~1,000 呼び出し/月 | ~$0.1 |
| Secrets Manager | 3 シークレット | ~$0.12 |
| API Gateway | ~10,000 呼び出し/月 | 無料枠内 |
| CloudWatch Logs | ~100 MB/月 | ~$0.05 |
| **合計** | | **~$2/月** |

---

## 8. デプロイ前提条件チェックリスト

```
[ ] AWS CLI が設定済み（aws configure）
[ ] SAM CLI がインストール済み（sam --version）
[ ] Python 3.14 がインストール済み
[ ] ars/line シークレットが Secrets Manager に作成済み
[ ] ars/google シークレットが Secrets Manager に作成済み
[ ] ars/rakuten シークレットが Secrets Manager に作成済み
[ ] LINE Developers コンソールで Webhook URL が設定済み
```
