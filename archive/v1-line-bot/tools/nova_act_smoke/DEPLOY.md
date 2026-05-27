# ECS デプロイ手順書

## 概要

Nova Act Amazon Worker + Login Server を ECS Fargate にデプロイする手順。

### アーキテクチャ

```
┌──────────────────────────────────────────────────────────┐
│  LIFF アプリ                                              │
│  [Amazon連携ボタン] → ALB URL → Login Server             │
└───────────────┬──────────────────────────────────────────┘
                │
         ┌──────▼──────┐
         │     ALB      │  ← HTTPS (port 80/443)
         └──────┬──────┘
                │
    ┌───────────▼───────────┐
    │   ECS Fargate Task     │
    │ ┌───────────────────┐  │
    │ │ Login Server (8080)│  │  ← Flask Web UI
    │ │ Worker (DDB Poll)  │  │  ← Cart Automation
    │ └────────┬──────────┘  │
    │          │              │
    │    ┌─────▼─────┐       │
    │    │  EFS Mount │       │  ← /data/profiles (Cookie保存)
    │    └───────────┘       │
    └────────────────────────┘
```

## 前提条件

- AWS CLI 設定済み (`--profile share`)
- Docker Desktop インストール済み
- SAM template が正常にデプロイ済み

## 手順

### 1. ECR リポジトリ作成 & ECS スタックデプロイ

```powershell
# VPC の Public Subnet を確認 (ALB 用)
aws ec2 describe-subnets --profile share --region ap-northeast-1 `
  --filters "Name=vpc-id,Values=vpc-0b8a3a0e30d59d7f3" "Name=map-public-ip-on-launch,Values=true" `
  --query "Subnets[].SubnetId" --output text

# ECS スタックをデプロイ (初回: ECR リポジトリ作成のみ)
cd tools/nova_act_smoke
aws cloudformation deploy --profile share --region ap-northeast-1 `
  --template-file ecs-template.yaml `
  --stack-name ars-nova-act-ecs `
  --parameter-overrides `
    ImageUri="PLACEHOLDER" `
    NovaActApiKey="YOUR_NOVA_ACT_API_KEY" `
    LoginTokenSecret="$(python -c 'import secrets; print(secrets.token_hex(32))')" `
  --capabilities CAPABILITY_NAMED_IAM `
  --no-fail-on-empty-changeset
```

### 2. Docker イメージビルド & ECR プッシュ

```powershell
# ECR リポジトリ URI を取得
$ECR_URI = aws cloudformation describe-stacks --profile share --region ap-northeast-1 `
  --stack-name ars-nova-act-ecs `
  --query "Stacks[0].Outputs[?OutputKey=='EcrRepositoryUri'].OutputValue" --output text

$ACCOUNT_ID = aws sts get-caller-identity --profile share --query Account --output text
$REGION = "ap-northeast-1"

# ECR ログイン
aws ecr get-login-password --profile share --region $REGION | `
  docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# イメージビルド
cd tools/nova_act_smoke
docker build -t ars-nova-act:latest .

# タグ付け & プッシュ
docker tag ars-nova-act:latest "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
```

### 3. ECS サービス更新 (ImageUri を実際の値に)

```powershell
aws cloudformation deploy --profile share --region ap-northeast-1 `
  --template-file ecs-template.yaml `
  --stack-name ars-nova-act-ecs `
  --parameter-overrides `
    ImageUri="${ECR_URI}:latest" `
    NovaActApiKey="YOUR_NOVA_ACT_API_KEY" `
    LoginTokenSecret="YOUR_SECRET" `
  --capabilities CAPABILITY_NAMED_IAM `
  --no-fail-on-empty-changeset
```

### 4. ALB URL を取得 & Lambda に設定

```powershell
# ALB DNS を取得
$ALB_URL = aws cloudformation describe-stacks --profile share --region ap-northeast-1 `
  --stack-name ars-nova-act-ecs `
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDNS'].OutputValue" --output text

echo "Login URL: $ALB_URL/login/{user_id}"

# Lambda の環境変数に ECS_LOGIN_SERVER_URL を追加
# template.yaml の Globals.Function.Environment.Variables に追加:
#   ECS_LOGIN_SERVER_URL: "http://<ALB_DNS>"
```

### 5. SAM スタック再デプロイ (ECS_LOGIN_SERVER_URL 追加)

```powershell
cd ../..  # プロジェクトルート
cmd /c "rmdir /s /q .aws-sam"
sam build --profile share
sam deploy --profile share --no-fail-on-empty-changeset
```

### 6. 動作確認

1. LIFF アプリ → 設定 → 「Amazon アカウント連携」セクション
2. 「Amazon にログインする」ボタンをタップ
3. 新しいウィンドウで Amazon ログインフォームが表示される
4. メール → パスワード → (OTP) → ログイン完了
5. LIFF に戻ると「✅ 連携済み」と表示される

## ローカルテスト

```powershell
# Docker で直接起動
cd tools/nova_act_smoke
docker build -t ars-nova-act:latest .
docker run -it --rm `
  -p 8080:8080 `
  -e MODE=login `
  -e NOVA_ACT_PROFILES_DIR=/data/profiles `
  -e LOGIN_TOKEN_SECRET=dev-secret `
  -v "${PWD}/local-profiles:/data/profiles" `
  ars-nova-act:latest

# ブラウザで http://localhost:8080/login/test-user にアクセス
```

## トラブルシューティング

| 問題 | 対策 |
|------|------|
| ECS タスクが起動しない | CloudWatch Logs `/ecs/ars-nova-act` を確認 |
| ALB がヘルスチェック失敗 | ECS SG で port 8080 が ALB SG から許可されているか確認 |
| EFS マウントエラー | EFS SG で port 2049 が ECS SG から許可されているか確認 |
| Login 後に Cookie が消える | EFS Access Point のパーミッションが 755/uid:1000 か確認 |
| Playwright 起動失敗 | Docker イメージ内で `python -c "from playwright.sync_api import sync_playwright"` を確認 |

## 環境変数一覧

| 変数名 | 説明 | デフォルト |
|--------|------|-----------|
| `MODE` | 起動モード (login/worker/all) | `all` |
| `NOVA_ACT_API_KEY` | Nova Act API キー | (必須) |
| `NOVA_ACT_PROFILES_DIR` | プロファイル保存先 | `/data/profiles` |
| `LOGIN_TOKEN_SECRET` | トークン署名シークレット | `dev-secret-change-me` |
| `ARS_TABLE_NAME` | DynamoDB テーブル名 | `ArsTable` |
| `AWS_DEFAULT_REGION` | AWS リージョン | `ap-northeast-1` |
| `ENABLE_REAL_PURCHASE` | 実購入の有効化 | `false` |
| `MAX_PURCHASE_AMOUNT` | 最大購入金額 | `1000` |
| `LOGIN_SERVER_PORT` | Login Server ポート | `8080` |
