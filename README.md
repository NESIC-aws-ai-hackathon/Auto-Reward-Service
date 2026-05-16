# オートリワードサービス（ARS）

<div align="center">

> ### 🎁 「話すだけで家計簿になる。好きなものを覚えて、買っていい理由をくれる。」

[![Status](https://img.shields.io/badge/AI--DLC-Inception_Complete-blue)](#)
[![Theme](https://img.shields.io/badge/theme-人をダメにする-ff69b4)](#)
[![LINE Bot](https://img.shields.io/badge/LINE-Messaging_API-00C300)](#)
[![AWS Lambda](https://img.shields.io/badge/AWS-Lambda_(Python)-FF9900)](#)
[![DynamoDB](https://img.shields.io/badge/AWS-DynamoDB-4053D6)](#)
[![Bedrock](https://img.shields.io/badge/AWS-Bedrock_(Nova)-232F3E)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#ライセンス)

</div>

---

## 概要

**オートリワードサービス（ARS）** は、AI-DLC ハッカソン「人をダメにする」テーマのもとで構築する、LINE Bot 中心の **AI 家計簿 × ご褒美提案サービス** です。

LINEで **リワードちゃん** と話しているだけで、愚痴・支出・好み・ご褒美履歴が **会話の副産物として** 育っていきます。
ユーザーは家計簿を頑張らない。でも気づいたら、自分の消費傾向が整理されている。
そしてリワードちゃんは、ユーザーの好きなものや今月の余裕を覚えて、ちょうど弱っているタイミングで「これ買っちゃおうよ〜」と財布をゆるめてきます。

> 💬 *「買っていいよ」の一言を、自分の代わりに AI が言ってくれる。*

---

## サービスコンセプト

| 項目 | 内容 |
|------|------|
| キャッチコピー | 頑張らない家計簿アプリ「ARS」 |
| テーマ | 人をダメにする |
| ターゲット | 忙しい社会人・育児中の親・フリーランス |
| コアバリュー | 会話するだけで家計が育ち、AI キャラが「買っていい理由」を作ってくれる |
| UI | LINE Bot（リワードちゃん）+ LIFF（最小限ダッシュボード） |

---

## 成功シナリオ

> 田中さん（26歳・会社員）は残業後、LINEでリワードちゃんにつぶやく。
>
> **ユーザー**: 今日疲れた  
> **リワードちゃん**: 前に抹茶好きって言ってたよね〜。今日ならこの抹茶プリン、ちょうどいいかも。320円だし、これは回復費でいけるよ。
>
> 家計簿をつけたつもりはないのに、支出も感情も好みも自然に記録されている。

---

## システムアーキテクチャ

AWS サーバーレスアーキテクチャを採用。LINE Bot を入口として、Lambda 関数群が連携します。

```
LINEユーザー
  ↓（テキスト / 画像 / スタンプ）
LINE Messaging API
  ↓（Webhook POST）
Amazon API Gateway（+ WAF）
  ↓
Lambda: webhook_handler
  ├─ LINE署名検証（X-Line-Signature）
  ├─ Message Router
  │     ├─ text  → intent_classifier
  │     │           ├─ EXPENSE    → expense_extractor  → DynamoDB
  │     │           ├─ REWARD     → reward_proposal    → DynamoDB
  │     │           ├─ GREET/CHAT → character_reply
  │     │           └─ ONBOARDING → onboarding_flow    → DynamoDB
  │     └─ image → receipt_analyzer → DynamoDB
  └─ LINE Reply API で応答

日次バッチ（EventBridge Scheduler）
  └─ reward_pool_updater → 楽天API → DynamoDB

Push通知（EventBridge Scheduler / 1日1回上限）
  └─ push_notifier → LINE Push API

LIFF（最小限）
  └─ API Gateway → liff_api → DynamoDB
```

### データストア

**DynamoDB シングルテーブルデザイン**

| PK | SK プレフィックス | 用途 |
|----|-------------------|------|
| `USER#{lineUserId}` | `PROFILE#` | 収入・固定費・ご褒美枠・口調設定 |
| `USER#{lineUserId}` | `EXPENSE#{isoTimestamp}` | 支出記録 |
| `USER#{lineUserId}` | `CHAT#{isoTimestamp}` | 会話ログ |
| `USER#{lineUserId}` | `PREF_MEMORY#` | 嗜好記憶（好きなカテゴリ・商品傾向） |
| `USER#{lineUserId}` | `REWARD_POOL#` | ご褒美候補プール |
| `USER#{lineUserId}` | `REWARD_SUGGESTION#{isoTimestamp}` | ご褒美提案・結果 |
| `USER#{lineUserId}` | `GOOGLE_OAUTH#` | Google OAuth refresh_token（暗号化）・接続日時 |

---

## 主要機能（8 Unit 構成）

| Unit | 名称 | 役割 | MVP |
|------|------|------|-----|
| Unit 0 | **SAM基盤** | SAMプロジェクト・共通Layer・DynamoDBテーブル定義 | ✅ |
| Unit 1 | **LINE Bot基盤** | Webhook受信・署名検証・Router・Reply/Push | ✅ |
| Unit 2 | **リワードちゃんキャラクター** | Intent分類・口調生成・感情把握・オンボーディング | ✅ |
| Unit 3 | **支出記録** | チャット支出抽出・確認フロー・レシート画像解析 | ✅ |
| Unit 4 | **ご褒美候補プール** | 嗜好記憶・楽天API連携・日次バッチ更新 | ✅ |
| Unit 5 | **ご褒美提案** | 状態推定・候補マッチング・余裕額チェック | ✅ |
| Unit 6 | **Push通知** | 通数管理・コンテンツ生成・EventBridge | ✅ |
| Unit 7 | **LIFFダッシュボード** | 履歴・設定・口調選択（最小限） | ✅ |

---

## 技術スタック

| レイヤー | 技術 | 備考 |
|---------|------|------|
| メッセージングUI | LINE Messaging API（フリープラン） | Reply中心、Push は月200通上限 |
| LIFF | LINE LIFF | ご褒美メモ・履歴・設定のみ |
| API エントリポイント | Amazon API Gateway | Webhook + LIFF API |
| バックエンド | AWS Lambda（Python） | 全関数 Python 統一 |
| データベース | Amazon DynamoDB | シングルテーブルデザイン |
| LLM | Amazon Bedrock（Nova Micro / Nova Lite） | モデル切り替え可能設計 |
| 画像解析 | Nova Lite → Textract+LLM → Claude Vision | フォールバック方式 |
| 外部API | 楽天ウェブサービスAPI | ご褒美候補プール |
| カレンダー連携 | Google Calendar API（OAuth 2.0） | 予定コンテキストでご褒美提案を強化 |
| スケジューラ | Amazon EventBridge Scheduler | 日次バッチ・Push通知 |
| IaC | AWS SAM | template.yaml で全リソース定義 |
| シークレット管理 | AWS Secrets Manager / SSM | チャネルシークレット・トークン等 |
| セキュリティ | AWS WAF | API Gateway に適用 |
| テスト | pytest + LLM応答品質テスト | プロンプトテスト重点 |

---

## プロジェクト構成

```
auto-reward-service/
├── src/
│   ├── handlers/              # Lambda関数ハンドラー
│   │   ├── webhook_handler.py
│   │   ├── intent_classifier.py
│   │   ├── expense_extractor.py
│   │   ├── receipt_analyzer.py
│   │   ├── character_reply.py
│   │   ├── onboarding_flow.py
│   │   ├── reward_proposal.py
│   │   ├── reward_pool_updater.py
│   │   ├── push_notifier.py
│   │   └── liff_api.py
│   ├── services/              # 共通サービスモジュール
│   │   ├── dynamodb_service.py
│   │   ├── bedrock_service.py
│   │   ├── line_service.py
│   │   ├── rakuten_service.py
│   │   ├── finance_engine.py
│   │   └── reward_pool_service.py
│   ├── models/                # スキーマ定義
│   │   └── schemas.py
│   ├── prompts/               # LLMプロンプト
│   │   ├── intent_prompt.py
│   │   ├── expense_prompt.py
│   │   ├── character_prompts.py
│   │   └── receipt_prompt.py
│   └── utils/
│       ├── secrets.py
│       └── logger.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── llm/                   # LLM応答品質テスト
├── template.yaml              # AWS SAM テンプレート
├── samconfig.toml
├── requirements.txt
├── requirements-dev.txt
└── Makefile
```

---

## セキュリティ設計

| 要件 | 対策 |
|------|------|
| LINE署名検証 | `X-Line-Signature` をチャネルシークレットで HMAC-SHA256 検証。検証失敗は 403 |
| シークレット管理 | チャネルシークレット・アクセストークンは Secrets Manager / SSM に格納（平文禁止） |
| データ暗号化 | DynamoDB 保存データの暗号化（AWS管理キー） |
| PII保護 | ログに LINE ユーザーID・チャット内容等 PII を出力しない |
| IAM最小権限 | 各Lambda関数の IAM Role は必要操作のみに限定 |
| WAF | API Gateway に AWS WAF（AWSManagedRulesCommonRuleSet）を適用 |
| LIFF検証 | LIFF アクセストークンを LINE Platform API で検証 |

---

## MVP スコープ

| 区分 | 含める機能 |
|------|-----------|
| LINE Bot基盤 | Webhook受信・署名検証・メッセージルーティング・Reply/Push |
| 初回登録 | 収入・固定費・ご褒美枠をチャットで登録 |
| キャラクター | リワードちゃん口調生成・口調カスタマイズ（2〜3種）・感情把握 |
| 支出記録 | チャット支出入力・レシート画像解析・確認フロー |
| 候補プール | 嗜好記憶・楽天API連携・日次バッチ更新 |
| ご褒美提案 | 状態推定・候補マッチング・余裕額チェック・買いすぎストップ |
| Push通知 | 1日1回デモ用Push・通数管理（月200通） |
| LIFF | ご褒美メモ・支出サマリー・設定・口調選択 |

### MVP対象外（将来フェーズ）

- アフィリエイト・収益機能
- 外部サービス連携（UberEats等）自動実行
- ウェアラブルデバイス連携

---

## ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [docs/コンセプト変更定義書.md](docs/コンセプト変更定義書.md) | コンセプトピボット（Web App → LINE Bot）の変更定義 |
| [old/docs/要件定義書.md](old/docs/要件定義書.md) | 旧要件定義書（参照用・old退避済み） |
| [aidlc-docs/](aidlc-docs/) | AI-DLC プロセス管理ドキュメント（状態・監査・設計・計画） |
| [aidlc-docs/inception/requirements/requirements.md](aidlc-docs/inception/requirements/requirements.md) | 要件定義書 v2（確定版） |
| [aidlc-docs/inception/application-design/application-design.md](aidlc-docs/inception/application-design/application-design.md) | 統合アプリケーション設計書 |

---
