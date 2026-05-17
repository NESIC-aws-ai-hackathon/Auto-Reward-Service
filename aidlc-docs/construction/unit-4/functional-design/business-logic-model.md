# ビジネスロジックモデル — Unit 4: ご褒美候補プール

**Unit**: Unit 4 — ご褒美候補プール（F5対応）  
**作成日**: 2026-05-16  
**対応要件**: F5-01〜F5-05

---

## 1. 主要フロー

### 1-A: 日次バッチ更新フロー（スライス 4-3〜4-4）

```
EventBridge Scheduler (02:00 JST)
  │
  └─► reward_pool_updater.lambda_handler()
         │
         ├─[1] DynamoDB GSI "entityType-index" で全 PROFILE エンティティを scan
         │       → active ユーザーのPKリストを取得
         │
         ├─[2] 各ユーザーに対して順次処理:
         │       │
         │       ├─[2a] DynamoDB から PREF_MEMORY# を取得
         │       │       → PrefMemory オブジェクトに変換
         │       │       → 嗜好なし（categories/items 空）の場合はデフォルトキーワード使用
         │       │
         │       ├─[2b] キーワード生成 (reward_pool_service.build_keywords)
         │       │       → categories から最大2件
         │       │       → items[positive] の detected_at 新しい順から最大3件
         │       │       → 重複排除・最大5件
         │       │
         │       ├─[2c] 楽天API検索 (rakuten_service.search_products)
         │       │       → 各キーワードで検索（件数: 5件/キーワード）
         │       │       → 3回リトライ（exponential backoff）
         │       │       → 全失敗時: 既存プール維持・エラーログ記録
         │       │
         │       ├─[2d] スコアリング (reward_pool_service.score_items)
         │       │       → キーワードマッチ数からbase_score算出
         │       │       → review_average からreview_bonus算出
         │       │       → 既存プールの outcome を読み込んでoutcome_adjustment適用
         │       │       → スコア降順ソート・上位20件に絞り込み
         │       │
         │       └─[2e] DynamoDB 差分マージ (dynamodb_service.put_item)
         │               → 既存 REWARD_POOL# を取得
         │               → item_id でマッチング:
         │                   - 新規: 追加
         │                   - 既存: スコア・name・price 更新（outcome は保持）
         │                   - 古いもの（今回取得リストにない）: 削除
         │               → 最終的に上位20件で put_item（上書き）
         │
         └─[3] PoolUpdateResult をログ出力
```

---

### 1-B: スコア調整フロー（スライス 4-5、Unit 5 から呼び出し）

```
Unit 5 (reward_proposal.py)
  │  ユーザーが提案をスルー or 購入記録時
  │
  └─► reward_pool_service.adjust_score(user_pk, item_id, outcome)
         │
         ├─[1] DynamoDB から REWARD_POOL# を取得
         │
         ├─[2] item_id に一致するアイテムを検索
         │       → 見つからない場合: ログ警告・早期リターン
         │
         ├─[3] スコア補正:
         │       outcome == "bought" → score += 0.15
         │       outcome == "skip"   → score -= 0.10
         │       clamp(score, 0.0, 1.0)
         │
         └─[4] DynamoDB に更新済みプールを put_item（上書き）
```

---

### 1-C: 楽天API商品検索フロー（スライス 4-1）

```
rakuten_service.search_products(keyword, hits=5)
  │
  ├─[1] Secrets Manager から AppID を取得（キャッシュ: Lambda実行内で1回のみ取得）
  │
  ├─[2] HTTP GET https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706
  │       params: {
  │         applicationId: AppID,
  │         keyword: keyword,
  │         hits: hits,
  │         sort: "+reviewAverage",  # レビュー高い順
  │         minPrice: 300,           # 300円以上（ちゃちいご褒美は除外）
  │         maxPrice: 50000          # 5万円以下
  │       }
  │
  ├─[3] レスポンスパース → List[RakutenProduct]
  │       → itemName を100文字にトリミング
  │       → mediumImageUrls[0] から image_url 取得（なければ None）
  │
  └─[4] 返却: List[RakutenProduct]（空リストも許容）
```

---

## 2. スコアリングロジック詳細（スライス 4-2）

### キーワードマッチスコア

```python
def _calc_base_score(product: RakutenProduct, keywords: list[str]) -> float:
    """
    商品名・カテゴリ名にキーワードが含まれる割合をスコアとする。
    
    - keywords が空の場合: 0.5（デフォルトスコア）
    - 1件でもマッチ: 最低 0.3 を保証
    """
    if not keywords:
        return 0.5
    matched = sum(1 for kw in keywords if kw.lower() in product.name.lower())
    ratio = matched / len(keywords)
    return max(ratio, 0.3) if matched > 0 else 0.1
```

### レビューボーナス

```python
def _calc_review_bonus(product: RakutenProduct) -> float:
    """
    レビュー平均 4.0以上・件数 10件以上で最大 +0.2 のボーナス。
    """
    if product.review_count < 10:
        return 0.0
    return min(product.review_average / 5.0, 1.0) * 0.2
```

### 最終スコア

```python
score = clamp(base_score + review_bonus + outcome_adjustment, 0.0, 1.0)
```

---

## 3. デフォルトキーワード（嗜好なしユーザー向け）

嗜好情報がないユーザー（新規・嗜好未蓄積）には以下のデフォルトキーワードを使用:

```python
DEFAULT_KEYWORDS = ["スイーツ", "コスメ", "本", "入浴剤", "アロマ"]
```

---

## 4. Secrets Managerシークレット構造

楽天 AppID は専用シークレット `ars/rakuten` に保存:

```json
{
  "RAKUTEN_APP_ID": "<楽天ウェブサービスApplicationID>"
}
```

`secrets.py` の `get_secret(RAKUTEN_SECRET_NAME)` で取得し `RAKUTEN_APP_ID` キーを参照する（`RAKUTEN_SECRET_NAME` 環境変数 = `ars/rakuten`）。
