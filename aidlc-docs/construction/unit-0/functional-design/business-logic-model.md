# Business Logic Model — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16

---

## 1. サービス層の責務マップ

```
src/services/
├── dynamodb_service.py      ← DynamoDB CRUD + GSI クエリ
├── bedrock_service.py       ← Bedrock テキスト/画像推論
├── line_service.py          ← LINE API 薄いラッパー
├── google_calendar_service.py ← Google Calendar OAuth + イベント取得
└── (rakuten_service.py)     ← Unit 4 で追加

src/utils/
├── secrets.py               ← Secrets Manager / SSM 取得・キャッシュ
├── logger.py                ← aws-lambda-powertools Logger + PII マスク
└── exceptions.py            ← 独自例外クラス

src/models/
└── schemas.py               ← Pydantic v2 エンティティモデル全定義
```

---

## 2. DynamoDBService

### 責務
- ArsTable への全 CRUD 操作を提供する単一窓口
- `ClientError` を `DynamoDBError` に変換して上位へ伝播

### メソッド一覧

| メソッド | シグネチャ | 説明 |
|---------|-----------|------|
| `put_item` | `(pk: str, sk: str, item: dict) → None` | アイテム作成・上書き |
| `get_item` | `(pk: str, sk: str) → dict \| None` | GetItem — 存在しない場合 None |
| `query_by_pk` | `(pk: str, sk_prefix: str = None) → List[dict]` | PK + SK プレフィックスでクエリ |
| `update_item` | `(pk: str, sk: str, updates: dict) → None` | 部分更新（UpdateExpression 自動生成） |
| `delete_item` | `(pk: str, sk: str) → None` | アイテム削除 |
| `query_by_gsi` | `(entity_type: str, filter_expr: dict = None) → List[dict]` | `entityType-index` GSI クエリ |

### 初期化

```python
class DynamoDBService:
    def __init__(self, table_name: str = None):
        self.table_name = table_name or os.environ["DYNAMODB_TABLE_NAME"]
        self._client = boto3.resource("dynamodb")
        self._table = self._client.Table(self.table_name)
```

### エラーハンドリング方針

```
boto3 ClientError
  → DynamoDBError(message, original_exception) を raise
  → 呼び出し元で catch して適切に処理
```

---

## 3. BedrockService

### 責務
- Amazon Bedrock Nova Micro（テキスト）/ Nova Lite（画像）の呼び出しを抽象化
- モデル ID は環境変数から取得（切り替え可能設計）

### メソッド一覧

| メソッド | シグネチャ | 説明 |
|---------|-----------|------|
| `invoke_text` | `(prompt: str, model_id: str = None, max_tokens: int = 1000) → str` | テキスト推論 |
| `invoke_image` | `(prompt: str, image_bytes: bytes, media_type: str = "image/jpeg", model_id: str = None) → str` | 画像+テキスト推論 |

### モデル選択ロジック

```
invoke_text(model_id=None)
  → model_id = os.environ.get("BEDROCK_TEXT_MODEL_ID", "amazon.nova-micro-v1:0")

invoke_image(model_id=None)
  → model_id = os.environ.get("BEDROCK_IMAGE_MODEL_ID", "amazon.nova-lite-v1:0")

invoke_text(model_id="anthropic.claude-haiku-...")
  → 引数で明示的に上書き可能
```

### 初期化

```python
class BedrockService:
    def __init__(self):
        self._client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "ap-northeast-1"))
        self.default_text_model = os.environ.get("BEDROCK_TEXT_MODEL_ID", "amazon.nova-micro-v1:0")
        self.default_image_model = os.environ.get("BEDROCK_IMAGE_MODEL_ID", "amazon.nova-lite-v1:0")
```

---

## 4. LineService（薄いラッパー）

### 責務
- `line-bot-sdk` v3 の薄いラッパー
- 公開するメソッドは3つのみに限定（`reply_message`, `push_message`, `verify_signature`）
- SDK の複雑な型を隠蔽してシンプルな引数で呼び出せるようにする

### メソッド一覧

| メソッド | シグネチャ | 説明 |
|---------|-----------|------|
| `verify_signature` | `(body: str, signature: str) → bool` | X-Line-Signature 検証 — 失敗時は `False` |
| `reply_message` | `(reply_token: str, messages: List[dict]) → None` | Reply API（最大5メッセージ） |
| `push_message` | `(user_id: str, messages: List[dict]) → None` | Push API（user_id は PII — ログ禁止） |
| `get_message_content` | `(message_id: str) → bytes` | 画像等コンテンツ取得 |

### メッセージdict形式

```python
# テキストメッセージ
{"type": "text", "text": "リワードちゃんのメッセージ"}

# Flex Message
{"type": "flex", "altText": "ご褒美提案", "contents": {...}}
```

### 初期化（Secrets キャッシュ利用）

```python
# モジュールレベルで初期化（コールドスタート時のみ実行）
_line_service: Optional[LineService] = None

def get_line_service() -> LineService:
    global _line_service
    if _line_service is None:
        secrets = get_secrets()  # secrets.py 経由
        _line_service = LineService(
            channel_secret=secrets["LINE_CHANNEL_SECRET"],
            channel_access_token=secrets["LINE_ACCESS_TOKEN"]
        )
    return _line_service
```

---

## 5. SecretsService

### 責務
- AWS Secrets Manager / SSM Parameter Store から秘匿値を取得
- モジュールレベルキャッシュによりコールドスタート時のみ取得（ウォームインボケーションで再利用）

### 取得する秘匿値一覧

| キー名 | 取得元 | 説明 |
|--------|--------|------|
| `LINE_CHANNEL_SECRET` | Secrets Manager | LINE チャネルシークレット |
| `LINE_ACCESS_TOKEN` | Secrets Manager | LINE チャネルアクセストークン |
| `RAKUTEN_APP_ID` | Secrets Manager | 楽天 Application ID |
| `GOOGLE_CLIENT_ID` | Secrets Manager | Google OAuth クライアントID |
| `GOOGLE_CLIENT_SECRET` | Secrets Manager | Google OAuth クライアントシークレット |

### 実装パターン

```python
_cached_secrets: Optional[dict] = None

def get_secrets(secret_name: str = None) -> dict:
    global _cached_secrets
    if _cached_secrets is None:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=os.environ["SECRET_NAME"])
        _cached_secrets = json.loads(response["SecretString"])
    if secret_name:
        return _cached_secrets[secret_name]
    return _cached_secrets
```

---

## 6. Logger（PII マスク付き）

### 責務
- `aws-lambda-powertools` Logger を使った JSON 構造化ログ
- LINE userId・チャット内容・カレンダーイベント内容の自動マスク処理を集約

### PII マスク対象フィールド

| フィールド名 | マスク方式 | 例 |
|-------------|-----------|-----|
| `line_user_id` / `user_id` | 先頭6文字 + `***` | `Uab1cd***` |
| `message` / `chat_content` | 全マスク | `[MASKED]` |
| `refresh_token` | 全マスク | `[MASKED]` |
| `access_token` | 全マスク | `[MASKED]` |
| `calendar_*` | 全マスク | `[MASKED]` |

### 使用パターン

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("Webhook received", extra={"intent": "expense", "user_id": user_id})
# → user_id は自動マスク: {"intent": "expense", "user_id": "Uab1cd***"}
```

---

## 7. GoogleCalendarService

### 責務
- Google Calendar API との通信（OAuth 2.0 token 管理 + イベント取得）
- `access_token` は常に `refresh_token` から取得（DynamoDBやメモリへの保存なし）
- カレンダーイベントの内容・タイトルはログ出力・DynamoDB保存を一切しない

### メソッド一覧

| メソッド | シグネチャ | 説明 |
|---------|-----------|------|
| `is_connected` | `(user_id: str) → bool` | DynamoDB `GOOGLE_OAUTH#` SK の存在確認 |
| `save_refresh_token` | `(user_id: str, refresh_token: str, email_hint: str = None) → None` | refresh_token を DynamoDB に保存 |
| `revoke_and_delete` | `(user_id: str) → None` | Google に revoke + DynamoDB から削除 |
| `_get_refresh_token` | `(user_id: str) → str \| None` | DynamoDB から refresh_token 取得（プライベート） |
| `_refresh_access_token` | `(refresh_token: str) → str` | Google OAuth endpoint へリフレッシュ要求（プライベート） |
| `get_today_events` | `(user_id: str) → List[dict]` | 今日+明日のイベント取得（非連携時は空リスト） |
| `_build_calendar_context` | `(events: List[dict]) → str` | イベントリストを「今日3件会議、明日フリー」等の自然言語コンテキストに変換（Bedrockプロンプト用）。イベント内容はログ禁止 |

### get_today_events の処理フロー

```
get_today_events(user_id)
  1. is_connected(user_id) → False なら [] を返す
  2. _get_refresh_token(user_id) → refresh_token 取得
  3. _refresh_access_token(refresh_token) → access_token 取得（毎回リフレッシュ）
  4. Google Calendar API: GET /calendars/primary/events
     - timeMin = 今日 00:00 JST → UTC変換
     - timeMax = 明後日 00:00 JST → UTC変換（今日+明日分）
     - maxResults = 20
     - singleEvents = True
     - orderBy = startTime
  5. イベントリスト返却（内容はログ出力禁止）
```

### OAuth フロー（LIFF連携 — Unit 7 で実装）

```
[LIFF] → Google OAuth URL 生成 → ユーザー同意
  → コールバック URL → 認可コード取得
  → Google token endpoint: code → refresh_token + access_token
  → save_refresh_token(user_id, refresh_token, email_hint)
```

---

## 8. データフロー概略図

```
Lambda Handler
  ↓
secrets.get_secrets()          [モジュールレベルキャッシュ]
  ↓
line_service.verify_signature()
  ↓
dynamodb_service.get_item()    [ユーザープロファイル取得]
  ↓
bedrock_service.invoke_text()  [Intent分類 / キャラ応答生成]
  ↓
dynamodb_service.put_item()    [ログ・支出等保存]
  ↓
line_service.reply_message()   [LINE Reply]

Google Calendar フロー（Unit 5 で呼び出し）:
  google_calendar_service.get_today_events(user_id)
    ↓ is_connected チェック
    ↓ _get_refresh_token (DynamoDB)
    ↓ _refresh_access_token (Google OAuth)
    ↓ Calendar API fetch
    ↓ イベントリスト返却（DDB非保存）
```
