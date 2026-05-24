# U8-D 機能設計書: ストレス判定 + 回復提案

## 概要

会話Transcript分析からストレスレベルを判定し、段階的な回復提案を行う。
0円回復案を優先し、「広告アプリ化」を避ける。

---

## 機能一覧

| ID | 機能名 | 説明 |
|----|--------|------|
| FD-D01 | ストレス判定 | 会話内容からストレスレベル（1〜5）を判定し保存 |
| FD-D02 | 0円回復案生成 | ストレスレベルに基づき無料で実践できる回復案を生成 |
| FD-D03 | 有料回復案生成 | 余剰額内での有料ご褒美案を生成（MVP: ルールベース） |
| FD-D04 | 口調変換 | 回復案をふれまーるちゃん口調に変換 |
| FD-D05 | 回復案API | GET /api/recovery — 最新の回復案を取得 |
| FD-D06 | permit/skip記録 | POST /api/recovery/permit, /api/recovery/skip |
| FD-D07 | RecoveryView | 回復案カードUI（段階的誘導） |

---

## FD-D01: ストレス判定

### 処理フロー
1. `analysis_handler` がセッション終了時に `assess_stress()` を呼び出し
2. 会話全体（session turns）をClaude Sonnetに送信
3. 以下を判定:
   - `stress_level`: 1〜5（1=リラックス、5=非常に高い）
   - `factors`: ストレス要因リスト
   - `positive_factors`: ポジティブ要因リスト
4. `STRESS_SUMMARY#{date}` として保存（同日は上書き = 最新会話が反映）

### LLMプロンプト（ストレス判定）
```
会話からユーザーのストレスレベルと要因を判定してください。
stress_level: 1（リラックス）〜 5（非常に高い）
factors: ストレスの原因（リスト）
positive_factors: ポジティブな要因（リスト）
mood: 全体的な気分（1語）
```

### DynamoDB Item
```
PK: USER#{user_id}
SK: STRESS_SUMMARY#{date}
stress_level: 3
factors: ["仕事の締め切り", "睡眠不足"]
positive_factors: ["ランチが美味しかった"]
mood: "疲れ"
session_id: "sess-xxx"
created_at: ISO8601
```

---

## FD-D02: 0円回復案生成

### ロジック
ストレスレベルに応じてカテゴリからランダム選択 + LLMで口調変換:

| レベル | 回復案カテゴリ |
|--------|---------------|
| 1-2 | 軽い気分転換（散歩、好きな音楽、ストレッチ） |
| 3 | 中程度の回復（深呼吸5分、短い瞑想、温かい飲み物） |
| 4-5 | しっかり回復（入浴、早めの就寝、信頼できる人に話す） |

### 0円回復案マスター
```python
FREE_RECOVERY_OPTIONS = {
    "light": [
        "好きな音楽を1曲聴く",
        "窓を開けて深呼吸する",
        "5分だけ外を散歩する",
        "軽いストレッチをする",
        "好きな香りを嗅ぐ",
    ],
    "moderate": [
        "5分間の深呼吸エクササイズ",
        "温かい飲み物をゆっくり飲む",
        "3分間の瞑想",
        "好きな動画を1本見る",
        "明日やることを3つだけ書き出す",
    ],
    "strong": [
        "ゆっくりお風呂に浸かる",
        "今日は早めに寝る",
        "信頼できる人に少し話す",
        "好きな場所の写真を眺める",
        "何もしない10分を作る",
    ],
}
```

---

## FD-D03: 有料回復案生成（MVP）

MVP段階ではルールベースで簡易生成:
- 余剰額（月の甘やかし枠残り）を確認
- 残額 > 0 の場合のみ有料案を表示
- カテゴリ: コンビニスイーツ、カフェ、お取り寄せ

> **将来**: 楽天API/ホットペッパーAPI連携はU8では実装しない（既存U4-U5で実装済み）

---

## FD-D04: 口調変換

BedrockClientを使い、回復案テキストをふれまーるちゃんの口調に変換:
- 「〜だよ」「〜してみない？」「がんばってる{display_name}へ」
- 押しつけがましくない、共感ベースの語り口

---

## FD-D05: 回復案API

### GET /api/recovery
```json
// Response
{
  "stress_level": 3,
  "mood": "疲れ",
  "free_recovery": [
    {
      "id": "fr-001",
      "text": "5分間の深呼吸エクササイズしてみない？ゆっくり息を吸って、ふぅーって吐くだけでも違うんだよ♪",
      "category": "moderate"
    }
  ],
  "paid_recovery": [
    {
      "id": "pr-001",
      "text": "今日がんばった{display_name}には、コンビニで好きなスイーツ1個どう？自分へのご褒美だよ♪",
      "category": "sweets",
      "budget_hint": "〜500円"
    }
  ],
  "message": "今日もおつかれさま。ちょっと疲れてるみたいだね..."
}
```

### POST /api/recovery/permit
ユーザーが回復案を「やってみる」と選択した記録。
```json
// Request
{ "recovery_id": "fr-001", "type": "free" }
// Response
{ "message": "recorded", "reward_permit_id": "rp-xxx" }
```

### POST /api/recovery/skip
ユーザーが「今日はいいや」とスキップした記録。
```json
// Request
{ "reason": "もう寝る" }
// Response
{ "message": "recorded" }
```

---

## FD-D07: RecoveryView

### UI構成
1. **共感メッセージ**: ふれまーるちゃんの一言（ストレスレベルに応じて変化）
2. **0円回復カード**: 2-3枚のカード表示（スワイプ可能）
3. **有料回復カード**: 余剰枠がある場合のみ表示（1-2枚）
4. **アクションボタン**: 「やってみる」「今日はいいや」

### 状態管理
- ローディング中: スケルトン表示
- データなし（ストレス未判定）: 「まだ今日の判定がないよ。話しかけてね♪」
- 回復案表示中: カード一覧
- 実行済み: 「えらい！お疲れ様♪」

---

## データフロー

```
VoiceSession終了
  → SQS → AnalysisHandler
    → process_conversation() [既存: U8-C]
    → assess_stress() [U8-D新規]
      → STRESS_SUMMARY#{date} 保存
      → Push通知（ストレスレベル3以上）

GET /api/recovery
  → STRESS_SUMMARY#{date} 取得
  → RecoveryProvider.generate()
    → 0円回復案選択
    → 有料回復案生成（残額確認）
    → ふれまーるちゃん口調変換
  → Response
```
