# NFR Design Patterns — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16

---

## 1. レジリエンスパターン（Resilience Patterns）

### 1.1 外部 API リトライ戦略（API 別使い分け）

#### Bedrock API — 指数バックオフリトライ

対象例外: `ThrottlingException`, `ServiceUnavailableException`, `ModelStreamErrorException`

```python
# bedrock_service.py 実装パターン
import time
from botocore.exceptions import ClientError

BEDROCK_RETRY_DELAYS = [0.5, 1.0, 2.0]  # 秒（最大3回）
BEDROCK_RETRYABLE_ERRORS = {
    "ThrottlingException",
    "ServiceUnavailableException",
    "ModelStreamErrorException",
}

def _invoke_with_retry(self, invoke_fn, *args, **kwargs):
    last_error = None
    for attempt, delay in enumerate(BEDROCK_RETRY_DELAYS):
        try:
            return invoke_fn(*args, **kwargs)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code not in BEDROCK_RETRYABLE_ERRORS:
                raise BedrockError(f"Non-retryable error: {error_code}", e)
            last_error = e
            if attempt < len(BEDROCK_RETRY_DELAYS) - 1:
                time.sleep(delay)
    raise BedrockError("Bedrock API failed after retries", last_error)
```

| 項目 | 値 |
|------|----|
| リトライ回数 | 最大 3 回 |
| バックオフ間隔 | 0.5s → 1.0s → 2.0s |
| リトライ対象 | ThrottlingException / ServiceUnavailableException |
| リトライ非対象 | ValidationException / ResourceNotFoundException など |

#### LINE API — リトライなし（冪等性なし）

```python
# line_service.py — リトライなし
# reply_message / push_message は冪等ではないため二重送信禁止
# エラー時は即 LineServiceError を raise
```

| 項目 | 値 |
|------|----|
| リトライ回数 | 0（即 raise） |
| 理由 | reply/push は冪等性が保証できない（二重送信 = ユーザー体験悪化） |

#### Google Calendar API — 固定インターバルリトライ

対象: HTTP 5xx エラー、429 Rate Limit

```python
# google_calendar_service.py 実装パターン
import time
import requests

GOOGLE_RETRY_COUNT = 2
GOOGLE_RETRY_DELAY = 1.0  # 秒（固定）
GOOGLE_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

def _request_with_retry(self, url, headers, params):
    last_error = None
    for attempt in range(GOOGLE_RETRY_COUNT + 1):
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code not in GOOGLE_RETRYABLE_STATUS:
            return response
        last_error = response
        if attempt < GOOGLE_RETRY_COUNT:
            time.sleep(GOOGLE_RETRY_DELAY)
    raise GoogleCalendarError(
        f"Google Calendar API failed after retries (status={last_error.status_code})"
    )
```

| 項目 | 値 |
|------|----|
| リトライ回数 | 最大 2 回 |
| インターバル | 1.0秒（固定） |
| リトライ対象 | HTTP 429 / 5xx |

---

## 2. パフォーマンスパターン（Performance Patterns）

### 2.1 boto3 クライアント モジュールレベルシングルトンパターン

サービスクラスをモジュールレベルでシングルトン化することで、コールドスタート後のウォームインボケーションで boto3 接続を再利用する。

```python
# 各 service ファイルの末尾に配置（共通パターン）
_instance: Optional[ServiceClass] = None

def get_service() -> ServiceClass:
    global _instance
    if _instance is None:
        _instance = ServiceClass()  # boto3 クライアントをコンストラクタで初期化
    return _instance
```

適用対象:

| サービスクラス | ゲッター関数 | boto3 クライアント |
|-------------|------------|-----------------|
| `DynamoDBService` | `get_dynamodb_service()` | `boto3.resource("dynamodb")` |
| `BedrockService` | `get_bedrock_service()` | `boto3.client("bedrock-runtime")` |
| `LineService` | `get_line_service()` | line-bot-sdk MessagingApi クライアント |
| `GoogleCalendarService` | `get_google_calendar_service()` | `requests.Session`（接続プール） |

> **注意**: `SecretsService` はモジュールレベルのグローバル変数（関数経由）でキャッシュ済み（Functional Design で確定）。

---

## 3. セキュリティパターン（Security Patterns）

### 3.1 Secrets Manager シークレット構成（サービス別分割）

| シークレット名 | 含まれるキー | Lambda 環境変数 |
|-------------|------------|---------------|
| `ars/line-{stage}` | `LINE_CHANNEL_SECRET`, `LINE_ACCESS_TOKEN` | `LINE_SECRET_NAME` |
| `ars/google-{stage}` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | `GOOGLE_SECRET_NAME` |
| `ars/rakuten-{stage}` | `RAKUTEN_APP_ID` | `RAKUTEN_SECRET_NAME` |

> `{stage}` = `dev` または `prod`（SAM の `StageName` パラメータで制御）

### 3.2 secrets.py の複数シークレット対応パターン

```python
# secrets.py — サービス別シークレットキャッシュ
_secret_cache: dict[str, dict] = {}

def get_secret(secret_name_env: str) -> dict:
    """
    secret_name_env: 環境変数名（例: "LINE_SECRET_NAME"）
    戻り値: シークレットの dict
    """
    secret_name = os.environ[secret_name_env]
    if secret_name not in _secret_cache:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_name)
        _secret_cache[secret_name] = json.loads(response["SecretString"])
    return _secret_cache[secret_name]

# 使用例
line_secret = get_secret("LINE_SECRET_NAME")  # → {"LINE_CHANNEL_SECRET": "...", "LINE_ACCESS_TOKEN": "..."}
```

### 3.3 IAM 最小権限パターン（Lambda 関数別）

各 Lambda 関数の IAM ポリシーには以下の原則を適用:
- Webhook Handler: DynamoDB(ArsTable) GetItem/PutItem/Query + Bedrock InvokeModel + Secrets Manager GetSecretValue(line-secret のみ)
- バッチ系: DynamoDB PutItem/UpdateItem/Query + Secrets Manager GetSecretValue(rakuten-secret のみ)
- LIFF API: DynamoDB GetItem/PutItem/UpdateItem + Secrets Manager GetSecretValue(google-secret のみ)

---

## 4. 可用性パターン（Availability Patterns）

### 4.1 非同期 Lambda エラーハンドリング（DLQ なし）

MVP 段階は DLQ なし。CloudWatch Logs のエラーアラートで検知。

```
EventBridge Scheduler → Lambda（非同期）
  ├ 成功 → 処理完了
  └ 失敗 → Lambda デフォルトリトライ（最大2回）→ CloudWatch Logs にエラー記録
```

> **将来対応**: ユーザー数増加時に SQS DLQ を RewardPoolUpdater / PushNotifier に追加予定。

### 4.2 Webhook Handler のエラーフォールバック

```python
# webhook_handler.py でのエラーハンドリングパターン（Unit 1 で実装）
try:
    reply_token = event["reply_token"]
    # ... 通常処理
except DynamoDBError as e:
    logger.error("DynamoDB error", error=str(e))
    line_service.reply_message(reply_token, [{"type": "text", "text": "ちょっと待ってて〜 すぐ戻ってくるね"}])
except BedrockError as e:
    logger.error("Bedrock error", error=str(e))
    line_service.reply_message(reply_token, [{"type": "text", "text": "今ちょっと考えすぎてた〜。もう1回送って？"}])
```
