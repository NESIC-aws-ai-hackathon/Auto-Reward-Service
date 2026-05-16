# コンポーネント定義 — オートリワードサービス（v2）

**改訂日**: 2026-05-15 / コンセプト変更後版

**アーキテクチャ方針:**
- 実行基盤: **AWS Lambda（Python）+ API Gateway + DynamoDB**
- LLM: **Amazon Bedrock（Nova Micro / Nova Lite）**
- IaC: **AWS SAM**

---

## リポジトリ構成

```
auto-reward-service/               <- SAM プロジェクトルート
+-- src/
|   +-- handlers/                  # Lambda関数ハンドラー（Unit 1-7）
|   |   +-- webhook_handler.py     # Unit 1: LINE Webhook受信・Router
|   |   +-- intent_classifier.py   # Unit 2: Intent分類（Nova Micro）
|   |   +-- character_reply.py     # Unit 2: リワードちゃん口調生成
|   |   +-- onboarding_flow.py     # Unit 2: 初回登録チャットフロー
|   |   +-- expense_extractor.py   # Unit 3: 支出抽出・確認フロー
|   |   +-- receipt_analyzer.py    # Unit 3: レシート画像解析（Nova Lite）
|   |   +-- reward_proposal.py     # Unit 5: ご褒美候補マッチング
|   |   +-- reward_pool_updater.py # Unit 4: 日次バッチ（楽天API）
|   |   +-- push_notifier.py       # Unit 6: Push通知送信
|   |   +-- liff_api.py            # Unit 7: LIFF用API
|   +-- services/                  # 共通サービスモジュール（Unit 0）
|   |   +-- dynamodb_service.py    # DynamoDB操作共通
|   |   +-- bedrock_service.py     # Bedrock呼び出し共通
|   |   +-- line_service.py        # LINE API（Reply/Push/署名検証）
|   |   +-- rakuten_service.py     # 楽天API連携（商品・トラベル）
|   |   +-- hotpepper_service.py   # ホットペッパーグルメAPI（Unit 4 Growth）
|   |   +-- google_calendar_service.py # Google Calendar参照（OAuth + 予定取得）
|   |   +-- finance_engine.py      # 余裕額算出ロジック
|   |   +-- reward_pool_service.py # 候補プール選択ロジック
|   +-- models/
|   |   +-- schemas.py             # DynamoDBスキーマ定数・Pydanticモデル
|   +-- prompts/                   # LLMプロンプトテンプレート
|   |   +-- intent_prompt.py       # Intent分類プロンプト
|   |   +-- expense_prompt.py      # 支出抽出プロンプト
|   |   +-- character_prompts.py   # 口調別リワードちゃんプロンプト
|   |   +-- receipt_prompt.py      # レシート解析プロンプト
|   +-- utils/
|       +-- secrets.py             # Secrets Manager/SSM取得
|       +-- logger.py              # 構造化ログ（PIIマスク）
+-- tests/
|   +-- unit/                      # ユニットテスト（pytest）
|   +-- integration/               # 統合テスト
|   +-- llm/                       # LLM応答品質テスト
+-- liff/                          # LIFFフロントエンド（Unit 7）
|   +-- index.html
|   +-- settings.html
|   +-- assets/
+-- template.yaml                  # AWS SAM テンプレート
+-- samconfig.toml                 # SAM設定
+-- requirements.txt               # 本番依存
+-- requirements-dev.txt           # 開発依存（pytest等）
+-- Makefile                       # ビルド・テスト・デプロイ用
```

---

## Lambda ハンドラー一覧

| Lambda関数名 | Unit | トリガー | 記述 |
|-----------|------|---------|------|
| `webhook_handler` | Unit 1 | API Gateway POST /webhook | LINE Webhook受信・Router |
| `intent_classifier` | Unit 2 | 内部呼び出し | Nova MicroでIntent分類 |
| `character_reply` | Unit 2 | 内部呼び出し | リワードちゃん口調生成 |
| `onboarding_flow` | Unit 2 | 内部呼び出し | 初回登録チャットフロー |
| `expense_extractor` | Unit 3 | 内部呼び出し | 支出抽出・JSON化・確認 |
| `receipt_analyzer` | Unit 3 | 内部呼び出し | Nova Lite画像解析 |
| `reward_proposal` | Unit 5 | 内部呼び出し | 候補プールマッチング |
| `reward_pool_updater` | Unit 4 | EventBridge Scheduler | 楽天API→候補プール更新 |
| `push_notifier` | Unit 6 | EventBridge Scheduler | Push送信・通数管理 |
| `liff_api` | Unit 7 | API Gateway GET/POST /liff/* | LIFF用API |

---

## Lambda ハンドラー詳細

### webhook_handler（Unit 1）

| 項目 | 内容 |
|------|------|
| **責務** | LINE Webhookイベント受信・署名検証・メッセージ種別判定・各ハンドラーへの振り分け |
| **トリガー** | API Gateway（POST /webhook） |
| **入力** | LINE Webhook Event（JSON） |
| **出力** | 200 OK（LINE Platformへの応答） |
| **依存サービス** | `line_service`（署名検証）, `secrets`（チャネルシークレット）, `logger` |
| **主要ロジック** | 1. X-Line-Signature検証 → 失敗時403 2. event.type判定 3. message.type分岐（text→intent_classifier, image→receipt_analyzer, その他→character_reply） |
| **NFR** | SEC-01（署名検証必須）, PERF-01（3秒以内応答） |

### intent_classifier（Unit 2）

| 項目 | 内容 |
|------|------|
| **責務** | ユーザーテキストのIntent分類（EXPENSE/REWARD/GREET/CHAT/ONBOARDING/UNKNOWN） |
| **入力** | `user_id: str`, `text: str` |
| **出力** | `{"intent": str, "confidence": float}` |
| **依存サービス** | `bedrock_service`（Nova Micro）, `dynamodb_service`（CHATログ保存）, `secrets`, `logger` |
| **主要ロジック** | 1. intent_prompt.py でプロンプト構築 2. Nova Micro呼び出し 3. Intent + confidence返却 4. CHAT SK でログ保存 |
| **NFR** | TEST-01（Intent分類精度テスト） |

### character_reply（Unit 2）

| 項目 | 内容 |
|------|------|
| **責務** | リワードちゃんの口調でReplyテキストを生成 |
| **入力** | `user_id: str`, `context: dict`, `tone_style: str` |
| **出力** | `str`（リワードちゃんの応答テキスト） |
| **依存サービス** | `bedrock_service`（Nova Micro）, `dynamodb_service`（LIFELOG保存）, `line_service`（Reply送信）, `secrets`, `logger` |
| **主要ロジック** | 1. DynamoDBからユーザーPROFILE・直近CHAT取得 2. character_prompts.pyで口調テンプレート選択 3. Nova Micro呼び出し 4. LINE Reply送信 5. LIFELOG保存（推定感情・疲労度） |
| **口調バリエーション** | `friendly`（デフォルト）, `polite`（やさしい敬語）, `devilish`（小悪魔） |

### onboarding_flow（Unit 2）

| 項目 | 内容 |
|------|------|
| **責務** | 初回登録チャットフロー（収入・固定費・ご褒美枠をチャットで収集） |
| **入力** | `user_id: str`, `text: str` |
| **出力** | Reply メッセージ（次の質問 or 登録完了） |
| **依存サービス** | `bedrock_service`（Nova Micro）, `dynamodb_service`（PROFILE/FIXED_COSTS保存）, `line_service`, `secrets`, `logger` |
| **主要ロジック** | 1. DynamoDBからPROFILE取得（onboarding_step確認） 2. ステップに応じた質問・回答解析 3. 完了時にPROFILE + FIXED_COSTS保存 + ご褒美枠算出 |

### expense_extractor（Unit 3）

| 項目 | 内容 |
|------|------|
| **責務** | テキストから支出情報をJSON化し、確認フローを経てDynamoDBに保存 |
| **入力** | `user_id: str`, `text: str` |
| **出力** | Reply メッセージ（確認質問 or 登録完了通知） |
| **依存サービス** | `bedrock_service`（Nova Micro）, `dynamodb_service`（PENDING_EXPENSE/EXPENSE保存）, `line_service`, `secrets`, `logger` |
| **主要ロジック** | 1. expense_prompt.pyでプロンプト構築 2. Nova Micro → 支出JSON 3. confidence低→追加質問 4. 確認→yes→EXPENSE保存 / no→破棄 5. ARSカテゴリ付与（情緒安定費・回復費等） |

### receipt_analyzer（Unit 3）

| 項目 | 内容 |
|------|------|
| **責務** | レシート画像から支出情報を抽出しJSON化 |
| **入力** | `user_id: str`, `message_id: str` |
| **出力** | Reply メッセージ（解析結果の確認） |
| **依存サービス** | `bedrock_service`（Nova Lite）, `line_service`（Content API + Reply）, `dynamodb_service`（PENDING_EXPENSE保存）, `secrets`, `logger` |
| **主要ロジック** | 1. LINE Content APIで画像バイナリ取得 2. receipt_prompt.pyでプロンプト構築 3. Nova Lite（マルチモーダル）で解析 4. 3秒以内→Reply / 3秒超→「解析中だよ〜」Reply + 非同期 |
| **NFR** | PERF-02（3秒超→非同期化） |

### reward_proposal（Unit 5）

| 項目 | 内容 |
|------|------|
| **責務** | ユーザーの状態と候補プールからご褒美を提案し、キャラ口調で返す |
| **入力** | `user_id: str`, `context: dict` |
| **出力** | Reply メッセージ（ご褒美提案 or 買いすぎ注意） |
| **依存サービス** | `finance_engine`, `reward_pool_service`, `google_calendar_service`（カレンダーコンテキスト取得）, `character_reply`, `dynamodb_service`（REWARD_SUGGESTION保存）, `line_service`, `secrets`, `logger` |
| **主要ロジック** | 1. finance_engine.calculate_available_budget() 2. 余裕額≦0→買いすぎストップ（やんわり口調） 3. reward_pool_service.select_candidates()で候補選択 4. character_replyでキャラ口調提案生成 5. REWARD_SUGGESTION保存 |

### reward_pool_updater（Unit 4）

| 項目 | 内容 |
|------|------|
| **責務** | 日次バッチで全ユーザーの候補プールを楽天APIから更新 |
| **トリガー** | EventBridge Scheduler（毎日深夜） |
| **入力** | Schedulerイベント |
| **出力** | なし（DynamoDB更新） |
| **依存サービス** | `dynamodb_service`（PREF_MEMORY取得/REWARD_POOL更新）, `rakuten_service`, `reward_pool_service`, `secrets`, `logger` |
| **主要ロジック** | 1. 全ユーザーのPREF_MEMORY取得 2. 嗜好カテゴリで楽天API検索 3. 既存候補のスコア更新（スルー→減、購入系統→増） 4. 古い候補削除 5. REWARD_POOL保存 |

### push_notifier（Unit 6）

| 項目 | 内容 |
|------|------|
| **責務** | 1日1回のPush通知送信・通数管理 |
| **トリガー** | EventBridge Scheduler（1日1回） |
| **入力** | Schedulerイベント |
| **出力** | なし（LINE Push送信） |
| **依存サービス** | `dynamodb_service`（対象ユーザー取得・Push履歴確認）, `bedrock_service`（Nova Micro）, `line_service`（Push送信）, `secrets`, `logger` |
| **主要ロジック** | 1. DynamoDBから対象ユーザー取得（今日未Push + 月200通未達） 2. Nova Microでコンテンツ生成 3. LINE Push API送信 4. Push履歴保存 |
| **NFR** | COST-03（月200通上限遵守） |

### liff_api（Unit 7）

| 項目 | 内容 |
|------|------|
| **責務** | LIFFアプリ用APIエンドポイント（履歴・設定・口調変更） |
| **トリガー** | API Gateway（GET/POST /liff/*） |
| **入力** | LIFFアクセストークン + リクエストパラメータ |
| **出力** | JSON レスポンス |
| **依存サービス** | `dynamodb_service`, `finance_engine`, `reward_pool_service`, `secrets`, `logger` |
| **主要ロジック** | 1. LIFFアクセストークン検証（LINE Platform API） 2. パス分岐（/history, /settings, /pool） 3. DynamoDB読み書き 4. JSON返却 |
| **NFR** | SEC-07（LIFFトークン検証必須） |

---

## 共通サービスモジュール詳細

### dynamodb_service（Unit 0）

| 項目 | 内容 |
|------|------|
| **責務** | DynamoDBシングルテーブルへの共通CRUD操作 |
| **提供メソッド** | `put_item`, `get_item`, `query_by_sk_prefix`, `update_item`, `delete_item`, `batch_get` |
| **設計ポイント** | PK/SK構築ヘルパー付き。エンティティ種別ごとのSKプレフィックス定数を`schemas.py`から参照 |

### bedrock_service（Unit 0）

| 項目 | 内容 |
|------|------|
| **責務** | Amazon Bedrockへのテキスト/画像推論リクエスト共通処理 |
| **提供メソッド** | `invoke_model(prompt, model_id, image_bytes)` |
| **設計ポイント** | model_idを設定ファイルから取得（モデル切り替え可能）。Nova Micro（テキスト）/ Nova Lite（マルチモーダル）をデフォルト |

### line_service（Unit 0）

| 項目 | 内容 |
|------|------|
| **責務** | LINE Messaging APIとの通信一元管理 |
| **提供メソッド** | `verify_signature`, `reply_message`, `push_message`, `get_content`, `get_profile` |
| **設計ポイント** | チャネルアクセストークン・シークレットはsecrets経由。Push送信前に通数チェックを呼び出し元の責務とする |

### rakuten_service（Unit 4）

| 項目 | 内容 |
|------|------|
| **責務** | 楽天ウェブサービスAPIとの連携（商品検索 + トラベル施設検索） |
| **提供メソッド** | `search_items(keyword, genre_id, price_range)`, `search_hotels(checkin, checkout, area_code, max_charge)` |
| **設計ポイント** | APIキーはsecrets経由。レート制限対応（リトライ + バックオフ）。レスポンスをARS内部候補フォーマットに変換。**MVPは `search_items` のみ**、`search_hotels` は Growthフェーズ。新ドメイン `openapi.rakuten.co.jp`（2026/2月移行済）・`accessKey`ヘッダー必須 |

### hotpepper_service（Unit 4 Growth）

| 項目 | 内容 |
|------|------|
| **責務** | ホットペッパーグルメAPIとの連携（エリア・ジャンル・予算・位置情報で検索） |
| **提供メソッド** | `search_restaurants(lat, lng, budget_code, genre_code, count)` |
| **設計ポイント** | APIキーはsecrets経由（`ars/hotpepper/api-key`）。リクルートID登録で即日無料取得。位置情報は将来LIFF経由で取得。**Growthフェーズ実装**。なおじゃらんWebサービスは同種の旅行検索APIだが、トラベルは楽天でカバーできるため優先度低 |

### google_calendar_service（Unit 0）

| 項目 | 内容 |
|------|------|
| **責務** | Google Calendar APIとの連携（OAuth 2.0 + 予定取得） |
| **提供メソッド** | `get_today_events(user_id)`, `get_upcoming_events(user_id, days)`, `exchange_code(auth_code)`, `is_connected(user_id)` |
| **OAuthフロー** | LIFF設定画面からGoogle OAuth 2.0同意画面へリダイレクト → コールバックでauthorization code取得 → `liff_api` 経由でtoken交換 |
| **スコープ** | `calendar.events.readonly`（読み取り専用）のみ |
| **データ保存ポリシー** | **カレンダーデータはDynamoDBに一切保存しない**。毎回APIでフェッチ。OAuth `refresh_token` のみDynamoDB `GOOGLE_OAUTH#` SKに保存（暗号化） |
| **ログ制約** | カレンダーのイベントタイトル・内容は一切ログ出力しない（SEC-04強化、個人情報保護） |
| **設計ポイント** | Google API Client ID / Secret は secrets 経由。access_token は毎回 refresh_token から再取得（Lambdaメモリ内のみ）。接続解除機能付き（LIFF設定画面から refresh_token 削除 + Google側revoke） |

### finance_engine（Unit 5）

| 項目 | 内容 |
|------|------|
| **責務** | ご褒美に使える余裕額算出（純粋計算ロジック） |
| **提供メソッド** | `calculate_available_budget(user_id)` |
| **算出ロジック** | `reward_budget = max(0, min(monthly_reward_limit, (income - fixed_costs) * 0.15) - current_month_expense)` |
| **設計ポイント** | 常に0以上を保証。DynamoDBからPROFILE・FIXED_COSTS・今月EXPENSEを取得して計算 |

### reward_pool_service（Unit 4/5）

| 項目 | 内容 |
|------|------|
| **責務** | 候補プールから状態に合った候補を選択するマッチングロジック |
| **提供メソッド** | `select_candidates(user_id, state, budget)` |
| **設計ポイント** | 感情・疲労度・嗜好カテゴリ・予算範囲でフィルタ&スコアリング。上位N件を返却 |

### secrets（Unit 0）

| 項目 | 内容 |
|------|------|
| **責務** | AWS Secrets Manager / SSM Parameter Storeからの認証情報取得 |
| **提供メソッド** | `get_secret(name)`, `get_parameter(name)` |
| **設計ポイント** | Lambda実行環境でキャッシュ（Cold Start対策）。平文ハードコード禁止の強制 |

### logger（Unit 0）

| 項目 | 内容 |
|------|------|
| **責務** | 構造化ログ出力（JSON形式）・PII自動マスク |
| **提供メソッド** | `info`, `warn`, `error`, `debug` |
| **設計ポイント** | LINEユーザーID・チャットテキスト等のPIIをマスク（SEC-04準拠）。CloudWatch Logs向けJSON構造化出力 |

---

## コンポーネント間インターフェースパターン

| パターン | 用途 | 例 |
|---------|------|-----|
| **Lambda内部呼び出し** | webhook_handler → 各ハンドラー | Python関数直接import（同一Lambda内の場合）または Lambda invoke |
| **共通サービスimport** | 各ハンドラー → services/ | `from services.dynamodb_service import put_item` |
| **EventBridge Scheduler** | 定時バッチ起動 | Scheduler → reward_pool_updater / push_notifier |
| **API Gateway → Lambda** | HTTP受信 | LINE Webhook / LIFF API |
| **LINE Platform API** | 外部通信 | line_service → LINE Messaging API |
| **Amazon Bedrock** | LLM推論 | bedrock_service → Bedrock Runtime API |
| **楽天API** | 外部商品検索 | rakuten_service → 楽天ウェブサービスAPI |
