# AI-DLC 状態管理

## プロジェクト情報
- **プロジェクト名**: オートリワードサービス（ARS）
- **プロジェクト種別**: グリーンフィールド（新規開発）
- **開始日**: 2026-05-07
- **コンセプト変更日**: 2026-05-15
- **現在のステージ**: CONSTRUCTION フェーズ — Unit 7: LIFFダッシュボード（Code Generation 完了）

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
- [x] Unit 0: SAM基盤 + 共通Layer
  - [x] Functional Design
  - [x] NFR Requirements
  - [x] NFR Design
  - [x] Infrastructure Design
  - [x] Code Generation
- [x] Unit 1: LINE Bot基盤
  - [x] Functional Design
  - [x] NFR Requirements
  - [x] NFR Design
  - [x] Infrastructure Design
  - [x] Code Generation
  - [x] Deploy Round 2（LINE疎通確認）✅ 2026-05-16
- [x] Unit 2: リワードちゃんキャラクター
  - [x] Functional Design
  - [x] NFR Requirements
  - [x] NFR Design
  - [x] Infrastructure Design
  - [x] Code Generation ✅ 2026-05-16／137テスト PASS
  - [x] Deploy Round 3（リワードちゃん応答確認）✅ 2026-05-16
- [x] Unit 3: 支出記録
  - [x] Functional Design ✅ 2026-05-16
  - [x] NFR Requirements ✅ 2026-05-16
  - [x] NFR Design ✅ 2026-05-16
  - [x] Infrastructure Design ✅ 2026-05-16
  - [x] Code Generation ✅ 2026-05-16／254テスト PASS
  - [x] Deploy（バグ修正含む）✅ 2026-05-16（ArsCommonLayer:13）
- [x] Unit 4: ご褒美候補プール
  - [x] Functional Design
  - [x] NFR Requirements
  - [x] NFR Design
  - [x] Infrastructure Design
  - [x] Code Generation ✅ 52テスト PASS
  - [x] Growth機能 (4-7/4-8/4-9) ✅ 221テスト PASS（楽天トラベルAPI・ホットペッパーAPI・カテゴリ重みづけ）
  - [x] Deploy Round 4 ✅ 2026-05-（UPDATE_COMPLETE）
- [x] Unit 5: ご褒美提案
  - [x] Functional Design ✅ 2026-05-16（F2-07 繰り越し機能含む）
  - [x] NFR Requirements ✅ 2026-05-16
  - [x] NFR Design ✅ 2026-05-16
  - [x] Infrastructure Design ✅ 2026-05-16
  - [x] Code Generation ✅ 313テスト PASS（繰り越し機能 F2-07 含む）
  - [x] Deploy Round 5 ✅ 2026-05-16（U3〜U5 まとめデプロイ）
- [ ] Unit 6: Push通知
- [ ] Unit 7: LIFFダッシュボード
  - [x] Functional Design ✅ 2026-05-16
  - [x] NFR Requirements ✅ 2026-05-16
  - [x] NFR Design ✅ 2026-05-16
  - [x] Infrastructure Design ✅ 2026-05-16
  - [x] Code Generation ✅ 344テスト PASS（31テスト追加）

### 🟡 OPERATIONS フェーズ
- [ ] 運用（プレースホルダー）
