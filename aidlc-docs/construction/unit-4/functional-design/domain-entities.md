# ドメインエンティティ定義 — Unit 4: ご褒美候補プール

**Unit**: Unit 4 — ご褒美候補プール（F5対応）  
**作成日**: 2026-05-16  
**対応要件**: F5-01〜F5-05

---

## エンティティ一覧

### 1. RakutenProduct

楽天ウェブサービスAPIから取得した商品情報の内部表現。

| フィールド | 型 | 説明 |
|---|---|---|
| `item_id` | `str` | 楽天商品コード（`itemCode`） |
| `name` | `str` | 商品名（`itemName`）。100文字に切り詰め |
| `price` | `Decimal` | 税込価格（`itemPrice`） |
| `category_name` | `str` | 楽天ジャンル名（`genreId`から逆引き、またはnull） |
| `item_url` | `str` | 商品URL |
| `image_url` | `Optional[str]` | サムネイル画像URL（`mediumImageUrls[0]`） |
| `shop_name` | `str` | 出店ショップ名 |
| `review_average` | `float` | レビュー平均（0.0〜5.0） |
| `review_count` | `int` | レビュー件数 |

---

### 2. RewardPoolItem（schemas.py 定義済み）

DynamoDB に保存するご褒美候補の1アイテム。

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `str` | 楽天商品コード（一意識別子） |
| `name` | `str` | 商品名 |
| `price` | `Decimal` | 価格（円） |
| `category` | `str` | ARSカテゴリ（"スイーツ" / "コスメ" / "本" / "ガジェット" 等） |
| `score` | `float` | マッチングスコア（0.0〜1.0）。高いほど優先提案 |
| `source_url` | `Optional[str]` | 商品URL |
| `image_url` | `Optional[str]` | サムネイル画像URL |
| `type` | `str` | 商品種別 `"product"`（MVP では固定） |

**スコア算出式:**

```
base_score = 嗜好キーワードマッチ数 / 総キーワード数
review_bonus = min(review_average / 5.0, 1.0) * 0.2
outcome_adjustment = フィードバック補正（スルー: -0.1, 購入: +0.15）

score = clamp(base_score + review_bonus + outcome_adjustment, 0.0, 1.0)
```

---

### 3. RewardPool（schemas.py 定義済み）

1ユーザー分のご褒美候補プール全体。

| フィールド | 型 | 説明 |
|---|---|---|
| `pk` | `str` | `USER#{line_user_id}` |
| `sk` | `str` | `REWARD_POOL#` |
| `items` | `list[RewardPoolItem]` | 最大20件のアイテムリスト（スコア降順） |
| `updated_at` | `str` | ISO 8601 更新日時 |

---

### 4. PrefMemory（schemas.py 定義済み・Unit 2 で生成）

ご褒美候補生成に使用する嗜好情報。Unit 4 では読み取りのみ。

| フィールド | 型 | 利用方法 |
|---|---|---|
| `categories` | `list[str]` | 楽天API キーワードの主軸（例: `["スイーツ", "コスメ"]`） |
| `items` | `list[PrefItem]` | 個別キーワード（positive のみ使用）。categories の補完 |

**キーワード生成ルール:**
- `categories` から最大2件を選択（ランダムまたはラウンドロビン）
- `items` の positive キーワードから上位3件（detected_at が新しい順）を選択
- 重複排除後、最大5件のキーワードで楽天APIをそれぞれ検索

---

### 5. PoolUpdateResult

バッチ1回分の更新結果サマリー（ログ用）。

| フィールド | 型 | 説明 |
|---|---|---|
| `total_users` | `int` | 処理対象ユーザー数 |
| `success_count` | `int` | 正常更新ユーザー数 |
| `skip_count` | `int` | プロフィールなしでスキップしたユーザー数 |
| `error_count` | `int` | エラー（3回リトライ失敗）ユーザー数 |
| `total_items_fetched` | `int` | 楽天APIから取得した総アイテム数 |
| `executed_at` | `str` | ISO 8601 実行日時 |

---

### 6. ScoreAdjustmentEvent

スルー・購入フィードバックイベント（スライス 4-5。Unit 5 から呼び出し）。

| フィールド | 型 | 説明 |
|---|---|---|
| `user_pk` | `str` | `USER#{line_user_id}` |
| `item_id` | `str` | フィードバック対象のアイテムID |
| `outcome` | `str` | `"bought"` または `"skip"` |

**スコア補正値:**

| outcome | score 変化量 |
|---------|------------|
| `"bought"` | +0.15 |
| `"skip"` | −0.10 |

補正後は `clamp(score, 0.0, 1.0)` で上下限を適用する。
