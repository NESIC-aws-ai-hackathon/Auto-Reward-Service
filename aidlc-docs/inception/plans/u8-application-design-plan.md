# Unit 8: Application Design Plan

## 設計スコープ

Unit 8 要件定義書（FR-8-01〜FR-8-09）に基づき、以下のアーティファクトを生成する：

- [ ] `components.md` — コンポーネント定義と責務
- [ ] `component-methods.md` — メソッドシグネチャ（詳細ロジックはFunctional Designで）
- [ ] `services.md` — サービス定義とオーケストレーション
- [ ] `component-dependency.md` — 依存関係と通信パターン
- [ ] `application-design.md` — 統合設計書

---

## 設計確認事項（5問）

### Q1: フロントエンド構成

Unit 8 PWA のフロントエンド実装方式を選択してください。

- A: Vanilla JS（現行LIFFと同じ単一HTMLアプローチ。最速実装）
- B: Vite + Vanilla JS（ビルドツールだけ導入。モジュール分割可能）
- C: React SPA（コンポーネント分割しやすいが学習コスト）
- D: Next.js（SSR/SSG、Vercelデプロイ。オーバースペック気味）

[Answer]: C — React SPA。実装は Vite + React SPA。Next.jsは不要。

### Q2: Lambda 関数構成

バックエンドのLambda構成を選択してください。

- A: 単一Lambda + ルーティング（現行 `liff_api.py` と同じパターン。管理コスト低）
- B: 機能別Lambda（auth, voice-session, transcript, analysis, push）に分離。個別デプロイ・スケーリング可能
- C: ハイブリッド（同期API系は1つのLambda、非同期分析系は別Lambda）

[Answer]: C — ハイブリッド構成。同期API系はまとめ、非同期分析系は別Lambdaに分ける。

### Q3: Transcript 保存方式

音声会話のTranscriptをバックエンドに送る方式を選択してください。

- A: ターンごと（ユーザー発話+AI応答のペアごとにAPIコール）
- B: セッション終了時一括（会話終了時にまとめて送信）
- C: 定期バッチ（30秒〜1分ごとに蓄積分を送信）
- D: ハイブリッド（通常はターンごと、切断時はローカルキャッシュから再送）

[Answer]: D — 通常はターンごとにTranscript保存、切断時はPWA側ローカルキャッシュから再送。

### Q4: ライフログ分析トリガー

Transcript からライフログを抽出する非同期分析のトリガー方式を選択してください。

- A: Transcript保存時にDynamoDB Streamsで発火（リアルタイム性高）
- B: 会話セッション終了イベントで発火（セッション単位で分析）
- C: EventBridge 定期実行（5分ごとに未分析Transcriptをバッチ処理）
- D: 手動 + 日次バッチ（日記サマリ生成の前にまとめて分析）

[Answer]: B — 会話セッション終了イベントで分析ジョブ作成。補助的にEventBridgeで取りこぼし再処理。

### Q5: PWA ホスティング

PWA の静的ファイルホスティング方式を選択してください。

- A: S3 + CloudFront（AWS内で完結、カスタムドメイン設定可能）
- B: API Gateway 経由で Lambda が返却（現行LIFFと同じ方式。インフラ追加なし）
- C: Vercel / Netlify（外部ホスティング。デプロイ簡単だがAWS外）

[Answer]: A — S3 + CloudFront。APIはAPI Gateway + Lambdaに分離。
