# NFR 設計 — Unit 5: ご褒美提案 + 繰り越し機能

**Unit**: Unit 5 — ご褒美提案（F6 対応）+ 繰り越し機能（F2-07）  
**作成日**: 2026-05-16

---

## 1. パフォーマンス設計

### DynamoDB アクセス最適化

Unit 5 の propose_reward() は最大 4 回の DynamoDB アクセスを行う。

| # | アクセス | 方式 | 説明 |
|---|---|---|---|
| 1 | PROFILE# | GetItem（PK+SK） | プロビジョニング済み読み取り ≤ 10 ms |
| 2 | MONTHLY_SUMMARY#{先月} | GetItem（PK+SK） | 繰り越し計算用（F2-07）|
| 3 | REWARD_POOL# | GetItem（PK+SK） | 候補プール取得 |
| 4 | EXPENSE#{今月}... | Query（SK前方一致） | 今月支出集計 |

アクセス 1・2・3 は独立しているため、将来的に `asyncio` + `aioboto3` で並列化可能。現時点ではシリアル実行（Lambda concurrency 100 以下のハッカソンスコープでは十分）。

### Bedrock レイテンシ管理

- モデル: Nova Micro（最速・低コスト）
- `max_tokens=500`（提案文の最大長）
- `temperature=0.8`（多様性確保）
- タイムアウト: boto3 デフォルト（60 秒）— LINE 5 秒タイムアウトはカバー済み（Reply API 非同期的利用）

---

## 2. セキュリティ設計

### SEC-08 カレンダーコンテキスト情報最小化

```python
def _build_calendar_context(events: list[dict]) -> Optional[str]:
    # event["summary"]（タイトル）のみ取得
    # event["description"], ["attendees"], ["location"] は取得しない
    summaries = [e.get("summary") for e in events[:3] if e.get("summary")]
    return "今日の予定: " + "、".join(summaries) if summaries else None
```

### Bedrock プロンプトの個人情報除外

`build_reward_proposal_prompt()` に渡す情報:
- 許可: user_message（ユーザーの発言）、slack（余裕額）、candidates（商品リスト）、emotion、fatigue_level、calendar_context（タイトルのみ）、tone
- 禁止: ユーザー ID、氏名、住所、LINE プロフィール画像 URL、メールアドレス

---

## 3. 信頼性設計

### エラーハンドリング階層

```
propose_reward()
  ├─ DynamoDB (profile/pool/summary) エラー → WARNING ログ、デフォルト値で継続
  ├─ get_monthly_spending() エラー       → WARNING ログ、spending=0 で継続
  ├─ get_last_month_remaining() エラー   → WARNING ログ、remaining=0 で継続
  ├─ GoogleCalendar エラー               → WARNING ログ、context=None で継続
  └─ BedrockError                        → WARNING ログ、フォールバックメッセージ返却
```

### フォールバックメッセージ設計

フォールバックは 3 口調 × 2 理由（候補なし / Bedrock 失敗）= 6 パターン。  
`_FALLBACK_NO_ITEMS` と `_FALLBACK_BEDROCK` の 2 dict で管理。

---

## 4. 繰り越しロジックの堅牢性設計

### 境界値処理

| 入力状態 | 処理 |
|---|---|
| `last_month_remaining < 0`（超過支出） | `max(carryover, 0)` でクランプ → 繰り越し 0 |
| `last_month_remaining` 非常に大きい | `min(carryover, base_budget)` で上限適用 |
| `base_budget = 0`（予算未設定のデフォルト） | 繰り越し上限も 0 → 繰り越し 0 |
| `carryover_rate = 0`（繰り越し無効設定） | 繰り越し 0 → 基本枠のみ |
| `bonus_amount < 0`（想定外の負値） | 呼び出し側で 0 に正規化 |

### 型安全性

`calculate_monthly_budget()` の引数は `int` を期待するが、`get_reward_budget()` が返す `Decimal` をそのまま渡すとオーバーフローの可能性はない。ただし `int()` でキャストしてから渡す（`calculate_slack()` 内で変換）。
