# AI-DLC Audit Log

## Project: オートリワードサービス (Auto Reward Service)

---

## [CONSTRUCTION開始] Unit 0: SAM基盤 + 共通Layer
**Timestamp**: 2026-05-16T00:00:00Z
**User Input**: "全て承認します AI-DLCに従ってconstractionフェーズに進んでください"
**AI Response**: INCEPTIONフェーズ完了を承認。CONSTRUCTIONフェーズ開始。Unit 0 (SAM基盤 + 共通Layer) のFunctional Designから着手。
**Context**: INCEPTION → CONSTRUCTION フェーズ遷移。Unit 0 Functional Design Plan 作成開始。

---

## [Unit 0 Code Generation] 承認
**Timestamp**: 2026-05-16T10:00:00Z
**User Input**: "承認します"
**AI Response**: Unit 0 Code Generation 承認確認。デプロイ確認手順を出力。Unit 1 Functional Design へ進行。
**Context**: AGENTS.md のハイブリッド方式確認。U0 = デプロイ 1回目対象。

---

## [Unit 0 Deploy Round 1] 完了
**Timestamp**: 2026-05-16T12:00:00Z
**結果**: SAM デプロイ成功。CloudFormation stack `auto-reward-service` = CREATE_COMPLETE。
**確認済みリソース**: ArsTable (ACTIVE, PAY_PER_REQUEST, GSI: entityType-index), ArsCommonLayer (v1, python3.14), ArsLambdaRole (スタック完了で存在確認)

---

## [Unit 1] Deploy Round 2 完了・LINE疎通確認
**Timestamp**: 2026-05-16T07:51:00Z
**User Input**: "おくった"
**AI Response**: CloudWatch ログ `reply_message success, message_count:1` 確認。LINE エコー応答成功。Deploy Round 2 完了。
**Context**: Unit 1 全ステージ完了。Unit 2 へ進行。

---

## [Unit 2 Functional Design] 承認
**Timestamp**: 2026-05-16T08:10:00Z
**User Input**: "承認します"
**AI Response**: Functional Design 承認確認。NFR Requirements ステージへ進行。
**Context**: Unit 2 FD 成果物（domain-entities.md / business-logic-model.md / business-rules.md BR-2-01〜BR-2-12+SEC-2-01/02）承認済み。

---

## [Unit 2 NFR Requirements] 承認
**Timestamp**: 2026-05-16T08:20:00Z
**User Input**: "承認します"
**AI Response**: NFR Requirements 承認確認。NFR Design ステージへ進行。
**Context**: nfr-requirements.md / tech-stack-decisions.md 承認済み。Bedrock Nova Micro 追加・DynamoDB 権限追加・PERF-06/07・COST-01 含む。

---

## [Unit 2 NFR Design] 承認
**Timestamp**: 2026-05-16T08:30:00Z
**User Input**: "承認します"
**AI Response**: NFR Design 承認確認。Infrastructure Design ステージへ進行。
**Context**: nfr-design-patterns.md / logical-components.md 承認済み。Bedrock フォールバックチェーン・Reply-First/Log-Later・アトミックカウンタ・プロンプトサンドボックス・入力長ガードパターン確定。

---

## [Unit 2 Infrastructure Design] 承認
**Timestamp**: 2026-05-16T08:40:00Z
**User Input**: "承認します"
**AI Response**: Infrastructure Design 承認確認。Code Generation ステージへ進行。
**Context**: infrastructure-design.md / deployment-architecture.md 承認済み。template.yaml 差分: DAILY_CHAT_LIMIT追加 + CodeUri/Handler変更のみ。

---

## [Unit 2 Code Generation] Plan 承認
**Timestamp**: 2026-05-16T08:50:00Z
**User Input**: "計画確認しました。schemas.py は layer/python/models/ のみ。Plan 承認します ✅ コード生成開始！"
**修正点**: schemas.py は src/models/ に置かない。Handler は `handlers.webhook_handler.handler`（ドット記法）

---

## [Unit 3 Infrastructure Design] 承認
**Timestamp**: 2026-05-16T19:40:00Z
**User Input**: "承認します"
**成果物**: infrastructure-design.md（template.yaml Timeout 変更 / 新規ファイル一覧 / DynamoDB スキーマ追加）
**確定変更**: `WebhookHandlerFunction.Timeout` 10→29秒。新規 AWS リソースなし
**次のアクション**: Code Generation Plan 作成 → コード生成開始

---

## [Unit 3 NFR Design] 承認
**Timestamp**: 2026-05-16T19:30:00Z
**User Input**: "承認します"
**成果物**: nfr-design-patterns.md（Bedrock 呼び出し設計 / Reply-First パターン / エラーハンドリング / PENDING_CLARIFICATION セッション設計 / MonthlyExpenseSummary 設計）
**確定変更**: `WebhookHandlerFunction.Timeout` 10秒 → 29秒（レシート画像解析対応）
**次のアクション**: Infrastructure Design ステージへ進行

---

## [Unit 3 NFR Requirements] 承認
**Timestamp**: 2026-05-16T19:20:00Z
**User Input**: "承認します"
**成果物**: nfr-requirements.md（PERF-3-01〜03 / COST-3-01〜02 / REL-3-01〜03）
**確定事項**: SEC-3-02 入力長を 500→1,000 文字に修正（Unit 2 と統一）
**次のアクション**: NFR Design ステージへ進行

---

## [Unit 3 Functional Design] 完了
**Timestamp**: 2026-05-16T19:10:00Z
**User Input**: Q1=D, Q2=C(amount不足時のみ), Q3=A(confidence<0.7), Q4=B(MVP同期), Q5=B(複数件JSON配列), Q6=固定10カテゴリ, Q7=C(キャラ口調+今月累計)
**AI Response**: Functional Design 3成果物生成完了。
**成果物**:
- `domain-entities.md`: Expense / PendingExpense / ExpenseExtractResult / ReceiptAnalysisResult / MonthlyExpenseSummary / ARSカテゴリ10種
- `business-logic-model.md`: テキスト抽出フロー・追加質問フロー・確認承認フロー・レシート解析フロー・複数件処理・記録後応答ロジック
- `business-rules.md`: BR-3-01〜BR-3-10（機能ルール）+ SEC-3-01〜SEC-3-03（セキュリティ）+ CONST-3-01〜03（制約）
**次のアクション**: NFR Requirements ステージへ進行

---

## [Unit 2 Deploy Round 3] 完了
**Timestamp**: 2026-05-16T18:47:00Z
**結果**: デプロイ成功（ArsCommonLayer:9）。LINE からの応答確認 OK。Unit 2 全ステージ完了。
**修正内容**:
- `put_item()` 引数不足バグ修正（`_handle_follow` + `_save_chat_log` 計3箇所）
- Bedrock モデル ID 修正: `amazon.nova-micro-v1:0`（ap-northeast-1 ON_DEMAND 非対応）→ `us.amazon.nova-micro-v1:0`（クロスリージョン推論、アカウント未設定のため無効）→ 最終: `amazon.nova-lite-v1:0`（全モデル統一）
- template.yaml + bedrock_service.py: `BEDROCK_TEXT/IMAGE/FALLBACK_MODEL_ID` = `amazon.nova-lite-v1:0`
**確認**: CloudWatch ログで `model_id: amazon.nova-lite-v1:0` → `classify_intent REWARD` → `reply_message success` を確認
**次のアクション**: Unit 3（支出記録）Functional Design へ進行

---

## [Unit 2 Code Generation] 完了
**Timestamp**: 2026-05-16T09:30:00Z
**AI Response**: Unit 2 Code Generation 全 12 ステップ完了。pytest 137/137 PASS。
**生成物**:
- `layer/python/models/__init__.py` + `schemas.py`（Pydantic v2 全モデル）
- `layer/python/services/dynamodb_service.py`（query_by_pk limit/descending + increment_atomic_counter 追加）
- `layer/python/services/bedrock_service.py`（invoke_text に system_prompt / temperature パラメータ追加）
- `src/prompts/__init__.py` + `intent_prompt.py` + `character_prompts.py`
- `src/handlers/intent_classifier.py` + `character_reply.py` + `onboarding_flow.py`
- `src/handlers/webhook_handler.py`（Unit 2 全面更新）
- `template.yaml`（DAILY_CHAT_LIMIT 追加 / CodeUri: src/ / Handler: handlers.webhook_handler.handler）
- `tests/unit/conftest.py`（src/ パス追加 / DAILY_CHAT_LIMIT 環境変数追加）
- `tests/unit/test_intent_classifier.py` + `test_character_reply.py` + `test_onboarding_flow.py`（新規 69 テスト）
- `tests/llm/__init__.py` + `test_intent_quality.py`（実 Bedrock LLM 品質テスト）
**テスト結果**: 137/137 PASS
**次のアクション**: Deploy Round 3 — sam build && sam deploy --profile share → LINE で「疲れた」→ リワードちゃん応答確認

---
**Timestamp**: 2026-05-16T07:51:00Z
**User Input**: "厳密にAI-DLCに従い次に進みましょう"
**AI Response**: aidlc-state.md 修正（Unit 1 完了マーク・重複エントリ削除）。Unit 2 Functional Design Plan 作成開始。
**Context**: Unit 2: リワードちゃんキャラクター（F2-01〜F2-06, F3-01〜F3-05）

---

## [Unit 1 Functional Design] 質問回答・成果物生成
**Timestamp**: 2026-05-16T13:00:00Z
**User Input**: Q1=A(同期処理), Q2=A(handler内), Q3=B(固定テンプレート返答), Q4=A(固定文言), Q5=A(WebhookHandler単一)
**AI Response**: 回答に曖昧さなし。FD 成果物 3 ファイル生成完了。
**成果物**: domain-entities.md, business-logic-model.md, business-rules.md
**Context**: Unit 1 Functional Design 成果物生成。承認待ち。

---

## [Unit 0 Code Generation] 成果物生成
**Timestamp**: 2026-05-16T09:00:00Z
**User Input**: "承認します"
**AI Response**: Unit 0 コード生成完了。全スライス (0-1ー0-9) + ユニットテストを生成。
**Context**: 生成ファイル: template.yaml / samconfig.toml / Makefile / requirements*.txt / schemas.py / dynamodb_service.py / bedrock_service.py / line_service.py / google_calendar_service.py / secrets.py / logger.py / exceptions.py + __init__.py群 + tests/unit/ テストコード

---

## [Unit 0 Infrastructure Design] 承認
**Timestamp**: 2026-05-16T08:00:00Z
**User Input**: "承認します"
**AI Response**: Infrastructure Design 承認確認。Code Generation ステージへ進行。
**Context**: Unit 0 Infrastructure Design 完了 → Code Generation 開始

---

## [Unit 0 Infrastructure Design] 成果物生成
**Timestamp**: 2026-05-16T07:00:00Z
**User Input**: "回答しました"
**AI Response**: 全4問の回答を確認。曖昧さなし。Infrastructure Design 成果物2点を生成。
**Context**: Q1:A(VPC外), Q2:A(SAM自動S3), Q3:A(アラームなし), Q4:prodのみ・環境分離なし / スタック名=auto-reward-service

---

## [Unit 0 NFR Design] 承認
**Timestamp**: 2026-05-16T06:00:00Z
**User Input**: "承認します"
**AI Response**: NFR Design 承認確認。Infrastructure Design ステージへ進行。
**Context**: Unit 0 NFR Design 完了 → Infrastructure Design 開始

---

## [Unit 0 NFR Design] 質問回答受取
**Timestamp**: 2026-05-16T05:00:00Z
**User Input**: "回答しました"
**AI Response**: 全4問の回答を確認。曖昧さなし。NFR Design 成果物 2点を生成。
**Context**: Q1:D(API別リトライ: Bedrock指数バックオフ/LINEナシ/Google固定), Q2:D(シングルトンサービスクラス), Q3:A(DLQなし), Q4:B(サービス別分割)

---

## [Unit 0 NFR Requirements] 承認
**Timestamp**: 2026-05-16T04:00:00Z
**User Input**: "承認します"
**AI Response**: NFR Requirements 承認確認。NFR Design ステージへ進行。
**Context**: Unit 0 NFR Requirements 完了 → NFR Design 開始

---

## [Unit 0 NFR Requirements] 質問回答受取
**Timestamp**: 2026-05-16T03:00:00Z
**User Input**: "回答しました"
**AI Response**: 全8問の回答を確認。Q7(Python 3.14)は選択肢外だが意図明確で採用。NFR Requirements 成果物2点を生成。
**Context**: Q1:A(DynamoDB オンデマンド), Q2:C(用途別メモリ), Q3:B(用途別タイムアウト), Q4:B(EventBridge warmup ping), Q5:C(X-Ray無効), Q6:A(Logs 30日), Q7:Python 3.14, Q8:A(ap-northeast-1)

---

## [Unit 0 Functional Design] 承認
**Timestamp**: 2026-05-16T02:00:00Z
**User Input**: "承認します"
**AI Response**: Functional Design 承認確認。NFR Requirements ステージへ進行。
**Context**: Unit 0 Functional Design 完了 → NFR Requirements 開始

---

## [Unit 0 Functional Design] 質問回答受取
**Timestamp**: 2026-05-16T01:00:00Z
**User Input**: "回答しました"
**AI Response**: 全10問の回答を確認。曖昧さなし。Functional Design 成果物3点を生成。
**Context**: Unit 0 Functional Design — Q1:C(entityType GSI), Q2:A(Pydantic v2全モデル), Q3:A(環境変数), Q4:D(SDK薄いラッパー), Q5:A(モジュールキャッシュ), Q6:D(PowerTools+PIIマスク), Q7:A(毎回リフレッシュ), Q8:D(今日+明日), Q9:A(DynamoDBError), Q10:C(services/utils/modelsのみLayer)

---

## [2026-05-16] Google Calendar連携（F9）追加

### 変更の性質
FEATURE_ADD — MVP機能追加（設計ドキュメント変更のみ、アプリコード未作成）

### 変更内容
| 対象ファイル | 変更内容 |
|-------------|---------|
| `requirements.md` | F9セクション追加（F9-01 カレンダーコンテキスト提案 Must, F9-02 LIFF OAuth UI Must）、GOOGLE_OAUTH# スキーマ追加、SEC-08/09追加、技術スタックにGoogle Calendar API追加 |
| `components.md` | `google_calendar_service.py` コンポーネント追加、reward_proposal依存サービスに追記 |
| `component-methods.md` | google_calendar_service の7関数シグネチャ追加 |
| `services.md` | GOOGLE_OAUTH# DynamoDB SK追加、Secrets Manager secrets追加、LIFF APIルート4本追加、LiffApiFunction備考更新 |
| `application-design.md` | システム図更新、リポ構成追加、SEC-08/09セキュリティルール追加 |
| `unit-of-work.md` | スライス 0-9（google_calendar_service基盤）、5-8（カレンダー活用提案）、7-6（OAuth UI）追加 |
| `component-dependency.md` | 呼び出しツリー・依存マトリクス・外部依存テーブル更新 |
| `unit-of-work-story-map.md` | カレンダー連携行追加、F9-01/F9-02カバレッジ追加、SEC-08/09追加、MVPスコープ外からカレンダー連携を削除 |
| `unit-of-work-dependency.md` | Unit 5/Unit 7 前提条件にGoogle Calendar依存追記 |
| `aidlc-state.md` | 確定技術スタックにGoogle Calendar API追加 |
| `README.md` | GOOGLE_OAUTH# スキーマ追加、技術スタックにGoogle Calendar API追加 |

### 設計上の重要決定
- **カレンダーデータのDDB非保存**: イベントタイトル・内容は毎回APIフェッチのみ（プライバシー保護）
- **OAuthスコープ最小化**: `calendar.events.readonly`のみ許可
- **refresh_tokenのみ保存**: `GOOGLE_OAUTH#` SK に暗号化して保存
- **ログ制約**: カレンダーイベント内容は一切CloudWatch Logsに出力しない（SEC-08）

---

## [2026-05-07] ワークフロー開始 / Workspace Detection

### ユーザーリクエスト（原文）
> AI-DLCで開発を進めたい。要件定義書.mdに要件まとめているので、これに沿って進めてください

- **タイムスタンプ**: 2026-05-07
- **結果**: Greenfield プロジェクト（既存アプリコードなし）
- **次フェーズ**: Requirements Analysis

---

## [2026-05-07] Requirements Analysis 完了

- **タイムスタンプ**: 2026-05-07
- **ソース**: `要件定義書.md` を入力として使用
- **回答ファイル**: `aidlc-docs/inception/requirements/requirement-verification-questions.md`
- **生成物**: `aidlc-docs/inception/requirements/requirements.md`
- **Extension Configuration**:
  - Security Baseline: **有効**（全ルール必須制約）
  - Property-Based Testing: **有効（Partial）**（純粋関数・シリアライズのみ）
- **主要決定事項**:
  - フロントエンド: React（Web のみ、MVP）
  - バックエンド: NestJS（TypeScript 統一）
  - 認証: Auth0 / AWS Cognito（マネージド）
  - LLM: OpenAI API（GPT-4o）
  - MVP ではメッセージブローカーなし（同期処理）。Kafka は Growth フェーズで導入
  - デプロイ: ローカル（Docker Compose）→ クラウド移行
- **ステータス**: 完了

---

## [2026-05-08] Units Generation 完了

- **タイムスタンプ**: 2026-05-08
- **回答ファイル**: `aidlc-docs/inception/plans/unit-of-work-plan.md`
- **生成物**:
  - `aidlc-docs/inception/application-design/unit-of-work.md`（Unit 0〜7、機能スライス定義）
  - `aidlc-docs/inception/application-design/unit-of-work-dependency.md`（依存マトリクス・実装順序）
  - `aidlc-docs/inception/application-design/unit-of-work-story-map.md`（US-01〜US-13 全カバレッジ）
- **実装順序**: Unit 0 → 1 → 2 → 4(Reward) → 3(Finance) → 5 → 7(Dashboard) → Web
- **ステータス**: ユーザー承認待ち

---

## [2026-05-08] Application Design 完了

- **タイムスタンプ**: 2026-05-08
- **回答ファイル**: `aidlc-docs/inception/plans/application-design-plan.md`
- **生成物**:
  - `aidlc-docs/inception/application-design/components.md`
  - `aidlc-docs/inception/application-design/component-methods.md`
  - `aidlc-docs/inception/application-design/services.md`
  - `aidlc-docs/inception/application-design/component-dependency.md`
  - `aidlc-docs/inception/application-design/application-design.md`（統合版）
- **主要決定事項**:
  - モノレポ: Turborepo（npm workspaces + ビルドキャッシュ）
  - モジュール境界: ハイブリッド（コアドメイン=ドメイン分割、共通機能=レイヤー分割）
  - サービス間通信: @ars/shared-clients（HTTP 同期）
  - JWT 検証: Nginx（API Gateway）で一元化、X-User-Id ヘッダー転送
  - OpenAI 統合: @ars/shared-ai（共有 AI クライアントモジュール）
  - フロントエンド状態管理: Zustand（グローバル）+ TanStack Query（サーバーステート）
  - フロントエンドコンポーネント: Feature-based
- **ステータス**: ユーザー承認待ち

---

## [2026-05-08] README 豪華化（整合性修正含む）

### ユーザーリクエスト
> AutoRewordServiceについて整合性をチェックしてReadmeを豪華にして

### 検出した不整合
| # | 内容 |
|---|------|
| 1 | README の「主要機能」に U1（ユーザー管理）と U5（通知・配信）が欠落（要件定義書では独立した Unit として定義） |
| 2 | 「購入し、プッシュ通知します」→ U6 は将来フェーズのため「プッシュ通知します」のみに修正 |
| 3 | 技術スタック・アーキテクチャ・KPI・ビジネスモデルが README に全くない |
| 4 | MVP スコープの記載なし |

### 修正・追加内容
- `README.md` を全面書き換え
- バッジ追加（Status / Theme / License / AI / Infra）
- 7 Unit 構成表（U1〜U7 全列、MVP マーク付き）
- アーキテクチャ図（ASCII）・データフロー図（6ステップ）
- ストレススコア算出式・リワード提案マトリクス
- ビジネスモデル・KPI ロードマップ
- 技術スタック・セキュリティ設計・MVP スコープ・ローカル起動手順
- **対象ファイル**: `README.md`

---

## [2026-05-08] Inception フェーズ 不整合チェック＆修正

### ユーザーリクエスト
> inceptionフェーズ内の不整合をチェックして

### 検出・修正した不整合

#### 不整合 A — `unit-of-work-dependency.md` マトリクスの Unit 番号誤り
- **問題**: 依存マトリクスの列ヘッダーが「U3 Reward / U4 Finance / U6 Dashboard」だったが、要件定義書の定義は U3=Finance / U4=Reward / U7=Dashboard
- **修正**: Unit 番号を要件定義書の定義に合わせて全列・全行を修正

#### 不整合 B — `unit-of-work-dependency.md` 誤ったブロッキング依存
- **問題**: Reward Service（U4）の開始前提として「Unit 2 の `/stress/score/current` API が動作する」が記載されていたが、Reward Service は Stress Service に**呼ばれる側**（受信側）であり API 依存は存在しない（`component-dependency.md` と矛盾）
- **修正**: 誤った前提を削除し、正しい説明（RewardClient スタブが定義済みであれば開始可能）に修正

#### 不整合 C — `unit-of-work-dependency.md` StressClient 実装スケジュール誤り
- **問題**: `StressClient` の実装完成が「Unit 2（スライス 2-x）」とあったが、Unit 2 のスライスにその工程は存在せず、StressClient を使用するのは Dashboard Service（Unit 7）のみ
- **修正**: 実装完成を「Unit 7 Dashboard Service（スライス 6-1 内で充実）」に変更

#### 不整合 D — `要件定義書.md` §12 Dashboard API エンドポイント不足
- **問題**: §12 の Dashboard API に `/dashboard/reward-summary` のみで、`services.md` で定義される `/dashboard/reward-history`（U7-02）・`/dashboard/finance-summary`（U7-03）が欠落
- **修正**: 4 エンドポイントすべて（対応機能 ID 付き）を要件定義書に明記

### 修正対象ファイル
- `aidlc-docs/inception/application-design/unit-of-work-dependency.md`（不整合 A / B / C）
- `要件定義書.md`（不整合 D）

---

## [2026-05-08] Audit Log 再構成

### ユーザーリクエスト
> AI-DLCに従ってauditも更新して

### 実施内容
- Requirements Analysis エントリが Application Design エントリの末尾に断片的に混在していた構造上の問題を修正
- 各フェーズのエントリを独立した H2 セクション（時系列順）に再構成
- README 豪華化・Inception 不整合修正の記録を追記
- **対象ファイル**: `aidlc-docs/audit.md`

---

## [2026-05-15] コンセプト大幅変更 — INCEPTION フェーズ再実行

### ユーザーリクエスト（原文）
> AI-DLCに従って開発を進める
> まずは現状の分析をして
> inceptionフェーズが終わったところだが、docs/コンセプト変更定義書.mdの通り大きくコンセプトを変更しようと考えている
> AI-DLCに従って全体的に変更をしてほしい
> 質問があれば質問もお願い

### 変更分類（Change Classification）
- **分類**: **SPEC_CHANGE**（仕様そのものの大幅変更）
- **深刻度**: **全面的なコンセプトピボット**
- **根拠**: `docs/コンセプト変更定義書.md` に基づく

### 旧コンセプト → 新コンセプトの主要差分

| 領域 | 旧コンセプト | 新コンセプト |
|------|-------------|-------------|
| **UI/UX** | React Web App（MVP）+ 将来モバイル | **LINE Bot中心**、Webアプリ不要 |
| **体験の中心** | ダッシュボード＋プッシュ通知 | **リワードちゃん（キャラクター）との会話** |
| **入力方式** | フォーム入力・5段階ストレス評価 | **チャット・画像（レシート）・愚痴** |
| **データ蓄積** | 明示的な記録 | **会話の副産物として自然に育つ** |
| **リワード提案** | ストレス閾値超過→リアルタイム提案 | **ご褒美候補プール方式**（事前蓄積→状態マッチング） |
| **アーキテクチャ** | 6 NestJS マイクロサービス + Nginx + Turborepo | **LINE Bot → API Gateway → Lambda + DynamoDB** |
| **DB** | PostgreSQL / TimescaleDB / ClickHouse / Redis | **DynamoDB** |
| **LLM** | OpenAI GPT-4o | **Amazon Nova（Micro/Lite）**、品質不足時 Haiku/Sonnet |
| **認証** | Auth0 / AWS Cognito + JWT | **LINE ユーザーID ベース** |
| **ダッシュボード** | React Web ダッシュボード | **LIFF（最小限）、数値は見せずキャラの言葉で表現** |
| **通知** | FCM/APNs プッシュ通知 | **LINE Push メッセージ（1日1回上限）** |
| **初回登録** | フォーム＋ウィザード | **リワードちゃんとのチャットで登録** |
| **収益モデル** | サブスクリプション中心 | **アフィリエイト・提携商品・プレミアム課金** |

### 影響範囲
- INCEPTION フェーズの全成果物が影響を受ける
  - `requirements.md` → 全面書き換え
  - `workflow-plan.md` → 全面書き換え
  - `application-design/` 配下全ファイル → 全面書き換え
  - `unit-of-work*.md` → 全面書き換え
- `docs/要件定義書.md` → 新コンセプトに合わせて全面改訂が必要

### 対応方針
- INCEPTION フェーズを Requirements Analysis から再実行
- 新コンセプトに基づく質問ファイルを作成し、不明点を確認
- 回答後、全 Inception 成果物を再生成

### ステータス
- **質問ファイル作成**: `aidlc-docs/inception/requirements/concept-change-questions.md`
- **回答完了**（2026-05-15）

### 確定技術スタック（Q&A 回答より）

| 項目 | 決定内容 |
|------|---------|
| **バックエンド** | AWS Lambda（Python）+ API Gateway（フルサーバーレス） |
| **データベース** | DynamoDB シングルテーブルデザイン（PK=LINEユーザーID, SK=PROFILE#/EXPENSE#…） |
| **LLM** | Amazon Bedrock（Nova Micro/Nova Lite）、モデル切り替え可能設計 |
| **画像解析** | Amazon Nova Lite 第一候補、精度不足時は Textract+LLM or Claude Vision |
| **IaC** | AWS SAM（Serverless Application Model） |
| **LINE APIプラン** | フリープラン（Push通常会話はReply中心、Pushはデモ用・1日1回） |
| **ご褒美データソース** | 楽天API |
| **認証** | LINEユーザーID + LIFF利用時はLINEログインアクセストークン |
| **開発優先順位** | LINE Bot基盤 → リワードちゃん会話品質 → 支出抽出 → ご褒美提案 → その他 |
| **セキュリティ重点** | LINE Bot特有（Webhook署名検証、チャネルシークレット管理） |
| **言語** | Python 統一 |
| **感情把握** | 会話自動推定 主 + 「今日どうだった？」的な間接質問 |
| **テスト戦略** | LLM応答テスト重点（プロンプトテスト・出力品質テスト） |
| **収益機能** | MVPでは実装しない |
| **口調カスタマイズ** | MVP で 2〜3 種類 |
| **MVP スコープ除外** | アフィリエイト実装・サービス強度測定基盤 |

### 次アクション
- Requirements Analysis 再実行 → `requirements.md` 全面書き換え
- Workflow Planning 再実行 → `workflow-plan.md` 全面書き換え
- Application Design 再実行 → `application-design/` 全面書き換え
- Units Generation 再実行 → `unit-of-work*.md` 全面書き換え

---

## [Unit 3 完了] Code Generation + Deploy
**Timestamp**: 2026-05-16T14:08:00Z
**結果**: Unit 3（支出記録）Code Generation 完了。254テスト PASS → Deploy 済み。
**修正内容**:
- `onboarding_flow.py` `_save_onboarding_state`: `ddb_service.put_item(item)` → `ddb_service.put_item(pk, "ONBOARDING_STATE#", item)` 修正。PK/SK を item から削除して3引数呼び出しに修正
- `webhook_handler.py`: follow イベント + 初回メッセージ時の PROFILE# チェック追加、ONBOARDING_STATE# 継続チェック追加
- `onboarding_flow.py`: `handle_onboarding(text=None)` → `start_onboarding()` 呼び出し対応
- `dynamodb_service.py`: `_sanitize_floats()` 追加（float→Decimal 変換）
- `expense_prompt.py`: 金額推測禁止ルール追加
- `.aws-sam/build` キャッシュ混入バグ: クリーンビルドで解消
**デプロイ**: ArsCommonLayer:13 → Lambda 更新確認済み

---

## [U0-U5 品質検証] バグハント + 修正 + Deploy
**Timestamp**: 2026-05-16T15:00:00Z
**ユーザーリクエスト**: "unit5までコードジェネレーション及びデプロイまで完了してるからバグがないかと問題なく動作しているか、想定通りの実装がなされているかを徹底して調査してほしい"
**調査範囲**: U0-U5 全ソースファイル（handlers/prompts/services/models/utils/template.yaml）

### 発見・修正したバグ

| # | 深刻度 | ファイル | 内容 | 影響 |
|---|--------|---------|------|------|
| BUG-01 | **HIGH** | `template.yaml` | `ArsCommonLayer.CompatibleRuntimes` が `python3.14` → 実際の Runtime は `python3.13` | Layer 互換性警告、将来のデプロイ失敗リスク |
| BUG-02 | **HIGH** | `reward_pool_updater.py` | `PrefMemory(**pref_raw)` で PK/SK ケーシング不一致（DynamoDB=大文字 `PK`、Pydantic=小文字 `pk`）→ ValidationError | バッチジョブ: 嗜好データあるユーザーでエラー、デフォルトキーワードにフォールバック |
| BUG-03 | **HIGH** | `reward_pool_updater.py` | `RewardPool(**existing_raw)` で同じ PK/SK 不一致 → 常に失敗 → `existing_items = []` | 差分マージが常に失敗、既存プール（bought/skip フィードバック）が毎回消失 |
| BUG-04 | **MEDIUM** | `webhook_handler.py` | `_detect_preferences` が `update_item` で PREF_MEMORY# を初回作成 → `entityType` なし | データ整合性違反（GSI では見つからない） |
| BUG-05 | **LOW** | `webhook_handler.py` | `UNSUPPORTED_REPLIES` typo:「嫌しいな」→「嬉しいな」 | ユーザーに不自然な日本語表示 |
| BUG-06 | **LOW** | `character_reply.py` | `_infer_emotion` 内で `text_lower = text.lower()` が未使用（デッドコード） | 機能影響なし（キーワードは日本語でケース不変） |

### 修正内容
1. `template.yaml`: `python3.14` → `python3.13`
2. `reward_pool_updater.py`: `PrefMemory(**pref_raw)` → 明示的フィールドマッピング `PrefMemory(pk=pref_raw.get("PK", ""), ...)`
3. `reward_pool_updater.py`: `RewardPool(**existing_raw)` → `raw_items` から `RewardPoolItem(**raw)` を直接構築
4. `webhook_handler.py`: `_detect_preferences` で初回は `put_item` + `entityType` 付き、既存なら `update_item`
5. `webhook_handler.py`: typo「嫌しいな」→「嬉しいな」
6. `character_reply.py`: 未使用変数 `text_lower` 削除

### テスト結果
- **313テスト全PASS**（修正後）

### デプロイ結果
- `sam build && sam deploy`: **UPDATE_COMPLETE**
- `ArsCommonLayer:14` にアップデート
- `WebhookHandlerFunction` + `RewardPoolUpdaterFunction` 両方更新確認

### セキュリティチェック
| チェック項目 | 結果 |
|-------------|------|
| SEC-01: LINE Webhook 署名検証 | ✅ `hmac.compare_digest` 使用 |
| SEC-2-01: プロンプトインジェクション防止 | ✅ `<user_message>` タグ使用（intent/character/reward） |
| SEC-3-02: 入力長ガード | ✅ 1000文字制限 |
| SEC-3-03: 金額範囲バリデーション | ✅ 1〜9,999,999円 |
| SEC-08: カレンダーイベント非保存 | ✅ summary のみ使用、ログ禁止 |
| SEC-09: refresh_token DynamoDB SSE 暗号化 | ✅ |
| PII マスキング | ✅ userId先頭6字+***, message/token=[MASKED] |

### 設計整合性チェック
| チェック項目 | 結果 |
|-------------|------|
| DynamoDB スキーマ整合性 | ✅ 全 SK プレフィックスが schemas.py 定義と一致 |
| Bedrock モデル ID 統一 | ✅ 全て `amazon.nova-lite-v1:0` |
| Reply-First パターン | ✅ webhook_handler で先に返信 → post-reply ops で DB保存 |
| エラーハンドリング | ✅ 全ハンドラーで try/except + WARNING ログ + フォールバック |
| シングルトンパターン | ✅ DDB/Bedrock/LINE の各サービスでモジュールレベルキャッシュ |
| TTL 設定 | ✅ ONBOARDING=7日, CHAT=30日, DAILY_COUNT=翌日, PENDING_CLARIFICATION=10分, PENDING_EXPENSE=24時間 |
