# デプロイ確認手順 — 第1回目（Unit 0）

**対象 Unit**: U0  
**確認内容**: SAM デプロイ成功 / DynamoDB テーブル作成 / Lambda Layer デプロイ

---

## 前提条件チェック

実行前に以下を確認してください:

```
[ ] AWS CLI が設定済み（aws configure で認証情報あり）
[ ] SAM CLI がインストール済み（sam --version で確認）
[ ] Python 3.14 がインストール済み
[ ] Secrets Manager に以下のシークレットを事前作成済み
      ars/line     → {"LINE_CHANNEL_SECRET": "...", "LINE_ACCESS_TOKEN": "..."}
      ars/google   → {"GOOGLE_CLIENT_ID": "...", "GOOGLE_CLIENT_SECRET": "..."}
      ars/rakuten  → {"RAKUTEN_APP_ID": "..."}
```

---

## デプロイ手順

```bash
# 1. リポルートに移動
cd Auto-Reward-Service

# 2. Layer の依存パッケージをインストール
pip install -r requirements.txt -t layer/python/ --upgrade

# 3. SAM ビルド
sam build

# 4. SAM デプロイ（初回は --guided も可）
sam deploy
```

---

## 確認手順

### A. CloudFormation スタック確認

```bash
aws cloudformation describe-stacks \
  --stack-name auto-reward-service \
  --query "Stacks[0].StackStatus"
# 期待値: "CREATE_COMPLETE" or "UPDATE_COMPLETE"
```

### B. DynamoDB テーブル確認

```bash
aws dynamodb describe-table \
  --table-name ArsTable \
  --query "Table.{Name:TableName, Status:TableStatus, BillingMode:BillingModeSummary.BillingMode}"
# 期待値:
#   Name: "ArsTable"
#   Status: "ACTIVE"
#   BillingMode: "PAY_PER_REQUEST"
```

GSI の確認:

```bash
aws dynamodb describe-table \
  --table-name ArsTable \
  --query "Table.GlobalSecondaryIndexes[0].{Name:IndexName, Status:IndexStatus}"
# 期待値:
#   Name: "entityType-index"
#   Status: "ACTIVE"
```

TTL の確認:

```bash
aws dynamodb describe-time-to-live \
  --table-name ArsTable
# 期待値: {"TimeToLiveDescription": {"TimeToLiveStatus": "ENABLED", "AttributeName": "ttl"}}
```

### C. Lambda Layer 確認

```bash
aws lambda list-layer-versions \
  --layer-name ArsCommonLayer \
  --query "LayerVersions[0].{ARN:LayerVersionArn, Runtime:CompatibleRuntimes[0]}"
# 期待値:
#   ARN: "arn:aws:lambda:ap-northeast-1:...:layer:ArsCommonLayer:1"
#   Runtime: "python3.14"
```

### D. IAM ロール確認

```bash
aws iam get-role \
  --role-name ArsLambdaRole \
  --query "Role.{Name:RoleName, Arn:Arn}"
# 期待値: RoleName: "ArsLambdaRole"
```

### E. SAM デプロイ出力確認

```bash
aws cloudformation describe-stacks \
  --stack-name auto-reward-service \
  --query "Stacks[0].Outputs"
# 以下の出力キーが存在すること:
#   ArsTableName
#   ArsTableArn
#   ArsCommonLayerArn
#   ArsLambdaRoleArn
```

---

## 合格基準

| 確認項目 | 期待値 |
|---------|--------|
| CloudFormation スタック | CREATE_COMPLETE / UPDATE_COMPLETE |
| ArsTable 状態 | ACTIVE |
| GSI entityType-index | ACTIVE |
| DynamoDB TTL | ENABLED (ttl) |
| DynamoDB SSE | 有効 |
| DynamoDB PITR | 有効 |
| ArsCommonLayer | python3.14 互換バージョンあり |
| ArsLambdaRole | 存在する |

---

## 次のステップ

確認完了後 → Unit 1（LINE Bot基盤）の開発へ進む。  
Unit 1 完了後に **デプロイ 2 回目**（LINE Webhook 疎通確認）を実施。
