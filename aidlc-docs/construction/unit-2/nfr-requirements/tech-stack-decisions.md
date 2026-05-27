# テックスタック決定 — Unit 2: リワードちゃんキャラクター

**作成日**: 2026-05-16  
**Unit**: Unit 2 — LINE Bot会話

---

## 確定テックスタック

Unit 2 は Unit 0/1 で確立したスタックを継承し、Bedrock Nova Micro と DynamoDB アクセスを追加する。

---

## 1. AI / LLM

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **Intent 分類モデル** | Amazon Bedrock Nova Micro | 低レイテンシ・低コスト。Intent 分類は短いプロンプトで十分 |
| **応答生成モデル** | Amazon Bedrock Nova Micro | キャラクター応答も Nova Micro で十分な品質。Lite は Unit 3 画像解析用 |
| **画像解析モデル** | Amazon Bedrock Nova Lite | Unit 3 で追加（本 Unit では未使用） |
| **呼び出し API** | `bedrock-runtime.invoke_model` | 既存 `bedrock_service.invoke_text()` を使用 |
| **モデル ID** | `amazon.nova-micro-v1:0` | Layer の `bedrock_service.py` に定数定義 |

---

## 2. Lambda 関数（更新内容のみ）

| 項目 | 決定内容 | 根拠 |
|------|---------|------|
| **メモリ** | 256 MB（継承・変更なし） | Unit 1 設定で既に Bedrock を考慮済み |
| **タイムアウト** | 10 秒（継承・変更なし） | Bedrock タイムアウト 5 秒 + バッファ |
| **ランタイム** | python3.13 | Unit 0/1 実績値 |
| **Lambda Layer** | `ArsCommonLayer` 継承 | `boto3`, `linebot.v3`, `pydantic`, `aws-lambda-powertools` を含む |
| **新規モジュール追加** | Layer 変更なし | 新規コードは `src/handlers/` と `src/prompts/` に配置 |

---

## 3. DynamoDB アクセスパターン

Unit 0 で確立したシングルテーブル設計（`ArsTable`）に対し以下のアクセスを追加する。

| エンティティ | PK | SK | 操作 |
|---|---|---|---|
| ユーザープロファイル | `USER#{userId}` | `PROFILE` | GetItem |
| オンボーディング状態 | `USER#{userId}` | `ONBOARDING_STATE` | GetItem / PutItem / DeleteItem |
| 日次会話カウント | `USER#{userId}` | `DAILY_COUNT#{YYYY-MM-DD}` | UpdateItem (ADD 1), GetItem |
| チャットログ | `USER#{userId}` | `CHAT#{ISO8601}` | PutItem / Query (begins_with CHAT, Limit=5) |
| 嗜好メモリ | `USER#{userId}` | `PREF_MEMORY#{category}#{keyword}` | PutItem |

---

## 4. IAM 権限追加

Unit 2 で `ArsLambdaRole` に追加する最小権限:

```yaml
- Effect: Allow
  Action:
    - bedrock:InvokeModel
  Resource:
    - arn:aws:bedrock:ap-northeast-1::foundation-model/amazon.nova-micro-v1:0
- Effect: Allow
  Action:
    - dynamodb:GetItem
    - dynamodb:PutItem
    - dynamodb:UpdateItem
    - dynamodb:DeleteItem
    - dynamodb:Query
  Resource:
    - !GetAtt ArsTable.Arn
    - !Sub "${ArsTable.Arn}/index/*"
```

> Unit 1 で `secretsmanager:GetSecretValue` は付与済み。DynamoDB 権限は Unit 2 で初めて追加。

---

## 5. 環境変数追加

`WebhookHandlerFunction` に追加する環境変数:

| 変数名 | 値 | 用途 |
|---|---|---|
| `DAILY_CHAT_LIMIT` | `50` | 1日会話上限（COST-01） |
| `BEDROCK_REGION` | `ap-northeast-1` | Bedrock エンドポイントリージョン |
| `NOVA_MICRO_MODEL_ID` | `amazon.nova-micro-v1:0` | モデル ID |

---

## 6. 新規ソースファイル構成

```
src/
  handlers/
    webhook_handler.py    # Unit 2 ルーティング統合（更新）
    intent_classifier.py  # Intent 分類ロジック（新規）
    character_reply.py    # キャラクター応答生成（新規）
    onboarding_flow.py    # オンボーディング状態機械（新規）
  prompts/
    intent_prompt.py      # Intent 分類プロンプトテンプレート（新規）
    character_prompts.py  # キャラクター応答プロンプトテンプレート（新規）
tests/
  unit/
    test_intent_classifier.py   # Intent 分類ユニットテスト（新規）
    test_character_reply.py     # キャラクター応答ユニットテスト（新規）
    test_onboarding_flow.py     # オンボーディングユニットテスト（新規）
  llm/
    test_intent_quality.py      # LLM 品質テスト（新規）
```

---

## 7. 観測性

Unit 1 設定継承。Unit 2 追加のログポイントは `nfr-requirements.md` MAINT-01 を参照。
