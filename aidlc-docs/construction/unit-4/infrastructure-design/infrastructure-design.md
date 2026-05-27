# Infrastructure Design — Unit 4: ご褒美候補プール

**作成日**: 2026-05-16  
**Unit**: Unit 4 — ご褒美候補プール

---

## template.yaml 追加差分

### 1. RewardPoolUpdaterFunction（新規 Lambda）

```yaml
  # ─────────────────────────────────────────
  # Lambda Functions（Unit 4）
  # ─────────────────────────────────────────
  RewardPoolUpdaterFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: RewardPoolUpdaterFunction
      Handler: handlers.reward_pool_updater.lambda_handler
      CodeUri: src/
      MemorySize: 256
      Timeout: 300
      Role: !GetAtt ArsLambdaRole.Arn
      Environment:
        Variables:
          RAKUTEN_DEFAULT_KEYWORDS: "スイーツ,コスメ,本,入浴剤,アロマ"
          RAKUTEN_MAX_ITEMS_PER_POOL: "20"
          RAKUTEN_HITS_PER_KEYWORD: "5"
      Tags:
        Project: auto-reward-service
        Stage: prod
```

### 2. RewardPoolUpdaterFunctionLogGroup（新規 CloudWatch Logs）

```yaml
  RewardPoolUpdaterFunctionLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub "/aws/lambda/${RewardPoolUpdaterFunction}"
      RetentionInDays: 30
```

### 3. SchedulerExecutionRole 更新（既存リソースに Resource 追加）

`SchedulerExecutionRole` の `InvokeLambdaPolicy` に `RewardPoolUpdaterFunction` を追加する。

**変更前（抜粋）:**
```yaml
              - Effect: Allow
                Action: lambda:InvokeFunction
                Resource:
                  - !GetAtt WebhookHandlerFunction.Arn
```

**変更後:**
```yaml
              - Effect: Allow
                Action: lambda:InvokeFunction
                Resource:
                  - !GetAtt WebhookHandlerFunction.Arn
                  - !GetAtt RewardPoolUpdaterFunction.Arn
```

### 4. RewardPoolScheduler（新規 EventBridge Scheduler）

```yaml
  # ─────────────────────────────────────────
  # EventBridge Scheduler（Unit 4 日次バッチ）
  # ─────────────────────────────────────────
  RewardPoolScheduler:
    Type: AWS::Scheduler::Schedule
    Properties:
      Name: RewardPoolScheduler
      ScheduleExpression: "cron(0 17 * * ? *)"
      FlexibleTimeWindow:
        Mode: "OFF"
      Target:
        Arn: !GetAtt RewardPoolUpdaterFunction.Arn
        RoleArn: !GetAtt SchedulerExecutionRole.Arn
        Input: '{"source": "scheduler"}'
```

---

## 変更ファイル一覧

| ファイル | 操作 | 変更内容 |
|---------|------|---------|
| `template.yaml` | 更新 | RewardPoolUpdaterFunction + RewardPoolScheduler + LogGroup 追加、SchedulerExecutionRole 更新 |
| `src/handlers/reward_pool_updater.py` | 新規作成 | Lambda ハンドラ |
| `layer/python/services/rakuten_service.py` | 新規作成 | 楽天APIクライアント |
| `layer/python/services/reward_pool_service.py` | 新規作成 | スコアリング・差分マージ |

---

## IAM 権限確認

| 必要権限 | 既存ポリシー | 状態 |
|---------|------------|------|
| `dynamodb:GetItem` (ArsTable) | ArsDynamoDBPolicy | ✅ 既存 |
| `dynamodb:PutItem` (ArsTable) | ArsDynamoDBPolicy | ✅ 既存 |
| `dynamodb:Query` (ArsTable + GSI) | ArsDynamoDBPolicy | ✅ 既存 |
| `dynamodb:Scan` (ArsTable + GSI) | ArsDynamoDBPolicy | ❌ 不足（追加必要） |
| `secretsmanager:GetSecretValue` (ars/rakuten*) | ArsSecretsManagerPolicy | ✅ 既存 |

> **注**: `dynamodb:Scan` が ArsDynamoDBPolicy に含まれていない。`_get_all_user_pks()` で GSI Scan を使う場合は追加が必要。  
> **代替案**: Scan の代わりに `Query` + `entityType = "PROFILE"` で GSI を使えば Scan 不要。こちらを採用（Query は既に許可済み）。

**結論**: IAM 権限追加は **不要**。GSI Query を使って全 PROFILE アイテムを取得する。
