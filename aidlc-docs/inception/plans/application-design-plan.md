# Application Design プラン — オートリワードサービス

**作成日**: 2026-05-08

> **回答方法**: 各 `[Answer]:` タグの後に選択肢（A, B, C...）を記入してください。
> 選択肢に合うものがない場合は「X」を記入し、その下に自由記述してください。

---

## 実行チェックリスト

- [x] Q1〜Q7 への回答収集
- [x] components.md 生成
- [x] component-methods.md 生成
- [x] services.md 生成
- [x] component-dependency.md 生成
- [x] application-design.md（統合版）生成
- [ ] ユーザー承認

---

## 【Q1】NestJS のモジュール境界

各マイクロサービス内での NestJS モジュール分割方針を教えてください。

A) **機能レイヤー分割** — Controller / Service / Repository の3層をモジュールで表現する  
B) **ドメイン分割** — ビジネスドメイン（例: StressEntry, StressScore）ごとにモジュールを作る  
C) **ハイブリッド** — コアドメインはドメイン分割、共通機能（Auth, Config, Logging）はレイヤー分割  
X) その他（以下に記述）

[Answer]: C

---

## 【Q2】サービス間通信（MVP 同期処理）の実装方法

MVP では Kafka を使わず HTTP 同期処理とする決定がありました。サービス間呼び出しの実装方法を教えてください。

A) **NestJS HttpModule（axios）** — 各サービスが他サービスの REST API を直接呼び出す  
B) **NestJS Microservices（TCP トランスポート）** — NestJS のマイクロサービス機能で TCP 通信  
C) **共有ライブラリ経由** — npm workspace 内の共有クライアントパッケージを通して呼び出す  
X) その他（以下に記述）

[Answer]: C

---

## 【Q3】フロントエンド（React）の状態管理

A) **React Query（TanStack Query）** — サーバーステートに特化、シンプル構成  
B) **Redux Toolkit + React Query** — グローバルステート + サーバーステートを分離  
C) **Zustand + React Query** — 軽量グローバルステート + サーバーステート  
D) **Context API のみ** — 最小構成  
X) その他（以下に記述）

[Answer]: C

---

## 【Q4】フロントエンドのコンポーネント設計方針

A) **Atomic Design** — atoms / molecules / organisms / templates / pages の5層  
B) **機能ベース（Feature-based）** — features/ ディレクトリ配下に画面単位でまとめる  
C) **ページベース** — pages/ + components/ のシンプル2層  
X) その他（以下に記述）

[Answer]: B

---

## 【Q5】Auth0 / Cognito との統合パターン

A) **各サービスが個別に JWT 検証** — NestJS Guard で各サービスが JWKS エンドポイントを叩いて検証  
B) **API Gateway で一元検証** — Nginx / Kong などで JWT 検証後、サービスには検証済みユーザー情報をヘッダーで渡す  
C) **Auth Service が中継** — Auth Service のみが Auth0/Cognito と通信し、他サービスは Auth Service に検証依頼  
X) その他（以下に記述）

[Answer]: B

---

## 【Q6】OpenAI API 呼び出しの配置

A) **各サービスが直接 OpenAI API を呼び出す** — Stress Service・Notification Service・Dashboard Service がそれぞれ呼び出す  
B) **共有 AI クライアントモジュール** — OpenAI 呼び出しを npm workspace の共有パッケージに切り出す  
C) **専用 AI Service（LLM Gateway）** — OpenAI 呼び出しをまとめる専用サービスを設ける  
X) その他（以下に記述）

[Answer]: B

---

## 【Q7】モノレポ構成

複数サービス + フロントエンドをどう管理しますか？

A) **npm workspaces（モノレポ）** — ルートの package.json で全サービスを一元管理  
B) **Turborepo** — npm workspaces ベースにビルドキャッシュを追加  
C) **Nx** — モノレポフレームワーク、依存グラフ管理が強力  
D) **独立リポジトリ** — サービスごとに別リポジトリ（ポリリポ）  
X) その他（以下に記述）

[Answer]: B
