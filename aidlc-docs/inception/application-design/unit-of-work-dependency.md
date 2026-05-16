# Unit of Work 依存マトリクス — オートリワードサービス（v2）

**改訂日**: 2026-05-15 / コンセプト変更後版

## 依存マトリクス

`✅` = 依存あり（実装前に依存先が必要）  
`—` = 依存なし

| Unit | U0 基盤 | U1 LINE基盤 | U2 キャラ | U3 支出記録 | U4 候補プール | U5 提案 | U6 Push | U7 LIFF |
|------|:------:|:----------:|:-------:|:---------:|:-----------:|:------:|:------:|:------:|
| **U0 基盤** | — | — | — | — | — | — | — | — |
| **U1 LINE基盤** | ✅ | — | — | — | — | — | — | — |
| **U2 キャラ** | ✅ | ✅ | — | — | — | — | — | — |
| **U3 支出記録** | ✅ | ✅ | ✅ | — | — | — | — | — |
| **U4 候補プール** | ✅ | — | ✅（嗜好取得） | — | — | — | — | — |
| **U5 提案** | ✅ | ✅ | ✅ | ✅（支出履歴） | ✅（候補） | — | — | — |
| **U6 Push** | ✅ | — | ✅ | — | — | ✅（提案内容） | — | — |
| **U7 LIFF** | ✅ | — | — | ✅（支出履歴） | ✅（候補一覧） | ✅（提案履歴） | — | — |

---

## 実装順序グラフ

```
Unit 0（SAM基盤 + 共通Layer）
    │
    ├──► Unit 1（LINE Bot基盤：Webhook + Router）
    │         │
    │         ▼
    └──► Unit 2（リワードちゃん：Intent + キャラ + 初回登録）
              │
         ┌────┤
         │    │
         ▼    ▼
    Unit 3    Unit 4（候補プール：楽天API + 日次バッチ）
  （支出記録）    │
         │    │
         └────┘
              ▼
         Unit 5（ご褒美提案：マッチング + 余裕額）
              │
         ┌────┤
         │    │
         ▼    ▼
    Unit 6    Unit 7（LIFFダッシュボード：履歴 + 設定）
  （Push通知：1日1回）
```

---

## 実装前提条件（ブロッキング依存）

| Unit | 開始前の必須条件 |
|------|--------------|
| Unit 1 | Unit 0の `dynamodb_service`, `line_service`, `secrets` がimportできる |
| Unit 2 | Unit 1のWebhook受信が動作し、ルーティングにフックできる |
| Unit 3 | Unit 2のIntent分類が動作する（EXPENSE Intentを受け取れる） |
| Unit 4 | Unit 2 の嗜好記憶（PREF_MEMORY#）スキーマが確定し、スライス 2-8 の書き込みが実装されていること |
| Unit 5 | Unit 3のEXPENSE保存 + Unit 4のREWARD_POOL保存が動作する。カレンダー活用提案（スライス 5-8）は Unit 0 の google_calendar_service（スライス 0-9）が実装済みであること |
| Unit 6 | Unit 5のREWARD_SUGGESTION保存が動作する |
| Unit 7 | Unit 3の支出履歴 + Unit 5の提案履歴が取得できる。Googleカレンダー連携（スライス 7-6）は Unit 0 の google_calendar_service および Secrets Manager に Google OAuth Client ID/Secret が設定済みであること |
