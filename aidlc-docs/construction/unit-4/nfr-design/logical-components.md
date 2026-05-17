# 論理コンポーネント — Unit 4: ご褒美候補プール

**作成日**: 2026-05-16  
**Unit**: Unit 4 — ご褒美候補プール

---

## コンポーネント一覧

```
EventBridge Scheduler (cron: UTC 17:00 = JST 02:00)
    │
    └─► RewardPoolUpdaterFunction (Lambda, 300秒タイムアウト)
            │
            ├── reward_pool_updater.lambda_handler()   [Layer外: src/handlers/]
            │       ├── DynamoDB Scan (GSI: entityType=PROFILE → 全ユーザーPK)
            │       ├── ループ: per-user update
            │       │       ├── reward_pool_service.build_keywords()
            │       │       ├── rakuten_service.search_products()  [Layer: services/]
            │       │       └── reward_pool_service.merge_pool()
            │       └── logger.info(PoolUpdateResult)
            │
            ├── rakuten_service (Layer: layer/python/services/rakuten_service.py)
            │       ├── _get_app_id()      [Secrets Manager キャッシュ]
            │       ├── search_products()  [HTTP GET + Retry + RateLimit]
            │       └── _parse_response()  [RakutenProduct 変換]
            │
            └── reward_pool_service (Layer: layer/python/services/reward_pool_service.py)
                    ├── build_keywords()   [PrefMemory → キーワードリスト]
                    ├── score_items()      [RakutenProduct → RewardPoolItem + スコア]
                    ├── merge_pool()       [差分マージ + 上位20件選択]
                    └── adjust_score()     [スルー/購入フィードバック適用]
```

---

## コンポーネント詳細

### 1. reward_pool_updater.py（src/handlers/）

| 項目 | 内容 |
|------|------|
| **責務** | Lambda エントリポイント。全ユーザーを取得し、per-user 更新ループを実行 |
| **入力** | EventBridge Scheduled Event（ペイロード不要） |
| **出力** | なし（CloudWatch Logs に PoolUpdateResult を出力） |
| **依存** | `dynamodb_service`, `rakuten_service`, `reward_pool_service`, `secrets`, `logger` |
| **エラー処理** | per-user 例外は吸収してカウント。Lambda自体は正常終了 |

```python
def lambda_handler(event: dict, context: Any) -> None:
    ddb = DynamoDBService(table_name=TABLE_NAME)
    result = PoolUpdateResult(executed_at=now_iso())
    user_pks = _get_all_user_pks(ddb)
    result.total_users = len(user_pks)
    
    total_requests = 0
    for user_pk in user_pks:
        if total_requests >= MAX_RAKUTEN_REQUESTS:
            result.skip_count += 1
            continue
        try:
            fetched = _update_user_pool(user_pk, ddb)
            result.success_count += 1
            result.total_items_fetched += fetched
            total_requests += _keyword_count_for(user_pk)
        except RakutenAPIError as exc:
            logger.warning("pool_update_error", user_pk=user_pk, error=str(exc))
            result.error_count += 1
        except Exception as exc:
            logger.error("pool_update_unexpected_error", user_pk=user_pk, error=str(exc))
            result.error_count += 1
    
    logger.info("pool_update_complete", **result.model_dump())
```

---

### 2. rakuten_service.py（layer/python/services/）

| 項目 | 内容 |
|------|------|
| **責務** | 楽天ウェブサービスAPIのHTTP呼び出し・レスポンスパース |
| **パブリックAPI** | `search_products(keyword: str, hits: int) -> list[RakutenProduct]` |
| **内部** | `_get_app_id()`, `_call_with_retry()`, `_parse_response()` |
| **キャッシュ** | `_RAKUTEN_APP_ID` モジュール変数 |
| **レートリミット** | `time.sleep(1.0)` を各呼び出し後に挿入 |

```python
RAKUTEN_SEARCH_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
RAKUTEN_RATE_LIMIT_SLEEP = 1.0

def search_products(keyword: str, hits: int = 5) -> list[RakutenProduct]:
    app_id = _get_app_id()
    params = {
        "applicationId": app_id,
        "keyword": keyword,
        "hits": hits,
        "sort": "+reviewAverage",
        "minPrice": 300,
        "maxPrice": 50000,
        "formatVersion": 2,
    }
    data = _call_with_retry(RAKUTEN_SEARCH_URL, params)
    products = _parse_response(data)
    time.sleep(RAKUTEN_RATE_LIMIT_SLEEP)
    return products
```

---

### 3. reward_pool_service.py（layer/python/services/）

| 項目 | 内容 |
|------|------|
| **責務** | キーワード生成・スコアリング・差分マージ・スコア調整 |
| **パブリックAPI** | `build_keywords()`, `score_items()`, `merge_pool()`, `adjust_score()` |
| **副作用** | `adjust_score()` は DynamoDB を直接更新（ddb_service を受け取る） |

```python
def build_keywords(pref: PrefMemory, defaults: list[str]) -> list[str]:
    """嗜好から楽天API検索キーワードを最大5件生成。"""
    keywords: list[str] = []
    # categories から最大2件
    keywords.extend(pref.categories[:2])
    # positive items から detected_at 新しい順に上位3件
    positive = sorted(
        [i for i in pref.items if i.sentiment == "positive"],
        key=lambda x: x.detected_at or "",
        reverse=True,
    )
    keywords.extend([i.keyword for i in positive[:3]])
    # 重複排除
    keywords = list(dict.fromkeys(keywords))
    # 空の場合はデフォルト使用
    return keywords[:5] if keywords else defaults[:5]
```

---

### 4. EventBridge Scheduler（RewardPoolScheduler）

| 項目 | 内容 |
|------|------|
| **リソース種別** | AWS::Scheduler::Schedule |
| **スケジュール式** | `cron(0 17 * * ? *)` （UTC 17:00 = JST 02:00） |
| **ターゲット** | `RewardPoolUpdaterFunction` ARN |
| **ロール** | `SchedulerRole`（`lambda:InvokeFunction` のみ）|
| **Flexible Time Window** | `FLEXIBLE_TIME_WINDOW_OFF` |
| **SAMリソース名** | `RewardPoolScheduler` |

---

## データフロー図

```
DynamoDB (ArsTable)
  PROFILE# (entityType=PROFILE)
    ↓ [GSI Scan]
  user_pk リスト
    ↓ [per-user loop]
  PREF_MEMORY# + REWARD_POOL# (既存)
    ↓ [build_keywords]
  キーワードリスト (最大5件)
    ↓ [search_products × N]
Rakuten API
  商品リスト (最大25件)
    ↓ [score_items]
  スコア付き RewardPoolItem リスト
    ↓ [merge_pool]
  差分マージ済み上位20件
    ↓ [put_item]
DynamoDB (ArsTable)
  REWARD_POOL# (更新済み)
```
