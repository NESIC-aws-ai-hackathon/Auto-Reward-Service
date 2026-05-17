# NFR Design Patterns — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**Unit**: Unit 1 — LINE Bot基盤

---

## 1. レジリエンスパターン（Resilience Patterns）

### 1.1 エラー封じ込めパターン（Error Containment）

WebhookHandler は LINE Platform に対して常に HTTP 200 を返す必要がある。内部例外を HTTP 500 に変換しないよう、トップレベルで例外を封じ込める。

```python
def handler(event: dict, context) -> dict:
    # ウォームアップ判定（最優先）
    if event.get("source") == "warmup":
        return {"statusCode": 200, "body": "warm"}

    # 署名検証（失敗のみ 403）
    body = event.get("body", "") or ""
    signature = _get_signature(event)
    if not signature or not _get_line_service().verify_signature(body, signature):
        logger.warning("signature_verification_failed")
        return {"statusCode": 403, "body": "Forbidden"}

    # イベント処理（全例外を封じ込め → 200 返却）
    try:
        events = json.loads(body).get("events", [])
        for line_event in events:
            try:
                _route_event(line_event)
            except Exception as e:
                _handle_error(line_event, e)
    except Exception:
        logger.exception("webhook_body_parse_error")

    return {"statusCode": 200, "body": "OK"}
```

| 項目 | 値 |
|------|-----|
| **パターン** | Error Containment（例外封じ込め） |
| **403 返却条件** | 署名検証失敗のみ |
| **500 返却条件** | なし（LINE Platform リトライ防止） |
| **イベントループ例外** | 個別イベント単位で catch → フォールバック Reply |
| **Body パース失敗** | ログのみ → 200 返却 |

### 1.2 フォールバック Reply パターン

処理中に例外が発生した場合でも、可能であれば LINE ユーザーにリワードちゃん口調のエラーメッセージを返す。

```python
ERROR_REPLY = "ちょっと調子が悪いみたい…またあとで話しかけてね🥲"

def _handle_error(event: dict, error: Exception) -> None:
    logger.exception("event_processing_error", error=str(type(error).__name__))
    reply_token = event.get("replyToken")
    if not reply_token:
        return
    try:
        _get_line_service().reply_message(
            reply_token, [TextMessage(text=ERROR_REPLY)]
        )
    except Exception:
        # Reply 自体の失敗はログのみ（二重障害防止）
        logger.warning("fallback_reply_failed")
```

| 項目 | 値 |
|------|-----|
| **パターン** | Fallback Reply |
| **エラー文言** | 固定（`ERROR_REPLY` 定数） |
| **二重障害防止** | Reply 失敗を握りつぶし、ログのみ |

### 1.3 LINE API リトライなしパターン（Unit 0 継承）

reply_message / push_message は冪等性が保証できないためリトライなし。失敗時は即 `LineServiceError` を raise。

---

## 2. パフォーマンスパターン（Performance Patterns）

### 2.1 ウォームアップ ping パターン（Unit 0 継承）

```python
# handler 先頭で即リターン
if event.get("source") == "warmup":
    return {"statusCode": 200, "body": "warm"}
```

| 項目 | 値 |
|------|-----|
| **スケジュール** | EventBridge 5 分毎 |
| **ペイロード** | `{"source": "warmup"}` |
| **効果** | コールドスタートによる応答遅延を防止 |

### 2.2 LineService シングルトンパターン（Unit 0 継承）

```python
# モジュールレベルキャッシュ（コールドスタート時のみ初期化）
_line_service: Optional[LineService] = None

def _get_line_service() -> LineService:
    global _line_service
    if _line_service is None:
        secrets = get_line_secrets()
        _line_service = LineService(
            channel_secret=secrets["channel_secret"],
            channel_access_token=secrets["channel_access_token"],
        )
    return _line_service
```

| 項目 | 値 |
|------|-----|
| **パターン** | Module-Level Singleton |
| **初期化タイミング** | コールドスタート時（最初の非 warmup 呼び出し） |
| **再利用** | ウォームインボケーションで boto3 接続と LINE SDK クライアントを再利用 |

### 2.3 シークレットキャッシュパターン（Unit 0 継承）

`get_line_secrets()` は `secrets.py` のモジュールレベルキャッシュを使用。コールドスタート後の 2 回目以降の呼び出しは Secrets Manager を呼ばない。

---

## 3. セキュリティパターン（Security Patterns）

### 3.1 署名検証ガードパターン

```
Request → [ Warmup Check ] → [ Signature Guard ] → [ Event Processing ]
                               ↓ 失敗時
                             403 Forbidden（処理なし）
```

| 項目 | 値 |
|------|-----|
| **パターン** | Security Guard（入口でブロック） |
| **検証アルゴリズム** | HMAC-SHA256（`line_service.verify_signature()` 使用） |
| **ヘッダー名** | `x-line-signature`（大文字小文字不問で検索） |
| **ヘッダーなし** | 403 返却（攻撃者へのヒント最小化） |

### 3.2 PII ガードパターン（Unit 0 継承）

```python
logger = get_logger(__name__)  # PIIMaskingLogger
# line_user_id, message フィールドは自動マスク
logger.info("event_received", event_type=event.get("type"))
# → user_id は絶対ログに含めない
```

---

## 4. スケーラビリティパターン（Scalability Patterns）

### 4.1 API Gateway スロットリング（Unit 1 新規）

API Gateway HTTP API v2 のデフォルトルートスロットリングを制限。

```yaml
# template.yaml 設定イメージ
WebhookApi:
  Type: AWS::Serverless::HttpApi
  Properties:
    DefaultRouteSettings:
      ThrottlingBurstLimit: 200
      ThrottlingRateLimit: 100
```

| 項目 | 値 |
|------|-----|
| **定常レート** | 100 req/s |
| **バーストリミット** | 200 req |
| **超過時** | API Gateway が 429 Too Many Requests を返す（Lambda 到達前） |
| **LINE Platform への影響** | 正常時は 1 req/s 未満。十分な余裕 |
