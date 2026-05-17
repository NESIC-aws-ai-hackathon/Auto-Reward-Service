# Functional Design Plan — Unit 4: ご褒美候補プール

**Unit**: Unit 4 — ご褒美候補プール（F5対応）  
**作成日**: 2026-05-16  
**対応要件**: F5-01〜F5-05

---

## 実行計画

- [x] Step 1: Unit コンテキスト分析（unit-of-work.md 読み込み）
- [x] Step 2: Functional Design Plan 作成
- [ ] Step 3: 質問への回答収集
- [ ] Step 4: Functional Design 成果物生成
  - [ ] domain-entities.md
  - [ ] business-logic-model.md
  - [ ] business-rules.md

---

## スコープ確認

**スライス一覧:**

| スライス | 機能 | 分類 |
|---------|------|------|
| 4-1 | `rakuten_service.py`: 楽天ウェブサービスAPI商品検索（`openapi.rakuten.co.jp`） | Must |
| 4-2 | `reward_pool_service.py`: 嗜好×候補スコアリングロジック | Must |
| 4-3 | `reward_pool_updater.py`: 全ユーザー嗜好取得→楽天API→プール更新 | Must |
| 4-4 | EventBridge Scheduler SAMリソース定義（RewardPoolScheduler） | Must |
| 4-5 | スルー・購入履歴によるスコア調整 | Must |
| 4-6 | 楽天APIモックテスト | Must |
| 4-7 | `rakuten_service.search_hotels()`: 楽天トラベル施設検索 | Growth |
| 4-8 | `hotpepper_service.py`: ホットペッパーグルメAPI検索 | Growth |
| 4-9 | REWARD_POOLアイテムに `type` フィールド追加・カテゴリ重みづけ | Growth |

---

## 質問

### Q1: Growthスライス（4-7〜4-9）のMVP扱い

楽天トラベル・ホットペッパー連携（4-7, 4-8）とカテゴリ重みづけ（4-9）は今回のコード生成に含めますか？

A) 今回は含めない（Must スライス 4-1〜4-6 のみ実装）
B) 4-7（楽天トラベル）のみ追加で含める（楽天API同一AppIDで実装コストが低い）
C) 4-7〜4-9 すべて含める
X) その他

[Answer]: A

---

### Q2: 楽天APIシークレット管理方法

楽天ウェブサービスの ApplicationID はどこに保存しますか？

A) AWS Secrets Manager（他のシークレットと同様に `/ars/secrets` に追加）
B) SSM Parameter Store（`/ars/rakuten-app-id`）
C) Lambda 環境変数（平文。開発簡略化）
X) その他

[Answer]: A

---

### Q3: プール更新ロジック

日次バッチで DynamoDB `REWARD_POOL#` を更新する際の方針は？

A) 全上書き（既存アイテムを削除し、新しい候補リストで置き換え）
B) 差分マージ（item_id でマッチングし、新規は追加・既存はスコア更新・古いものは削除）
C) 追記のみ（既存は保持し、新しいものだけ追加。スコアが高い順に上位N件に絞る）
X) その他

[Answer]: B

---

### Q4: 楽天API検索キーワードの生成方法

`PREF_MEMORY#` の嗜好データから楽天APIへの検索キーワードをどう生成しますか？

A) `PrefMemory.categories`（カテゴリ一覧）をそのままキーワードに使う
B) `PrefMemory.items[].keyword`（個別キーワード）をそのまま使う
C) categories と items の両方を組み合わせて複数キーワードで検索する（カテゴリ1件 + keywords上位3件等）
D) Nova Microに「この嗜好リストから楽天検索に適したキーワードを3つ生成して」と依頼する
X) その他

[Answer]: C

---

### Q5: バッチスケジュール

EventBridge Schedulerの実行タイミングは？

A) 毎日深夜2時（JST）
B) 毎日深夜0時（JST）
C) 毎日午前4時（JST）
X) その他

[Answer]: A

---

### Q6: スルー・購入フィードバックのトリガー

スルー・購入履歴によるスコア調整（スライス4-5）はいつ呼び出しますか？

A) Unit 5のご褒美提案時にユーザーがスルー/購入を記録する際に reward_pool_service を呼んでスコア更新
B) 日次バッチ（reward_pool_updater.py）の中でREWARD_SUGGESTIONの outcome を集計してスコア調整
C) A + Bの両方（リアルタイム調整 + 日次バッチでも再集計）
X) その他

[Answer]: A

---

### Q7: プール上限アイテム数

1ユーザーあたりの `REWARD_POOL#` に保存するアイテムの最大数は？

A) 10件（シンプル・DynamoDBアイテムサイズ小）
B) 20件（バランス型）
C) 50件（豊富な候補。Unit5での選択肢が多くなる）
X) その他

[Answer]: B

---

### Q8: 楽天APIレートリミット・エラー処理

楽天APIが失敗した場合の動作は？

A) そのユーザーの更新をスキップし、既存プールを維持（ログに記録）
B) 3回リトライ後に失敗した場合は古いプールを維持
C) 失敗ユーザーをSQSデッドレターキューに入れ、別途リトライ
X) その他

[Answer]: B

---

## 確認済み前提条件

以下は unit-of-work.md / schemas.py から確認済み：

| 項目 | 確認内容 |
|------|---------|
| `RewardPool` スキーマ | schemas.py に `RewardPool` + `RewardPoolItem` 定義済み（type フィールド含む） |
| `PrefMemory` スキーマ | schemas.py に `PrefMemory` + `PrefItem` 定義済み |
| `SK_PREFIX_REWARD_POOL` | schemas.py で `"REWARD_POOL#"` 定義済み |
| `dynamodb_service.py` | `put_item`, `get_item`, `query_by_pk`, `update_item` 利用可能 |
| `secrets.py` | Secrets Manager取得ユーティリティ利用可能 |
| 楽天APIドメイン | `openapi.rakuten.co.jp`（新ドメイン） |
