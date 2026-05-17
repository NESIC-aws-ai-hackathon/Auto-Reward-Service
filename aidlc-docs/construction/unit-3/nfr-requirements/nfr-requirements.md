# Unit 3: 支出記録 — NFR Requirements

**作成日**: 2026-05-16

---

## PERF（パフォーマンス）

| ID | 要件 | 目標値 | 根拠 |
|---|---|---|---|
| PERF-3-01 | テキスト支出抽出レスポンス時間 | p95 ≤ 5秒 | Bedrock Nova Lite 呼び出し1回（intent 分類 + 抽出を同一プロンプトで実施） |
| PERF-3-02 | レシート画像解析レスポンス時間 | p95 ≤ 10秒、上限 29秒 | Nova Lite マルチモーダル。MVP は同期処理。Lambda タイムアウト内で完結 |
| PERF-3-03 | DynamoDB 月次累計更新 | Reply 後に非同期実行（Reply-First パターン） | 記録後応答の体感速度を優先 |

---

## COST（コスト）

| ID | 要件 | 根拠 |
|---|---|---|
| COST-3-01 | レシート解析は Nova Lite のみ使用（Nova Micro 不可） | 画像入力対応モデルは Nova Lite 以上 |
| COST-3-02 | テキスト抽出は 1 Bedrock 呼び出しで完結（カテゴリ分類を同時実施） | 呼び出し回数削減 |

---

## RELIABILITY（信頼性）

| ID | 要件 | 内容 |
|---|---|---|
| REL-3-01 | LLM 抽出失敗時のフォールバック | parse_failed = True の場合はリトライ促進メッセージを返す。Expense 保存はしない |
| REL-3-02 | DynamoDB 書き込み失敗時 | Bedrock は成功・DynamoDB 書き込み失敗の場合、ユーザーには「記録できなかった」旨を返す。リトライは行わない（冪等性担保のため） |
| REL-3-03 | 確認フロー中断時の自動回収 | TTL により PendingExpense / PENDING_CLARIFICATION は自動削除。ユーザーが再入力すれば新しいフローが始まる |
