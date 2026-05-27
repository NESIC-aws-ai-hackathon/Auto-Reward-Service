# アーカイブ: v1 LINE Bot コンセプト

## アーカイブ日
2026-05-26

## アーカイブ理由
LINE Bot 中心のコンセプト（v1）から **PWA スタンドアロン（v2）** へピボットしたため。

### LINE を廃止した理由
- **Push通知の制限**: フリープランでは月200通まで。ユーザー数が増えた場合にスケールしない
- **LIFF の UX 制限**: LIFF 内のWebViewは制約が多く、リッチなダッシュボードUIが作れない
- **Messaging API の応答速度**: Webhook → Lambda → Bedrock → Reply の往復で体感遅延が大きい
- **リッチメニューの固定性**: 動的な UI 変更ができず、キャラクターの表情変化等が表現できない
- **開発イテレーション速度**: LINE 側の設定変更が必要なたびにデプロイサイクルが遅れる
- **認証の複雑さ**: LIFF + LINE Login + JWT の組み合わせが過剰に複雑

### 新コンセプト（v2）の方向性
- PWA スタンドアロン（Cognito認証）
- CloudFront + S3 でフロントエンド配信
- Lambda バックエンド（API Gateway HTTP API）
- リアルタイム音声チャット（Nova Sonic via WebSocket）
- ブラウザ Push 通知（VAPID）

## このアーカイブに含まれるもの
| ディレクトリ/ファイル | 説明 |
|---------------------|------|
| `src/handlers/` | LINE Webhook・Intent分類・キャラ応答・支出抽出・レシート解析・ご褒美提案・Push通知 |
| `src/prompts/` | Bedrock用プロンプト定義 |
| `layer/` | Lambda Layer（line-bot-sdk, requests, boto3等） |
| `template.yaml` | AWS SAM テンプレート（LINE Bot全リソース定義） |
| `samconfig.toml` | SAM デプロイ設定 |
| `Makefile` | ビルド・デプロイコマンド |
| `requirements.txt` | Python依存（line-bot-sdk等） |
| `scripts/` | LINE Rich Menu 登録スクリプト |
| `images/` | Rich Menu 画像 |
| `pwa/` | PWA通知受信用（LINE Push代替として一時使用） |
| `worker/` | Nova Act Worker（Amazon商品検索） |
| `tools/` | Nova Act Smoke テスト |
| `tests/` | ユニットテスト・LLMテスト |

## AWS リソース（未削除）
旧スタック `auto-reward-service` は AWS 上に残存しています。
**ArsTable (DynamoDB)** を新コンセプト（ars-u8-pwa）が参照しているため、手動で対応が必要です。

### 削除手順（後日対応）
1. `template.yaml` の ArsTable に `DeletionPolicy: Retain` を追加してデプロイ
2. `aws cloudformation delete-stack --stack-name auto-reward-service` 実行
3. ArsTable は孤立リソースとして残るため、u8 から引き続き参照可能

## 再利用可能な設計資産
旧コンセプトの設計で新コンセプトに持ち越せるアイデアは [BACKLOG.md](../../BACKLOG.md) に記載。
