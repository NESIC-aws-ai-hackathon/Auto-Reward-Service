# Unit of Work 依存マトリクス — オートリワードサービス

## 依存マトリクス

`✅` = 依存あり（実装前に依存先が必要）  
`—` = 依存なし

※ Unit番号は要件定義書の Unit 番号と一致させています（U4=Reward Service、U3=Finance Service、U7=Dashboard Service）。
実装サイクル順は「推奨実装順序」セクションを参照してください。

| Unit | U0 基盤 | U1 Auth | U2 Stress | U4 Reward | U3 Finance | U5 Notif | U7 Dashboard |
|------|--------|---------|----------|----------|-----------|---------|------------|
| **U0 基盤** | — | — | — | — | — | — | — |
| **U1 Auth** | ✅ | — | — | — | — | — | — |
| **U2 Stress** | ✅ | ✅ | — | ✅（Client） | — | — | — |
| **U4 Reward** | ✅ | ✅ | ✅（受信側） | — | ✅（Client） | ✅（Client） | — |
| **U3 Finance** | ✅ | ✅ | — | — | — | — | — |
| **U5 Notif** | ✅ | ✅ | — | ✅（受信側） | — | — | — |
| **U7 Dashboard** | ✅ | ✅ | ✅（Client） | ✅（Client） | ✅（Client） | — | — |
| **Web** | ✅（types） | ✅（API） | ✅（API） | ✅（API） | ✅（API） | ✅（API） | ✅（API） |

---

## 実装順序グラフ

```
Unit 0（基盤）
    │
    ├──► Unit 1（Auth Service）
    │         │
    │    ┌────┤
    │    │    │
    │    ▼    ▼
    ├──► Unit 2（Stress Service）─────────────────────────┐
    │              │                                       │
    │              │ RewardClient 呼び出し                  │
    │              ▼                                       │
    ├──► Unit 3（Reward Service）◄── FinanceClient ───────┤
    │              │                                       │
    │              │ NotificationClient 呼び出し            │
    │              ▼                                       │
    ├──► Unit 5（Notification Service）                    │
    │                                                      │
    ├──► Unit 4（Finance Service）─────────────────────────┘
    │
    └──► Unit 6（Dashboard Service）
              │ 全 Client 依存
              ▼
         （全 Unit 完了後に実装推奨）

Unit 7（Web Frontend）
    └── 全バックエンド Unit 完了後（または並行して API モックで開発）
```

---

## 推奨実装順序

```
[1] Unit 0  — 基盤（Turborepo + 共有パッケージ + Docker Compose 骨格）
[2] Unit 1  — Auth Service
[3] Unit 2  — Stress Service（RewardClient はスタブ呼び出し）
[4] Unit 3  — Reward Service（FinanceClient, NotifClient はスタブ呼び出し）
[5] Unit 4  — Finance Service（FinanceClient の実装を完成）
[6] Unit 5  — Notification Service（NotifClient の実装を完成）
[7] Unit 6  — Dashboard Service
[8] Unit 7  — Web Frontend（バックエンド完成後 or MSW モック並行開発）
```

---

## shared-clients 実装スケジュール

| Client | スタブ作成 | 実装完成 |
|--------|----------|---------|
| `RewardClient` | Unit 0 | Unit 3（スライス 3-8） |
| `FinanceClient` | Unit 0 | Unit 4（スライス 4-9） |
| `NotificationClient` | Unit 0 | Unit 5（スライス 5-8） |
| `StressClient` | Unit 0 | Unit 7 Dashboard Service（スライス 6-1 内で充実） |
| `DashboardClient` | Unit 0 | Unit 6（必要に応じて） |

---

## ブロッキング依存（実装開始の前提）

| 実装順 | サービス | 開始前に必要なこと |
|--------|---------|------------------|
| 第1 | U1 Auth Service | Unit 0 完了 |
| 第2 | U2 Stress Service | Unit 0 完了, U1 Auth の users テーブルが存在する |
| 第3 | U4 Reward Service | Unit 0 完了, U1 Auth 完了（※Stress Serviceは呼び出し元なので完了不要。RewardClientスタブが定義済みであれば開始可能） |
| 第4 | U3 Finance Service | Unit 0 完了, U1 Auth 完了 |
| 第5 | U5 Notification Service | Unit 0 完了, U1 Auth 完了, U4 Reward の RewardProposalDto が確定している |
| 第6 | U7 Dashboard Service | Unit 0 完了, U1 Auth 完了, U2〜U5 の API が動作する |
| 第7 | Web Frontend | Unit 0 の shared-types が確定している（MSW で並行開発可） |
