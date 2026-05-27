# AI-DLC Audit Log

## Project: オートリワードサービス (Auto Reward Service)

---

## [MAINTENANCE] v1 LINE Bot → archive 移行・リポジトリ構造刷新
**Timestamp**: 2026-05-26T01:00:00+09:00
**Status**: Complete
**User Input (raw)**: "u1-u7は旧コンセプトだからアーカイブして。旧コンセプトで出た設計等は課題としてbacklogに入れておいて。u8が現コンセプトであるため今後はここをブラッシュアップする必要がある 旧コードも整理して、アーカイブするようにしてほしい 現在使っているものがないかは確認して LINE利用は制限が多かったためやめた旨を記載して 旧コンセプトでデプロイしたものもすべて削除してほしい そのうえで新コンセプトに合わせてREADMEを更新してほしい"

### 実施内容
1. **依存チェック**: U8 が旧コード (`src/`, `layer/`) に依存していないことを確認。ArsTable のみ共有
2. **アーカイブ移動**: 旧コード一式を `archive/v1-line-bot/` に移動
   - `src/`, `layer/`, `template.yaml`, `samconfig.toml`, `Makefile`, `requirements*.txt`
   - `scripts/`, `images/`, `pwa/`, `worker/`, `tools/`, `tests/`
3. **旧スタック削除**: ユーザー判断で**スキップ**（ArsTable がブロッカー。手動で後日対応）
4. **BACKLOG.md 作成**: 旧設計から持ち越すべき15件の課題を優先度付きで整理
5. **README.md 全面書換**: LINE Bot → PWA スタンドアロンに合わせた内容に更新
6. **AGENTS.md 更新**: 新コンセプトのデプロイ・テスト方針に変更
7. **archive/v1-line-bot/README.md 作成**: LINE廃止理由・削除手順・再利用可能資産の説明

### 旧スタック (auto-reward-service) リソース一覧
- Lambda: WebhookHandlerFunction, LiffApiFunction, PwaTemptationFunction, ReceiptProcessorFunction, RewardPoolUpdaterFunction, ScheduledPushFunction
- API Gateway: WebhookApi
- DynamoDB: ArsTable (**U8参照中のため保持**)
- SQS: ReceiptProcessingQueue
- EventBridge: RewardPoolScheduler, ScheduledPushEvening/Night, WarmupWebhookScheduler
- IAM: ArsLambdaRole, SchedulerExecutionRole
- Layer: ArsCommonLayer

### リポジトリ構造（変更後）
```
├── u8/              ← 現行メインアプリ
├── archive/v1-line-bot/  ← 旧コード（参照専用）
├── docs/            ← ドキュメント
├── aidlc-docs/      ← AI-DLC成果物
├── .aidlc/          ← AI-DLCルール
├── BACKLOG.md       ← 旧設計からの課題
├── AGENTS.md        ← 開発ルール
└── README.md        ← プロジェクト説明（新コンセプト）
```

---

## [MAINTENANCE] リポジトリ整理 — 不要ファイル削除
**Timestamp**: 2026-05-26T00:00:00+09:00
**Status**: Complete
**User Input (raw)**: "AI-DLCに従ってリポジトリ内をしっかりと整理してほしい 不要ファイルはすべて削除して"

### 削除対象と理由
| カテゴリ | 削除ファイル/ディレクトリ | 理由 |
|---------|------------------------|------|
| ワンタイムスクリプト | `check_amazon.py`, `check_db.py`, `fix_quotes.py`, `fix_quotes2.py`, `test_wishlist_scrape.py` | アドホックデバッグ・一回限りの修正スクリプト |
| 一時出力 | `deploy-output.txt`, `env-update.json`, `out.json`, `payload.json`, `temp_wishlist.html`, `tmp_pwa_logs.txt` | デプロイログ・テストペイロード・一時ファイル |
| アーカイブ | `layer-update.zip`, `layer.zip` | ビルド成果物（再生成可能） |
| 非推奨コード | `old/` | コンセプト変更前のドキュメント（参照不要） |
| 壊れたGitバックアップ | `.git-NSAPC-61003131A/` | 破損したgitディレクトリ |
| ビルドキャッシュ | `.aws-sam/`, `.pytest_cache/`, `__pycache__/` (src, tests, worker) | 再生成可能なキャッシュ |
| ビルドログ | `u8/sam-build.log`, `u8/sam-deploy.log` | 一時的なログファイル |

### .gitignore更新
- `.git_backup/` → `.git-*/` + `!.git/` + `!.github/` (壊れたバックアップ全般を除外)
- `*.log` / `sam-build.log` / `sam-deploy.log` 追加

### 整理後のルートディレクトリ構成
```
.aidlc/       — AI-DLCルール定義
.github/      — GitHub設定
aidlc-docs/   — AI-DLC成果物（設計書・状態管理）
docs/         — プロジェクトドキュメント
images/       — LINE Rich Menu画像
layer/        — Lambda Layer依存パッケージ
pwa/          — PWA静的ファイル
scripts/      — 運用スクリプト（Rich Menu登録等）
src/          — メインLambdaソースコード
tests/        — テストコード
tools/        — Nova Act Smoke等ツール
u8/           — Unit 8（PWAダッシュボード: frontend + backend + SAM）
worker/       — Nova Act Worker
.gitignore    — Git除外設定
AGENTS.md     — AI Agent設定
Makefile      — ビルドコマンド
README.md     — プロジェクト説明
requirements.txt / requirements-dev.txt — Python依存
samconfig.toml / template.yaml — SAM設定
```

---

## [CONSTRUCTION] Unit 8-B — 音声チャット方針変更 (Nova Sonic 移行)
**Timestamp**: 2026-05-24T18:00:00+09:00
**Status**: Complete
**変更理由**: AWS内完結アーキテクチャの実現（OpenAI API Key不要化）

### 方針変更内容
| 項目 | 旧（OpenAI） | 新（Nova Sonic） |
|------|------------|----------------|
| 音声エンジン | OpenAI Realtime API (gpt-4o-realtime) | Amazon Nova Sonic (amazon.nova-sonic-v1:0) |
| 接続方式 | PWA → WebRTC → OpenAI直接 | PWA → WebSocket → Lambda → Bedrock |
| 認証 | ephemeral key (バックエンド発行) | JWT query param ($connect検証) |
| Transcript保存 | フロントエンドから bulk 送信 | バックエンド側で自動保存 |
| テキストフォールバック | なし | Claude Sonnet テキスト応答 |
| 外部API依存 | OpenAI API Key 必須 | AWS IAM のみ（API Key不要） |

### 影響ファイル（実装）
- `u8/template.yaml` — WebSocket API + VoiceGatewayFunction 追加, OpenAiApiKey 削除
- `u8/backend/handlers/voice_gateway.py` — 新規（WebSocket Lambda）
- `u8/backend/services/sonic_voice_session.py` — 新規（Nova Sonic セッション管理）
- `u8/backend/shared/config.py` — nova_sonic_model_id, websocket_api_endpoint
- `u8/backend/shared/auth.py` — validate_jwt_token() 追加
- `u8/frontend/src/hooks/useVoiceChat.ts` — WebRTC → WebSocket + VAD 全面書換
- `u8/frontend/src/pages/ChatPage.tsx` — テキスト入力追加
- `u8/frontend/src/lib/api.ts` — startVoiceSession() 削除

### 影響ファイル（設計書）
- `aidlc-docs/construction/u8-b/functional-design/business-logic-model.md` — 全面書換
- `aidlc-docs/construction/u8-b/functional-design/business-rules.md` — 全面書換
- `aidlc-docs/construction/u8-b/functional-design/frontend-components.md` — 全面書換
- `aidlc-docs/construction/u8-b/functional-design/domain-entities.md` — VoiceSession属性更新
- `aidlc-docs/inception/application-design/u8-application-design.md` — 音声欄修正

### テスト結果
- 全 70 テスト PASS（新規 9 テスト追加）

---

## [INCEPTION] Unit 8: PWAダッシュボード強化 — Requirements Analysis 開始
**Timestamp**: 2026-05-23T19:00:00+09:00
**User Input (raw)**:
```
方針を変更する
AI-DLCのunit-8機能拡張として仕様書駆動で作成して
PWAサイトを強化して、専用ダッシュボードとしよう
LLMモデルは性能を優先して高価なものも利用することとする
PWAサイトのトップは音声チャット画面、ここでふれまーるちゃんと自由に会話ができる
将来拡張として3Dモデルの利用を検討
会話の内容からライフログ機能と簡易的なダッシュボードと連携する
家計簿ダッシュボードは、余剰金の支出監理にする。この機能は現状の機能を強化する形でおいておく
ライフログは普段どこ行ったかとかどれくらい運動したかやどのようなことをやったかをふれまーるちゃんとの会話の内容から積み上げていく。1日の最後に日記調でサマリを報告する。
ライフログ機能及び家計簿の余剰金の状況から、本人のストレス度などを判定し会話の流れで自然にお金を使ってもいいよという風にサービスや商品に誘導する。
```

### Intent Analysis
- **Request Type**: New Feature (Unit 8 機能拡張)
- **Request Clarity**: Standard（主要方針は明確だが詳細仕様の確認が必要）
- **Scope**: System-wide（PWAフロントエンド + バックエンド + LLM連携 + 新データモデル）
- **Complexity**: Complex（音声チャット + ライフログ + ストレス判定 + 自然な商品誘導）
- **Requirements Depth**: Standard

### Key Feature Areas Identified
1. PWAトップ = 音声チャット（ふれまーるちゃん）
2. 高性能LLMモデル利用（コスト制約緩和）
3. ライフログ機能（会話から自動抽出）
4. 日記サマリ（1日の最後に報告）
5. 余剰金支出管理ダッシュボード（既存強化）
6. ストレス判定 → 商品/サービス誘導
7. 将来拡張: 3Dモデル

### Next Step
- 要件確認質問ファイル生成 → ユーザー回答待ち

### Requirements Analysis 完了
**Timestamp**: 2026-05-23T19:30:00+09:00
**Status**: ユーザー回答受領 → 要件定義書生成完了

**回答サマリ:**
| Q# | トピック | 回答 |
|----|---------|------|
| Q1 | 音声チャット方式 | X: OpenAI Realtime API（分析は別LLMで非同期） |
| Q2 | LLMモデル選定 | E: 用途別使い分け（Realtime: OpenAI / 分析: Claude Sonnet） |
| Q3 | 音声UX | B+テキスト: VADメイン + テキスト切り替え |
| Q4 | ライフログ粒度 | C（詳細だが自然な会話から読み取れる範囲のみ） |
| Q5 | 日記サマリ配信 | D+PWA Push: ふれまーるちゃん読み上げ + ダッシュボード + Push |
| Q6 | ストレス判定 | C: 会話+余剰金+ライフログ複合判定 |
| Q7 | ご褒美誘導 | D: 段階的アプローチ |
| Q8 | LINE Bot関係 | X: LINE Bot廃止、PWAに統合 |
| Q9 | オフライン対応 | A: オンライン前提 |
| Q10 | 3Dモデル準備 | B: アバターエリア予約、初期は静止画 |
| Q11 | 認証 | X: Cognito に寄せる。LINE認証廃止方向 |

**成果物**: `aidlc-docs/inception/requirements/u8-requirements.md`

---

## [INCEPTION] Unit 8 — Requirements Analysis 承認
**Timestamp**: 2026-05-23T19:45:00+09:00
**User Response**: "承認します"（補正3件適用後に承認）
**Status**: Approved
**補正内容**:
1. WebSocket → WebRTC + ephemeral key パターンに変更
2. 広告的文言排除（「おすすめ商品」→「今日の回復案」、カート誘導を主導線から外す）
3. DynamoDB SK統一命名（CONVERSATION_TURN#, LIFE_LOG#, DAILY_FUREMARU_SUMMARY# 等）

---

## [INCEPTION] Unit 8 — Workflow Planning 完了
**Timestamp**: 2026-05-23T19:50:00+09:00
**Status**: Plan Generated

**実行フェーズ決定:**
| フェーズ | 決定 | 理由 |
|---------|------|------|
| User Stories | SKIP | 要件定義書で仕様明確。ハッカソンスピード優先 |
| Application Design | EXECUTE | 新規コンポーネント多数。依存関係定義が必要 |
| Units Generation | EXECUTE | 9機能のデプロイ単位分割が必要 |
| Functional Design | EXECUTE (per-unit) | API仕様・シーケンス詳細化 |
| NFR Requirements | SKIP | 要件定義書で定義済み |
| NFR Design | SKIP | 既存パターン踏襲 |
| Infrastructure Design | SKIP | SAM差分のみ |
| Code Generation | EXECUTE | 実装必須 |
| Build and Test | EXECUTE | テスト必須 |

**成果物**: `aidlc-docs/inception/plans/u8-workflow-plan.md`

## [INCEPTION] Unit 8 — Workflow Planning 承認
**Timestamp**: 2026-05-23T19:55:00+09:00
**User Response**: "承認します"
**Status**: Approved
**Next Stage**: Application Design

---

## [INCEPTION] Unit 8 — Application Design 承認
**Timestamp**: 2026-05-23T20:20:00+09:00
**User Response**: "承認します"（補正4件適用後に承認）
**Status**: Approved
**補正内容**:
1. VOICE_SESSION#{sessionId} エンティティ追加
2. ANALYSIS_JOB#{jobId} エンティティ追加
3. EXPENSE# 書込元修正（SyncApi + Analysis）
4. RecoveryProvider LLM利用範囲明確化
**Next Stage**: Units Generation

---

## [INCEPTION] Unit 8 — Units Generation 完了
**Timestamp**: 2026-05-23T20:30:00+09:00
**Status**: Units Generated

**設計判断回答:**
| Q# | トピック | 回答 |
|----|---------|------|
| Q1 | デプロイスタック | B: 新SAMスタック `ars-u8-pwa`（DynamoDBは既存ArsTable参照） |
| Q2 | 実装優先度 | 提示順通り（U8-A→B→C→D→E） |
| Q3 | 既存コード共存 | A: 完全分離。liff_api.py変更なし |

**Unit分割:**
| Unit | 名称 | 規模 |
|------|------|------|
| U8-A | PWA基盤 + Cognito認証 | Medium |
| U8-B | 音声チャット | Large |
| U8-C | ライフログ + 日記サマリ | Large |
| U8-D | ストレス判定 + 回復提案 | Medium |
| U8-E | ダッシュボード統合 | Medium |

**成果物:**
- `aidlc-docs/inception/application-design/u8-unit-of-work.md`
- `aidlc-docs/inception/application-design/u8-unit-of-work-dependency.md`
- `aidlc-docs/inception/application-design/u8-unit-of-work-story-map.md`

---

## [INCEPTION] Unit 8 — Units Generation 承認
**Timestamp**: 2026-05-24T10:00:00+09:00
**User Response**: "承認します"（補正4件適用後に承認）
**Status**: Approved
**補正内容**:
1. U8-AにDataAccess SK命名規則定義追加
2. U8-C Push範囲明確化（ストレス通知はU8-D）
3. U8-D 0円回復案優先
4. U8-E E2Eデモシナリオ追加
**Next Phase**: CONSTRUCTION — U8-A Functional Design

---

**設計判断回答:**
| Q# | トピック | 回答 |
|----|---------|------|
| Q1 | フロントエンド | C: Vite + React SPA（Next.js不要） |
| Q2 | Lambda構成 | C: ハイブリッド（同期API + 非同期分析分離） |
| Q3 | Transcript保存 | D: ターンごと + 切断時ローカルキャッシュ再送 |
| Q4 | 分析トリガー | B: セッション終了イベント + EventBridge補助 |
| Q5 | PWAホスティング | A: S3 + CloudFront |

**成果物:**
- `aidlc-docs/inception/application-design/u8-components.md`
- `aidlc-docs/inception/application-design/u8-component-methods.md`
- `aidlc-docs/inception/application-design/u8-services.md`
- `aidlc-docs/inception/application-design/u8-component-dependency.md`
- `aidlc-docs/inception/application-design/u8-application-design.md`

---

## [BUG FIX] Webhook 応答欠落 + LIFF URL オンボーディング誘導
**Timestamp**: 2026-05-17T14:00:00Z
**User Input**: "返信しても応答が返ってこないことが多々ある" / "オンボーディングの時はリワードちゃんからオンボーディング用URLへの誘導があるといいかも"

### 根本原因分析
1. **[PRIMARY] Bedrock タイムアウト**: boto3 デフォルト `read_timeout=60s`。ThrottlingException 発生時、`_RETRY_DELAYS = [0.5, 1.0, 2.0]`（3試行）で最悪60s×3+遅延=181秒/Bedrockコール。Lambda 29s制限を超えてタイムアウト → LINE に 200 OK が返らない → 応答なし
2. **[SECONDARY] Warmup がサービス初期化をしない**: `{"source": "warmup"}` 受信時に即返却していたため LINE Service / DynamoDB が未初期化。最初のリクエストで全初期化コストが発生
3. **[PERFORMANCE] Intent 分類に Nova Lite 使用**: 単純な分類に Nova Lite（重い）を使用していた

### 修正内容
| ファイル | 修正内容 |
|---------|---------|
| `layer/python/services/bedrock_service.py` | boto3 に `Config(connect_timeout=5, read_timeout=20, retries={'max_attempts': 1})` 追加。`_RETRY_DELAYS` を `[0.5, 1.0, 2.0]` → `[0.5, 1.0]`（最大2試行）に削減 |
| `src/handlers/intent_classifier.py` | `BEDROCK_INTENT_MODEL_ID` 環境変数追加（デフォルト `nova-micro-v1:0`）。Intent分類をNova Micro（高速・安価）に変更 |
| `src/handlers/webhook_handler.py` | Warmupハンドラーで `get_line_service()` + `_get_ddb()` を事前初期化するよう修正 |
| `src/handlers/onboarding_flow.py` | `import os` 追加。`_liff_hint_for_welcome()` / `_liff_hint_for_completed()` 関数追加。`start_onboarding` と WAITING_BIRTHDAY 完了箇所で LIFF URL 誘導メッセージを付加 |
| `template.yaml` | `BEDROCK_INTENT_MODEL_ID: "amazon.nova-micro-v1:0"` と `LIFF_URL: ""` を Globals に追加 |
| `tests/unit/test_bedrock_service.py` | (変更なし — 既存テストは `_RETRY_DELAYS = [0.5, 1.0]` と互換) |
| `tests/unit/test_webhook_handler.py` | `test_warmup_does_not_initialize_line_service` → `test_warmup_initializes_services` に名称・期待値変更 |

### テスト結果
- **448 テスト全 PASS**（既存 426 + 修正2件のテスト更新）

### デプロイ結果
- SAM `sam build + sam deploy` → CloudFormation `UPDATE_COMPLETE`
- 全 Lambda 関数更新済み（WebhookHandlerFunction 含む）

### 利用方法: LIFF URL の設定
LIFF URL を設定する場合は AWS コンソールまたは samconfig.toml の `parameter_overrides` で:
```
LIFF_URL=https://liff.line.me/{your-liff-id}
```
設定されていない場合はメッセージに URL は含まれない（安全なデフォルト）。

---

## [CONSTRUCTION] Unit 6: Push通知 — Code Generation 完了
**Timestamp**: 2026-05-17T10:00:00Z
**User Input**: "unit6を始めてほしい 要件が明確なものについては質問を飛ばしていいよ、どんどん作って ただし、AI-DLCに従った資料は確実にしっかりと作成するようにして 追加機能指示もunit-6のフォルダに作成しているのでそれも参照して"

### 実施内容
1. **AI-DLC ドキュメント作成**（追加機能指示.md の詳細仕様に基づき質問スキップ）
   - `functional-design/business-logic-model.md` — BL-6-01〜BL-6-06 ビジネスロジック
   - `functional-design/business-rules.md` — BR-6-01〜BR-6-09 ビジネスルール
   - `functional-design/domain-entities.md` — PUSH_QUEUE / PUSH_LOG / PUSH_SETTINGS スキーマ
   - `nfr-infrastructure-design.md` — NFR要件 + NFR設計 + インフラ設計

2. **サービス層（layer/python/services/）**
   - `daily_push.py` — 日次 Push メッセージ生成（8 カテゴリ、時間帯別トーン、重み調整、重複回避）
   - `push_manager.py` — Push 送信 + 月間通数管理（190 通上限）+ PUSH_LOG 記録
   - `preference_extractor.py` — Bedrock による嗜好自動抽出 → PREF_MEMORY 更新

3. **ハンドラー層（src/handlers/）**
   - `push_scheduler_handler.py` — 毎朝 10:00 JST: GSI で全ユーザー取得 → ランダム時刻 → PUSH_QUEUE 書き込み
   - `push_dispatcher_handler.py` — 10 分おき: PUSH_QUEUE から予定時刻到達分を送信
   - `monthly_push_handler.py` — 毎月 1 日 9:00 JST: 月初レポート Push + push_count リセット

4. **template.yaml 更新**
   - PushSchedulerFunction / PushDispatcherFunction / MonthlyPushFunction 追加
   - EventBridge Scheduler 3 本追加（cron/rate）
   - SchedulerExecutionRole に新 Lambda ARN 追加
   - CloudWatch LogGroup 3 本追加
   - Outputs に新 Lambda ARN 追加

5. **schemas.py 更新**
   - `SK_PUSH_SETTINGS` / `SK_PREFIX_PUSH_QUEUE` 定数追加

### テスト結果
- **426 テスト全 PASS**（既存 344 + 新規 82）
- テストファイル: test_daily_push.py / test_push_manager.py / test_preference_extractor.py / test_push_scheduler_handler.py / test_push_dispatcher_handler.py / test_monthly_push_handler.py

### セキュリティ準拠
| チェック | 結果 |
|---------|------|
| SEC-2-01: プロンプトインジェクション防止 | ✅ preference_extractor で `<user_message>` タグ使用 |
| PII マスキング | ✅ user_id は先頭6字 + *** でログ出力 |
| 月間通数制限 | ✅ 190 通上限チェック（フリープラン 200 通の安全マージン） |

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
