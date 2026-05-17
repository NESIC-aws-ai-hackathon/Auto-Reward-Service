# Domain Entities — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16

---

## 1. DynamoDB テーブル定義（ArsTable）

### 主キー設計

| 属性 | 型 | 役割 |
|------|----|------|
| `PK` | String | `USER#{lineUserId}` |
| `SK` | String | エンティティ種別プレフィックス |

### GSI 定義

| GSI名 | Partition Key | Sort Key | 用途 |
|--------|--------------|----------|------|
| `entityType-index` | `entityType` (String) | `PK` (String) | 全ユーザーの特定エンティティ横断検索（PREF_MEMORY#, PROFILE# のみ） |

> **重要**: `entityType` 属性は PREF_MEMORY# と PROFILE# アイテムにのみ付与する。  
> CHAT#{timestamp}、EXPENSE#{timestamp}、LIFELOG#{timestamp} 等の高頻度書き込みアイテムには付与しない（GSI書き込みコスト削減）。

---

## 2. エンティティ一覧と Pydantic v2 モデル

### 2.1 UserProfile（SK: `PROFILE#`）

```python
class UserProfile(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str                          # USER#{lineUserId}
    sk: str = "PROFILE#"
    entity_type: str = "PROFILE"     # GSI用 — entityType-index の PK
    status: str = "ACTIVE"           # ACTIVE | INACTIVE — GSI上でのフィルタリングに使用
    display_name: Optional[str] = None
    monthly_income: Optional[Decimal] = None
    bonus_annual: Optional[Decimal] = None
    reward_budget_monthly: Optional[Decimal] = None
    reward_budget_remaining: Optional[Decimal] = None
    tone: str = "friendly"           # friendly | polite | devil
    push_count_this_month: int = 0
    last_push_date: Optional[str] = None  # YYYY-MM-DD
    created_at: str                  # ISO 8601
    updated_at: str                  # ISO 8601
```

### 2.2 FixedCosts（SK: `FIXED_COSTS#`）

```python
class FixedCostItem(BaseModel):
    model_config = ConfigDict(extra='ignore')
    name: str
    amount: Decimal

class FixedCosts(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str
    sk: str = "FIXED_COSTS#"
    items: List[FixedCostItem] = []
    total: Decimal = Decimal("0")
    updated_at: str                  # ISO 8601
```

### 2.3 ChatLog（SK: `CHAT#{timestamp}`）

```python
class ChatLog(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str
    sk: str                          # CHAT#{timestamp} — entityType属性なし（GSI除外）
    role: str                        # "user" | "assistant"
    message: str                     # ※ PII — ログ出力禁止
    intent: Optional[str] = None     # 分類されたIntent
    ttl: Optional[int] = None        # Unix epoch — DynamoDB TTL 自動削除用（created_at + 30日）
    created_at: str                  # ISO 8601
```

### 2.4 LifeLog（SK: `LIFELOG#{timestamp}`）

```python
class LifeLog(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str
    sk: str                          # LIFELOG#{timestamp} — entityType属性なし（GSI除外）
    emotion: Optional[str] = None    # "tired" | "happy" | "stressed" | etc.
    fatigue_level: Optional[int] = None  # 1〜5
    memo: Optional[str] = None       # ※ PII — ログ出力禁止
    ttl: Optional[int] = None        # Unix epoch — DynamoDB TTL 自動削除用（created_at + 90日）
    created_at: str                  # ISO 8601
```

### 2.5 PendingExpense（SK: `PENDING_EXPENSE#`）

```python
class PendingExpense(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str
    sk: str = "PENDING_EXPENSE#"
    raw_text: str                    # ※ PII — ログ出力禁止
    extracted: dict                  # LLM抽出済み支出データ（item_name, amount, shop等）
    confidence: float                # 0.0〜1.0
    expires_at: str                  # ISO 8601 — 確認タイムアウト用
    ttl: Optional[int] = None        # Unix epoch — DynamoDB TTL 自動削除用（created_at + 24時間）
    created_at: str                  # ISO 8601
```

### 2.6 Expense（SK: `EXPENSE#{timestamp}`）

```python
class Expense(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str
    sk: str                          # EXPENSE#{timestamp} — entityType属性なし（GSI除外）
    amount: Decimal
    item_name: str
    shop_name: Optional[str] = None
    ars_category: str                # 情緒安定費 | 回復費 | 緊急回復費 | 浪費 | etc.
    source: str = "chat"             # "chat" | "receipt"
    created_at: str                  # ISO 8601
```

### 2.7 PrefMemory（SK: `PREF_MEMORY#`）

```python
class PrefItem(BaseModel):
    model_config = ConfigDict(extra='ignore')
    name: str
    score: float = 1.0               # 正規化スコア 0.0〜1.0
    last_seen: str                   # ISO 8601

class PrefMemory(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str
    sk: str = "PREF_MEMORY#"
    entity_type: str = "PREF_MEMORY"  # GSI用 — entityType-index の PK
    categories: List[str] = []       # 好きなカテゴリ（"スイーツ", "カフェ" 等）
    items: List[PrefItem] = []       # 嗜好品目リスト
    updated_at: str                  # ISO 8601
```

### 2.8 RewardPool（SK: `REWARD_POOL#`）

```python
class RewardPoolItem(BaseModel):
    model_config = ConfigDict(extra='ignore')
    item_id: str                     # 楽天商品ID等
    name: str
    price: Decimal
    url: str
    category: str
    score: float = 1.0               # マッチングスコア 0.0〜1.0
    source: str = "rakuten"          # "rakuten" | "rakuten_travel" | "hotpepper"
    skip_count: int = 0
    purchase_count: int = 0
    last_updated: str                # ISO 8601

class RewardPool(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str
    sk: str = "REWARD_POOL#"
    items: List[RewardPoolItem] = []
    updated_at: str                  # ISO 8601
```

### 2.9 RewardSuggestion（SK: `REWARD_SUGGESTION#{timestamp}`）

```python
class RewardSuggestion(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str
    sk: str                          # REWARD_SUGGESTION#{timestamp} — entityType属性なし（GSI除外）
    item: RewardPoolItem
    message: str                     # リワードちゃん口調の提案メッセージ
    was_purchased: Optional[bool] = None
    was_skipped: Optional[bool] = None
    created_at: str                  # ISO 8601
```

### 2.10 GoogleOAuth（SK: `GOOGLE_OAUTH#`）

```python
class GoogleOAuth(BaseModel):
    model_config = ConfigDict(extra='ignore')

    pk: str
    sk: str = "GOOGLE_OAUTH#"
    refresh_token: str               # 暗号化保存（DynamoDB KMS）— ※ ログ出力禁止
    email_hint: Optional[str] = None # 表示用マスク済みメール（例: "u***@gmail.com"）
    scope: str = "calendar.events.readonly"
    connected_at: str                # ISO 8601
    updated_at: str                  # ISO 8601
```

---

## 3. GSI アクセスパターン早見表

| クエリ目的 | アクセス方法 | 対象エンティティ |
|-----------|-------------|-----------------|
| 特定ユーザーの全エンティティ取得 | PK クエリ | すべて |
| 特定ユーザーの特定エンティティ取得 | PK + SK GetItem | すべて |
| 全ユーザーの嗜好取得（バッチ用） | GSI1 `entityType-index`: `entityType=PREF_MEMORY` | PrefMemory |
| アクティブユーザー一覧取得（バッチ用） | GSI1 `entityType-index`: `entityType=PROFILE` + FilterExpression `status=ACTIVE` | UserProfile |

---

## 4. 例外クラス

```python
# src/utils/exceptions.py
class DynamoDBError(Exception):
    """DynamoDB操作失敗時に発生する独自例外"""
    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original

class BedrockError(Exception):
    """Bedrock API呼び出し失敗時に発生する独自例外"""
    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original

class GoogleCalendarError(Exception):
    """Google Calendar API呼び出し失敗時に発生する独自例外"""
    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original

class LineServiceError(Exception):
    """LINE API呼び出し失敗時に発生する独自例外"""
    def __init__(self, message: str, original: Exception = None):
        super().__init__(message)
        self.original = original
```
