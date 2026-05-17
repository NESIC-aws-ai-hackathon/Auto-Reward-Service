# ビジネスロジックモデル — Unit 5: ご褒美提案 + 繰り越し機能

**Unit**: Unit 5 — ご褒美提案（F6 対応）+ 繰り越し機能（F2-07）  
**作成日**: 2026-05-16  
**対応要件**: F6-01〜F6-06、F2-07

---

## 1. 主要フロー

### 1-A: ご褒美提案フロー（スライス 5-1〜5-8）

```
LINE ユーザーメッセージ（意図: REWARD_PROPOSAL）
  │
  └─► reward_proposal.propose_reward(user_id, text, ddb, tone, emotion, fatigue_level)
         │
         ├─[1] プロファイル取得
         │       DynamoDB.get_item(PK=USER#{id}, SK=PROFILE#) → profile dict
         │
         ├─[2] 余裕額算出（スライス 5-1）with 繰り越し（F2-07）
         │       │
         │       ├─ get_reward_budget(profile)  → base_budget (Decimal)
         │       ├─ get_last_month_remaining(user_id, ddb) → last_remaining (int)
         │       │      └─ MONTHLY_SUMMARY#{先月YYYY-MM} を GetItem
         │       │             → total_budget - total_amount = remaining
         │       │             → MonthlyExpenseSummary が存在しない場合 → 0
         │       ├─ calculate_monthly_budget(base_budget, last_remaining, carryover_rate)
         │       │      → carryover = min(last_remaining × 0.5, base_budget)
         │       │      → total_budget = base_budget + carryover + bonus_amount
         │       └─ get_monthly_spending(user_id, ddb)  → spending (Decimal)
         │              slack = max(total_budget − spending, 0)
         │
         ├─[3] 余裕額 ≤ 0 → やんわり止め返信（スライス 5-5）
         │       build_stop_reply(tone) を返して終了
         │
         ├─[4] ご褒美候補プール取得（スライス 5-2）
         │       DynamoDB.get_item(PK=USER#{id}, SK=REWARD_POOL#)
         │       → List[RewardPoolItem] に変換
         │
         ├─[5] 余裕額内で絞り込み（スライス 5-3）
         │       price <= slack のアイテムをスコア降順で最大 5 件に絞り込み
         │       → candidates が空 → フォールバックメッセージを返して終了
         │
         ├─[6] Google Calendar コンテキスト取得（スライス 5-8）
         │       GoogleCalendarService.is_connected(user_id) が True の場合のみ
         │       → get_today_events(user_id) → イベントのサマリー（最大3件）を文字列化
         │       失敗時: 警告ログのみ（calendar_context = None で続行）
         │
         ├─[7] プロンプト構築・Bedrock 呼び出し（スライス 5-4）
         │       build_reward_proposal_prompt(user_message, slack, candidates,
         │                                    emotion, fatigue_level, calendar_context, tone)
         │       → BedrockService.invoke_text(prompt, system, max_tokens=500, temp=0.8)
         │       Bedrock 失敗時: フォールバックメッセージを返して終了
         │
         └─[8] 提案履歴保存（スライス 5-6）
                 DynamoDB.put_item(PK=USER#{id}, SK=REWARD_SUGGESTION#{ISO8601}, ...)
                 失敗時: 警告ログのみ（処理継続）
```

---

### 1-B: 繰り越し予算算出フロー（F2-07）

```
calculate_monthly_budget(base_budget, last_month_remaining, bonus_amount, carryover_rate)
  │
  ├─[1] carryover = min(last_month_remaining × carryover_rate, base_budget)
  │       carryover = max(carryover, 0)  # マイナス防止
  │
  ├─[2] total_budget = base_budget + carryover + bonus_amount
  │
  └─[3] 返却: {
            "base_budget":      base_budget,
            "carryover_amount": carryover,
            "bonus_amount":     bonus_amount,
            "total_budget":     total_budget,
          }
```

**計算例**

| ケース | 基本枠 | 先月残 | ボーナス | 繰り越し | 総予算 |
|---|---|---|---|---|---|
| 通常月 | 20,000 | 8,000 | 0 | 4,000 | 24,000 |
| ボーナス月 | 20,000 | 8,000 | 30,000 | 4,000 | 54,000 |
| 先月使い切り | 20,000 | 0 | 0 | 0 | 20,000 |
| 繰り越し上限 | 20,000 | 50,000 | 0 | 20,000 | 40,000 |

---

### 1-C: 先月残額取得フロー（F2-07）

```
get_last_month_remaining(user_id, ddb)
  │
  ├─[1] 先月の YYYY-MM を算出（当月1日 - 1日 → 先月末日 → strftime）
  │
  ├─[2] DynamoDB.get_item(PK=USER#{id}, SK=MONTHLY_SUMMARY#{先月YYYY-MM})
  │       → item が None → 0 を返す（初回利用・新規ユーザー）
  │
  ├─[3] total_budget = item["total_budget"] または item["reward_budget"] または 0
  │       total_amount = item["total_amount"] または 0
  │
  ├─[4] remaining = max(int(total_budget - total_amount), 0)
  │       マイナス（超過支出月）は 0 にクランプ
  │
  └─[5] 返却: remaining (int)
             DDB エラー時は 0 を返す（処理継続）
```

---

### 1-D: スコア調整フロー（スライス 4-5、Unit 5 から呼び出し）

```
reward_pool_service.adjust_score(user_pk, item_id, outcome)
  │
  ├─[1] DynamoDB から REWARD_POOL# を取得
  ├─[2] item_id に一致するアイテムを検索
  ├─[3] スコア補正:
  │       outcome == "bought" → score += 0.15（clamp 0〜1）
  │       outcome == "skip"   → score -= 0.10（clamp 0〜1）
  └─[4] DynamoDB に更新済みプールを put_item
```

---

## 2. 制御フロー詳細

### 余裕額 0 判定（スライス 5-5）

```
slack <= 0 の場合:
  → 提案履歴に "stopped" として保存（item_id/name/price は None）
  → build_stop_reply(tone) で口調に合わせたやんわり止めメッセージを返す
  → Bedrock は呼ばない（コスト節約）
```

### フォールバック判定（候補なし）

```
candidates == [] の場合:
  → _FALLBACK_NO_ITEMS[tone] を返す
  → 提案履歴への保存は行わない
```

### Bedrock 失敗時

```
BedrockError 発生時:
  → _FALLBACK_BEDROCK[tone] を返す
  → 提案履歴は保存済み（item の情報は記録される）
```
