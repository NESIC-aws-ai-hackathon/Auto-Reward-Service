# AI-DLC 状態管理

## プロジェクト情報
- **プロジェクト名**: オートリワードサービス（ARS）
- **プロジェクト種別**: グリーンフィールド（新規開発）
- **開始日**: 2026-05-07
- **コンセプト変更日**: 2026-05-15
- **現在のステージ**: INCEPTION フェーズ 完了（承認待ち）

## コンセプト変更サマリー
- **変更根拠**: `docs/コンセプト変更定義書.md`
- **変更の性質**: 全面的なコンセプトピボット（Web App → LINE Bot中心）
- **変更分類**: SPEC_CHANGE

## 確定技術スタック
| 項目 | 決定内容 |
|------|---------|
| バックエンド | AWS Lambda（Python）+ API Gateway |
| DB | DynamoDB シングルテーブルデザイン |
| LLM | Amazon Bedrock（Nova Micro / Nova Lite）、モデル切り替え可能 |
| 画像解析 | Amazon Nova Lite（精度不足時 Textract+LLM or Claude Vision） |
| IaC | AWS SAM |
| LINE APIプラン | フリープラン（Push 1日1回・通常はReply中心） |
| ご褒美データ | 楽天ウェブサービスAPI |
| カレンダー連携 | Google Calendar API（OAuth 2.0 / calendar.events.readonly） |
| 認証 | LINEユーザーID + LIFF時LINEログイン |
| 言語 | Python 統一 |

## ワークスペース状態
- **既存コード**: なし
- **リバースエンジニアリング**: 不要
- **ワークスペースルート**: Auto-Reward-Service

## コード配置ルール
- **アプリケーションコード**: ワークスペースルート直下（aidlc-docs/ 配下には置かない）
- **ドキュメント**: aidlc-docs/ 配下のみ

## 拡張設定
| 拡張名 | 有効 | 決定ステージ |
|---|---|---|
| セキュリティベースライン | 有効（LINE Bot特有ルール重点） | 要件分析（v2） |
| プロパティベーステスト | 無効（LLMテスト重点に変更） | 要件分析（v2） |

## ステージ進捗
### 🔵 INCEPTION フェーズ
- [x] ワークスペース検出
- [x] 要件分析（v2 コンセプト変更後）
- [x] ワークフロー計画（v2）
- [x] アプリケーション設計（v2）
- [x] Unit 生成（v2）

### 🟢 CONSTRUCTION フェーズ
- [ ] Unit 0: SAM基盤 + 共通Layer
- [ ] Unit 1: LINE Bot基盤
- [ ] Unit 2: リワードちゃんキャラクター
- [ ] Unit 3: 支出記録
- [ ] Unit 4: ご褒美候補プール
- [ ] Unit 5: ご褒美提案
- [ ] Unit 6: Push通知
- [ ] Unit 7: LIFFダッシュボード

### 🟡 OPERATIONS フェーズ
- [ ] 運用（プレースホルダー）
