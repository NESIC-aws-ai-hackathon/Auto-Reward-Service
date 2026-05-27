# デプロイ・テスト方針 — Auto-Reward-Service (v2: PWA)

## 現在のアーキテクチャ

U8 (PWA スタンドアロン) が現行コンセプト。U0〜U7 は LINE Bot 中心の旧コンセプトで `archive/v1-line-bot/` にアーカイブ済み。

## デプロイ対象

| スタック | 用途 | テンプレート |
|---------|------|-------------|
| `ars-u8-pwa` | バックエンド（Lambda + Cognito + API Gateway） | `u8/template.yaml` |
| CloudFront + S3 | フロントエンド配信 | 手動 / CI |

## デプロイ手順

### フロントエンド
```bash
cd u8/frontend
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

## テスト方針

| 対象 | 方法 |
|------|------|
| フロントエンド | ブラウザ手動確認 + デモモード再生 |
| バックエンド | pytest (`u8/tests/`) |
| E2E | デモシナリオ 12 パターンの自動再生確認 |

## 開発ルール

- 明確な要件の場合は承認をスキップして次の作業に進むことも許可する
- AI-DLC 成果物はすべて確実に生成すること
- 旧コンセプトの設計で活かせるものは [BACKLOG.md](BACKLOG.md) を参照
- `archive/` フォルダは参照専用。編集しない

## 残存する旧リソース（AWS）

旧スタック `auto-reward-service` が AWS 上に残っています（ArsTable を含む）。
U8 が ArsTable を参照しているため、削除は手動で段階的に対応してください。
手順は `archive/v1-line-bot/README.md` に記載。
