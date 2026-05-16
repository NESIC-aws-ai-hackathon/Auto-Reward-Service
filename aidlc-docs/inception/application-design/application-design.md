# Application Design（統合版） — オートリワードサービス（v2）

**改訂日**: 2026-05-15  
**変更理由**: コンセプト変更（LINE Bot + Lambda + DynamoDB へのアーキテクチャ刷新）
**ステータス**: 確定

---

## 1. アーキテクチャ概要

### 設計方針まとめ

| 項目 | 決定内容 |
|------|---------|
| 実行基盤 | **AWS Lambda（Python）+ API Gateway** フルサーバーレス |
| データベース | **DynamoDB シングルテーブルデザイン** |
| LLM | **Amazon Bedrock（Nova Micro / Nova Lite）** モデル切り替え可能設計 |
| 画像解析 | **Nova Lite 第一候補** → Textract+LLM → Claude Vision（フォールバック） |
| 外部API | **楽天ウェブサービスAPI**（ご褒美候補プール） |
| カレンダー連携 | **Google Calendar API**（OAuth 2.0 / `calendar.events.readonly`） |
| スケジューラ | **EventBridge Scheduler**（日次バッチ） |
| IaC | **AWS SAM**（Serverless Application Model） |
| 認証 | **LINEユーザーID**（Webhook署名検証）+ LIFF時LINEログイン |
| シークレット管理 | **AWS Secrets Manager / SSM Parameter Store** |
| フロントエンド | **LINE LIFF**（最小限）|

---

## 2. システム構成図

```
LINEユーザー
  ↓（LINEアプリ：テキスト / 画像 / スタンプ）
LINE Messaging API
  ↓（Webhook POST）
Amazon API Gateway
  ↓
Lambda: webhook_handler
  ├─ LINE署名検証
  ├─ Message Router
  │     ├─ text → Lambda: intent_classifier
  │     │           ├─ EXPENSE → Lambda: expense_extractor
  │     │           ├─ REWARD  → Lambda: reward_proposal
  │     │           ├─ GREET/CHAT → Lambda: character_reply
  │     │           └─ ONBOARDING → Lambda: onboarding_flow
  │     └─ image → Lambda: receipt_analyzer
  └─ DynamoDB（シングルテーブル）

日次バッチ
  EventBridge Scheduler
    └─ Lambda: reward_pool_updater
          ├─ 楽天ウェブサービスAPI（商品取得）
          └─ DynamoDB reward_pool 更新

Push通知
  EventBridge Scheduler（1日1回）
    └─ Lambda: push_notifier
          ├─ DynamoDB（対象ユーザー取得）
          └─ LINE Messaging API（Push送信）

LIFF（最小限）
  LINE LIFF App
    ├─ API Gateway
    └─ Lambda: liff_api
          └─ DynamoDB

外部サービス連携
  Amazon Bedrock（Nova Micro / Nova Lite）← 各Lambda
  楽天ウェブサービスAPI               ← reward_pool_updater
  Google Calendar API                  ← reward_proposal / character_reply（毎回APIフェッチ、DDBにカレンダーデータ保存せず）
  AWS Secrets Manager / SSM           ← 全Lambda（シークレット取得）
```

---

## 3. リポジトリ構成

```
auto-reward-service/
├── src/
│   ├── handlers/
│   │   ├── webhook_handler.py         # LINE Webhook受信・署名検証・Router
│   │   ├── intent_classifier.py       # Intent分類（Nova Micro）
│   │   ├── expense_extractor.py       # 支出抽出・確認フロー（Nova Micro）
│   │   ├── receipt_analyzer.py        # レシート画像解析（Nova Lite）
│   │   ├── character_reply.py         # リワードちゃん口調生成（Nova Micro）
│   │   ├── onboarding_flow.py         # 初回登録チャットフロー
│   │   ├── reward_proposal.py         # ご褒美提案（候補プールマッチング）
│   │   ├── reward_pool_updater.py     # 日次バッチ（楽天API → DynamoDB）
│   │   ├── push_notifier.py           # Push通知（1日1回）
│   │   └── liff_api.py                # LIFF用APIエンドポイント
│   ├── services/
│   │   ├── dynamodb_service.py        # DynamoDB操作共通
│   │   ├── bedrock_service.py         # Bedrock呼び出し共通（モデル切替対応）
│   │   ├── line_service.py            # LINE API（Reply/Push/署名検証）
|   │   ├── rakuten_service.py         # 楽天API連携
|   │   ├── google_calendar_service.py # Google Calendar参照（OAuth + 予定取得）
│   │   ├── finance_engine.py          # 余裕額算出ロジック
│   │   └── reward_pool_service.py     # 候補プール選択ロジック
│   ├── models/
│   │   └── schemas.py                 # DynamoDBスキーマ定数・Pydanticモデル
│   ├── prompts/
│   │   ├── intent_prompt.py           # Intent分類プロンプト
│   │   ├── expense_prompt.py          # 支出抽出プロンプト
│   │   ├── character_prompts.py       # 口調別リワードちゃんプロンプト
│   │   └── receipt_prompt.py          # レシート解析プロンプト
│   └── utils/
│       ├── secrets.py                 # Secrets Manager取得ユーティリティ
│       └── logger.py                  # 構造化ログ（PII出力禁止）
├── tests/
│   ├── unit/
│   ├── integration/
│   └── llm/                           # LLM応答品質テスト
├── template.yaml                      # AWS SAM テンプレート
├── samconfig.toml                     # SAM設定
├── requirements.txt
├── requirements-dev.txt
└── Makefile
```

---

## 4. Lambda関数サマリー

| Lambda関数 | Unit | トリガー | 主な責務 |
|-----------|------|---------|----------|
| `webhook_handler` | Unit 1 | API Gateway（LINE Webhook） | 署名検証・メッセージルーティング |
| `intent_classifier` | Unit 2 | Lambda（webhook_handler から呼び出し） | テキストのIntent分類（Nova Micro） |
| `character_reply` | Unit 2 | Lambda（intent_classifier から） | リワードちゃん口調のReply生成（Nova Micro） |
| `onboarding_flow` | Unit 2 | Lambda（intent_classifier から） | 初回登録チャットフロー管理 |
| `expense_extractor` | Unit 3 | Lambda（intent_classifier から） | 支出テキスト抽出・JSON化・確認フロー |
| `receipt_analyzer` | Unit 3 | Lambda（webhook_handler から） | レシート画像解析（Nova Lite） |
| `reward_proposal` | Unit 5 | Lambda（intent_classifier から） | ご褒美提案（候補プールマッチング + 余裕額チェック） |
| `reward_pool_updater` | Unit 4 | EventBridge Scheduler（日次） | 楽天API → 候補プール更新 |
| `push_notifier` | Unit 6 | EventBridge Scheduler（1日1回） | Push通知送信・通数管理 |
| `liff_api` | Unit 7 | API Gateway（LIFF） | LIFF用API（履歴・設定・口調変更） |

### Lambda 呼び出しモデル（設計決定）

> **MVP方針: 同一 Lambda 内 Python import（単一 Lambda 構成）**

webhook_handler / intent_classifier / character_reply 等は**同一 Lambda 関数（webhook_handler）内で Python モジュールとして直接 import して呼び出す**。Lambda-to-Lambda 同期呼び出しは採用しない。

| 方式 | 採否 | 理由 |
|------|------|------|
| **同一Lambda内 Python import** | ✅ **採用** | Cold Start 連鎖なし・10s タイムアウト1段・コスト最小 |
| Lambda-to-Lambda 同期呼び出し | ❌ 不採用 | Cold Start 連鎖でタイムアウトリスク（10s × 3段）・コスト増 |

- `services.md` に記載の個別 Lambda 関数設定（メモリ・タイムアウト）は**論理的な責務分割の記録**として保持
- `template.yaml` 実装では `WebhookHandlerFunction` 1関数にまとめ、handlers/ 配下モジュールを import する形で構成
- ただし **EventBridge トリガーの `reward_pool_updater` と `push_notifier`** は独立した Lambda 関数として維持（Webhook とは別トリガー）

---

## 5. 主要フロー

### 会話フロー（テキスト）

```
1. ユーザーがLINEにメッセージ送信
2. webhook_handler: 署名検証 → メッセージ種別判定
3. intent_classifier: Nova Micro でIntent分類
   （ONBOARDING / EXPENSE / REWARD / GREET / CHAT / UNKNOWN）
4a. EXPENSE → expense_extractor: 支出JSON化 → 確認フロー → DynamoDB保存
4b. REWARD → reward_proposal: 候補プールマッチング → キャラReply
4c. GREET/CHAT → character_reply: 感情把握 → Nova Micro でリワードちゃんReply
4d. ONBOARDING → onboarding_flow: 収入・固定費チャット → DynamoDB登録
5. LINE Reply API で応答
```

### レシート画像フロー

```
1. ユーザーがLINEにレシート画像送信
2. webhook_handler: 画像メッセージ検出 → receipt_analyzer 呼び出し
3. receipt_analyzer: LINE Content API で画像取得 → Nova Lite で解析 → 支出JSON
4. 解析時間が3秒以内 → Reply で確認
   解析時間が3秒超 → 「解析中だよ〜」Reply → 非同期完了後 Push または「結果を見る」ボタン
5. ユーザー確認後 → DynamoDB保存
```

### ご褒美候補プール更新フロー（日次バッチ）

```
1. EventBridge Scheduler が reward_pool_updater を起動（毎日深夜）
2. 全ユーザーの嗜好（preference_memory）を DynamoDB から取得
3. 楽天APIで嗜好カテゴリに合致する商品を取得
4. 購入・スルー履歴でスコアリング → プール更新
5. 古い候補削除 → DynamoDB reward_pool 保存
```

---

## 6. LLMテスト対象

| Lambda / 関数 | テスト方針 | テスト内容 |
|--------------|-----------|----------|
| `intent_classifier` | プロンプトテスト | 各Intentが正しく分類されるか（EXPENSE/REWARD/GREET等） |
| `expense_extractor` | 出力品質テスト | 支出JSON（item/amount/category）が正しく抽出されるか |
| `character_reply` | 口調品質テスト | リワードちゃんの口調・キャラ性格が維持されるか |
| `receipt_analyzer` | 出力品質テスト | レシート画像から支出情報が正確に抽出されるか |
| `finance_engine` | ユニットテスト | 余裕額算出が0以上かつ上限を超えないか |
| `reward_pool_service` | ユニットテスト | 候補選択が余裕額・状態条件を満たすか |

---

## 7. セキュリティ設計ポイント

| ルール | 実装方針 |
|--------|----------|
| SEC-01 LINE署名検証 | `X-Line-Signature` ヘッダーをチャネルシークレットで検証。検証失敗は 403 返却 |
| SEC-02 シークレット管理 | チャネルシークレット・アクセストークン・Bedrock設定はすべて Secrets Manager / SSM に格納 |
| SEC-03 DynamoDB暗号化 | デフォルト暗号化（AWS管理キー）を有効化 |
| SEC-04 ログPII禁止 | LINEユーザーID・チャット内容は `logger.py` でマスク。テキスト内容はログ出力しない |
| SEC-05 IAM最小権限 | 各Lambda関数のIAM RoleはDynamoDB・Bedrock・SSMの必要操作のみに限定 |
| SEC-06 WAF基本ルール | API GatewayにAWS WAF（AWSManagedRulesCommonRuleSet）を適用 |
| SEC-07 LIFF検証 | LIFFアクセストークンをLINE Platform APIで検証してからDynamoDBアクセス |
| SEC-08 カレンダーデータ保護 | カレンダーのイベント内容はDynamoDBに保存しない（毎回APIフェッチ）。ログにも出力しない。OAuth `refresh_token` のみ暗号化保存 |
| SEC-09 OAuthスコープ最小化 | Google Calendarは `calendar.events.readonly` のみ。書き込み権限は要求しない |

---

## 8. 詳細ドキュメントへの参照

| ドキュメント | パス |
|------------|------|
| コンポーネント定義 | [components.md](./components.md) |
| 関数シグネチャ | [component-methods.md](./component-methods.md) |
| サービス詳細 | [services.md](./services.md) |
| 依存関係マトリクス | [component-dependency.md](./component-dependency.md) |
| Unit定義 | [unit-of-work.md](./unit-of-work.md) |
| Unit依存関係 | [unit-of-work-dependency.md](./unit-of-work-dependency.md) |
| ストーリーマップ | [unit-of-work-story-map.md](./unit-of-work-story-map.md) |
