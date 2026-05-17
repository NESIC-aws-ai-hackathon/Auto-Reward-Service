# Infrastructure Design — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**Unit**: Unit 1 — LINE Bot基盤

---

## 1. インフラ決定事項サマリー

| 項目 | 決定値 | 根拠 |
|------|--------|------|
| API Gateway 種別 | HTTP API v2 (`AWS::Serverless::HttpApi`) | 低コスト・低レイテンシ |
| Lambda メモリ | 256 MB | Unit 2 以降の Bedrock 追加後も変更不要 |
| Lambda タイムアウト | 10 秒 | LINE 応答 3 秒目標 + バッファ |
| Lambda ランタイム | python3.14 (Globals 継承) | Unit 0 で確定 |
| IAM ロール | `ArsLambdaRole`（Unit 0 共有）| 既に `ars/line` の GetSecretValue 権限を保有 |
| スロットリング | 定常 100 req/s / バースト 200 | 誤爆防止・ハッカソン規模 |
| X-Ray | `PassThrough`（Globals 継承・実質無効）| コスト優先 |
| CloudWatch Logs 保持 | 30 日 | デバッグに十分 |
| ウォームアップ | EventBridge Scheduler 5 分毎 | PERF-03 |

---

## 2. 追加 AWS リソース一覧

| リソース論理 ID | AWS 種別 | 役割 |
|--------------|---------|------|
| `WebhookApi` | `AWS::Serverless::HttpApi` | LINE Webhook エンドポイント |
| `WebhookHandlerFunction` | `AWS::Serverless::Function` | Webhook 受信・検証・ルーティング |
| `WarmupWebhookScheduler` | `AWS::Scheduler::Schedule` | 5 分毎ウォームアップ |
| `SchedulerExecutionRole` | `AWS::IAM::Role` | EventBridge Scheduler → Lambda 呼び出し権限 |
| `WebhookFunctionLogGroup` | `AWS::Logs::LogGroup` | CloudWatch Logs (30 日保持) |

---

## 3. WebhookApi（API Gateway HTTP API v2）

### 3.1 設定

| パラメータ | 値 |
|-----------|---|
| 種別 | `AWS::Serverless::HttpApi` |
| プロトコル | HTTP API v2 |
| ルート | `POST /webhook` |
| 認証 | なし（Lambda 内で署名検証） |
| CORS | 無効（LINE Platform からのみコール） |
| ステージ | `$default`（SAM デフォルト） |
| スロットリング (定常) | 100 req/s |
| スロットリング (バースト) | 200 req |

### 3.2 SAM 定義

```yaml
WebhookApi:
  Type: AWS::Serverless::HttpApi
  Properties:
    StageName: $default
    DefaultRouteSettings:
      ThrottlingBurstLimit: 200
      ThrottlingRateLimit: 100
    Tags:
      Project: auto-reward-service
      Stage: prod
```

---

## 4. WebhookHandlerFunction（Lambda）

### 4.1 設定

| パラメータ | 値 |
|-----------|---|
| 論理 ID | `WebhookHandlerFunction` |
| ハンドラ | `webhook_handler.handler` |
| CodeUri | `src/handlers/` |
| メモリ | 256 MB |
| タイムアウト | 10 秒 |
| ランタイム | python3.14（Globals 継承） |
| IAM ロール | `ArsLambdaRole`（Unit 0、GetSecretValue 権限保有済み） |
| Layer | `ArsCommonLayer`（Globals 継承） |
| イベントソース | `WebhookApi` POST /webhook |
| 環境変数 | Globals 継承（`LINE_SECRET_NAME`, `TABLE_NAME`, `LOG_LEVEL` 等） |

### 4.2 SAM 定義

```yaml
WebhookHandlerFunction:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: WebhookHandlerFunction
    Handler: webhook_handler.handler
    CodeUri: src/handlers/
    MemorySize: 256
    Timeout: 10
    Role: !GetAtt ArsLambdaRole.Arn
    Events:
      WebhookPost:
        Type: HttpApi
        Properties:
          ApiId: !Ref WebhookApi
          Path: /webhook
          Method: POST
    Tags:
      Project: auto-reward-service
      Stage: prod
```

---

## 5. WarmupWebhookScheduler（EventBridge Scheduler）

### 5.1 設定

| パラメータ | 値 |
|-----------|---|
| スケジュール | `rate(5 minutes)` |
| ターゲット | `WebhookHandlerFunction` |
| ペイロード | `{"source": "warmup"}` |
| タイムウィンドウ | OFF（フレキシブルなし） |
| 実行ロール | `SchedulerExecutionRole`（新規） |

### 5.2 SAM 定義

```yaml
WarmupWebhookScheduler:
  Type: AWS::Scheduler::Schedule
  Properties:
    Name: WarmupWebhookScheduler
    ScheduleExpression: rate(5 minutes)
    FlexibleTimeWindow:
      Mode: "OFF"
    Target:
      Arn: !GetAtt WebhookHandlerFunction.Arn
      RoleArn: !GetAtt SchedulerExecutionRole.Arn
      Input: '{"source": "warmup"}'

SchedulerExecutionRole:
  Type: AWS::IAM::Role
  Properties:
    RoleName: ArsSchedulerExecutionRole
    AssumeRolePolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Principal:
            Service: scheduler.amazonaws.com
          Action: sts:AssumeRole
    Policies:
      - PolicyName: InvokeLambdaPolicy
        PolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action: lambda:InvokeFunction
              Resource:
                - !GetAtt WebhookHandlerFunction.Arn
```

> **Note**: Unit 4 の `WarmupBedrockScheduler` 追加時に `Resource` リストへ対象 Lambda を追記する。

---

## 6. CloudWatch Logs

### 6.1 ロググループ設定

| パラメータ | 値 |
|-----------|---|
| ロググループ名 | `/aws/lambda/WebhookHandlerFunction` |
| 保持期間 | 30 日 |
| 暗号化 | なし（デフォルト） |

### 6.2 SAM 定義

```yaml
WebhookFunctionLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub "/aws/lambda/${WebhookHandlerFunction}"
    RetentionInDays: 30
```

---

## 7. IAM 権限マッピング

`ArsLambdaRole`（Unit 0 定義済み）の既存ポリシーで Unit 1 に必要な権限を全て保有。

| 必要権限 | ポリシー | ステータス |
|---------|---------|----------|
| `secretsmanager:GetSecretValue` (ars/line*) | `ArsSecretsManagerPolicy` | ✅ 既存 |
| CloudWatch Logs 書き込み | `AWSLambdaBasicExecutionRole` | ✅ 既存 |
| DynamoDB アクセス | `ArsDynamoDBPolicy` | ✅ 既存（Unit 2 以降で使用） |

---

## 8. template.yaml 差分（Unit 1 追加分）

`template.yaml` の `Resources` セクションに以下を追加する（コード生成フェーズで実施）:

1. `WebhookApi`
2. `WebhookHandlerFunction`
3. `WarmupWebhookScheduler`
4. `SchedulerExecutionRole`
5. `WebhookFunctionLogGroup`

`Outputs` セクションに追加:
- `WebhookApiEndpoint`（LINE Webhook URL として使用）
