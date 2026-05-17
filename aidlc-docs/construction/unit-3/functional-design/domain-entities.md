# Unit 3: 支出記録 — ドメインエンティティ設計

**作成日**: 2026-05-16

---

## エンティティ一覧

| エンティティ | 概要 | DynamoDB PK/SK |
|---|---|---|
| Expense | 確定済み支出記録 | `USER#{line_user_id}` / `EXPENSE#{timestamp}` |
| PendingExpense | 確認待ち支出（confidence < 0.7） | `USER#{line_user_id}` / `PENDING_EXPENSE#{timestamp}` |
| ExpenseExtractResult | LLM テキスト抽出結果（一時オブジェクト、DDB 保存なし） | — |
| ReceiptAnalysisResult | LLM レシート画像解析結果（一時オブジェクト、DDB 保存なし） | — |
| MonthlyExpenseSummary | 月次累計集計（Expense からリアルタイム集計） | `USER#{line_user_id}` / `MONTHLY_SUMMARY#{YYYY-MM}` |

---

## Expense（確定済み支出）

```python
class Expense(BaseModel):
    # キー
    line_user_id: str                    # LINE ユーザーID
    expense_id: str                      # タイムスタンプベースのID（ISO 8601）

    # 支出情報
    amount: int                          # 金額（円）必須
    item_name: Optional[str] = None      # 商品名・購入物（任意）
    store_name: Optional[str] = None     # 店名（任意）
    category: str                        # ARSカテゴリ（固定10カテゴリ）
    memo: Optional[str] = None          # ユーザー入力の生テキスト（記録用）

    # メタデータ
    source: str                          # "text" | "receipt_image"
    confidence: float                    # LLM 信頼度（0.0〜1.0）
    recorded_at: str                     # 記録日時（ISO 8601 UTC）
    ttl: Optional[int] = None           # Unix timestamp（将来的に TTL 設定する場合）
```

---

## PendingExpense（確認待ち支出）

confidence < 0.7 の場合に一時保存し、ユーザーが yes/no で確認するまで保留する。

```python
class PendingExpense(BaseModel):
    line_user_id: str
    pending_id: str                      # タイムスタンプベース

    # 仮抽出された支出情報
    amount: int
    item_name: Optional[str] = None
    store_name: Optional[str] = None
    category: str
    memo: Optional[str] = None
    source: str                          # "text" | "receipt_image"
    confidence: float

    # 状態
    status: str = "AWAITING_CONFIRM"    # "AWAITING_CONFIRM" | "CONFIRMED" | "REJECTED"
    created_at: str
    ttl: int                             # 24時間後 Unix timestamp（自動削除）
```

---

## ExpenseExtractResult（テキスト抽出結果、一時オブジェクト）

LLM が返す JSON をパースした結果。DynamoDB には保存しない。

```python
class ExtractedItem(BaseModel):
    amount: Optional[int] = None         # 金額（null なら追加質問フローへ）
    item_name: Optional[str] = None      # 商品名（任意）
    store_name: Optional[str] = None     # 店名（任意）
    category: str                        # ARSカテゴリ
    confidence: float                    # 0.0〜1.0
    needs_clarification: bool = False    # amount が null → True

class ExpenseExtractResult(BaseModel):
    items: list[ExtractedItem]           # 複数件対応（Q5: JSON 配列）
    is_expense: bool                     # 支出メッセージか否か
    raw_text: str                        # 元のユーザーメッセージ
```

---

## ReceiptAnalysisResult（画像解析結果、一時オブジェクト）

Nova Lite が返すレシート解析 JSON をパースした結果。DynamoDB には保存しない。

```python
class ReceiptAnalysisResult(BaseModel):
    items: list[ExtractedItem]           # レシート上の各品目
    total_amount: Optional[int] = None  # 合計金額（レシートに記載あれば）
    store_name: Optional[str] = None    # 店名
    purchased_at: Optional[str] = None  # 購入日時（レシート記載あれば）
    confidence: float                   # 全体の解析信頼度
    parse_failed: bool = False          # 読み取り不能フラグ
```

---

## MonthlyExpenseSummary（月次累計）

支出記録成功のたびに更新（DynamoDB UpdateItem ADD）。

```python
class MonthlyExpenseSummary(BaseModel):
    line_user_id: str
    month: str                           # "YYYY-MM"
    total_amount: int                    # 月次累計支出（円）
    reward_budget: int                   # 月次ご褒美枠（PROFILE から取得）
    remaining_budget: int                # reward_budget - total_amount
    expense_count: int                   # 記録件数
    updated_at: str
```

---

## ARSカテゴリ定義（固定10カテゴリ）

| ID | カテゴリ名 | 説明 | 代表的な支出例 |
|---|---|---|---|
| 1 | 情緒安定費 | 日常のちょっとした癒し | プリン・カフェ・スイーツ |
| 2 | 回復費 | 疲れた時のリカバリー | マッサージ・銭湯・映画 |
| 3 | 緊急回復費 | ストレス爆発時の衝動買い | 深夜コンビニ爆買い・ヤケ食い |
| 4 | ご褒美費 | 頑張った自分への報酬 | 新しい服・ガジェット・コスメ |
| 5 | 高級ご褒美費 | 特別な日の贅沢 | 高級ディナー・ブランド品・スパ |
| 6 | 旅行・体験費 | 非日常の体験投資 | 温泉旅行・ホテル・アクティビティ |
| 7 | 成長投資費 | 自分磨き・スキルアップ | 書籍・セミナー・資格・ジム |
| 8 | おすそわけ費 | 大切な人へのギフト | 誕生日プレゼント・記念日ディナー |
| 9 | 日常消費 | 生活必需品 | 食料品・日用品・交通費 |
| 10 | その他 | 上記に該当しないもの | — |

```python
# constants として定義
ARS_CATEGORIES = [
    "情緒安定費",
    "回復費",
    "緊急回復費",
    "ご褒美費",
    "高級ご褒美費",
    "旅行・体験費",
    "成長投資費",
    "おすそわけ費",
    "日常消費",
    "その他",
]
```

---

## エンティティ関係図

```
UserProfile (PROFILE#)
    |
    |-- reward_budget (月次ご褒美枠)
    |
    v
Expense (EXPENSE#{timestamp})  ←── ExpenseExtractResult（一時）
    |                                   ↑
    |                               テキスト入力
    |                                   |
MonthlyExpenseSummary (MONTHLY_SUMMARY#{YYYY-MM})
    |
    |-- total_amount (累計)
    |-- remaining_budget (残枠)

PendingExpense (PENDING_EXPENSE#{timestamp})  ←── ReceiptAnalysisResult（一時）
    |                                                  ↑
    |                                           レシート画像入力
    |
    |-- CONFIRMED → Expense に昇格
    |-- REJECTED  → 削除（TTL で自動削除）
```
