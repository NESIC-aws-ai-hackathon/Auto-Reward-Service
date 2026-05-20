"""
DynamoDB スキーマ定数 + Pydantic v2 モデル定義

配置: layer/python/models/schemas.py（Lambda Layer のみ）
Lambda パッケージ側（src/）には含めない。

SK プレフィックス定数は DynamoDB アクセスパターンを一元管理するために定義する。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

# ─────────────────────────────────────────
# SK プレフィックス定数
# ─────────────────────────────────────────
SK_PROFILE = "PROFILE#"
SK_ONBOARDING_STATE = "ONBOARDING_STATE#"
SK_FIXED_COSTS = "FIXED_COSTS#"
SK_PENDING_EXPENSE = "PENDING_EXPENSE#"
SK_PENDING_CLARIFICATION = "PENDING_CLARIFICATION#"
SK_PREF_MEMORY = "PREF_MEMORY#"
SK_GOOGLE_OAUTH = "GOOGLE_OAUTH#"

SK_PREFIX_CHAT = "CHAT#"
SK_PREFIX_LIFELOG = "LIFELOG#"
SK_PREFIX_EXPENSE = "EXPENSE#"
SK_PREFIX_DAILY_COUNT = "DAILY_COUNT#"
SK_PREFIX_REWARD_POOL = "REWARD_POOL#"
SK_PREFIX_REWARD_SUGGESTION = "REWARD_SUGGESTION#"
SK_PREFIX_MONTHLY_SUMMARY = "MONTHLY_SUMMARY#"
SK_PREFIX_PUSH_LOG = "PUSH_LOG#"
SK_PUSH_SETTINGS = "PUSH_SETTINGS#"
SK_PREFIX_PUSH_QUEUE = "PUSH_QUEUE#"

# 変更依頼書_2 追加分
SK_PREFIX_WISHLIST_SOURCE = "WISHLIST_SOURCE#"
SK_PREFIX_WISHLIST_ITEM = "WISHLIST_ITEM#"
SK_PREFIX_RECOMMENDATION = "RECOMMENDATION#"
SK_PREFIX_NOTIFICATION = "NOTIFICATION#"
SK_PREFIX_CART_AUTOMATION_JOB = "CART_AUTOMATION_JOB#"
SK_PREFIX_BROWSER_SESSION = "BROWSER_SESSION#"

# entityType GSI 値
ENTITY_PROFILE = "PROFILE"
ENTITY_PREF_MEMORY = "PREF_MEMORY"
ENTITY_EXPENSE = "EXPENSE"
ENTITY_REWARD_SUGGESTION = "REWARD_SUGGESTION"


# ─────────────────────────────────────────
# 共通 Config
# ─────────────────────────────────────────
class _ArsBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ─────────────────────────────────────────
# ユーザープロファイル
# ─────────────────────────────────────────
class UserProfile(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=PROFILE#"""

    pk: str
    sk: str = SK_PROFILE
    entity_type: str = ENTITY_PROFILE
    status: str = "ACTIVE"
    tone: str = "friendly"           # friendly / polite / devilish
    push_count_this_month: int = 0

    # 収支情報（F2-02〜F2-04）
    monthly_income: Optional[Decimal] = None
    reward_budget_monthly: Optional[Decimal] = None

    # 表示名
    nickname: Optional[str] = None
    line_user_id: Optional[str] = None

    # ボーナス情報（F2-05）
    bonus_months: Optional[list[int]] = None    # [6, 12]
    bonus_amount: Optional[int] = None          # 1回あたり概算額（円）

    # 誕生日・記念日（F2-06）
    birthday: Optional[str] = None             # "MM-DD"（年は保存しない）
    anniversaries: Optional[list[dict]] = None # [{"name": "結婚記念日", "date": "06-15"}]

    # 繰り越し設定（F2-07）
    carryover_rate: float = 0.5                # 繰り越し率（デフォルト 50%）

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ─────────────────────────────────────────
# オンボーディング状態
# ─────────────────────────────────────────
class OnboardingState(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=ONBOARDING_STATE#"""

    pk: str
    sk: str = SK_ONBOARDING_STATE
    step: str = "WAITING_INCOME"
    # WAITING_INCOME / WAITING_FIXED_COSTS / CONFIRM_REWARD_BUDGET /
    # WAITING_BONUS / WAITING_BIRTHDAY / COMPLETED

    # 収集済み情報（ステップ間で引き継ぐ）
    monthly_income: Optional[Decimal] = None
    fixed_costs_total: Optional[Decimal] = None
    reward_budget: Optional[Decimal] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    ttl: Optional[int] = None  # 7日後の Unix タイムスタンプ（未完了オンボーディング自動削除）


# ─────────────────────────────────────────
# 固定費
# ─────────────────────────────────────────
class FixedCostItem(_ArsBase):
    name: str
    amount: Decimal


class FixedCosts(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=FIXED_COSTS#"""

    pk: str
    sk: str = SK_FIXED_COSTS
    items: list[FixedCostItem] = []
    total: Optional[Decimal] = None
    updated_at: Optional[str] = None


# ─────────────────────────────────────────
# チャットログ
# ─────────────────────────────────────────
class ChatLog(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=CHAT#{ISO8601}  TTL=30日"""

    pk: str
    sk: str                         # "CHAT#2026-05-16T..."
    role: str                       # "user" | "assistant"
    message: str
    intent: Optional[str] = None    # user ロールのみ
    created_at: str
    ttl: Optional[int] = None       # Unix タイムスタンプ（30日後）


# ─────────────────────────────────────────
# ライフログ（感情・疲労度記録）
# ─────────────────────────────────────────
class LifeLog(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=LIFELOG#{ISO8601}  TTL=30日"""

    pk: str
    sk: str
    emotion: Optional[str] = None
    fatigue_level: Optional[int] = None
    created_at: str
    ttl: Optional[int] = None


# ─────────────────────────────────────────
# 支出
# ─────────────────────────────────────────
# ARS カテゴリ固定10種
ARS_CATEGORIES: list[str] = [
    "情緒安定費",
    "回復費",
    "緊急回復費",
    "ご襲美費",
    "高級ご襲美費",
    "旅行・体験費",
    "成長投資費",
    "おすそわけ費",
    "日常消費",
    "その他",
]


class ExtractedItem(_ArsBase):
    """LLM が抗出した支出1件分（一時オブジェクト、DDB 保存なし）"""

    amount: Optional[int] = None          # None → 追加質問フローへ
    item_name: Optional[str] = None
    store_name: Optional[str] = None
    category: str = "その他"
    confidence: float = 1.0


class ExpenseExtractResult(_ArsBase):
    """LLM テキスト抽出結果（一時オブジェクト、DDB 保存なし）"""

    items: list[ExtractedItem] = []
    is_expense: bool = False
    raw_text: str = ""


class ReceiptAnalysisResult(_ArsBase):
    """LLM レシート画像解析結果（一時オブジェクト、DDB 保存なし）"""

    items: list[ExtractedItem] = []
    total_amount: Optional[int] = None
    store_name: Optional[str] = None
    purchased_at: Optional[str] = None
    confidence: float = 1.0
    parse_failed: bool = False


class Expense(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=EXPENSE#{ISO8601}"""

    pk: str
    sk: str                             # "EXPENSE#2026-05-16T..."
    entity_type: str = ENTITY_EXPENSE
    item_name: Optional[str] = None     # amount のみ必須、item_name は任意
    amount: Decimal
    store_name: Optional[str] = None
    ars_category: Optional[str] = None
    source: str = "text"               # "text" | "receipt_image"
    confidence: float = 1.0
    raw_text: Optional[str] = None
    created_at: str


class PendingExpense(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=PENDING_EXPENSE#  TTL=24時間"""

    pk: str
    sk: str = SK_PENDING_EXPENSE
    extracted: dict[str, Any]
    confidence: float
    raw_text: str
    status: str = "AWAITING_CONFIRM"    # AWAITING_CONFIRM | CONFIRMED | REJECTED
    expires_at: str
    created_at: str
    ttl: Optional[int] = None


class PendingClarification(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=PENDING_CLARIFICATION#  TTL=10分"""

    pk: str
    sk: str = SK_PENDING_CLARIFICATION
    waiting_for: str = "amount"         # "amount" | "item_name_and_amount"
    partial_items: list[dict[str, Any]] = []
    retry_count: int = 0
    created_at: str
    ttl: Optional[int] = None


class MonthlyExpenseSummary(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=MONTHLY_SUMMARY#{YYYY-MM}"""

    pk: str
    sk: str                             # "MONTHLY_SUMMARY#2026-05"
    total_amount: Decimal = Decimal("0")
    expense_count: int = 0
    reward_budget: Decimal = Decimal("0")  # PROFILE.reward_budget_monthly のコピー
    # 繰り越し情報（F2-07）
    carryover_amount: int = 0           # 先月から繰り越された額
    bonus_amount: int = 0               # ボーナス加算額
    total_budget: int = 0               # 総予算（base + carryover + bonus）
    remaining: int = 0                  # 残額（total_budget - total_amount）
    updated_at: Optional[str] = None


# ─────────────────────────────────────────
# 嗜好メモリ
# ─────────────────────────────────────────
class PrefItem(_ArsBase):
    keyword: str
    category: str
    sentiment: str = "positive"  # positive | negative
    detected_at: Optional[str] = None


class PrefMemory(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=PREF_MEMORY#"""

    pk: str
    sk: str = SK_PREF_MEMORY
    entity_type: str = ENTITY_PREF_MEMORY
    categories: list[str] = []
    items: list[PrefItem] = []
    updated_at: Optional[str] = None


# ─────────────────────────────────────────
# Google OAuth
# ─────────────────────────────────────────
class GoogleOAuth(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=GOOGLE_OAUTH#"""

    pk: str
    sk: str = SK_GOOGLE_OAUTH
    refresh_token: str
    connected_at: str
    scope: str = "calendar.events.readonly"
    email_hint: Optional[str] = None  # デバッグ用（実 email は保存しない）
    updated_at: Optional[str] = None


# ─────────────────────────────────────────
# ご褒美候補プール
# ─────────────────────────────────────────
class RewardPoolItem(_ArsBase):
    id: str
    name: str
    price: Decimal
    category: str
    score: float = 0.0
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    type: str = "product"           # product / travel / restaurant


class RewardPool(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=REWARD_POOL#"""

    pk: str
    sk: str = SK_PREFIX_REWARD_POOL
    items: list[RewardPoolItem] = []
    updated_at: Optional[str] = None


# ─────────────────────────────────────────
# ご褒美提案履歴
# ─────────────────────────────────────────
class RewardSuggestion(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=REWARD_SUGGESTION#{ISO8601}"""

    pk: str
    sk: str                                  # "REWARD_SUGGESTION#2026-05-16T..."
    entity_type: str = ENTITY_REWARD_SUGGESTION
    item_id: Optional[str] = None
    item_name: Optional[str] = None
    price: Optional[Decimal] = None
    proposed_at: str
    outcome: Optional[str] = None           # "bought" | "skip" | None


# ─────────────────────────────────────────
# 公開ほしい物リスト / 欲望在庫
# ─────────────────────────────────────────
class WishlistSource(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=WISHLIST_SOURCE#{wishlistSourceId}"""

    pk: str
    sk: str
    wishlist_source_id: str
    user_id: str
    source_type: str = "AMAZON_PUBLIC_WISHLIST"
    wishlist_url: str
    display_name: Optional[str] = None
    status: str = "ACTIVE"  # ACTIVE | SYNC_FAILED | DISABLED
    last_synced_at: Optional[str] = None
    created_at: str
    updated_at: str


class WishlistItem(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=WISHLIST_ITEM#{wishlistItemId}"""

    pk: str
    sk: str
    wishlist_item_id: str
    wishlist_source_id: str
    user_id: str
    product_id: Optional[str] = None
    product_title: str
    product_url: str
    product_image_url: Optional[str] = None
    price: Optional[Decimal] = None
    currency: str = "JPY"
    category: Optional[str] = None
    availability: Optional[str] = None
    first_seen_at: str
    last_seen_at: str
    desire_aging_days: int = 0
    recommendation_score: Optional[float] = None
    status: str = "ACTIVE"  # ACTIVE | RECOMMENDED | CART_ADDED | DECLINED | PURCHASED | UNAVAILABLE
    created_at: str
    updated_at: str


# ─────────────────────────────────────────
# レコメンド
# ─────────────────────────────────────────
class Recommendation(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=RECOMMENDATION#{recommendationId}"""

    pk: str
    sk: str
    recommendation_id: str
    user_id: str
    type: str = "WISHLIST_PRODUCT"  # WISHLIST_PRODUCT | LOCATION_STORE | MANUAL_DEMO
    title: str
    description: Optional[str] = None
    reason_text: str = ""
    product_url: Optional[str] = None
    product_image_url: Optional[str] = None
    store_id: Optional[str] = None
    price: Optional[Decimal] = None
    status: str = "RECOMMENDED"
    # RECOMMENDED | NOTIFICATION_SENT | CART_ADDING | CART_ADDED |
    # WAITING_USER_DECISION | DECLINED | CART_REMOVING | REMOVED_FROM_CART |
    # PURCHASE_CONFIRMATION_REQUIRED | PURCHASE_APPROVED | PURCHASING |
    # PURCHASED | PURCHASE_SIMULATED | PURCHASE_FAILED | ERROR
    created_at: str
    updated_at: str


# ─────────────────────────────────────────
# ふれまーるちゃん通知
# ─────────────────────────────────────────
class FuremaruNotification(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=NOTIFICATION#{notificationId}"""

    pk: str
    sk: str
    notification_id: str
    user_id: str
    recommendation_id: Optional[str] = None
    type: str = "RECOMMENDATION"
    # RECOMMENDATION | CART_ADDED | LOCATION_RECOMMENDATION |
    # MONTHLY_REMAINING | SYSTEM | LOGIN_REQUIRED | PURCHASE_READY
    title: str
    message_text: str
    status: str = "CREATED"  # CREATED | SENT | OPENED | EXPIRED
    created_at: str
    expires_at: Optional[str] = None


# ─────────────────────────────────────────
# カート搬送ジョブ
# ─────────────────────────────────────────
class CartAutomationJob(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=CART_AUTOMATION_JOB#{jobId}"""

    pk: str
    sk: str
    job_id: str
    user_id: str
    recommendation_id: str
    action: str = "ADD_TO_CART"  # ADD_TO_CART | REMOVE_FROM_CART | PURCHASE
    provider: str = "STUB"  # STUB | NOVA_ACT
    mode: str = "stub"  # stub | nova_act | hybrid
    status: str = "QUEUED"
    # QUEUED | RUNNING | LOGIN_REQUIRED | MFA_REQUIRED | CAPTCHA_REQUIRED |
    # USER_TAKEOVER_REQUIRED | READY_TO_PURCHASE | SUCCEEDED | FAILED | CANCELLED
    product_url: Optional[str] = None
    expected_product_title: Optional[str] = None
    expected_price: Optional[Decimal] = None
    quantity: int = 1
    max_allowed_price: Decimal = Decimal("1000")
    explicit_approval_text: Optional[str] = None
    fallback_reason: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    evidence_screenshot_key: Optional[str] = None
    created_at: str
    updated_at: str


# ─────────────────────────────────────────
# ブラウザセッション
# ─────────────────────────────────────────
class BrowserSession(_ArsBase):
    """DynamoDB: PK=USER#{id}  SK=BROWSER_SESSION#{browserSessionId}"""

    pk: str
    sk: str
    browser_session_id: str
    user_id: str
    provider: str = "NOVA_ACT"
    status: str = "NOT_CONNECTED"
    # NOT_CONNECTED | LOGIN_REQUIRED | ACTIVE | EXPIRED | REVOKED | ERROR
    session_storage_key: Optional[str] = None
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: str
    updated_at: str
