# コンポーネントメソッド定義 — オートリワードサービス（v2）

**改訂日**: 2026-05-15 / コンセプト変更後版

> **注**: 詳細なビジネスロジック・バリデーションルールは Construction フェーズの Functional Design で定義します。
> 本ファイルは主要関数シグネチャ・入出力型・高レベルの目的を記載します。

---

## Lambda ハンドラー

### webhook_handler

```python
def handler(event: dict, context) -> dict:
    """
    LINE Webhookを受信し、署名検証後、メッセージ種別に応じて各ハンドラーにルーティングする。
    event: API Gateway Lambda Proxy Integration イベント
    Returns: {"statusCode": 200, "body": "OK"} （LINE Platformへの応答）
    Raises: 403 if signature verification fails
    """

def _verify_signature(body: str, signature: str) -> bool:
    """X-Line-Signature をチャネルシークレットで HMAC-SHA256 検証する。"""

def _route_message(event_type: str, message: dict, user_id: str) -> None:
    """メッセージ種別に応じて適切なハンドラーを呼び出す。
    text -> intent_classifier, image -> receipt_analyzer, other -> character_reply
    """
```

### intent_classifier

```python
def classify_intent(user_id: str, text: str) -> dict:
    """
    Nova MicroでテキストのIntentを分類する。
    直近のCHATログも参照してコンテキストを加味する。
    Returns: {"intent": "EXPENSE"|"REWARD"|"GREET"|"CHAT"|"ONBOARDING"|"UNKNOWN", "confidence": float}
    """

def _build_intent_prompt(text: str, recent_chats: list[dict]) -> str:
    """intent_prompt.py のテンプレートにテキスト・直近会話を埋め込む。"""

def _save_chat_log(user_id: str, role: str, text: str, intent: str) -> None:
    """DynamoDB CHAT#{isoTimestamp} にログ保存。"""
```

### character_reply

```python
def generate_reply(user_id: str, context: dict, tone_style: str = "friendly") -> str:
    """
    リワードちゃん口調のテキストをNova Microで生成する。
    context: {"text": str, "emotion": str|None, "recent_chats": list}
    tone_style: "friendly"|"polite"|"devilish"
    Returns: str（リワードちゃんの応答テキスト）
    """

def _build_character_prompt(context: dict, tone_style: str, profile: dict) -> str:
    """character_prompts.py の口調テンプレートにコンテキストを埋め込む。"""

def _infer_emotion(text: str, response: str) -> dict:
    """ユーザー発話から感情・疲労度を間接推定する。
    Returns: {"emotion": str, "fatigue_level": int (1-5)}
    """

def _save_lifelog(user_id: str, emotion: str, fatigue_level: int, inferred_from: str) -> None:
    """DynamoDB LIFELOG#{isoTimestamp} に保存。"""
```

### onboarding_flow

```python
def handle_onboarding(user_id: str, text: str) -> str:
    """
    初回登録チャットフロー。ステップに応じた質問・回答解析を行う。
    Returns: str（次の質問 or 登録完了メッセージ）
    """

def _get_current_step(user_id: str) -> int:
    """DynamoDB PROFILEからonboarding_stepを取得。未登録なら0。"""

def _parse_income(text: str) -> dict:
    """LLMで月収・ボーナス情報を抽出する。
    Returns: {"monthly_income": int, "bonus": int|None}
    """

def _parse_fixed_costs(text: str) -> list[dict]:
    """LLMで固定費項目を抽出する。
    Returns: [{"name": str, "amount": int}]
    """

def _calculate_initial_reward_limit(income: int, fixed_costs_total: int) -> int:
    """初期ご褒美枠を算出する。(income - fixed_costs_total) * 0.15"""

def _save_profile(user_id: str, profile: dict) -> None:
    """DynamoDB PROFILE# + FIXED_COSTS# に保存。"""
```

### expense_extractor

```python
def extract_expense(user_id: str, text: str) -> dict:
    """
    テキストから支出情報をJSON化する。信頼度が低い場合は確認フローを起動する。
    Returns: {"item": str, "amount": int|None, "ars_category": str, "confidence": float, "needs_confirm": bool}
    """

def _build_expense_prompt(text: str, recent_chats: list[dict]) -> str:
    """expense_prompt.py のテンプレートにテキスト・直近会話を埋め込む。"""

def _handle_confirmation(user_id: str, text: str, pending: dict) -> str:
    """確認フロー: yes→EXPENSE保存 / no→PENDING_EXPENSE削除。
    Returns: str（リワードちゃん口調の応答）
    """

def _save_pending_expense(user_id: str, expense: dict, message_id: str) -> None:
    """DynamoDB PENDING_EXPENSE# に仮保存。"""

def _confirm_expense(user_id: str, pending: dict) -> None:
    """PENDING_EXPENSE → EXPENSE#{isoTimestamp} に確定移動。"""
```

### receipt_analyzer

```python
def analyze_receipt(user_id: str, message_id: str) -> dict:
    """
    LINE Content APIで画像取得し、Nova Liteで支出情報を抽出する。
    Returns: {"store": str, "total": int, "items": list[{"name": str, "price": int}], "confidence": float}
    """

def _fetch_image(message_id: str) -> bytes:
    """LINE Content API で画像バイナリを取得する。"""

def _build_receipt_prompt() -> str:
    """receipt_prompt.py のレシート解析プロンプトを返す。"""

def _handle_async_fallback(user_id: str, message_id: str) -> str:
    """3秒超の場合「解析中だよ〜」Replyを返し、非同期で処理を継続する。
    Returns: str（「解析中だよ〜」メッセージ）
    """
```

### reward_proposal

```python
def propose_reward(user_id: str, context: dict) -> str:
    """
    余裕額チェック→候補マッチング→キャラ口調で提案。
    context: {"emotion": str, "fatigue_level": int}
    Returns: str（ご褒美提案 or 買いすぎ注意メッセージ）
    """

def _check_budget_and_select(user_id: str, context: dict) -> dict:
    """余裕額算出 + 候補選択を一括実行する。
    Returns: {"budget": int, "candidates": list[dict], "over_budget": bool}
    """

def _generate_proposal_message(candidates: list[dict], budget: int, tone_style: str) -> str:
    """候補からキャラ口調の提案メッセージを生成。"""

def _generate_stop_message(tone_style: str) -> str:
    """余裕額≦0時の「買いすぎストップ」メッセージ生成。"""

def _save_suggestion(user_id: str, candidate: dict) -> None:
    """DynamoDB REWARD_SUGGESTION#{isoTimestamp} に保存。"""
```

### reward_pool_updater

```python
def handler(event: dict, context) -> None:
    """
    EventBridge Scheduler から起動される日次バッチ。
    全ユーザーの候補プールを楽天APIで更新する。
    """

def _get_all_active_users() -> list[str]:
    """GSI1を使ってアクティブユーザー一覧を取得。"""

def _update_user_pool(user_id: str) -> None:
    """1ユーザーの候補プールを更新する。
    1. PREF_MEMORY取得 2. 楽天API検索 3. スコアリング 4. REWARD_POOL保存
    """

def _adjust_scores(candidates: list[dict], suggestion_history: list[dict]) -> list[dict]:
    """過去のスルー/購入履歴でスコアを調整する。"""

def _remove_stale_candidates(candidates: list[dict], max_age_days: int = 14) -> list[dict]:
    """古い候補を削除する。"""
```

### push_notifier

```python
def handler(event: dict, context) -> None:
    """
    EventBridge Scheduler から起動される1日1回Push通知バッチ。
    """

def _get_push_targets() -> list[str]:
    """今日未Push + 月200通未達のユーザー一覧を取得。"""

def _check_monthly_limit(user_id: str) -> bool:
    """月間Push送信数が200通未満かチェック。True=送信可。"""

def _generate_push_content(user_id: str) -> str:
    """Nova Microでリワードちゃん口調のPushコンテンツを生成する。
    例: 「今日ちょっとだけ話したいことある〜」
    """

def _send_and_log(user_id: str, content: str) -> None:
    """LINE Push API送信 + PUSH_LOG保存。"""
```

### liff_api

```python
def handler(event: dict, context) -> dict:
    """
    LIFF用APIエンドポイント。パスに応じてルーティング。
    Returns: {"statusCode": int, "body": str(JSON)}
    """

def _verify_liff_token(access_token: str) -> str:
    """LIFFアクセストークンをLINE Platform APIで検証し、userIdを返す。
    Raises: 401 if invalid token
    """

def _get_history(user_id: str, limit: int = 20) -> dict:
    """EXPENSE + REWARD_SUGGESTION 履歴を取得する。"""

def _get_settings(user_id: str) -> dict:
    """PROFILE から設定情報を取得する。"""

def _update_settings(user_id: str, updates: dict) -> dict:
    """PROFILE の口調・ご褒美枠等を更新する。"""

def _get_pool(user_id: str) -> dict:
    """REWARD_POOL から現在の候補一覧を取得する。"""
```

---

## 共通サービスモジュール

### dynamodb_service

```python
def put_item(pk: str, sk: str, attributes: dict, ttl: int | None = None) -> None:
    """アイテムを保存する。ttl指定時はexpires_at属性を自動付与。"""

def get_item(pk: str, sk: str) -> dict | None:
    """PK+SKでアイテムを取得する。存在しなければNone。"""

def query_by_sk_prefix(pk: str, sk_prefix: str, limit: int = 50, ascending: bool = False) -> list[dict]:
    """PK固定でSKプレフィックスに一致するアイテムを検索する。"""

def update_item(pk: str, sk: str, updates: dict) -> dict:
    """指定属性を部分更新する。UpdateExpression自動構築。"""

def delete_item(pk: str, sk: str) -> None:
    """アイテムを削除する。"""

def batch_get(keys: list[dict]) -> list[dict]:
    """複数アイテムを一括取得する。"""

def query_gsi(index_name: str, pk: str, sk_prefix: str | None = None) -> list[dict]:
    """GSIを使ってクエリする。"""
```

### bedrock_service

```python
def invoke_model(prompt: str, model_id: str | None = None, image_bytes: bytes | None = None) -> str:
    """
    Amazon Bedrockにテキスト or 画像を送信し、レスポンステキストを返す。
    model_id: Noneの場合は環境変数 BEDROCK_MODEL_TEXT のデフォルトモデルを使用。
    image_bytes: 指定時は BEDROCK_MODEL_MULTIMODAL を使用。
    Returns: str
    """

def invoke_model_with_retry(prompt: str, model_id: str | None = None, max_retries: int = 2) -> str:
    """リトライ付きのinvoke_model。ThrottlingException時にexponential backoff。"""
```

### line_service

```python
def verify_signature(body: str, signature: str) -> bool:
    """X-Line-Signatureをチャネルシークレットで HMAC-SHA256 検証。"""

def reply_message(reply_token: str, messages: list[dict]) -> None:
    """LINE Reply API でメッセージ送信。"""

def push_message(user_id: str, messages: list[dict]) -> None:
    """LINE Push API でメッセージ送信。"""

def get_content(message_id: str) -> bytes:
    """LINE Content API で画像等のバイナリコンテンツを取得。"""

def get_profile(user_id: str) -> dict:
    """LINE Profile API でユーザー表示名等を取得。"""

def build_text_message(text: str) -> dict:
    """テキストメッセージオブジェクトを構築。"""

def build_confirm_template(text: str, yes_label: str, no_label: str) -> dict:
    """確認テンプレートメッセージを構築（支出確認フロー用）。"""
```

### rakuten_service

```python
def search_items(keyword: str, genre_id: str | None = None, price_min: int | None = None, price_max: int | None = None) -> list[dict]:
    """楽天商品検索APIを呼び出し、ARS内部候補フォーマットに変換して返す。
    Returns: [{"id": str, "name": str, "price": int, "category": str, "source_url": str, "image_url": str}]
    """

def _convert_to_candidate(rakuten_item: dict) -> dict:
    """楽天APIレスポンスをARS候補フォーマットに変換。"""
```

### finance_engine

```python
def calculate_available_budget(user_id: str) -> int:
    """
    DynamoDBから収入・固定費・今月支出を取得し、ご褒美に使える余裕額を算出する。
    算出式: max(0, min(monthly_reward_limit, (income - fixed_costs) * 0.15) - current_month_expense)
    Returns: int (円、常に0以上)
    """

def _get_current_month_expenses(user_id: str) -> int:
    """今月のEXPENSE合計を取得。"""

def _get_financial_profile(user_id: str) -> dict:
    """PROFILE + FIXED_COSTS から収入・固定費情報を取得。"""
```

### reward_pool_service

```python
def select_candidates(user_id: str, state: dict, budget: int, top_n: int = 3) -> list[dict]:
    """
    DynamoDBのreward_poolから、現在状態と余裕額に合う候補を選択する。
    state: {"emotion": str, "fatigue_level": int, "preferred_categories": list}
    Returns: list[{"name": str, "price": int, "category": str, "score": float, "reason": str}]
    """

def score_candidate(candidate: dict, state: dict, budget: int) -> float:
    """候補のスコアを算出する。カテゴリ一致・価格帯適合・既存スコアを加味。"""

def update_scores_after_feedback(user_id: str, item_id: str, outcome: str) -> None:
    """bought/skip/noneのフィードバック結果でスコアを更新。"""
```

### secrets

```python
def get_secret(name: str) -> str:
    """Secrets Managerからシークレット値を取得する。Lambda実行環境でキャッシュ。"""

def get_parameter(name: str, decrypt: bool = True) -> str:
    """SSM Parameter Storeからパラメータを取得する。"""
```

### logger

```python
def info(message: str, **kwargs) -> None:
    """INFOレベルの構造化ログ出力。PII自動マスク。"""

def warn(message: str, **kwargs) -> None:
    """WARNレベルの構造化ログ出力。"""

def error(message: str, **kwargs) -> None:
    """ERRORレベルの構造化ログ出力。"""

def debug(message: str, **kwargs) -> None:
    """DEBUGレベルの構造化ログ出力。"""

def _mask_pii(data: dict) -> dict:
    """LINEユーザーID・チャットテキスト等のPIIをマスクする。"""
```

---

## Pydantic モデル定義（schemas.py）

```python
class Profile(BaseModel):
    """ユーザープロフィール"""
    pk: str                          # USER#{lineUserId}
    sk: str = "PROFILE#"
    name: str | None = None
    monthly_income: int = 0
    bonus: int = 0
    monthly_reward_limit: int = 0
    onboarding_done: bool = False
    onboarding_step: int = 0
    tone_style: str = "friendly"     # friendly | polite | devilish
    created_at: str
    updated_at: str

class FixedCosts(BaseModel):
    """固定費"""
    pk: str
    sk: str = "FIXED_COSTS#"
    items: list[dict]                # [{"name": str, "amount": int}]
    total: int
    updated_at: str

class Expense(BaseModel):
    """確定支出"""
    pk: str
    sk: str                          # EXPENSE#{isoTimestamp}
    item: str
    amount: int
    ars_category: str
    store: str | None = None
    confirmed_at: str
    source: str                      # "chat" | "receipt"

class PendingExpense(BaseModel):
    """仮支出（確認待ち）"""
    pk: str
    sk: str = "PENDING_EXPENSE#"
    item: str
    amount: int | None = None
    ars_category: str | None = None
    confidence: float
    message_id: str
    status: str = "pending"          # pending | confirmed | rejected

class RewardSuggestion(BaseModel):
    """ご褒美提案"""
    pk: str
    sk: str                          # REWARD_SUGGESTION#{isoTimestamp}
    item_id: str
    item_name: str
    price: int
    proposed_at: str
    outcome: str = "none"            # bought | skip | none
    feedback_at: str | None = None

class PushLog(BaseModel):
    """Push通知ログ"""
    pk: str
    sk: str                          # PUSH_LOG#{isoDate}
    sent_at: str
    content_preview: str
    message_count_today: int
    message_count_month: int
```
