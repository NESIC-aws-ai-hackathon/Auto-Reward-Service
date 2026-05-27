# BACKLOG — 旧コンセプト設計からの課題・持ち越し項目

> 旧コンセプト（v1: LINE Bot中心）で設計・実装した機能のうち、
> 新コンセプト（v2: PWAスタンドアロン）にも適用すべき設計資産と課題。

---

## 凡例
- 🔴 高優先: デモ・ハッカソン発表に直結
- 🟡 中優先: 体験向上に寄与
- 🟢 低優先: 将来のブラッシュアップ

---

## 🔴 高優先

### BL-001: オンボーディングフロー強化
**旧設計**: Unit 2 — 月収・固定費・ボーナス・誕生日・記念日を段階的に収集
**現状**: U8 に簡易オンボーディングあり（名前・予算・好きなもの・日記時刻）
**課題**: 月収/固定費からの自動ご褒美枠算出、ボーナス月の特別枠設定が未実装
**対応案**: オンボーディング拡張 or 設定画面から追加入力

### BL-002: Intent分類 → 自動支出記録
**旧設計**: Unit 2/3 — 会話テキストから支出情報を自動抽出（金額・品名・カテゴリ）
**現状**: U8 chat_service.py に簡易実装あり
**課題**: 精度向上（「コンビニで1000円使った」→ 曖昧さの解消ロジック）
**対応案**: Bedrock プロンプト改善 + 確認フロー

### BL-003: レシートOCR → 支出自動登録
**旧設計**: Unit 3 — 画像送信 → Nova Lite で解析 → 品目・金額抽出
**現状**: U8 receipt_service.py に実装済み
**課題**: 精度不足時のフォールバック（Textract + LLM）、複数品目の分割記録
**対応案**: 解析結果の確認UI改善

### BL-004: ご褒美候補プール自動更新
**旧設計**: Unit 4 — 楽天API + Amazon Wishlist + EventBridge定期更新
**現状**: U8 product_search.py（楽天）+ wishlist_service.py（Amazon）
**課題**: 定期更新スケジューラが未実装、キャッシュ戦略
**対応案**: EventBridge Schedule → Lambda で定期更新

### BL-005: ストレス検知 → プロアクティブ提案
**旧設計**: Unit 5/6 — 感情推定 + 疲労スコア → Push通知でご褒美提案
**現状**: U8 proactive_message.py に実装開始
**課題**: Push通知のタイミング最適化、提案の押し付け感回避
**対応案**: ブラウザPush + アプリ内通知の使い分け

---

## 🟡 中優先

### BL-006: キャラクター口調の一貫性
**旧設計**: Unit 2 — `character_prompts.py` で口調パターン定義（friendly/polite/devilish）
**現状**: U8 chat_service にキャラプロンプト埋め込み
**課題**: 長い会話で口調がブレる、感情に応じたトーン切り替え
**対応案**: プロンプトテンプレート分離 + few-shot examples

### BL-007: 嗜好メモリ（PREF_MEMORY）自動蓄積
**旧設計**: Unit 2 — 会話から「好き」「嫌い」を検出 → 嗜好DBに自動保存
**現状**: U8 未実装
**課題**: ご褒美提案の精度に直結するが実装なし
**対応案**: 会話後処理で嗜好抽出 → DynamoDB PREF# に保存

### BL-008: Google Calendar連携
**旧設計**: Unit 0 — OAuth 2.0 でカレンダー取得 → 忙しさ推定
**現状**: 旧スタックで ENABLE_GOOGLE_CALENDAR=false（無効化済み）
**課題**: 忙しさの客観指標として有用だが、OAuth UXが複雑
**対応案**: v2で再検討（PWAなら OAuth redirect がシンプル）

### BL-009: ご褒美予算の月次繰越ロジック
**旧設計**: Unit 5 — 余剰は次月へ繰越、超過はリセット
**現状**: U8 デモシナリオにのみ存在（バックエンド未実装）
**課題**: 月末処理のEventBridgeスケジュール未設定
**対応案**: Lambda + EventBridge で月初に自動計算

### BL-010: Nova Act による商品検索自動化
**旧設計**: worker/ — Playwright ベースで Amazon 商品検索・情報抽出
**現状**: アーカイブ済み（`archive/v1-line-bot/worker/`）
**課題**: Nova Act の安定性（ブラウザ自動操作は壊れやすい）
**対応案**: 楽天API + Amazon PA-API で代替検討、Nova Act は補助的に

---

## 🟢 低優先

### BL-011: DynamoDB TTL による自動データクリーンアップ
**旧設計**: Unit 0/2 — CHATログに TTL 30日設定
**課題**: U8 でTTL未設定（無限蓄積）
**対応案**: テーブル設計見直し時に対応

### BL-012: LLM出力品質テスト
**旧設計**: tests/llm/ — Intent分類精度・口調一貫性のリグレッションテスト
**課題**: U8 でLLMテスト未整備
**対応案**: CI/CD パイプライン整備時に追加

### BL-013: 構造化ログ（PII除外）
**旧設計**: Unit 0 — `logger.py` で個人情報をマスキング
**課題**: U8 は print ベースのログ
**対応案**: aws-lambda-powertools 導入

### BL-014: 記念日の自然収集
**旧設計**: Unit 2 — 会話中「結婚記念日」等を検出 → anniversaries に保存
**課題**: U8 未実装
**対応案**: BL-007（嗜好メモリ）と同じ仕組みで対応可能

### BL-015: Secrets Manager 統合管理
**旧設計**: Unit 0 — `secrets.py` で一元管理 + キャッシュ
**課題**: U8 は環境変数直接参照
**対応案**: セキュリティ強化フェーズで対応

---

## 旧スタック削除（インフラ課題）

### BL-100: auto-reward-service スタック削除
**状況**: AWS上にLINE Bot関連リソースが残存（Lambda×6, API Gateway, SQS, EventBridge等）
**ブロッカー**: ArsTable (DynamoDB) を ars-u8-pwa が参照中
**手順**:
1. template.yaml の ArsTable に `DeletionPolicy: Retain` を追加してデプロイ
2. `aws cloudformation delete-stack --stack-name auto-reward-service`
3. 不要な Secrets Manager シークレット（ars/line等）も削除

---

## LINE 廃止の経緯メモ

LINE Messaging API を中心にMVPを構築したが、以下の制約により PWA へピボット:

1. **Push制限**: フリープラン月200通。プロアクティブ提案の頻度が制限される
2. **LIFF制限**: WebView内でのUX制約が大きく、リッチなダッシュボードが作れない
3. **レスポンス遅延**: Webhook→Lambda→Bedrock→Replyの往復で2-4秒かかる
4. **Rich Menu固定性**: 動的UI変更不可。キャラクター表情変化が表現できない
5. **開発速度**: LINE Developer Console での設定変更がボトルネック
6. **音声対応不可**: LINE内で音声リアルタイム会話ができない（PWAならWebSocket+Nova Sonic可能）
