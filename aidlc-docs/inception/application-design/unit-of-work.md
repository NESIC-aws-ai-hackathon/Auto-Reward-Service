# Unit of Work 定義 — オートリワードサービス（v2）

**改訂日**: 2026-05-15 / コンセプト変更後版

## 実装サイクル方針（確定）

| 項目 | 決定内容 |
|------|---------|
| 実装粒度 | **機能スライス単位**（各 Unit の中の機能を小さく区切って実装） |
| 基盤 | **Unit 0 として最初のサイクルで実装**（SAMプロジェクト + DynamoDB + 共通Layer） |
| テスト | **コード生成と同じサイクル**（ユニットテスト + LLM品質テストを含める） |
| デプロイ | **AWS SAM**（`sam build && sam deploy`）で各Unitをデプロイ |

---

## プロジェクト コード構成方針

```
auto-reward-service/               ← SAM プロジェクトルート
├── src/
│   ├── handlers/
│   │   ├── webhook_handler.py     # Unit 1
│   │   ├── intent_classifier.py   # Unit 2
│   │   ├── character_reply.py     # Unit 2
│   │   ├── onboarding_flow.py     # Unit 2
│   │   ├── expense_extractor.py   # Unit 3
│   │   ├── receipt_analyzer.py    # Unit 3
│   │   ├── reward_pool_updater.py # Unit 4
│   │   ├── reward_proposal.py     # Unit 5
│   │   ├── push_notifier.py       # Unit 6
│   │   └── liff_api.py            # Unit 7
│   ├── services/
│   │   ├── dynamodb_service.py    # Unit 0
│   │   ├── bedrock_service.py     # Unit 0
│   │   ├── line_service.py        # Unit 0
│   │   ├── rakuten_service.py     # Unit 4
│   │   ├── finance_engine.py      # Unit 5
│   │   └── reward_pool_service.py # Unit 4/5
│   ├── models/
│   │   └── schemas.py             # Unit 0
│   ├── prompts/
│   │   ├── intent_prompt.py       # Unit 2
│   │   ├── expense_prompt.py      # Unit 3
│   │   ├── character_prompts.py   # Unit 2
│   │   └── receipt_prompt.py      # Unit 3
│   └── utils/
│       ├── secrets.py             # Unit 0
│       └── logger.py              # Unit 0
├── tests/
│   ├── unit/
│   ├── integration/
│   └── llm/                       # LLM応答品質テスト
├── template.yaml                  # AWS SAM テンプレート
├── samconfig.toml
├── requirements.txt
├── requirements-dev.txt
└── Makefile
```

---

## Unit 一覧

### Unit 0: SAM基盤 + 共通Layer

**最初のサイクルで実装（先行必須）**

| 内容 | 詳細 |
|------|------|
| **スコープ** | SAMプロジェクト初期化、DynamoDBテーブル定義、共通Layerモジュール |
| **成果物** | `template.yaml`（骨格）, `dynamodb_service.py`, `bedrock_service.py`, `line_service.py`, `schemas.py`, `secrets.py`, `logger.py` |
| **完了条件** | `sam deploy` でDynamoDBテーブル作成成功; 共通Layerが各Lambdaからimportできる |

**機能スライス:**

| スライス | 内容 |
|---------|------|
| 0-1 | SAMプロジェクト初期化・`template.yaml`骨格・`samconfig.toml`・`Makefile` |
| 0-2 | `schemas.py`: DynamoDBスキーマ定数・Pydanticモデル定義 |
| 0-3 | `dynamodb_service.py`: put/get/query/update共通操作 |
| 0-4 | `bedrock_service.py`: Bedrockテキスト/画像呼び出し共通（モデルID設定ファイル化） |
| 0-5 | `line_service.py`: Reply/Push/署名検証/Content API |
| 0-6 | `secrets.py`: Secrets Manager/SSM取得ユーティリティ |
| 0-7 | `logger.py`: 構造化ログ（PII出力禁止） |
| 0-8 | DynamoDB `ArsTable` SAMリソース定義（PK/SK + GSI） |

---

### Unit 1: LINE Bot基盤（F1対応）

**対応要件**: F1-01〜F1-04

| 内容 | 詳細 |
|------|------|
| **スコープ** | Webhook受信・署名検証・メッセージルーティング |
| **依存** | Unit 0 |
| **完了条件** | LINE Webhookが受信できる; テキスト/画像/その他を正しくルーティングできる |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 1-1 | `webhook_handler.py`: API Gateway Lambda統合・LINEイベント受信 | F1-01 |
| 1-2 | 署名検証（`X-Line-Signature`検証）・失敗時403返却 | F1-01 |
| 1-3 | Message Router（text/image/sticker分岐）+ 各Lambdaへのルーティング | F1-02 |
| 1-4 | Reply送信（line_service）・エラー時フォールバック | F1-03 |
| 1-5 | SAMテンプレートに WebhookHandlerFunction + WebhookApi 追加 | — |
| 1-6 | Webhook署名検証のセキュリティテスト | SEC-01 |

---

### Unit 2: リワードちゃんキャラクター（F2・F3対応）

**対応要件**: F2-01〜F2-04, F3-01〜F3-04

| 内容 | 詳細 |
|------|------|
| **スコープ** | Intent分類・キャラ口調生成・初回登録フロー・感情把握 |
| **依存** | Unit 0, Unit 1 |
| **完了条件** | 「今日疲れた」に対してリワードちゃん口調でReplyが返る; 初回登録フローが完結する |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 2-1 | `intent_prompt.py` + `intent_classifier.py`: Intent分類（Nova Micro） | F3-04 |
| 2-2 | `character_prompts.py`: フレンドリー口調プロンプト（デフォルト） | F3-01 |
| 2-3 | `character_reply.py`: Nova Microで口調生成・DynamoDB LIFELOG保存 | F3-01 |
| 2-4 | `onboarding_flow.py`: 収入/固定費チャット登録フロー・DynamoDB PROFILE/FIXED_COSTS保存 | F2-01〜F2-04 |
| 2-5 | 口調カスタマイズ追加（やさしい敬語・小悪魔） | F3-02 |
| 2-6 | 制限到達退場演出（複数パターン） | F3-03 |
| 2-7 | LLMプロンプトテスト（Intent精度・口調品質テスト） | TEST-01 |

---

### Unit 3: 支出記録（F4対応）

**対応要件**: F4-01〜F4-05

| 内容 | 詳細 |
|------|------|
| **スコープ** | チャット支出抽出・確認フロー・レシート画像解析 |
| **依存** | Unit 0, Unit 1, Unit 2 |
| **完了条件** | 「プリン買った」で支出登録できる; レシート画像から支出JSON化できる |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 3-1 | `expense_prompt.py` + `expense_extractor.py`: テキスト→支出JSON化（Nova Micro） | F4-01 |
| 3-2 | 追加質問フロー（金額・商品名が不足時にリワードちゃんが聞く） | F4-02 |
| 3-3 | 確認・承認フロー（信頼度低→確認メッセージ→yes/noで保存） | F4-03 |
| 3-4 | DynamoDB EXPENSE保存（確定後） | F4-01 |
| 3-5 | `receipt_prompt.py` + `receipt_analyzer.py`: Nova Liteで画像→支出JSON | F4-04 |
| 3-6 | レシート解析時間チェック（3秒超→非同期化→Push or「結果を見る」ボタン） | PERF-02 |
| 3-7 | ARSカテゴリ分類（情緒安定費・回復費・緊急回復費等） | F4-05 |
| 3-8 | LLM出力品質テスト（支出抽出精度） | TEST-01 |

---

### Unit 4: ご褒美候補プール（F5対応）

**対応要件**: F5-01〜F5-05

| 内容 | 詳細 |
|------|------|
| **スコープ** | 嗜好記憶蓄積・楽天API連携・日次バッチでプール更新 |
| **依存** | Unit 0, Unit 2 |
| **完了条件** | 日次バッチが動作し、楽天APIの商品がDynamoDB reward_poolに格納される |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 4-1 | `rakuten_service.py`: 楽天ウェブサービスAPI商品検索 | F5-03 |
| 4-2 | `reward_pool_service.py`: 嗜好×候補スコアリングロジック | F5-01 |
| 4-3 | `reward_pool_updater.py`: 全ユーザー嗜好取得→楽天API→プール更新 | F5-02 |
| 4-4 | EventBridge Scheduler SAMリソース定義（RewardPoolScheduler） | F5-02 |
| 4-5 | スルー・購入履歴によるスコア調整 | F5-04, F5-05 |
| 4-6 | 楽天APIモックテスト | TEST-04 |

---

### Unit 5: ご褒美提案（F6対応）

**対応要件**: F6-01〜F6-05

| 内容 | 詳細 |
|------|------|
| **スコープ** | 状態推定・候補プールマッチング・余裕額チェック・キャラ口調での提案 |
| **依存** | Unit 0, Unit 2, Unit 3, Unit 4 |
| **完了条件** | 「疲れた」でご褒美提案がリワードちゃん口調で返る; 余裕額超過時はやんわり止める |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 5-1 | `finance_engine.py`: DynamoDBから余裕額算出（0以上・上限超えない） | F6-04 |
| 5-2 | `reward_proposal.py`: 状態ベクトル生成→候補プールマッチング | F6-01, F6-02 |
| 5-3 | 余裕額チェック→予算内候補のみ選択 | F6-04 |
| 5-4 | キャラ口調での提案メッセージ生成（Nova Micro） | F6-03 |
| 5-5 | 買いすぎストップ（余裕額≦0時のやんわり止めReply） | F6-05 |
| 5-6 | 提案履歴をDynamoDB REWARD_SUGGESTIONに保存 | F6-01 |
| 5-7 | finance_engineユニットテスト（余裕額常に0以上・上限超えない） | TEST-02 |

---

### Unit 6: Push通知（F7対応）

**対応要件**: F7-01〜F7-03

| 内容 | 詳細 |
|------|------|
| **スコープ** | Push通知送信・1日1回上限管理・コンテンツ生成 |
| **依存** | Unit 0, Unit 2, Unit 5 |
| **完了条件** | EventBridgeからPush通知が送信される; 月200通超過しない |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 6-1 | `push_notifier.py`: 対象ユーザー取得・Push送信 | F7-01 |
| 6-2 | 通数管理（今日既にPush済みかDynamoDBで確認） | F7-01, F7-03 |
| 6-3 | Push通知コンテンツ生成（Nova Micro）「今日ちょっとだけ話したいことある〜」 | F7-02 |
| 6-4 | EventBridge Scheduler SAMリソース定義（PushNotifierScheduler） | F7-01 |
| 6-5 | 月200通上限チェックロジック（フリープラン保護） | COST-03 |

---

### Unit 7: LIFFダッシュボード（F8対応）

**対応要件**: F8-01〜F8-03

| 内容 | 詳細 |
|------|------|
| **スコープ** | LIFF用API + 最小限フロントエンド（HTML + LINE LIFF SDK） |
| **依存** | Unit 0〜6 |
| **完了条件** | LINEアプリ内でLIFFが開き、履歴・設定が表示できる |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 7-1 | `liff_api.py`: 履歴取得API・設定取得/更新API | F8-01, F8-03 |
| 7-2 | LIFF App（最小HTML + LINE LIFF SDK）初期化 | F8-01 |
| 7-3 | ご褒美メモ・履歴表示（キャラの言葉で表現） | F8-01, F8-02 |
| 7-4 | 設定画面（口調選択・ご褒美枠変更） | F8-03 |
| 7-5 | SAMテンプレートに LiffApiFunction + LiffApi 追加 | — |

---
