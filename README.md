# オートリワードサービス（ARS）

<div align="center">

> ### 🎁 「話すだけで家計簿になる。がんばった自分に、ちょうどいいご褒美を。」

[![Status](https://img.shields.io/badge/AI--DLC-Construction-orange)](#)
[![Theme](https://img.shields.io/badge/theme-人をダメにする-ff69b4)](#)
[![PWA](https://img.shields.io/badge/PWA-Standalone-5A0FC8)](#)
[![React](https://img.shields.io/badge/React-19-61DAFB)](#)
[![AWS Lambda](https://img.shields.io/badge/AWS-Lambda_(Python_3.13)-FF9900)](#)
[![DynamoDB](https://img.shields.io/badge/AWS-DynamoDB-4053D6)](#)
[![Bedrock](https://img.shields.io/badge/AWS-Bedrock_(Nova)-232F3E)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#ライセンス)

**🌐 デモ**: https://d39spqovcq7od.cloudfront.net/demo

</div>

---

## 概要

**オートリワードサービス（ARS）** は、AI ハッカソン「人をダメにする」テーマのもとで構築する、PWA スタンドアロンの **AI 家計簿 × ご褒美提案サービス** です。

AI キャラクター **ふれまーるちゃん** と話しているだけで、支出・感情・嗜好が **会話の副産物として** 育っていきます。ユーザーは家計簿を頑張らない。でも気づいたら、自分の消費傾向が整理されている。そしてふれまーるちゃんは、ユーザーの好きなものや今月の余裕を覚えて、ちょうど弱っているタイミングで「これ買っちゃおうよ〜」と提案してくれます。

> 💬 *「買っていいよ」の一言で、ふれまーるちゃんが最適なご褒美を探して提案してくれる。*

---

## サービスコンセプト

| 項目 | 内容 |
|------|------|
| キャッチコピー | 頑張らない家計簿アプリ「ARS」 |
| テーマ | 人をダメにする |
| ターゲット | 忙しい社会人・育児中の親・フリーランス |
| コアバリュー | 会話するだけで家計が育ち、AI キャラが「買っていい理由」を作ってご褒美を提案 |
| UI | PWA（ふれまーるちゃんとのチャット + ダッシュボード + 日記） |
| キャラクター | ふれまーるちゃん — 甘やかし特化の AI アシスタント |

---

## 成功シナリオ

> 田中さん（26歳・会社員）は残業後、スマホでふれまーるちゃんに話しかける。
>
> **ユーザー**: 今日もう限界かも…会議3つあってさ
>
> **ふれまーるちゃん**: 会議3つはきつかったね…。お疲れの度合い、かなり高めかも。
>
> **ユーザー**: なんか自分にご褒美あげたいけど何がいいかな
>
> **ふれまーるちゃん**: 田中さんカフェ好きでしょ？今月まだ余剰が¥6,200あるから、こういうのどうかな？ちょっといいやつ。
>
> 🛍 **ルピシア お茶のバラエティセット** ¥2,480
> *カフェ好きなあなたへ。自宅で本格ティータイムはどう？*
>
> **ユーザー**: おっ、これいいかも！買っちゃおうかな
>
> **ふれまーるちゃん**: えへへ、いいと思う！自宅ティータイムって意外と効くよ。回復費として記録しておくね。
>
> ✅ 支出記録: 回復費 ¥2,480
>
> **ふれまーるちゃん**: あと、今すぐできる0円回復もあるよ。
>
> ▶ **自律神経を整えるヨガ（10分）** — YouTube
> *体を動かすと気分が切り替わるかも*

**裏側で起きていること:**
- 会話から感情（疲労度:高）を自動推定 → ライフログに記録
- ユーザーの嗜好（カフェ好き）をPREF_MEMORYから参照
- 今月の余剰金（¥6,200）を計算して予算内で提案
- 楽天APIで商品検索 + YouTubeで0円回復候補を取得
- 22時に今日の日記を自動生成

---

## ふれまーるちゃんについて

<table>
<tr>
<td width="120">

🧸

</td>
<td>

**ふれまーるちゃん** は ARS の中核を担う AI キャラクターです。

- **性格**: 甘やかし特化。ユーザーの味方。でも無駄遣いには「う〜ん、それはちょっと待とっか」と言える
- **口調**: フレンドリー。タメ口。絵文字少なめ。でも的確
- **役割**: 会話相手 / 家計記録 / 感情ケア / ご褒美提案 / 日記作成
- **6つの表情**: neutral / happy / support / shy / excited / listening
- **設計思想**: 数字や率で見せず、キャラの言葉で伝える

> *「今月はコンビニスイーツ多めだけど、大きな無駄遣いはまだしてないよ〜。
> あと少しなら、甘いもの買っても大丈夫そう。でもガジェット系は来月まで待と？」*

内部ではスコアリングする。表にはふれまーるちゃんの言葉で出す。

</td>
</tr>
</table>

---

## 主要機能

| 機能 | 説明 | 画面 |
|------|------|------|
| 💬 AIチャット | テキスト/音声で会話。共感・支出記録・ご褒美提案をすべてチャット内で | Chat |
| 🎤 リアルタイム音声 | Amazon Nova Sonic によるリアルタイム音声応答（WebSocket + VAD） | Chat |
| 🛍 商品レコメンド | ストレス検知 → 嗜好×予算×気分で最適な商品をカード表示 | Chat |
| 📊 ダッシュボード | 今月の余剰金・回復費・気分スコア・連続記録日数 | Dashboard |
| 📝 ライフログ | 会話するたび感情付きログが蓄積。時系列で1日の流れが見える | Diary |
| 📔 日記自動生成 | 22時にその日のログからふれまーるちゃんが日記を書いてくれる | Diary |
| 🧾 レシート解析 | カメラ撮影 → Nova Lite OCR → 品目分割 → 自動記録 | Chat |
| 🌿 リカバリー提案 | 0円回復（YouTube/散歩）〜小ごほうび（カフェ/スイーツ）を提案 | Recovery |
| 💰 予算繰越 | 余ったご褒美予算は来月へ。使いすぎてもリセットで再スタート | Dashboard |
| 🔔 Push通知 | ブラウザ Push でプロアクティブ提案（VAPID） | — |
| 🎭 デモモード | 12シナリオの自動再生。ハッカソン発表用 | Demo |

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│                        User (Browser / PWA)                      │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │       CloudFront        │
                    │    (React PWA + S3)     │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
   ┌──────────┴─────┐  ┌───────┴────────┐  ┌─────┴──────────┐
   │  API Gateway   │  │ WebSocket API  │  │   Cognito      │
   │  (HTTP API)    │  │ (Voice Chat)   │  │  (Auth)        │
   └──────┬─────────┘  └───────┬────────┘  └────────────────┘
          │                     │
   ┌──────┴─────────┐  ┌───────┴────────┐
   │  API Lambda    │  │ Voice Gateway  │
   │  (Python)      │  │  Lambda        │
   └──────┬─────────┘  └───────┬────────┘
          │                     │
   ┌──────┴─────────────────────┴────────┐
   │          Amazon Bedrock              │
   │   Nova Lite (text) / Nova Sonic (voice) │
   └──────┬──────────────────────────────┘
          │
   ┌──────┴──────────┐     ┌─────────────────┐
   │   DynamoDB      │     │  External APIs  │
   │  (Single Table) │     │  楽天/HotPepper │
   │   ArsTable      │     │  YouTube/Amazon │
   └─────────────────┘     └─────────────────┘
```

---

## DynamoDB スキーマ（Single Table Design）

| PK | SK パターン | 用途 |
|----|------------|------|
| `USER#{userId}` | `PROFILE` | ユーザープロフィール・予算設定 |
| `USER#{userId}` | `EXPENSE#{timestamp}` | 支出記録 |
| `USER#{userId}` | `LIFELOG#{timestamp}` | 感情付きライフログ |
| `USER#{userId}` | `DIARY#{date}` | 日記（自動生成） |
| `USER#{userId}` | `CHAT#{timestamp}` | 会話ログ |
| `USER#{userId}` | `PREF#{category}` | 嗜好メモリ |
| `USER#{userId}` | `REWARD_POOL#{id}` | ご褒美候補プール |
| `USER#{userId}` | `PUSH_SUB` | Push通知サブスクリプション |

---

## 技術スタック

| カテゴリ | 技術 | 選定理由 |
|---------|------|---------|
| フロントエンド | React 19 + TypeScript 5.7 + Vite 6 | 高速ビルド・型安全・PWA対応 |
| ルーティング | react-router-dom v7 | SPA内画面遷移 |
| バックエンド | Python 3.13 + AWS Lambda | サーバーレス・Bedrock SDK直結 |
| AI (テキスト) | Amazon Bedrock Nova Lite | 高速・低コスト・日本語対応 |
| AI (音声) | Amazon Nova Sonic | リアルタイム双方向音声 |
| データベース | DynamoDB (Single Table) | スケーラブル・サーバーレス |
| 認証 | Amazon Cognito | マネージド認証・JWT |
| ホスティング | CloudFront + S3 | グローバルCDN・低レイテンシ |
| API | API Gateway HTTP API | Lambda統合・CORS対応 |
| 音声通信 | WebSocket API + Lambda | リアルタイム双方向 |
| IaC | AWS SAM | Lambda特化・ローカルテスト |
| Push通知 | Web Push (VAPID) | ブラウザネイティブ・サーバーレス |
| 外部API | 楽天 / HotPepper / YouTube | 商品検索・店舗検索・無料コンテンツ |

---

## 画面構成

| 画面 | 説明 | パス |
|------|------|------|
| チャット | ふれまーるちゃんとの会話。音声/テキスト切替。商品カード表示 | `/` |
| ダッシュボード | 月間サマリー。余剰金・回復費・気分スコア・支出グループ | `/dashboard` |
| ダイアリー | ライフログ一覧 + 日記。感情タイムライン | `/diary` |
| リカバリー | ご褒美提案一覧。0円回復〜小ごほうび。タブ切替 | `/recovery` |
| 設定 | プロフィール・予算・通知・ログアウト | `/settings` |
| オンボーディング | 初回設定（名前・予算・好きなもの・日記時刻） | `/onboarding` |
| デモ | 12シナリオ自動再生。コントロールパネル付き | `/demo` |

---

## プロジェクト構成

```
Auto-Reward-Service/
├── u8/                              ← メインアプリケーション
│   ├── frontend/                      React PWA
│   │   ├── src/
│   │   │   ├── pages/                画面コンポーネント (7画面)
│   │   │   │   ├── ChatPage.tsx         チャット
│   │   │   │   ├── DashboardPage.tsx    ダッシュボード
│   │   │   │   ├── DiaryPage.tsx        日記
│   │   │   │   ├── RecoveryPage.tsx     リカバリー
│   │   │   │   ├── SettingsPage.tsx     設定
│   │   │   │   └── OnboardingPage.tsx   オンボーディング
│   │   │   ├── demo/                 デモモード (12シナリオ)
│   │   │   │   ├── DemoPage.tsx         デモ画面
│   │   │   │   ├── DemoScreens.tsx      本番同等の再現画面
│   │   │   │   ├── demoScenarios.ts     シナリオ定義
│   │   │   │   ├── demoState.tsx        状態管理 + 再生エンジン
│   │   │   │   ├── demoTypes.ts         型定義
│   │   │   │   └── demoData.ts          モックデータ
│   │   │   ├── hooks/                カスタムフック
│   │   │   │   └── useVoiceChat.ts      WebSocket音声通信
│   │   │   └── lib/                  共通ライブラリ
│   │   │       ├── api.ts              バックエンドAPI呼出
│   │   │       ├── auth.ts             Cognito認証
│   │   │       └── emotionImages.ts    ふれまーるちゃん表情
│   │   ├── public/                   静的アセット
│   │   ├── package.json
│   │   └── vite.config.ts
│   ├── backend/                       Python Lambda
│   │   ├── handlers/
│   │   │   ├── api_handler.py          REST API エントリポイント
│   │   │   ├── voice_gateway.py        WebSocket 音声ゲートウェイ
│   │   │   ├── analysis_handler.py     感情分析
│   │   │   └── pre_signup_handler.py   Cognito Pre-Signup
│   │   ├── services/
│   │   │   ├── chat_service.py         チャットロジック + Bedrock呼出
│   │   │   ├── dashboard.py            ダッシュボード集計
│   │   │   ├── diary.py                日記自動生成
│   │   │   ├── receipt_service.py      レシートOCR
│   │   │   ├── recovery.py             リカバリー提案
│   │   │   ├── product_search.py       楽天API商品検索
│   │   │   ├── hotpepper_service.py    HotPepper店舗検索
│   │   │   ├── wishlist_service.py     Amazon Wishlist
│   │   │   ├── proactive_message.py    プロアクティブ提案
│   │   │   ├── push_service.py         Web Push送信
│   │   │   ├── sonic_voice_session.py  Nova Sonic管理
│   │   │   └── transcript.py          音声文字起こし保存
│   │   └── shared/
│   │       ├── bedrock_client.py       Bedrock共通クライアント
│   │       ├── data_access.py          DynamoDB CRUD
│   │       ├── config.py               設定管理
│   │       ├── auth.py                 JWT検証
│   │       └── secrets.py              Secrets Manager
│   ├── tests/                         テスト
│   ├── template.yaml                  SAM テンプレート
│   └── samconfig.toml                 デプロイ設定
├── docs/                              ドキュメント
│   ├── コンセプト変更定義書.md
│   ├── 機能仕様書.md
│   ├── demo-guide.md
│   └── API設定ガイド.md
├── aidlc-docs/                        AI-DLC 成果物
│   ├── aidlc-state.md                   プロジェクト状態
│   ├── audit.md                         監査ログ
│   └── inception/                       設計書一式
├── archive/                           旧コンセプト（参照用）
│   └── v1-line-bot/                     LINE Bot版コード一式
├── .aidlc/                            AI-DLCルール定義
├── .github/                           GitHub設定
├── BACKLOG.md                         課題・持ち越し項目
├── AGENTS.md                          AI Agent設定
└── README.md
```

---

## デプロイ

### 前提条件
- Node.js 18+
- Python 3.13
- AWS CLI v2 + SAM CLI
- AWS SSO プロファイル `share` 設定済み

### フロントエンド
```bash
cd u8/frontend
npm install
npm run build
aws s3 sync dist/ s3://ars-u8-frontend-dev-890236016419/ --delete --profile share
aws cloudfront create-invalidation --distribution-id E1IBFWTO596D98 --paths "/*" --profile share
```

### バックエンド
```bash
cd u8
sam build
sam deploy --profile share
```

### 環境情報

| リソース | 値 |
|---------|---|
| CloudFront | `d39spqovcq7od.cloudfront.net` |
| S3 バケット | `ars-u8-frontend-dev-890236016419` |
| CloudFront Distribution ID | `E1IBFWTO596D98` |
| SAM スタック名 | `ars-u8-pwa` |
| DynamoDB テーブル | `ArsTable` |
| リージョン | `ap-northeast-1` |

---

## デモモード

デモモードは **12 シナリオ** を自動再生します。ハッカソン発表・社内プレゼン向けに、バックエンド不要で全機能を体感できます。

### シナリオ一覧

| # | シナリオ | 内容 | 所要時間 |
|---|---------|------|---------|
| 1 | オンボーディング | 名前→予算→好きなもの→日記時刻 | ~22秒 |
| 2 | ボイスチャット | マイクON→文字起こし→AI応答 | ~16秒 |
| 3 | 会話から支出記録 | 「プリン買った」→記録→ダッシュボード反映 | ~14秒 |
| 4 | レシートアップロード | 画像→OCR→品目分割→確認→記録 | ~14秒 |
| 5 | ダッシュボード | 余剰金/回復費/気分のカウントアップ演出 | ~9秒 |
| 6 | 日記・ライフログ | 朝〜夜のログ蓄積→日記自動生成 | ~14秒 |
| 7 | リカバリー提案 | ストレス検知→0円回復→候補表示→選択 | ~14秒 |
| 8 | ごほうび予算繰越 | 余剰→繰越 / 超過→リセット | ~10秒 |
| 9 | 推薦元の使い分け | 楽天/HotPepper/YouTube/Amazon | ~14秒 |
| 10 | **ストレス検知→ご褒美提案** | 疲労検知→好み分析→商品カード提案→購入→0円提案 | ~32秒 |
| 11 | **日記自動生成のしくみ** | 朝〜夜の会話→ライフログ蓄積→22時に日記生成 | ~35秒 |
| 12 | **ライフログ蓄積** | 7件のログが時系列で追加→感情推移→日記 | ~28秒 |
| 全 | フルデモ | 1〜12 連続再生 | ~5-7分 |

### デモURL

```
https://d39spqovcq7od.cloudfront.net/demo?scenario=stress-reco
https://d39spqovcq7od.cloudfront.net/demo?scenario=diary-generation
https://d39spqovcq7od.cloudfront.net/demo?scenario=lifelog-accumulation
https://d39spqovcq7od.cloudfront.net/demo?scenario=full
```

コントロールパネル非表示: `&hideControls=1`

---

## データフロー

### 会話 → 支出記録 → ダッシュボード

```
User: 「プリン買ったよ 320円」
  │
  ▼
[Chat Service] → Bedrock (intent=EXPENSE, item=プリン, amount=320, category=ごほうび費)
  │
  ├── DynamoDB: EXPENSE#{timestamp} 保存
  ├── DynamoDB: LIFELOG#{timestamp} 保存 (emotion: happy)
  └── Response: 「プリン！それは『ごほうび費』だね。しっかり受け取ってね。」
```

### ストレス検知 → ご褒美提案

```
User: 「今日もう限界…」
  │
  ▼
[Chat Service] → Bedrock (emotion: stressed, fatigue: high)
  │
  ├── PREF_MEMORY から嗜好取得 (カフェ好き)
  ├── Dashboard から余剰金取得 (¥6,200)
  ├── [Product Search] → 楽天API (カフェ × ¥2,500以下)
  ├── [Recovery] → YouTube (0円回復候補)
  │
  └── Response: 商品カード + 0円回復カード + 共感メッセージ
```

### ライフログ → 日記自動生成

```
[22:00 EventBridge trigger]
  │
  ▼
[Diary Service]
  ├── 当日の LIFELOG#{*} を全件取得
  ├── 感情の推移を分析
  ├── Bedrock で日記文を生成（ふれまーるちゃん視点）
  └── DynamoDB: DIARY#{date} 保存
```

---

## コンセプト変更の経緯

当初は **LINE Bot 中心（v1）** で構築しましたが、以下の制約により **PWA スタンドアロン（v2）** へピボットしました:

| 制約 | 影響 | v2 での解決 |
|------|------|------------|
| Push通知 月200通制限 | プロアクティブ提案が打てない | Web Push (VAPID) で無制限 |
| LIFF WebView制約 | リッチUI不可 | React PWA でフル制御 |
| Webhook往復 2-4秒 | 会話テンポが悪い | API直接呼出 <1秒 |
| 音声対応不可 | リアルタイム音声会話ができない | WebSocket + Nova Sonic |
| Rich Menu固定 | キャラ表情変化不可 | 6表情アバター動的切替 |
| LINE Console設定 | 開発イテレーション遅い | SAM deploy のみ |

詳細: [docs/コンセプト変更定義書.md](docs/コンセプト変更定義書.md)

旧コンセプトの設計資産・持ち越し課題: [BACKLOG.md](BACKLOG.md)

---

## 開発手法

**AI-DLC** (AI-Driven Development Lifecycle) に基づき、要件定義→設計→実装を AI 協調で推進。

| フェーズ | 成果物 | パス |
|---------|--------|------|
| Inception | 要件定義・設計書・Unit分割 | `aidlc-docs/inception/` |
| Construction | 機能設計・コード生成 | `aidlc-docs/construction/` |
| 監査ログ | 全意思決定の記録 | `aidlc-docs/audit.md` |
| 状態管理 | 現在のフェーズ・進捗 | `aidlc-docs/aidlc-state.md` |

---

## ローカル開発

### フロントエンド
```bash
cd u8/frontend
npm install
npm run dev          # http://localhost:5173
```

### バックエンド（SAM Local）
```bash
cd u8
sam build
sam local start-api  # http://localhost:3000
```

### テスト
```bash
cd u8
pip install -r tests/requirements-test.txt
pytest tests/
```

---

## 今後の予定

[BACKLOG.md](BACKLOG.md) に旧コンセプトから持ち越した課題を含め整理しています。主なもの:

- 🔴 嗜好メモリ (PREF_MEMORY) の自動蓄積
- 🔴 ご褒美候補プールの定期更新
- 🟡 LLM出力品質テストの整備
- 🟡 Google Calendar 連携（忙しさ推定）
- 🟢 構造化ログ + PII除外

---

## ライセンス

MIT
