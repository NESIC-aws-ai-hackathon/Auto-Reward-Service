# Functional Design Plan — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**ステータス**: 完了

---

## 実行計画チェックリスト

- [x] Step 1: 要件定義書・Unit 0 成果物レビュー
- [x] Step 2: Functional Design Plan 作成（本ファイル）
- [x] Step 3: 質問収集・回答受取
- [x] Step 4: 回答の曖昧さ解消（曖昧さなし）
- [x] Step 5: Functional Design 成果物生成
  - [x] `domain-entities.md`（Unit 1 入出力データ構造）
  - [x] `business-logic-model.md`（WebhookHandler ロジック）
  - [x] `business-rules.md`（Unit 1 固有ルール 7 件）
- [x] Step 6: 承認・次ステージへ進行

---

## 対応要件

| 要件 ID | 内容 |
|--------|------|
| F1-01 | LINE Webhook 受信・署名検証（失敗時 403） |
| F1-02 | テキスト / 画像 / スタンプ のメッセージ種別ルーティング |
| F1-03 | エラー時フォールバック（リワードちゃん口調でエラー返答） |
| F1-04 | ウォームアップ ping 早期リターン |
| SEC-01 | X-Line-Signature 検証の徹底 |

---

## 既確定事項（質問不要）

| 項目 | 決定内容 |
|------|---------|
| 署名検証ライブラリ | `line_service.verify_signature()`（Unit 0 実装済み） |
| ウォームアップ判定 | `event.get("source") == "warmup"` → 即 `{"statusCode": 200}` 返却 |
| Lambda メモリ / タイムアウト | 128 MB / 10 秒 |
| エラーログ | `logger.exception()` + PII マスク |

---

## 質問一覧（[Answer]: タグで回答してください）

### Q1: Webhook 処理方式

LINE は 1 秒以内（厳密には 5 秒以内）に HTTP 200 を返すことを推奨しています。

A) **同期処理**：WebhookHandler が Intent 分類・キャラ応答生成・Reply 送信まで一連を 10 秒以内に完結させる  
B) **非同期 Lambda invoke**：WebhookHandler は即 200 を返し、処理 Lambda（CharacterReply 等）を `InvocationType=Event` で非同期起動する  
C) **SQS キュー**：WebhookHandler → SQS Enqueue → 処理 Lambda（オーバーエンジニアリングのため非推奨）

[Answer]: A
タイムアウト 10秒で Bedrock 2回呼び出し（Intent + Reply）は十分収まる。B（非同期 invoke）にすると Reply Token の管理が複雑になるだけ

---

### Q2: Message Router の実装場所

A) **WebhookHandler 内に含める**（handler ファイル内の関数として実装）  
B) **別ファイル `message_router.py`** として src/handlers/ に切り出す  
C) **Layer 内 `utils/router.py`** として実装（複数 Unit から参照可能）

[Answer]: A

---

### Q3: 未対応メッセージ種別の扱い

スタンプ（sticker）、動画（video）、音声（audio）等、現時点で処理できないメッセージ種別への対応:

A) **無視（応答なし）**：200 を返すが LINE にはメッセージを送らない  
B) **リワードちゃん口調で「対応できません」と Reply**：ユーザーが無応答を疑わないよう返答  
C) **「スタンプかわいい！」等の簡単な固定返答**

[Answer]: B
ただし Bedrock を呼ぶ必要はなく、固定テンプレートから口調に合ったものをランダム選択で十分：

UNSUPPORTED_REPLIES = [
    "スタンプかわいい〜！でもリワードちゃん、文字の方が得意なんだ😊",
    "ん〜それはまだ読めないかも！テキストで話しかけてくれると嬉しいな〜",
    "おっ、それ気になる！…けど今はテキストだけ対応してるんだ〜ごめんね🥲",
]

---

### Q4: エラー時フォールバックの文言

システムエラー発生時に LINE ユーザーへ送る Reply の文言:

A) **固定文言**：「ちょっと調子が悪いみたい…またあとで話しかけてね🥲」  
B) **ユーザー定義**：文言を直接入力してください  
C) **応答なし**（エラーをユーザーに知らせない。ログのみ）

[Answer]: A

---

### Q5: SAM template.yaml への追加リソース（Unit 1 差分）

Unit 1 で template.yaml に追加する Lambda 関数の名前を確認します。

A) `WebhookHandler`（単一関数。ルーティングも同一関数内で処理）  
B) `WebhookHandler` + `MessageRouter`（別関数）  
C) その他（名前を指定してください）

[Answer]: A

