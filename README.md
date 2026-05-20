# オートリワードサービス（ARS）

<div align="center">

> ### 🎁 「話すだけで家計簿になる。好きなものを覚えて、買っていい理由をくれる。」

[![Status](https://img.shields.io/badge/AI--DLC-Construction-orange)](#)
[![Theme](https://img.shields.io/badge/theme-人をダメにする-ff69b4)](#)
[![LINE Bot](https://img.shields.io/badge/LINE-Messaging_API-00C300)](#)
[![AWS Lambda](https://img.shields.io/badge/AWS-Lambda_(Python)-FF9900)](#)
[![DynamoDB](https://img.shields.io/badge/AWS-DynamoDB-4053D6)](#)
[![Bedrock](https://img.shields.io/badge/AWS-Bedrock_(Nova)-232F3E)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#ライセンス)

</div>

---

## 概要

**オートリワードサービス（ARS）** は、AI-DLC ハッカソン「人をダメにする」テーマのもとで構築する、LINE Bot 中心の **AI 家計簿 × ご褒美自動購入サービス** です。

LINEで **ふれまーるちゃん** と話しているだけで、愚痴・支出・好み・ご褒美履歴が **会話の副産物として** 育っていきます。
ユーザーは家計簿を頑張らない。でも気づいたら、自分の消費傾向が整理されている。
そしてふれまーるちゃんは、ユーザーの好きなものや今月の余裕を覚えて、ちょうど弱っているタイミングで「これ買っちゃおうよ〜」と提案し、許可が出たら **Amazon カートに自動で入れて購入まで代行** します。

> 💬 *「買っていいよ」の一言で、ふれまーるちゃんが全部やってくれる。*

---

## サービスコンセプト

| 項目 | 内容 |
|------|------|
| キャッチコピー | 頑張らない家計簿アプリ「ARS」 |
| テーマ | 人をダメにする |
| ターゲット | 忙しい社会人・育児中の親・フリーランス |
| コアバリュー | 会話するだけで家計が育ち、AI キャラが「買っていい理由」を作って自動購入まで代行 |
| UI | LINE Bot（ふれまーるちゃん）+ PWA（ダッシュボード・通知） |
| キャラクター | ふれまーるちゃん — 甘やかし特化の AI アシスタント |

---

## 成功シナリオ

> 田中さん（26歳・会社員）は残業後、LINEでふれまーるちゃんにつぶやく。
>
> **ユーザー**: 今日疲れた  
> **ふれまーるちゃん**: ほしい物リストで熟成していた入浴剤、今のあなたにちょうどよさそうだったので、買い物かごに入れておいたよ〜。疲れてるんだもん仕方ないよね！お風呂でゆっくりリラックスしよう！買うって言ってくれたら買っちゃうよ！
>
> **ユーザー**: 買って！
> **ふれまーるちゃん**: はーい！注文確定したよ〜 🎉 明日届くからね！
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
  │     │           ├─ TEMPTATION → temptation_engine  → LIFF
  │     │           ├─ GREET/CHAT → character_reply
  │     │           └─ ONBOARDING → onboarding_flow    → DynamoDB
  │     └─ image → receipt_analyzer → DynamoDB
  ├─ Purchase Intent Check（活性レコメンド時）
  │     ├─ DECLINE       → カート取消＋通知
  │     ├─ AMBIGUOUS_BUY → 確認メッセージ
  │     └─ EXPLICIT_PURCHASE → 安全チェック → 購入実行
  └─ LINE Reply API で応答

日次バッチ（EventBridge Scheduler）
  └─ reward_pool_updater → 楽天API → DynamoDB

PWA通知（notification_service）
  └─ LIFF ダッシュボード内チャット風UI

カート自動化（cart_automation_worker）
  ├─ Stub モード（デモ用・即時成功）
  ├─ Nova Act モード（ブラウザ自動操作）
  └─ Hybrid モード（Nova Act + Stub フォールバック）
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
| `USER#{lineUserId}` | `WISHLIST_SOURCE#{url_hash}` | ほしい物リスト登録元 |
| `USER#{lineUserId}` | `WISHLIST_ITEM#{item_id}` | ほしい物リストアイテム |
| `USER#{lineUserId}` | `RECOMMENDATION#{rec_id}` | レコメンド（提案・カート・購入） |
| `USER#{lineUserId}` | `NOTIFICATION#{notif_id}` | PWA通知レコード |
| `USER#{lineUserId}` | `CART_AUTOMATION_JOB#{job_id}` | カート自動化ジョブ |
| `USER#{lineUserId}` | `BROWSER_SESSION#{session_id}` | ブラウザセッション（Nova Act） |

---

## 主要機能

| Unit | 名称 | 役割 | MVP |
|------|------|------|-----|
| Unit 0 | **SAM基盤** | SAMプロジェクト・共通Layer・DynamoDBテーブル定義 | ✅ |
| Unit 1 | **LINE Bot基盤** | Webhook受信・署名検証・Router・Reply | ✅ |
| Unit 2 | **ふれまーるちゃんキャラクター** | Intent分類・口調生成・感情把握・オンボーディング | ✅ |
| Unit 3 | **支出記録** | チャット支出抽出・確認フロー・レシート画像解析 | ✅ |
| Unit 4 | **ご褒美候補プール** | 嗜好記憶・楽天API連携・日次バッチ更新 | ✅ |
| Unit 5 | **ご褒美提案** | 状態推定・候補マッチング・余裕額チェック | ✅ |
| Unit 7 | **PWAダッシュボード** | 通知・支出・在庫・寄り道・設定 | ✅ |

### 追加機能（変更依頼書_2）

| 機能 | 説明 |
|------|------|
| **ほしい物リスト連携** | Amazon ほしい物リスト URL 登録 → 商品同期 → 熟成スコアリング |
| **レコメンドエンジン** | 熟成度 + 価格適合度 + 疲労ブーストでご褒美候補を選定 |
| **購入意図分類** | ユーザー発話を DECLINE / AMBIGUOUS_BUY / EXPLICIT_PURCHASE に分類 |
| **カート自動化** | Stub / Nova Act / Hybrid の3モード対応。Amazon カート操作を自動化 |
| **安全チェック** | 購入前に金額上限・数量・サブスク・決済方法変更を多重検証 |
| **PWA通知** | LINE PUSH 廃止 → PWA 内チャット風通知UIに移行 |

---

## 技術スタック

| レイヤー | 技術 | 備考 |
|---------|------|------|
| メッセージングUI | LINE Messaging API（フリープラン） | Reply 中心（Push 廃止済み） |
| PWA | LIFF + Service Worker | ダッシュボード・通知・ウィッシュリスト管理 |
| API エントリポイント | Amazon API Gateway | Webhook + LIFF API |
| バックエンド | AWS Lambda（Python 3.13） | 全関数 Python 統一 |
| データベース | Amazon DynamoDB | シングルテーブルデザイン |
| LLM | Amazon Bedrock（Nova Lite） | Intent分類・キャラ応答生成 |
| 画像解析 | Nova Lite（マルチモーダル） | レシート OCR |
| 外部API | 楽天ウェブサービスAPI / じゃらん / ホットペッパー | ご褒美候補プール |
| カート自動化 | Amazon Nova Act（予定） | ブラウザ自動操作でカート管理 |
| スケジューラ | Amazon EventBridge Scheduler | 日次バッチ |
| IaC | AWS SAM | template.yaml で全リソース定義 |
| シークレット管理 | AWS Secrets Manager / SSM | チャネルシークレット・トークン等 |
| セキュリティ | AWS WAF | API Gateway に適用 |
| テスト | pytest | ユニットテスト重点 |

---

## プロジェクト構成

```
auto-reward-service/
├── src/
│   └── handlers/              # Lambda関数ハンドラー
│       ├── webhook_handler.py      # LINE Webhook メインルーター
│       ├── expense_extractor.py    # 支出抽出エンジン
│       ├── receipt_processor_handler.py  # レシート画像非同期処理
│       ├── reward_pool_updater.py  # 日次バッチ候補更新
│       ├── liff_api.py             # LIFF/PWA API エンドポイント
│       ├── pwa_temptation.py       # PWA 寄り道API
│       └── liff/
│           └── index.html          # PWA フロントエンド
├── layer/
│   └── python/
│       ├── models/
│       │   └── schemas.py         # DynamoDB スキーマ定義
│       ├── services/              # 共通サービスモジュール
│       │   ├── dynamodb_service.py
│       │   ├── bedrock_service.py
│       │   ├── line_service.py
│       │   ├── rakuten_service.py
│       │   ├── finance_engine.py
│       │   ├── wishlist_service.py       # ほしい物リスト管理
│       │   ├── recommendation_engine.py  # レコメンドエンジン
│       │   ├── notification_service.py   # PWA通知管理
│       │   ├── cart_automation_worker.py # カート自動化ワーカー
│       │   ├── cart_job_service.py       # カートジョブ管理
│       │   └── purchase_intent.py        # 購入意図分類
│       ├── utils/
│       │   ├── secrets.py
│       │   └── logger.py
│       └── prompts/               # LLMプロンプト
├── tests/
│   └── unit/                      # ユニットテスト
├── template.yaml                  # AWS SAM テンプレート
├── samconfig.toml
└── aidlc-docs/                    # AI-DLC プロセスドキュメント
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
| LINE Bot基盤 | Webhook受信・署名検証・メッセージルーティング・Reply |
| 初回登録 | 収入・固定費・ご褒美枠をチャットで登録 |
| キャラクター | ふれまーるちゃん口調生成・感情把握 |
| 支出記録 | チャット支出入力・レシート画像解析・確認フロー |
| 候補プール | 嗜好記憶・楽天API連携・日次バッチ更新 |
| ご褒美提案 | 状態推定・候補マッチング・余裕額チェック |
| ウィッシュリスト | Amazon ほしい物リスト連携・熟成スコアリング |
| カート自動化 | Stub モード（デモ）+ Nova Act 拡張可能設計 |
| 安全チェック | 購入意図分類・多重安全検証 |
| PWA通知 | チャット風通知UI・LINE PUSH 廃止 |
| PWAダッシュボード | 通知・支出・在庫・寄り道・設定 |

### MVP対象外（将来フェーズ）

- アフィリエイト・収益機能
- Nova Act 本番モード（実ブラウザ購入実行）
- ウェアラブルデバイス連携

---

## 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `CART_AUTOMATION_MODE` | `stub` | カート自動化モード: `stub` / `nova_act` / `hybrid` |
| `ENABLE_REAL_PURCHASE` | `false` | 実購入の有効化フラグ |
| `NOVA_ACT_DEMO_MODE` | `true` | Nova Act デモモード（実ブラウザ操作をスキップ） |
| `MAX_PURCHASE_AMOUNT` | `1000` | 1回の自動購入上限金額（円） |

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
