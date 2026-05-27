# Unit 3: 支出記録 — ビジネスロジックモデル

**作成日**: 2026-05-16

---

## 1. テキスト支出抽出フロー（スライス 3-1〜3-4）

```
ユーザーメッセージ（EXPENSE Intent 確定後）
        |
        v
  expense_extractor.extract(text)
        |
        v
  ┌─────────────────────────────────────┐
  │    ExpenseExtractResult             │
  │    items: list[ExtractedItem]       │
  │    is_expense: bool                 │
  └─────────────────────────────────────┘
        |
   is_expense = False?
        |──── YES ──→ CHAT ルーティングへ（支出でないと判断）
        |
        v
  各 item をチェック（複数件対応）
        |
   item.amount が null?
        |──── YES ──→ [追加質問フロー] ──→ 再抽出 ──→ 以下へ
        |
        v
   item.confidence < 0.7?
        |──── YES ──→ PendingExpense 保存
        |             リワードちゃん: 「○○ ×××円であってる？🤔」
        |             [確認フロー] ──→ CONFIRMED → Expense 保存
        |                           ──→ REJECTED  → キャンセル
        |
        v  （confidence >= 0.7）
   Expense 保存（DynamoDB）
   MonthlyExpenseSummary 更新（ADD amount）
        |
        v
   リワードちゃん応答:
   「○○ ×××円ね、覚えた〜🍮
    今月のご褒美は合計 X,XXX円。まだ XX,XXX円使えるよ！」
```

---

## 2. 追加質問フロー（スライス 3-2）

amount が null の場合にのみ発動する。

```
条件: item.amount is None

パターン1（item_name あり）:
  → 「プリンいくらだった？」
  → ユーザー返答（数値抽出）→ amount 確定 → 通常フローへ

パターン2（item_name も null）:
  → 「何をいくらで買ったの？😊」
  → ユーザー返答（再抽出）→ 通常フローへ

失敗ガード:
  → 数値が取れない返答が続いた場合（2回まで）
  → 「うまく読み取れなかったよ〜😅 「プリン320円」みたいに入力してくれると嬉しい！」
  → フロー中断（PendingExpense に partial 保存しない）
```

### 追加質問セッション管理

複数ターンの追加質問のために、DynamoDB に一時状態を保存する。

```
PENDING_CLARIFICATION#{timestamp}
  {
    "waiting_for": "amount",         # "amount" | "item_name_and_amount"
    "partial_item": {...},           # 現時点で判明している情報
    "retry_count": 0,                # 最大2回
    "ttl": <10分後>                  # 10分で自動削除
  }
```

---

## 3. 確認・承認フロー（スライス 3-3）

confidence < 0.7 の場合に発動する。

```
PendingExpense 保存（status: AWAITING_CONFIRM）
    |
    v
リワードちゃん: 「○○ ×××円であってる？🤔」
（Flex Message の Quick Reply ボタンを使用: 「うん✅」「違う🙅」）
    |
    |── Intent = CONFIRM_YES ──→ Expense に昇格・PendingExpense 削除
    |                             MonthlyExpenseSummary 更新
    |                             リワードちゃん: 「覚えた〜！×××円ね🍮」
    |
    |── Intent = CONFIRM_NO  ──→ PendingExpense を REJECTED に更新
    |                             リワードちゃん: 「ごめんね！改めて入力してくれる？😊」
    |
    └── 10分タイムアウト（TTL） ──→ PendingExpense 自動削除（確認なしキャンセル）
```

### 修正フロー（「違う」と言われた場合）

```
リワードちゃん: 「改めて教えて！ どんな感じ？」
ユーザー: 「350円だった」
  → amount を 350 に修正して再保存
  → confidence は 1.0（ユーザー確認済み）として Expense 保存
```

---

## 4. レシート画像解析フロー（スライス 3-5〜3-6）

MVP は同期処理。Lambda タイムアウト（29秒）内で処理する。

```
ユーザー: [レシート画像送信]
    |
    v
receipt_analyzer.analyze(image_content)
    → Nova Lite の Converse API（画像 + テキストプロンプト）
    |
    v
  ReceiptAnalysisResult
    |
  parse_failed = True?
    |──── YES ──→ 「ごめん読めなかった〜😅 
    |              もう少し明るい場所で撮り直してみて！」
    |
    v
  confidence < 0.7?
    |──── YES ──→ 確認フロー（→ 3 と同様）
    |
    v  （confidence >= 0.7）
  items が複数件?
    |──── YES ──→ 全件を Expense として保存
    |              リワードちゃん: 「レシート読んだよ〜🧾
    |                             ○○ XXX円 / △△ YYY円 ... 合計 Z,ZZZ円！」
    v
  1件のみ → 通常の Expense 保存フローへ
```

---

## 5. ARSカテゴリ分類ロジック（スライス 3-7）

テキスト抽出・レシート解析の両方で使用する。

### 分類タイミング

ExpenseExtractResult / ReceiptAnalysisResult 内の各 ExtractedItem に対して、
LLM プロンプトで category を決定する。
（支出抽出プロンプトに category 選択を同時に含める ＝ 別呼び出しは不要）

### プロンプト指示（expense_prompt.py に含める）

```
以下の10カテゴリから最も適切なものを1つ選び、"category" フィールドに入れてください：
- 情緒安定費：プリン・カフェ・スイーツなど日常の小さな癒し
- 回復費：マッサージ・銭湯・映画など意図的なリカバリー
- 緊急回復費：深夜コンビニ爆買いやヤケ食いなど衝動的な出費
- ご褒美費：新しい服・ガジェット・コスメなど自分へのご褒美
- 高級ご褒美費：高級ディナー・ブランド品・スパなど特別な贅沢
- 旅行・体験費：温泉旅行・ホテル・アクティビティなど非日常体験
- 成長投資費：書籍・セミナー・資格・ジムなど自己投資
- おすそわけ費：誕生日プレゼント・記念日ディナーなど他者向けギフト
- 日常消費：食料品・日用品・交通費など生活必需品
- その他：上記に該当しないもの
```

---

## 6. 複数件抽出フロー（スライス 3-1 の拡張）

1メッセージに複数の支出が含まれる場合。

```
ユーザー: 「スタバ500円とコンビニ800円使った」

ExpenseExtractResult:
  items: [
    {amount: 500, item_name: "スタバ", category: "情緒安定費", confidence: 0.9},
    {amount: 800, item_name: "コンビニ", category: "日常消費", confidence: 0.85},
  ]
  is_expense: True

処理フロー:
  全 items の confidence >= 0.7 の場合:
    → 全件を Expense として保存
    → MonthlyExpenseSummary を 1,300円 増加
    → リワードちゃん: 「2件覚えたよ〜！
                      スタバ 500円🍵 + コンビニ 800円🏪
                      今月は合計 X,XXX円。あとYY,YYY円使えるよ！」

  一部の confidence < 0.7 の場合:
    → confidence >= 0.7 の件は即保存
    → confidence < 0.7 の件は確認フローへ（順次）
```

---

## 7. 記録成功後の応答ロジック（スライス 3-4）

```python
def build_success_reply(
    items: list[Expense],
    monthly_summary: MonthlyExpenseSummary,
) -> str:
    """
    支出記録成功後のキャラクター応答を生成する。
    Nova Lite で生成（system_prompt にキャラクター口調を指定）。
    """
    # プロンプトに含める情報:
    # - 記録した支出リスト（品目・金額・カテゴリ）
    # - 今月の累計支出
    # - 今月の残りご褒美枠
    # - リワードちゃんのキャラクター設定（character_prompts.py から）
```

応答例:
- 1件: 「濃厚たまごプリン 320円ね、覚えた〜🍮  今月のご褒美は合計 8,320円。まだ 11,680円使えるよ！」
- 複数件: 「2件覚えたよ〜！スタバ 500円🍵 + コンビニ 800円🏪  今月は合計 9,620円。あとYY,YYY円使えるよ！」
- ご褒美枠超過: 「うーん、今月のご褒美枠オーバーしちゃった😅  でも頑張ったんだから仕方ない！来月また頑張ろ！」

---

## 8. webhook_handler.py との統合（スライス 3-4 の一部）

Intent = EXPENSE の場合、以下を呼び出す。

```
_handle_text() ← Intent = EXPENSE
    |
    v
_handle_expense(user_id, text, line_user)
    |
    |── PENDING_CLARIFICATION がある場合
    |    → clarification 回答として処理
    |
    |── PENDING_EXPENSE（AWAITING_CONFIRM）がある場合
    |    → _handle_expense_confirmation(user_id, text)
    |
    v
  expense_extractor.extract(text)
  → 上記フロー 1〜6 を実行
```
