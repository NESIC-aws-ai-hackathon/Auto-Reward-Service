# ワークフロー実行計画 — オートリワードサービス

**作成日**: 2026-05-08  
**プロジェクトタイプ**: Greenfield  
**複雑度**: Complex（7 Unit、マイクロサービス、AI 連携）

---

## スコープ・影響分析

### 変更影響範囲

| 影響領域 | 詳細 |
|----------|------|
| ユーザー影響 | エンドユーザー向け新規サービス全体 |
| アーキテクチャ影響 | マイクロサービス（6 サービス）+ React フロントエンド |
| データモデル影響 | PostgreSQL / TimescaleDB / Redis / ClickHouse |
| API 影響 | 新規 REST API（全 Unit） |
| NFR 影響 | セキュリティ（必須）・パフォーマンス・テスト戦略 |

### リスク評価

| リスク | レベル | 理由 |
|--------|--------|------|
| 総合リスク | **High** | 6 サービス新規構築、LLM 連携、Auth マネージドサービス、Growth 拡張性設計が必要 |
| 技術的不確実性 | Medium | NestJS + TypeScript 統一構成は標準的だが、TimescaleDB / ClickHouse は専門性が必要 |
| スコープリスク | Medium | MVP に絞ったが、Growth 見据えの設計判断が複雑 |

---

## 実行フェーズ判定

### INCEPTION PHASE

| ステージ | 実行判定 | 理由 |
|----------|----------|------|
| Workspace Detection | ✅ 完了 | — |
| Reverse Engineering | ⏭️ スキップ | Greenfield のため不要 |
| Requirements Analysis | ✅ 完了 | — |
| **User Stories** | ⏭️ スキップ | `要件定義書.md` §9 に US-01〜US-13 が完全定義済み。新規作成不要 |
| **Workflow Planning** | ✅ 実行中 | 常に実行 |
| **Application Design** | ✅ 実行する | 6 サービス × コンポーネント設計が必要 |
| **Units Generation** | ✅ 実行する | 7 Unit の分解・依存関係・ストーリーマップが必要 |

### CONSTRUCTION PHASE（Unit ごとにループ）

実装順序は要件確認の回答（Q2=C「コアバリュー優先」）に従い以下の順とする：

| 順序 | Unit | サービス名 | 設計ステージ |
|------|------|----------|------------|
| 1 | U1 | Auth Service | Functional Design + NFR Design + Infrastructure Design + Code Generation |
| 2 | U2 | Stress Service | Functional Design + NFR Design + Infrastructure Design + Code Generation |
| 3 | U4 | Reward Service | Functional Design + NFR Design + Infrastructure Design + Code Generation |
| 4 | U3 | Finance Service | Functional Design + NFR Design + Infrastructure Design + Code Generation |
| 5 | U5 | Notification Service | Functional Design + NFR Design + Code Generation |
| 6 | U7 | Dashboard Service | Functional Design + NFR Design + Code Generation |

> **注**: U1（Auth Service）は U2/U4 の依存前提のため最初に実装する

### NFR 設計の適用

| NFR | 適用対象 | 判定 |
|-----|----------|------|
| セキュリティ（Security Baseline） | 全 Unit | ✅ 必須（全ルール） |
| パフォーマンス（p95 < 500ms） | 全 API | ✅ 各 Unit の NFR Design で定義 |
| テスト（Unit + 統合テスト） | 全 Unit | ✅ Code Generation に含める |
| PBT（Partial モード） | U2・U3・U4 の純粋関数 | ✅ 対象 Unit の Functional Design で特定 |

### インフラ設計の適用

| ステージ | 判定 | 内容 |
|----------|------|------|
| Infrastructure Design（Docker Compose） | ✅ 実行する | ローカル開発環境の Docker Compose 設計（全サービス統合） |
| Infrastructure Design（Cloud） | ⏭️ 将来 | ローカル動作後にクラウド移行（本計画外） |

---

## 成果物一覧

### INCEPTION フェーズ成果物

```
aidlc-docs/
├── aidlc-state.md
├── audit.md
└── inception/
    ├── requirements/
    │   ├── requirement-verification-questions.md ✅
    │   └── requirements.md ✅
    ├── plans/
    │   ├── workflow-plan.md（本ファイル）✅
    │   ├── application-design-plan.md（次ステップで作成）
    │   └── unit-of-work-plan.md（Units Generation で作成）
    └── application-design/
        ├── components.md
        ├── component-methods.md
        ├── services.md
        ├── component-dependency.md
        ├── application-design.md
        ├── unit-of-work.md
        ├── unit-of-work-dependency.md
        └── unit-of-work-story-map.md
```

### CONSTRUCTION フェーズ成果物（Unit ごと）

```
aidlc-docs/construction/
└── {unit-name}/
    ├── functional-design.md
    ├── nfr-requirements.md
    ├── nfr-design.md
    └── infrastructure-design.md

{project-root}/
├── docker-compose.yml
├── apps/
│   ├── auth-service/
│   ├── stress-service/
│   ├── reward-service/
│   ├── finance-service/
│   ├── notification-service/
│   └── dashboard-service/
└── frontend/
    └── web/
```

---

## 次のステップ

1. **Application Design** — コンポーネント・サービス・依存関係の設計
2. **Units Generation** — Unit 境界・依存マトリクス・ストーリーマップの生成
3. **Construction Phase（U1 から順次）** — 設計 → コード生成 → テスト
