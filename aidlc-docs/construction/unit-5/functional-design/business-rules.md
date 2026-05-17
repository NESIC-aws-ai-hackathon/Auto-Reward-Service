# ビジネスルール — Unit 5: ご褒美提案 + 繰り越し機能

**Unit**: Unit 5 — ご褒美提案（F6 対応）+ 繰り越し機能（F2-07）  
**作成日**: 2026-05-16

---

## 1. 予算・余裕額ルール

| ID | ルール | 実装箇所 |
|---|---|---|
| BR-5-01 | `reward_budget_monthly` 未設定時は DEFAULT_REWARD_BUDGET=5,000 円を使用 | `get_reward_budget()` |
| BR-5-02 | ボーナス月は `bonus_amount × 10%` をご褒美枠に加算 | `get_reward_budget()` |
| BR-5-03 | 余裕額は常に 0 以上（下限クランプ） | `calculate_slack()` |
| BR-5-04 | 余裕額 = max(total_budget − 今月支出合計, 0) | `calculate_slack()` |

---

## 2. 繰り越しルール（F2-07）

| ID | ルール | 値 | 実装箇所 |
|---|---|---|---|
| BR-5-05 | 繰り越し率デフォルト 50% | `CARRYOVER_RATE = 0.5` | `finance_engine.py` |
| BR-5-06 | 繰り越し上限 = 基本枠と同額（100%） | `min(carryover, base_budget)` | `calculate_monthly_budget()` |
| BR-5-07 | 繰り越し対象 = 前月の未使用額（total_budget − total_amount） | — | `get_last_month_remaining()` |
| BR-5-08 | 先月の MonthlyExpenseSummary が存在しない場合、繰り越し = 0 | item が None → 0 | `get_last_month_remaining()` |
| BR-5-09 | 繰り越し額がマイナスになる場合（超過支出月翌月）、繰り越し = 0 | `max(carryover, 0)` | `calculate_monthly_budget()` |
| BR-5-10 | 繰り越し率は `UserProfile.carryover_rate` で管理（デフォルト 0.5） | — | `calculate_slack()` |
| BR-5-11 | ボーナス月との併用可（carryover + bonus を両方加算） | `total = base + carryover + bonus` | `calculate_monthly_budget()` |

---

## 3. 提案ルール

| ID | ルール | 実装箇所 |
|---|---|---|
| BR-5-12 | 余裕額 ≤ 0 の場合、ご褒美提案を止める（やんわり止めメッセージ） | `propose_reward()` スライス 5-5 |
| BR-5-13 | 候補は `price ≤ slack` のアイテムのみ対象 | `_filter_candidates()` |
| BR-5-14 | 候補はスコア降順で最大 `PROPOSAL_MAX_CANDIDATES`（デフォルト 5）件 | `_filter_candidates()` |
| BR-5-15 | 候補が 0 件の場合、フォールバックメッセージを返す（Bedrock 呼び出しなし） | `propose_reward()` |
| BR-5-16 | 提案は口調（friendly / polite / devilish）に応じてメッセージを生成 | `build_reward_proposal_prompt()` |
| BR-5-17 | 感情・疲労度をプロンプトに注入して共感度を高める | `build_reward_proposal_prompt()` |
| BR-5-18 | Google Calendar 連携済みユーザーは今日の予定をコンテキストに追加（スライス 5-8） | `propose_reward()` |
| BR-5-19 | カレンダーコンテキストはイベントのサマリー（タイトル）のみ。内容・参加者・場所は含めない（SEC-08） | `_build_calendar_context()` |

---

## 4. 提案履歴ルール

| ID | ルール | 実装箇所 |
|---|---|---|
| BR-5-20 | 提案結果は常に REWARD_SUGGESTION# に保存（停止・フォールバック含む） | `_save_suggestion()` |
| BR-5-21 | 提案履歴保存失敗は WARNING ログのみ（処理継続） | `_save_suggestion()` |
| BR-5-22 | 提案に対して "bought" の場合 score += 0.15（上限 1.0） | `adjust_score()` |
| BR-5-23 | 提案に対して "skip" の場合 score -= 0.10（下限 0.0） | `adjust_score()` |

---

## 5. エラーハンドリングルール

| ID | ルール | 実装箇所 |
|---|---|---|
| BR-5-24 | DynamoDB エラー時の今月支出は 0 円として扱う（余裕額 = 予算全額） | `get_monthly_spending()` |
| BR-5-25 | 先月サマリー取得エラー時の繰り越しは 0 として扱う | `get_last_month_remaining()` |
| BR-5-26 | Bedrock エラー時はフォールバックメッセージを返す（例外は上位に伝播しない） | `propose_reward()` |
| BR-5-27 | Google Calendar エラーは WARNING ログのみ（提案処理は継続） | `propose_reward()` |
