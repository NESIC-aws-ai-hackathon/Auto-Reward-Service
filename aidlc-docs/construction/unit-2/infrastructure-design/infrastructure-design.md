# Infrastructure Design — Unit 2: リワードちゃんキャラクター

**作成日**: 2026-05-16  
**Unit**: Unit 2 — LINE Bot会話

---

## 1. インフラ決定事項サマリー

| 項目 | 決定値 | 根拠 |
|------|--------|------|
| 新規 Lambda 関数 | **なし** | `intent_classifier.py` / `character_reply.py` / `onboarding_flow.py` はすべて `WebhookHandlerFunction` 内モジュールとして動作 |
| 新規 API Gateway | **なし** | `WebhookApi` 継続使用（Unit 1 より） |
| 新規 IAM 権限 | **なし** | `bedrock:InvokeModel` / DynamoDB CRUD は Unit 0 `template.yaml` で定義済み |
| 新規 DynamoDB テーブル/GSI | **なし** | `ArsTable` 継続使用（Unit 0 より）。Unit 2 アクセスパターンはすべて PK/SK で解決可能 |
| 環境変数追加 | **`DAILY_CHAT_LIMIT: "50"`** | 1 日会話上限（BR-2-12・COST-01）。環境変数化で変更容易に |
| template.yaml 変更箇所 | **Globals.Environment.Variables に 1 行追加** | 上記環境変数のみ |

---

## 2. Unit 2 の template.yaml 差分

### 追加箇所: Globals → Environment → Variables

```yaml
# 変更前（Unit 1 現状）
Globals:
  Function:
    ...
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

# 変更後（Unit 2 追加）
Globals:
  Function:
    ...
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
        DAILY_CHAT_LIMIT: "50"    # ← Unit 2 追加
```

### 変更なし（Unit 0 で先行定義済み）

| リソース / 設定 | 状態 |
|---|---|
| `ArsBedrockPolicy` (`bedrock:InvokeModel`) | ✅ 定義済み (`Resource: "*"`) |
| `ArsDynamoDBPolicy` (GetItem/PutItem/UpdateItem/DeleteItem/Query) | ✅ 定義済み |
| `ArsSecretsManagerPolicy` (GetSecretValue) | ✅ 定義済み |
| `ArsTable` (DynamoDB PAY_PER_REQUEST, TTL 有効) | ✅ 定義済み |
| `BEDROCK_TEXT_MODEL_ID: "amazon.nova-micro-v1:0"` | ✅ 定義済み（Globals） |
| `BEDROCK_IMAGE_MODEL_ID: "amazon.nova-lite-v1:0"` | ✅ 定義済み（Globals） |
| `TABLE_NAME: !Ref ArsTable` | ✅ 定義済み（Globals） |
| `WebhookHandlerFunction` (256 MB / 10 s) | ✅ 定義済み（Unit 1） |
| `WarmupWebhookScheduler` (rate 5 min) | ✅ 定義済み（Unit 1） |

---

## 3. 既存 IAM ポリシー（変更なし・参考）

Unit 2 が使用する AWS サービス権限はすでに `ArsLambdaRole` に付与済み:

```yaml
# Unit 0 定義済み（抜粋）
- PolicyName: ArsDynamoDBPolicy
  PolicyDocument:
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
    Statement:
      - Effect: Allow
        Action:
          - bedrock:InvokeModel
        Resource: "*"
```

---

## 4. コード配置（新規ファイル）

新規ファイルはすべて `src/handlers/` または `src/prompts/` に配置。  
`WebhookHandlerFunction` の `CodeUri: src/handlers/` がすでに Lambda パッケージの起点となっているため、`src/prompts/` のモジュールも Python パスに含まれるよう `PYTHONPATH` 設定またはパッケージ構成で対応する。

| ファイル | 配置先 | Lambda からの import |
|---|---|---|
| `intent_classifier.py` | `src/handlers/` | `from intent_classifier import classify_intent` |
| `character_reply.py` | `src/handlers/` | `from character_reply import generate_reply` |
| `onboarding_flow.py` | `src/handlers/` | `from onboarding_flow import handle_onboarding` |
| `intent_prompt.py` | `src/prompts/` | `sys.path` に `src/` を追加（後述） |
| `character_prompts.py` | `src/prompts/` | 同上 |

### PYTHONPATH 対応

`src/handlers/` 直下に `webhook_handler.py` があり、`CodeUri: src/handlers/` の場合、`src/prompts/` は **Lambda パッケージに含まれない**。  
対応策: `src/handlers/` 配下に `prompts/` ディレクトリとしてシンボリックリンクまたはコピーを配置する代わりに、`CodeUri: src/` に変更して Handler を `handlers/webhook_handler.handler` に更新する方が保守性が高い。

**Unit 2 での決定**: `CodeUri: src/` へ変更し、Handler を `handlers/webhook_handler.handler` に更新。

```yaml
# 変更後（Unit 2）
WebhookHandlerFunction:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: WebhookHandlerFunction
    Handler: handlers/webhook_handler.handler   # ← 変更
    CodeUri: src/                               # ← 変更
    MemorySize: 256
    Timeout: 10
    ...
```

---

## 5. Deploy Round 3 確認内容

| 確認項目 | 手順 |
|---|---|
| SAM デプロイ成功 | `sam build && sam deploy --profile share` |
| Bedrock 呼び出し成功 | LINE から「疲れた」送信 → リワードちゃん口調の返答を確認 |
| オンボーディング起動 | 新規ユーザー or `PROFILE` 未登録状態で `こんにちは` 送信 → 月収質問が返る |
| 1日上限動作 | `DAILY_CHAT_LIMIT=2` に一時変更して 3 回目のメッセージで退場演出を確認 |
