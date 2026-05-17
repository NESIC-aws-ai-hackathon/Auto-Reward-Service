# NFR Design Plan — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16  
**ステータス**: 完了

---

## 実行計画チェックリスト

- [x] Step 1: NFR Requirements 成果物分析
- [x] Step 2: NFR Design Plan 作成（本ファイル）
- [x] Step 3: 質問収集・回答受取
- [x] Step 4: 回答の曖昧さ解消（全問明確）
- [x] Step 5: NFR Design 成果物生成
  - [x] `nfr-design-patterns.md`
  - [x] `logical-components.md`
- [ ] Step 6: 承認・次ステージへ進行

---

## 質問一覧（[Answer]: タグで回答してください）

### Q1: 外部API リトライ戦略（Bedrock / LINE / Google Calendar）

Bedrock や外部 API の一時的なエラー（ThrottlingException、503 等）に対するリトライ戦略を選択してください。

A) **リトライなし** — エラー時は即 `BedrockError` / `LineServiceError` を raise。呼び出し元がエラーをユーザーにフィードバック  
B) **固定インターバルリトライ** — 1秒待って最大2回リトライ。それでも失敗なら例外  
C) **指数バックオフリトライ** — 1回目: 0.5秒, 2回目: 1秒, 3回目: 2秒 (最大3回)。`aws-lambda-powertools` の `retry` ユーティリティを使用  
D) **API 別に使い分け**:
   - Bedrock: 指数バックオフ（C）— ThrottlingException が発生しやすい
   - LINE API: リトライなし（A）— 冪等性が保証できないため
   - Google Calendar: 固定インターバル（B）  
E) その他（具体的に記述してください）

[Answer]: D

---

### Q2: boto3 クライアント/リソース の再利用パターン

Lambda の boto3 クライアント（DynamoDB、Bedrock、Secrets Manager）をコールドスタート以降のウォームインボケーションで再利用する方式を選択してください。

A) **モジュールレベルで初期化**（`secrets.py` の secrets キャッシュと同じパターン）— コールドスタート時のみ接続確立  
B) **ハンドラ関数内で毎回初期化**（シンプルだが接続オーバーヘッドあり）  
C) **サービスクラスのコンストラクタで初期化** + クラスインスタンスをモジュールレベルでシングルトン化  
D) A と C の組み合わせ（モジュールレベルのシングルトンサービスクラス）  
E) その他（具体的に記述してください）

[Answer]: D

---

### Q3: 非同期 Lambda（EventBridge トリガー）の Dead Letter Queue

`RewardPoolUpdater`（Unit 4）、`PushNotifier`（Unit 6）、ウォームアップ Scheduler は EventBridge から非同期呼び出しされます。  
Lambda が失敗した場合の DLQ（Dead Letter Queue）設定を選択してください。

A) **DLQ なし**（MVP 段階は許容。失敗は CloudWatch Logs で検知）  
B) **SQS DLQ** を全 EventBridge トリガー Lambda に設定（失敗メッセージを SQS に保持）  
C) **DLQ なし**、ただし Lambda の `MaximumRetryAttempts=1`（デフォルトは2）に制限  
D) **SQS DLQ** をバッチ系（RewardPoolUpdater / PushNotifier）のみに設定  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q4: Secrets Manager シークレット構成

秘匿値を Secrets Manager にどのように格納するか選択してください。

A) **1つのシークレットにまとめる** — `ars-secrets-{env}` キーに JSON で全シークレットを格納  
B) **サービス別に分割** — `ars/line-{env}`, `ars/bedrock-{env}`, `ars/google-{env}`, `ars/rakuten-{env}` と分割  
C) **A（まとめる）** ただし Google OAuth の `GOOGLE_CLIENT_SECRET` のみ別シークレット（ローテーション管理のため）  
D) **2分割** — アプリシークレット（LINE/楽天）と OAuth シークレット（Google）  
E) その他（具体的に記述してください）

[Answer]: B

