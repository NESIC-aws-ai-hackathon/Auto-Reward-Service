# Unit 3: 支出記録 — ビジネスルール

**作成日**: 2026-05-16

---

## 機能ルール（BR）

### BR-3-01: amount 必須チェック

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-01 |
| 名称 | amount 必須チェック |
| 説明 | 支出の金額（amount）は記録の必須フィールドである。LLM が amount を特定できない場合、追加質問フローへ遷移する。 |
| 条件 | ExtractedItem.amount is None |
| アクション | 追加質問フロー開始。PENDING_CLARIFICATION を DynamoDB に保存（TTL: 10分）。 |
| 例外 | なし |

---

### BR-3-02: 追加質問リトライ上限

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-02 |
| 名称 | 追加質問リトライ上限 |
| 説明 | 追加質問は最大2回まで。2回試みても amount が取得できない場合は入力ガイドメッセージを返してフローを中断する。 |
| 条件 | PENDING_CLARIFICATION.retry_count >= 2 |
| アクション | 「うまく読み取れなかったよ〜😅 「プリン320円」みたいに入力してくれると嬉しい！」を返信。PENDING_CLARIFICATION を削除。 |

---

### BR-3-03: 信頼度閾値による確認フロー

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-03 |
| 名称 | 信頼度閾値チェック |
| 説明 | LLM の抽出信頼度が 0.7 未満の場合、即時保存せず確認フローを挟む。 |
| 条件 | ExtractedItem.confidence < 0.7 かつ amount が取得済み |
| アクション | PendingExpense 保存（status: AWAITING_CONFIRM、TTL: 24時間）。確認メッセージを送信。 |
| 即時保存条件 | confidence >= 0.7 |

---

### BR-3-04: 確認フロー タイムアウト

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-04 |
| 名称 | 確認フロー TTL 自動削除 |
| 説明 | AWAITING_CONFIRM の PendingExpense は 24時間で TTL 自動削除される。タイムアウト後に yes/no が来た場合は「期限切れ」としてフロー不成立とする。 |
| 条件 | PendingExpense.ttl < now() |
| アクション | 「入力が古すぎるよ〜😅 もう一度入力してくれる？」を返信。 |

---

### BR-3-05: 複数件支出の処理順序

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-05 |
| 名称 | 複数件支出の一括処理 |
| 説明 | 1メッセージから複数の支出が抽出された場合、confidence >= 0.7 の件を先に全て保存してから、confidence < 0.7 の件を確認フローで処理する。 |
| 条件 | ExpenseExtractResult.items の件数 > 1 |
| アクション | 高信頼度件を先行保存 → 低信頼度件を順次確認（1件ずつ確認メッセージ）。 |

---

### BR-3-06: レシート画像 parse_failed 処理

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-06 |
| 名称 | レシート読み取り失敗時の案内 |
| 説明 | Nova Lite がレシートを読み取れない場合（parse_failed = True）、ユーザーに撮り直しを促す。 |
| 条件 | ReceiptAnalysisResult.parse_failed = True |
| アクション | 「ごめん読めなかった〜😅 もう少し明るい場所で撮り直してみて！」を返信。PendingExpense は保存しない。 |

---

### BR-3-07: ARSカテゴリ 必須設定

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-07 |
| 名称 | ARSカテゴリ必須 |
| 説明 | 全ての Expense は必ず ARS_CATEGORIES の10カテゴリのいずれかが設定される。LLM が不明な場合は「その他」にフォールバックする。 |
| 条件 | ExtractedItem.category が ARS_CATEGORIES に含まれない |
| アクション | category = "その他" に強制上書きする。 |

---

### BR-3-08: 月次累計 アトミック更新

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-08 |
| 名称 | MonthlyExpenseSummary アトミックカウンタ更新 |
| 説明 | Expense 保存後、MonthlyExpenseSummary の total_amount と expense_count を DynamoDB UpdateItem ADD で更新する。 |
| 条件 | Expense 保存成功時 |
| アクション | `UPDATE MonthlyExpenseSummary SET total_amount += amount, expense_count += 1` |
| 注意 | Reply-First パターン。月次更新は Reply 送信後に非同期実行。 |

---

### BR-3-09: 残枠マイナス許容

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-09 |
| 名称 | ご褒美枠超過の許容 |
| 説明 | MonthlyExpenseSummary.remaining_budget がマイナスになることを許容する。超過した場合はリワードちゃんが共感メッセージを返す（ブロックしない）。 |
| 条件 | remaining_budget < 0 |
| アクション | 超過メッセージを含む応答を返す。記録はそのまま保存。 |

---

### BR-3-10: 支出入力の is_expense 判定

| 項目 | 内容 |
|---|---|
| ルールID | BR-3-10 |
| 名称 | 支出メッセージ判定 |
| 説明 | Intent = EXPENSE に分類されたメッセージでも、expense_extractor が「支出ではない」と判断した場合は CHAT フローへフォールバックする。 |
| 条件 | ExpenseExtractResult.is_expense = False |
| アクション | character_reply.generate_reply() を CHAT として呼び出す。 |

---

## セキュリティルール（SEC）

### SEC-3-01: PII 抽出禁止

| 項目 | 内容 |
|---|---|
| ルールID | SEC-3-01 |
| 名称 | 個人情報の支出記録への混入防止 |
| 説明 | 支出 JSON に個人を特定できる情報（フルネーム・電話番号・クレジットカード番号等）を保存しない。item_name / store_name はユーザー入力の生テキストをトリミングして保存するが、LLM プロンプトで PII を含む場合の出力ルールを明示する。 |
| 実装 | プロンプトに「個人名・電話番号・カード番号は item_name / store_name に含めないこと」を指示。 |

---

### SEC-3-02: 入力長ガード

| 項目 | 内容 |
|---|---|
| ルールID | SEC-3-02 |
| 名称 | 支出テキスト入力長の上限 |
| 説明 | expense_extractor に渡すテキストは最大 1,000 文字に切り捨てる。LLM への不正プロンプトインジェクション対策。Unit 2（SEC-2-02）と統一し、webhook_handler.py での Intent 別切り替えを不要にする。 |
| 条件 | len(text) > 1000 |
| アクション | text = text[:1000] に切り捨て。ログに警告を出力。 |

---

### SEC-3-03: amount 範囲バリデーション

| 項目 | 内容 |
|---|---|
| ルールID | SEC-3-03 |
| 名称 | 金額の妥当性チェック |
| 説明 | LLM が返す amount は 1〜9,999,999 円の範囲に限定する。範囲外の場合は confidence を 0.0 に設定して確認フローへ遷移する。 |
| 条件 | amount < 1 または amount > 9,999,999 |
| アクション | confidence = 0.0 に上書き → 確認フローへ。 |

---

## 制約ルール（CONSTRAINT）

### CONST-3-01: レシート解析は同期処理（MVP）

MVP 段階ではレシート解析を Lambda のタイムアウト（29秒）内で完結させる。
SQS 非同期化は Deploy Round 4 の実測結果に基づいて判断する。

### CONST-3-02: 支出記録の上限件数

1ユーザー・1ヶ月の支出記録件数に上限は設けない（DynamoDB PAY_PER_REQUEST のため）。

### CONST-3-03: TTL 設定方針

| エンティティ | TTL |
|---|---|
| Expense | なし（永続保存） |
| PendingExpense | 作成から 24 時間後 |
| PENDING_CLARIFICATION | 作成から 10 分後 |
| MonthlyExpenseSummary | なし（永続保存） |
