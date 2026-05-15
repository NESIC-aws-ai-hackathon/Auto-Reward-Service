# ワークフロー実行計画 — オートリワードサービス（v2 / コンセプト変更後）

**改訂日**: 2026-05-15  
**プロジェクトタイプ**: Greenfield  
**複雑度**: Moderate-Complex（Lambda サーバーレス + Bedrock LLM + LINE API + 楽天API）

---

## スコープ・影響分析

### 変更影響範囲

| 影響領域 | 詳細 |
|----------|------|
| ユーザー影響 | LINE Bot 経由のエンドユーザー体験全体 |
| アーキテクチャ影響 | AWS Lambda（Python）+ API Gateway + DynamoDB + Bedrock + SAM |
| データモデル影響 | DynamoDB シングルテーブル（PK=USER#{lineUserId}, SK=種別プレフィックス） |
| API 影響 | LINE Webhook受信 + 楽天API連携 + LIFF API |
| NFR 影響 | セキュリティ（LINE署名検証必須）・応答速度（3秒以内）・コスト管理 |

### リスク評価

| リスク | レベル | 理由 |
|--------|--------|------|
| 総合リスク | **Medium** | サーバーレス + LLMの組み合わせは標準的だが、LINE応答3秒制約とCold Startが課題 |
| LLM品質リスク | Medium | キャラ口調品質がプロダクト価値の中心。Nova品質不足時のフォールバック設計が必要 |
| 楽天API依存リスク | Low | API仕様変更・レート制限のリスクはあるが、候補プール方式なのでリアルタイム依存は低い |
| LINE制約リスク | Low | フリープランの月200通制約は設計済み（Push=デモ用・1日1回、Reply中心） |

---

## 実行フェーズ判定

### INCEPTION PHASE

| ステージ | 実行判定 | 理由 |
|----------|----------|------|
| Workspace Detection | ✅ 完了 | — |
| Reverse Engineering | ⏭️ スキップ | Greenfield のため不要 |
| Requirements Analysis | ✅ 再完了 | コンセプト変更に伴い再実行済み（v2） |
| **User Stories** | ⏭️ スキップ | `requirements.md` §7 に主要シナリオ S1〜S5 が定義済み |
| **Workflow Planning** | ✅ 実行中（本ファイル） | — |
| **Application Design** | ✅ 実行する | Lambda関数・DynamoDBスキーマ・モジュール設計が必要 |
| **Units Generation** | ✅ 実行する | 実装スライス分解・依存関係定義が必要 |

### CONSTRUCTION PHASE（Unit ごとにループ）

実装優先順位: **LINE Bot基盤 → リワードちゃん会話品質 → 支出抽出 → ご褒美提案 → その他**

| 順序 | Unit | 内容 | 優先度 |
|------|------|------|--------|
| 0 | Unit 0 | SAMプロジェクト基盤・共通Layer・DynamoDBテーブル定義 | 先行必須 |
| 1 | Unit 1 | LINE Bot基盤（Webhook受信・署名検証・Router・Reply/Push） | 最優先 |
| 2 | Unit 2 | リワードちゃんキャラクター（Intent分類・口調生成・感情把握） | 最優先 |
| 3 | Unit 3 | 支出記録（チャット抽出・確認フロー・レシート画像解析） | 高 |
| 4 | Unit 4 | ご褒美候補プール（嗜好記憶・楽天API連携・日次バッチ） | 高 |
| 5 | Unit 5 | ご褒美提案（状態推定・マッチング・余裕額チェック） | 高 |
| 6 | Unit 6 | Push通知（通数管理・コンテンツ生成・EventBridge） | 中 |
| 7 | Unit 7 | LIFFダッシュボード（最小限・履歴・設定・口調選択） | 中 |

### NFR 設計の適用

| NFR | 適用対象 | 判定 |
|-----|----------|------|
| セキュリティ（LINE署名検証・Secrets管理） | Unit 1（必須）、全Unit | ✅ 必須 |
| 応答速度（LINE Reply 3秒以内） | Unit 1, 2, 3, 5 | ✅ 各 Unit の設計で考慮 |
| コスト管理（Nova使用量・楽天API・Push通数） | Unit 2, 4, 6 | ✅ 各 Unit の設計で定義 |
| LLMテスト（プロンプトテスト・出力品質） | Unit 2, 3, 5, 6 | ✅ Code Generation に含める |

---

## 成果物一覧

### INCEPTION フェーズ成果物

```
aidlc-docs/
├── aidlc-state.md（更新済み）
├── audit.md（更新済み）
└── inception/
    ├── requirements/
    │   ├── concept-change-questions.md（回答済み）
    │   └── requirements.md（v2 - 新コンセプト版）✅
    ├── plans/
    │   ├── workflow-plan.md（本ファイル v2）✅
    │   ├── application-design-plan.md（次ステップで更新）
    │   └── unit-of-work-plan.md（Units Generation で更新）
    └── application-design/
        ├── application-design.md（v2 - 全面書き換え）
        ├── components.md（v2）
        ├── component-methods.md（v2）
        ├── services.md（v2）
        ├── component-dependency.md（v2）
        ├── unit-of-work.md（v2）
        ├── unit-of-work-dependency.md（v2）
        └── unit-of-work-story-map.md（v2）
```
