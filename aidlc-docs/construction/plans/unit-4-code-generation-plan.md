# Unit 4 Code Generation Plan

**作成日**: 2026-05-16  
**Unit**: Unit 4 — ご褒美候補プール  
**対応機能スライス**: 4-1〜4-6

---

## 対応ストーリー

| スライス | 機能 | 対応要件 |
|---|---|---|
| 4-1 | `rakuten_service.py`: 楽天ウェブサービスAPI商品検索 | F5-03 |
| 4-2 | `reward_pool_service.py`: 嗜好×候補スコアリングロジック | F5-01 |
| 4-3 | `reward_pool_updater.py`: 全ユーザー嗜好取得→楽天API→プール更新 | F5-02 |
| 4-4 | EventBridge Scheduler SAMリソース定義（RewardPoolScheduler） | F5-02 |
| 4-5 | スルー・購入履歴によるスコア調整（adjust_score） | F5-04, F5-05 |
| 4-6 | 楽天APIモックテスト | TEST-04 |

---

## 生成ファイル一覧

| ステップ | ファイル | 操作 |
|---|---|---|
| 1 | `layer/python/services/rakuten_service.py` | 新規作成 |
| 2 | `layer/python/services/reward_pool_service.py` | 新規作成 |
| 3 | `src/handlers/reward_pool_updater.py` | 新規作成 |
| 4 | `template.yaml` | 更新（RewardPoolUpdaterFunction + RewardPoolScheduler + LogGroup + SchedulerExecutionRole更新） |
| 5 | `tests/unit/conftest.py` | 更新（RAKUTEN_DEFAULT_KEYWORDS 等の env var 追加） |
| 6 | `tests/unit/test_rakuten_service.py` | 新規作成 |
| 7 | `tests/unit/test_reward_pool_service.py` | 新規作成 |
| 8 | `tests/unit/test_reward_pool_updater.py` | 新規作成 |

---

## 詳細ステップ

- [x] **Step 1**: `layer/python/services/rakuten_service.py` 生成
  - `RakutenProduct` dataclass または pydantic モデル（schemas.py に追加せず service 内 private）
  - `RakutenAPIError` カスタム例外
  - `_get_app_id()`: Secrets Manager キャッシュ（`get_secret(RAKUTEN_SECRET_NAME)["RAKUTEN_APP_ID"]`）
  - `_call_with_retry()`: 最大3回リトライ + exponential backoff
  - `_parse_response()`: レスポンス→RakutenProduct変換（itemName100文字トリム・imageUrl抽出）
  - `search_products(keyword, hits)`: メイン関数（レートリミットsleep含む）

- [x] **Step 2**: `layer/python/services/reward_pool_service.py` 生成
  - `build_keywords(pref: PrefMemory, defaults: list[str]) -> list[str]`: categories+items混合
  - `score_items(products: list[RakutenProduct], keywords: list[str]) -> list[RewardPoolItem]`: スコアリング
  - `merge_pool(existing: list[RewardPoolItem], new_items: list[RewardPoolItem]) -> list[RewardPoolItem]`: 差分マージ
  - `adjust_score(user_pk: str, item_id: str, outcome: str, ddb: DynamoDBService) -> None`: フィードバック反映

- [x] **Step 3**: `src/handlers/reward_pool_updater.py` 生成
  - `lambda_handler(event, context)`: エントリポイント
  - `_get_all_user_pks(ddb)`: GSI query（entityType=PROFILE）→ PKリスト
  - `_update_user_pool(user_pk, ddb)`: per-user 更新ループ
  - `PoolUpdateResult` dataclass（domain-entities.md 定義）
  - `MAX_RAKUTEN_REQUESTS = 900` ガード

- [x] **Step 4**: `template.yaml` 更新
  - `RewardPoolUpdaterFunction` Lambda（Timeout: 300, MemorySize: 256）
  - `RewardPoolUpdaterFunctionLogGroup` CloudWatch Logs
  - `SchedulerExecutionRole` に RewardPoolUpdaterFunction への InvokeFunction 追加
  - `RewardPoolScheduler` EventBridge Scheduler（cron(0 17 * * ? *)）

- [x] **Step 5**: `tests/unit/conftest.py` 更新
  - `RAKUTEN_DEFAULT_KEYWORDS`, `RAKUTEN_MAX_ITEMS_PER_POOL`, `RAKUTEN_HITS_PER_KEYWORD` env var 追加

- [x] **Step 6**: `tests/unit/test_rakuten_service.py` 生成
  - `requests.get` モックで正常系・異常系テスト
  - リトライロジックテスト（3回試行）
  - レスポンスパーステスト（itemName切り詰め等）

- [x] **Step 7**: `tests/unit/test_reward_pool_service.py` 生成
  - `build_keywords()`: 嗜好あり・なし・混合テスト
  - `score_items()`: スコア算出テスト（0.0〜1.0範囲確認）
  - `merge_pool()`: 差分マージ・20件上限・outcome保持テスト
  - `adjust_score()`: DynamoDBモック + スコア変化テスト

- [x] **Step 8**: `tests/unit/test_reward_pool_updater.py` 生成
  - DynamoDB GSI mock（全ユーザーPK取得）
  - rakuten_service mock
  - `lambda_handler` 正常系・楽天API全失敗系テスト
