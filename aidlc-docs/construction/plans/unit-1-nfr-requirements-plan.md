# NFR Requirements Plan — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**ステータス**: 完了

---

## 実行計画チェックリスト

- [x] Step 1: Functional Design レビュー・Unit 0 NFR 継承確認
- [x] Step 2: NFR Requirements Plan 作成（本ファイル）
- [x] Step 3: 質問収集・回答受取
- [x] Step 4: 回答の曖昧さ解消（曖昧さなし）
- [x] Step 5: NFR Requirements 成果物生成
  - [x] `nfr-requirements.md`
  - [x] `tech-stack-decisions.md`
- [x] Step 6: 承認・次ステージへ進行

---

## Unit 0 NFR からの継承（質問不要）

以下は Unit 0 で確定済みのため、Unit 1 でも同じルールを適用する。

| NFR ID | 内容 | 継承元 |
|--------|------|--------|
| PERF-03 | ウォームアップ ping（EventBridge 5分毎 `{"source":"warmup"}`） | Unit 0 PERF-03 |
| PERF-05 | WebhookHandler タイムアウト: **10 秒** | Unit 0 PERF-05 |
| SEC-01 | X-Line-Signature 検証必須 → 失敗時 403 | Unit 0 SEC-01 |
| SEC-02 | シークレット平文ハードコード禁止 | Unit 0 SEC-02 |
| SEC-04 | ログに PII 出力禁止（PIIMaskingLogger） | Unit 0 SEC-04 |
| SEC-06 | Lambda IAM 最小権限原則 | Unit 0 SEC-06 |
| SCAL-02 | 予約済み同時実行なし（デフォルト） | Unit 0 SCAL-02 |

---

## 質問一覧（[Answer]: タグで回答してください）

### Q1: WebhookHandlerFunction のメモリ設定

`services.md` では **256 MB** と記載されていますが、Unit 0 の PERF-04 では「軽量ルーティングのみ」として **128 MB** と記載されています。  
Unit 1 時点の WebhookHandler は Bedrock 呼び出しなし・DynamoDB 呼び出しなし（純粋なルーティングのみ）ですが、Unit 2 以降で Bedrock 呼び出しを追加するため、将来的には 256 MB 相当の処理が入ります。

A) **256 MB** — services.md の設定を採用。Unit 2 追加後も変更不要でシンプル  
B) **128 MB** — Unit 1 時点は軽量。Unit 2 で 256 MB に変更

[Answer]: A

---

### Q2: API Gateway スロットリング設定

LINE Platform からの Webhook は正常時でも複数ユーザーが同時送信する可能性があります。
不正リクエストや負荷テストによる誤爆に備えてスロットリングを設定しますか？

A) **デフォルト**（AWS アカウントデフォルト: バースト 5,000 req/s、定常 10,000 req/s）  
B) **カスタム制限**（例: 定常 100 req/s、バースト 200 req/s）— 誤爆防止  
C) **AWS WAF** と組み合わせる（オーバーエンジニアリングのため非推奨）

[Answer]: B
ハッカソン規模（テストユーザー数人）なので 100/200 で十分。誤爆コスト防止優先

---

### Q3: AWS X-Ray トレーシング

Lambda + API Gateway の X-Ray トレーシングを有効にしますか？  
デバッグに有用ですが、コストとコード依存が増えます。

A) **無効**（コスト・シンプルさ優先）  
B) **有効**（Lambda レベルのみ / コード変更なし）  
C) **有効**（Lambda + API Gateway 両方 / CloudWatch ServiceLens と連携）

[Answer]: A
ハッカソン期間中は CloudWatch Logs で十分
