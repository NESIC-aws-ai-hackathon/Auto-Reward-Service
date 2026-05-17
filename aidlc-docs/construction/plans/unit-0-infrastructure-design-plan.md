# Infrastructure Design Plan — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16  
**ステータス**: 完了

---

## 実行計画チェックリスト

- [x] Step 1: Functional Design / NFR Design 成果物分析
- [x] Step 2: Infrastructure Design Plan 作成（本ファイル）
- [x] Step 3: 質問収集・回答受取
- [x] Step 4: 回答の曖昧さ解消
- [x] Step 5: Infrastructure Design 成果物生成
  - [x] `infrastructure-design.md`
  - [x] `deployment-architecture.md`
- [ ] Step 6: 承認・次ステージへ進行

---

## 既確定インフラ（質問不要）

| コンポーネント | 決定内容 |
|-------------|---------|
| AWS リージョン | ap-northeast-1（東京） |
| DynamoDB | ArsTable / オンデマンド / GSI:entityType-index / TTL / SSE / PITR |
| Lambda Layer | ArsCommonLayer（services + utils + models） |
| Secrets Manager | ars/line-{stage} / ars/google-{stage} / ars/rakuten-{stage} |
| CloudWatch Logs | 30日保持 / JSON 構造化ログ |
| EventBridge | ウォームアップ ping 5分毎（Webhook / CharacterReply） |
| X-Ray | 無効（SAM PassThrough） |
| Python | 3.14 |
| IaC | AWS SAM |

---

## 質問一覧（[Answer]: タグで回答してください）

### Q1: Lambda の VPC 配置

Lambda 関数を VPC 内に配置するか選択してください。  
VPC 配置はセキュリティ強化になりますが、Cold Start が増加し、NAT Gateway コストが発生します。

A) **VPC 外**（デフォルト）— Cold Start 最小・コスト最小。MVP に最適  
B) **VPC 内**（既存 VPC を利用）— DynamoDB・Secrets Manager には VPC エンドポイントが必要  
C) **VPC 内**（新規 VPC を SAM で作成）— IaC 管理だがセットアップコスト大  
D) **VPC 外**（MVP）→ **VPC 内**（本番）の段階移行  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q2: SAM デプロイ用 S3 バケット

`sam deploy` のアーティファクト格納先 S3 バケットを選択してください。

A) **SAM が自動作成**（`--resolve-s3` オプション）— `aws-sam-cli-managed-default-samclisourcebucket-*` が自動生成  
B) **手動で事前作成**した既存バケット名を `samconfig.toml` に指定  
C) **A（自動作成）** を dev 環境で使用し、prod は B（既存バケット）  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q3: CloudWatch アラーム

MVP 段階で設定する基本アラートを選択してください。

A) **なし**（ログ確認のみ。問題が起きたら手動調査）  
B) **Lambda エラー率アラーム**のみ（WebhookHandler エラー率 > 5% で SNS 通知）  
C) **最小セット**: Lambda エラー率 + DynamoDB スロットリング の2種類  
D) **フルセット**: エラー率 / スロットリング / Bedrock タイムアウト / Lambda Duration の4種類  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q4: SAM スタック名・環境分離

SAM スタック名と dev/prod 環境の分離方式を選択してください。

A) スタック名: `auto-reward-service-{stage}`（dev / prod で同一テンプレートをデプロイ）  
B) スタック名: `ars-{stage}`（短縮形）  
C) dev と prod で別々の `samconfig.toml` プロファイルを用意  
D) A + C（スタック名 `auto-reward-service-{stage}` + 別プロファイル）  
E) その他（具体的に記述してください）

[Answer]: そもそもprodのみでいいよ。ハッカソンで使えればいいので環境を分ける必要ない

