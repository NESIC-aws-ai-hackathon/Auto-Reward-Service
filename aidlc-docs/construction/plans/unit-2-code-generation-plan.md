# Unit 2 Code Generation Plan

**作成日**: 2026-05-16  
**Unit**: Unit 2 — リワードちゃんキャラクター  
**対応機能スライス**: 2-1〜2-9 + schemas.py (Unit 0 未生成分)

---

## 対応ストーリー

| スライス | 機能 | 対応要件 |
|---|---|---|
| 0-2 (未生成) | `schemas.py`: Pydantic モデル | Unit 0 成果物補完 |
| 2-1 | `intent_prompt.py` + `intent_classifier.py` | F3-01 |
| 2-2 | `character_prompts.py` + `character_reply.py` | F3-02/03 |
| 2-3 | 感情・疲労度推定（`_infer_emotion`） | F3-04 |
| 2-4 | `onboarding_flow.py` | F2-01〜F2-06 |
| 2-5 | CHAT ログ保存 | F3-05 |
| 2-6 | `webhook_handler.py` ルーティング統合 | F1-02 |
| 2-7 | PREF_MEMORY 自動蓄積 | F3-04 |
| 2-8 | LLM 品質テスト | TEST-01 |
| 2-9 | 記念日自然収集 | F2-06 |

---

## 生成ファイル一覧

| ステップ | ファイル | 操作 |
|---|---|---|
| 1 | `layer/python/models/__init__.py` | 新規作成 |
| 1 | `layer/python/models/schemas.py` | 新規作成 |
| 2 | `layer/python/services/dynamodb_service.py` | 更新（query limit + atomic counter 追加） |
| 3 | `src/prompts/__init__.py` | 新規作成 |
| 3 | `src/prompts/intent_prompt.py` | 新規作成 |
| 4 | `src/prompts/character_prompts.py` | 新規作成 |
| 5 | `src/handlers/intent_classifier.py` | 新規作成 |
| 6 | `src/handlers/character_reply.py` | 新規作成 |
| 7 | `src/handlers/onboarding_flow.py` | 新規作成 |
| 8 | `src/handlers/webhook_handler.py` | 更新（Unit 2 ルーティング統合） |
| 9 | `template.yaml` | 更新（DAILY_CHAT_LIMIT / CodeUri / Handler） |
| 10 | `tests/unit/conftest.py` | 更新（src/prompts パス追加 / DAILY_CHAT_LIMIT env） |
| 11 | `tests/unit/test_intent_classifier.py` | 新規作成 |
| 11 | `tests/unit/test_character_reply.py` | 新規作成 |
| 11 | `tests/unit/test_onboarding_flow.py` | 新規作成 |
| 12 | `tests/llm/test_intent_quality.py` | 新規作成 |

---

## 詳細ステップ

- [ ] **Step 1**: `layer/python/models/schemas.py` 生成
  - `UserProfile` (bonus_months / bonus_amount / birthday / anniversaries フィールド含む)
  - `ChatLog`, `LifeLog`, `PendingExpense`, `PrefMemory`, `PrefItem`
  - `GoogleOAuth`, `Expense`, `FixedCostItem`, `FixedCosts`
  - `RewardPool`, `RewardPoolItem`, `RewardSuggestion`
  - `layer/python/models/__init__.py` 生成

- [ ] **Step 2**: `layer/python/services/dynamodb_service.py` 更新
  - `query_by_pk()` に `limit` / `descending` パラメータ追加
  - `increment_atomic_counter()` メソッド追加（UpdateItem ADD 1）

- [ ] **Step 3**: `src/prompts/intent_prompt.py` 生成
  - `INTENT_SYSTEM_PROMPT`: Intent 分類システムプロンプト + プロンプトインジェクション防御
  - `build_intent_prompt(user_message: str) -> str`: `<user_message>` タグ囲み

- [ ] **Step 4**: `src/prompts/character_prompts.py` 生成
  - `CHARACTER_SYSTEM_PROMPTS`: 口調別 (friendly / polite / devilish) システムプロンプト
  - `build_character_prompt(ctx: dict) -> str`: コンテキスト埋め込み

- [ ] **Step 5**: `src/handlers/intent_classifier.py` 生成
  - `classify_intent(text: str) -> dict`: Nova Micro 呼び出し → IntentResult 返却
  - フォールバック: `BedrockError` → `{"intent": "UNKNOWN", "confidence": 0.0}`

- [ ] **Step 6**: `src/handlers/character_reply.py` 生成
  - `generate_reply(user_id: str, intent: str, text: str, reply_token: str, ddb) -> str`
  - `_infer_emotion(text: str) -> dict`: ルールベース感情推定
  - `_load_recent_chats(user_id: str, ddb, limit=5) -> list`
  - フォールバックチェーンパターン適用

- [ ] **Step 7**: `src/handlers/onboarding_flow.py` 生成
  - `handle_onboarding(user_id: str, text: str, state: dict | None, ddb) -> str`
  - 状態機械: WAITING_INCOME → WAITING_FIXED_COSTS → CONFIRM_REWARD_BUDGET → WAITING_BONUS → WAITING_BIRTHDAY → COMPLETED
  - ご褒美枠算出: `max(3000, min(余剰 * 0.15, 30000))`

- [ ] **Step 8**: `src/handlers/webhook_handler.py` 更新
  - `_route_message()` 更新:
    - 入力長ガード (> 1000 文字)
    - DAILY_COUNT チェック (`increment_atomic_counter` → BR-2-12)
    - `classify_intent()` 呼び出し
    - Intent ディスパッチ (ONBOARDING / EXPENSE stub / REWARD stub / その他)
    - Reply-First / Log-Later パターン
    - `_save_chat_log()`: PutItem CHAT
    - `_detect_preferences()`: キーワードマッチ → PutItem PREF_MEMORY
  - `_route_event()` 更新: `follow` イベントでオンボーディング開始

- [ ] **Step 9**: `template.yaml` 更新
  - Globals に `DAILY_CHAT_LIMIT: "50"` 追加
  - `WebhookHandlerFunction.CodeUri`: `src/handlers/` → `src/`
  - `WebhookHandlerFunction.Handler`: `webhook_handler.handler` → `handlers/webhook_handler.handler`

- [ ] **Step 10**: `tests/unit/conftest.py` 更新
  - `src/prompts/` を sys.path に追加
  - `DAILY_CHAT_LIMIT=50` env 追加

- [ ] **Step 11**: ユニットテスト生成
  - `tests/unit/test_intent_classifier.py`
  - `tests/unit/test_character_reply.py`
  - `tests/unit/test_onboarding_flow.py`

- [ ] **Step 12**: LLM 品質テスト生成
  - `tests/llm/test_intent_quality.py`
  - `tests/llm/__init__.py`

---

## 依存関係

| 依存先 | 提供するもの |
|---|---|
| Unit 0: `layer/python/services/bedrock_service.py` | `BedrockService.invoke_text()` |
| Unit 0: `layer/python/services/dynamodb_service.py` | CRUD + 追加メソッド |
| Unit 0: `layer/python/services/line_service.py` | `reply_message()` |
| Unit 1: `src/handlers/webhook_handler.py` | 更新対象（ルーティング統合） |

---

## 完了条件

- `pytest tests/unit/ -v` が全テスト PASS
- `sam build` が成功
- LINE から「疲れた」送信 → リワードちゃん口調の返答（Deploy Round 3 で確認）
