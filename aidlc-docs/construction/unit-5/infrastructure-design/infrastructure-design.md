# インフラ設計 — Unit 5: ご褒美提案 + 繰り越し機能

**Unit**: Unit 5 — ご褒美提案（F6 対応）+ 繰り越し機能（F2-07）  
**作成日**: 2026-05-16

---

## 1. Lambda 関数マッピング

| Lambda 関数 | 処理 | トリガー |
|---|---|---|
| `WebhookHandlerFunction` | LINE Webhook 受信 → Intent 分類 → `propose_reward()` ディスパッチ | API Gateway POST /webhook |

Unit 5 はハンドラー関数を新たに追加せず、既存の `webhook_handler.py` に `REWARD_PROPOSAL` インテント用のルーティングを追加する。`reward_proposal.py` は `src/handlers/` に配置済み。

---

## 2. DynamoDB テーブル（既存 ArsTable）

| アイテム | PK | SK | 新規/既存 |
|---|---|---|---|
| PROFILE# | USER#{id} | PROFILE# | 既存（carryover_rate フィールド追加） |
| MONTHLY_SUMMARY# | USER#{id} | MONTHLY_SUMMARY#{YYYY-MM} | 既存（carryover_amount, bonus_amount, total_budget, remaining フィールド追加） |
| REWARD_POOL# | USER#{id} | REWARD_POOL# | 既存 |
| REWARD_SUGGESTION# | USER#{id} | REWARD_SUGGESTION#{ISO8601} | 既存 |
| EXPENSE# | USER#{id} | EXPENSE#{ISO8601} | 既存（読み取りのみ） |

**スキーマ変更の後方互換性**: 追加フィールドはすべてデフォルト値あり（0 または 0.5）。既存の MONTHLY_SUMMARY アイテムには `total_budget` がないが、`get_last_month_remaining()` で `item.get("total_budget") or item.get("reward_budget") or 0` とフォールバックするため互換性を維持。

---

## 3. template.yaml への変更

Unit 5 は新規 Lambda 関数を追加しない。以下の環境変数のみ追加（`WebhookHandlerFunction` または `RewardProposalFunction` として分離する場合に備えて記載）:

```yaml
# WebhookHandlerFunction 既存 Environment.Variables に追加
PROPOSAL_MAX_CANDIDATES: "5"
```

`PROPOSAL_MAX_CANDIDATES` は `reward_proposal.py` で `os.environ.get()` で取得済みのため、未設定でもデフォルト値 5 が使用される。明示的に設定することで本番チューニングが容易になる。

---

## 4. IAM ポリシー

Unit 5 の追加アクセスパターンは既存の `ArsLambdaRole` でカバー済み:

| アクセス | リソース | 既存 Policy |
|---|---|---|
| `dynamodb:GetItem` | ArsTable | ARS-DynamoDB-Policy に含む |
| `dynamodb:PutItem` | ArsTable | ARS-DynamoDB-Policy に含む |
| `dynamodb:Query` | ArsTable | ARS-DynamoDB-Policy に含む |
| `bedrock:InvokeModel` | Nova Micro | ARS-Bedrock-Policy に含む |

追加 IAM 変更は不要。

---

## 5. Secrets Manager

Unit 5 で新規シークレット追加なし。既存シークレットを参照:

| シークレット | 用途 |
|---|---|
| `ars/line` | LINE Reply API トークン |
| `ars/google` | Google Calendar OAuth（連携済みユーザーのみ） |

---

## 6. デプロイ判断

Unit 3〜5 まとめデプロイ（Deploy Round 4）を予定。Unit 5 単独でのインフラ変更はないため、コードデプロイのみ。

**確認手順**（Deploy Round 4 で実施）:
1. LINE で「疲れた」→ ご褒美提案が返ってくることを確認
2. LINE で「プリン買った 320円」→ 支出記録 → 「ご褒美おすすめして」→ 余裕額内の候補が提案されることを確認
3. CloudWatch Logs で `carryover_amount`, `total_budget` のログを確認
