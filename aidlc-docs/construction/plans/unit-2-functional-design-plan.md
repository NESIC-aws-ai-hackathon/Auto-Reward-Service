# Functional Design Plan — Unit 2: リワードちゃんキャラクター

**Unit**: Unit 2 — LINE Bot会話（F2/F3対応）  
**作成日**: 2026-05-16  
**対応要件**: F2-01〜F2-06, F3-01〜F3-05

---

## 実行計画

- [x] Step 1: Unit コンテキスト分析（unit-of-work.md 読み込み）
- [x] Step 2: Functional Design Plan 作成
- [x] Step 3: 質問生成
- [x] Step 4: 回答収集（unit-of-work.md から推定）
- [x] Step 5: 成果物生成
  - [x] business-logic-model.md
  - [x] business-rules.md
  - [x] domain-entities.md

---

## スコープ確認

**スライス一覧:**

| スライス | 機能 |
|---------|------|
| 2-1 | intent_prompt.py + intent_classifier.py（Nova Micro） |
| 2-2 | character_prompts.py + character_reply.py（Nova Micro） |
| 2-3 | _infer_emotion（感情・疲労度推定） |
| 2-4 | onboarding_flow.py（初回登録チャットフロー） |
| 2-5 | DynamoDB CHAT#{timestamp} 保存（TTL 30日） |
| 2-6 | webhook_handler.py ルーティング統合 |
| 2-7 | PREF_MEMORY 自動蓄積 |
| 2-8 | LLM出力品質テスト |
| 2-9 | 記念日の自然収集 |

---

## 質問

### Q1: Intent 分類の UNKNOWN 閾値とフォールバック動作
Intent 分類で UNKNOWN になった場合の動作を確認します。

**A)** UNKNOWN はそのまま `character_reply` に渡し、雑談として応答する（Nova Micro が判断）  
**B)** UNKNOWN の場合は固定テンプレート「ちょっと意味がわからなかったよ〜😅 もう一度教えて？」を返す  
**C)** UNKNOWN の場合はユーザーに選択肢を提示する（「支出？それともご褒美の話？」）

[Answer]: 

---

### Q2: オンボーディング進行状態の管理方法
オンボーディングは複数ターンにわたる会話フローです。どこで「今どのステップか」を管理しますか？

**A)** DynamoDB に `ONBOARDING_STATE` アイテムを保存し、次回メッセージ時に読み込む  
**B)** `PROFILE` アイテムのフィールド（例: `onboarding_step`）に状態を持つ  
**C)** ステートレス設計にする（ユーザーの返答内容から Nova Micro がステップを推定する）

[Answer]: 

---

### Q3: オンボーディング既完了ユーザーへの再オンボーディング
プロフィール登録済みのユーザーが「オンボーディングしたい」と言ったり、グリート（「こんにちは」）したりした場合の動作は？

**A)** オンボーディングを最初からやり直す（上書き）  
**B)** 「もう登録済みだよ！変更したければ『設定変更して』って言ってね」と返す  
**C)** 変更したい項目だけ個別に聞く差分更新フローにする

[Answer]: 

---

### Q4: character_reply の「口調」選択タイミング
リワードちゃんの口調（friendly / polite / devilish）をどこで決定しますか？

**A)** ユーザープロフィール（PROFILE.tone_preference）に保存されている値を使用  
**B)** システムデフォルト（friendly）固定。Unit 7（LIFF設定画面）で変更可能にするが、Unit 2 では固定で実装  
**C)** Intent と疲労度から動的に決定する（例: 疲労高 → polite/friendly、低 → devilish）

[Answer]: 

---

### Q5: PREF_MEMORY の保存トリガーと抽出方法
PREF_MEMORY（嗜好記憶）はどのように会話から抽出・保存しますか？

**A)** LLM（Nova Micro）がチャット内容を解析し、嗜好情報を JSON で返す。専用プロンプトで抽出  
**B)** キーワードマッチング（「好き」「嫌い」「苦手」「好きじゃない」等のパターン）でルールベース抽出  
**C)** A + B のハイブリッド（キーワード検出時のみ LLM で精緻化）

[Answer]: 

---

### Q6: CHAT ログの DynamoDB スキーマ
CHAT ログの PK/SK 構造を確認します。

**A)** PK: `USER#{line_user_id}` / SK: `CHAT#{ISO8601_timestamp}`  
**B)** PK: `USER#{line_user_id}` / SK: `CHAT#{unix_timestamp_ms}`  
**C)** 別設計がある

[Answer]: 

---

### Q7: webhook_handler.py とのルーティング統合方式
Unit 2 の各ハンドラー（intent_classifier, character_reply, onboarding_flow）を webhook_handler.py からどう呼び出しますか？

**A)** 同一 Lambda 内の関数呼び出し（モジュール import。Lambda はデプロイ済み `WebhookHandlerFunction` に統合）  
**B)** 別 Lambda 関数として分離し、`WebhookHandlerFunction` から boto3 Lambda invoke で呼び出す  
**C)** 共有 Lambda だが、ファイル分割は Unit 2 のハンドラーファイル（intent_classifier.py 等）を src/handlers/ に追加し、webhook_handler.py から import する

[Answer]: 

---

### Q8: 記念日収集（スライス 2-9）の実装スコープ
記念日の自然収集（会話中に「結婚記念日」等を検出）は Unit 2 で実装しますか？

**A)** Unit 2 で実装する（PREF_MEMORY と同じ処理パスに乗せる）  
**B)** Unit 2 では PREF_MEMORY のみ実装し、記念日収集は後回し（Could 要件のため）  
**C)** 記念日収集は今回スコープ外（ハッカソン優先度の観点）

[Answer]: 
