# NFR Design Patterns — Unit 4: ご褒美候補プール

**作成日**: 2026-05-16  
**Unit**: Unit 4 — ご褒美候補プール

---

## 1. Retry with Exponential Backoff パターン（楽天API）

**対応NFR**: PERF-4-02、AVAIL-4-01、BR-4-06

楽天APIの一時的な障害・タイムアウト時に自動リトライを行い、恒久的な障害時は既存プールを維持する。

```python
import time
import requests
from requests.exceptions import RequestException

MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds

def _call_with_retry(url: str, params: dict) -> dict:
    """
    楽天API呼び出しを最大3回リトライ（指数バックオフ）。
    全失敗時は RakutenAPIError を raise。
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=(3.0, 10.0))
            resp.raise_for_status()
            return resp.json()
        except RequestException as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                sleep_time = BACKOFF_BASE * (2 ** attempt)
                time.sleep(sleep_time)
    raise RakutenAPIError(f"楽天API {MAX_RETRIES}回リトライ失敗") from last_exc
```

| 項目 | 値 |
|------|-----|
| **最大リトライ回数** | 3回 |
| **バックオフ** | 1秒 → 2秒 → 4秒（指数バックオフ） |
| **timeout** | connect=3秒、read=10秒 |
| **全失敗時** | `RakutenAPIError` を raise → updater でキャッチ → そのユーザースキップ |

---

## 2. Module-Level Cache パターン（Secrets Manager）

**対応NFR**: PERF-4-03、COST-4-02

Lambda の実行コンテキスト内でシークレットを1回だけ取得し、以降は再利用する。

```python
# layer/python/services/rakuten_service.py
_RAKUTEN_APP_ID: str | None = None

def _get_app_id() -> str:
    global _RAKUTEN_APP_ID
    if _RAKUTEN_APP_ID is None:
        secrets = get_secrets()  # secrets.py
        _RAKUTEN_APP_ID = secrets["RAKUTEN_APP_ID"]
    return _RAKUTEN_APP_ID
```

| 項目 | 値 |
|------|-----|
| **キャッシュスコープ** | Lambda 実行コンテキスト（ウォームスタート時は再利用） |
| **キャッシュキー** | モジュールレベル変数 `_RAKUTEN_APP_ID` |
| **初期化** | `None` チェック → 初回のみ Secrets Manager から取得 |
| **セキュリティ** | メモリ内のみ保持。ログ出力・永続化なし |

---

## 3. Rate Limiter パターン（楽天API 1req/秒制限）

**対応NFR**: PERF-4-02

楽天ウェブサービスAPIの利用規約（1アプリIDあたり1リクエスト/秒）を遵守する。

```python
RAKUTEN_RATE_LIMIT_SLEEP = 1.0  # seconds between requests

def search_products(keyword: str, hits: int = 5) -> list[RakutenProduct]:
    # ... API呼び出し ...
    time.sleep(RAKUTEN_RATE_LIMIT_SLEEP)  # レートリミット遵守
    return products
```

| 項目 | 値 |
|------|-----|
| **スリープ時間** | 1.0秒（各キーワード検索後に挿入） |
| **適用箇所** | `rakuten_service.search_products()` の末尾 |
| **バースト考慮** | 3件連続後に1秒スリープではなく、毎回スリープ（シンプルで安全） |

---

## 4. Fail-Safe Default パターン（楽天API全障害時）

**対応NFR**: AVAIL-4-01、BR-4-06

楽天APIが全失敗した際にも既存のプールを壊さず、サービス継続を保証する。

```python
# reward_pool_updater.py
for user_pk in user_pks:
    try:
        _update_user_pool(user_pk, ddb_service)
        result.success_count += 1
    except RakutenAPIError as exc:
        logger.warning("pool_update_error", user_pk=user_pk, error=str(exc))
        result.error_count += 1
        # 既存プールは変更しない（DynamoDBへの書き込みは update_user_pool 内部で行うため、
        # 例外発生時は書き込みが発生しない）
        continue
```

| 項目 | 値 |
|------|-----|
| **フォールバック動作** | 既存 `REWARD_POOL#` を変更しない（書き込みが発生しないことで担保） |
| **エラー記録** | `WARNING` ログ + `result.error_count` カウント |
| **次回バッチ** | 翌日のバッチで再試行される |
| **Unit 5 への影響** | 古いプールでも提案は動作する（空プールの場合はデフォルト提案を Unit 5 で実装） |

---

## 5. 総リクエスト数ガードパターン（楽天API無料枠保護）

**対応NFR**: COST-4-01（BR追加）

楽天APIの無料枠（1日1,000リクエスト）を超過しないよう、バッチ実行中にカウントして上限に近づいたら停止する。

```python
MAX_RAKUTEN_REQUESTS = 900  # 1000のうち900でセーフティストップ

total_requests = 0
for user_pk in user_pks:
    keywords = _get_keywords(user_pk)
    if total_requests + len(keywords) > MAX_RAKUTEN_REQUESTS:
        logger.warning("rakuten_request_limit_reached", remaining_users=len(remaining))
        result.skip_count += len(remaining)
        break
    # ... API呼び出し ...
    total_requests += len(keywords)
```

| 項目 | 値 |
|------|-----|
| **上限値** | 900リクエスト（1,000枠の90%でストップ） |
| **超過時** | 残りユーザーをスキップ（翌日に自動更新） |
| **ログ** | `WARNING: rakuten_request_limit_reached` |
