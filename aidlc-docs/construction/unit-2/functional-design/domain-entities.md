# ドメインエンティティ定義 — Unit 2: リワードちゃんキャラクター

**Unit**: Unit 2 — LINE Bot会話  
**作成日**: 2026-05-16  
**対応要件**: F2-01〜F2-06, F3-01〜F3-05

---

## エンティティ一覧

### 1. IntentClassificationResult

Intent 分類の出力結果。

| フィールド | 型 | 説明 |
|---|---|---|
| `intent` | `IntentType` | 分類されたIntent種別 |
| `confidence` | `float` | 信頼度スコア (0.0〜1.0) |
| `raw_text` | `str` | 入力テキスト |

**IntentType 列挙値:**

| 値 | 意味 |
|---|---|
| `EXPENSE` | 支出記録（「プリン買った」等） |
| `REWARD` | ご褒美要求（「ご褒美が欲しい」「疲れた」等） |
| `GREET` | 挨拶（「こんにちは」「おはよう」等） |
| `CHAT` | 雑談・一般会話 |
| `ONBOARDING` | 初回登録開始意図（「はじめる」「登録したい」等） |
| `CONFIRM_YES` | 確認への肯定回答（「はい」「うん」「OK」等） |
| `CONFIRM_NO` | 確認への否定回答（「いいえ」「やめる」「ちがう」等） |
| `UNKNOWN` | 分類不能 → character_reply に渡して雑談対応 |

---

### 2. EmotionState

感情・疲労度の推定結果（スライス 2-3）。

| フィールド | 型 | 説明 |
|---|---|---|
| `emotion` | `str` | 推定感情: `positive` / `neutral` / `negative` |
| `fatigue_level` | `int` | 疲労度: 0（元気）〜5（疲弊） |
| `inferred_from` | `str` | 推定元テキスト（ログ用） |

**疲労度判定基準:**

| fatigue_level | トリガーワード例 | 応答トーン |
|---|---|---|
| 0〜1 | なし / 「楽しい」「最高」 | 通常の friendly |
| 2〜3 | 「ちょっと疲れた」「眠い」 | 労い寄り (friendly) |
| 4〜5 | 「もう限界」「つらい」「死にそう」 | 共感優先 (polite) |

---

### 3. OnboardingState

オンボーディング進行状態（DynamoDB 保存）。

| フィールド | 型 | 説明 |
|---|---|---|
| `step` | `OnboardingStep` | 現在のステップ |
| `collected_data` | `dict` | 収集済みデータの中間保存 |
| `started_at` | `str` | ISO8601 開始日時 |

**OnboardingStep 列挙値:**

| ステップ | 収集情報 |
|---|---|
| `WAITING_INCOME` | 月収入力待ち |
| `WAITING_FIXED_COSTS` | 固定費入力待ち |
| `CONFIRM_REWARD_BUDGET` | ご褒美枠提示・確認中 |
| `WAITING_BONUS` | ボーナス情報入力待ち (Should) |
| `WAITING_BIRTHDAY` | 誕生日入力待ち (Should) |
| `COMPLETED` | オンボーディング完了 |

**DynamoDB スキーマ:**
- `PK`: `USER#{line_user_id}`
- `SK`: `ONBOARDING_STATE`

---

### 4. ChatLogEntry

会話ログエントリ（DynamoDB 保存、TTL 30日）。

| フィールド | 型 | 説明 |
|---|---|---|
| `line_user_id` | `str` | LINE ユーザーID |
| `timestamp` | `str` | ISO8601 タイムスタンプ |
| `role` | `str` | `user` / `assistant` |
| `content` | `str` | メッセージ内容（PII マスク済み） |
| `intent` | `str` | 分類されたIntent |
| `ttl` | `int` | Unix タイムスタンプ（30日後） |

**DynamoDB スキーマ:**
- `PK`: `USER#{line_user_id}`
- `SK`: `CHAT#{ISO8601_timestamp}`（例: `CHAT#2026-05-16T07:50:00.000Z`）
- `TTL`: `ttl` 属性（DynamoDB TTL 設定済み）

---

### 5. PrefMemoryEntry

嗜好記憶エントリ（DynamoDB 保存）。

| フィールド | 型 | 説明 |
|---|---|---|
| `category` | `str` | 嗜好カテゴリ（`food` / `hobby` / `place` / `item` / `other`） |
| `keyword` | `str` | 嗜好キーワード（例: 「チョコレート」） |
| `sentiment` | `str` | `positive` / `negative` |
| `detected_at` | `str` | ISO8601 検出日時 |
| `source_text` | `str` | 検出元テキスト（デバッグ用） |

**DynamoDB スキーマ:**
- `PK`: `USER#{line_user_id}`
- `SK`: `PREF_MEMORY#{category}#{keyword}`

---

### 6. AnniversaryEntry

記念日エントリ（PROFILE.anniversaries フィールドに保存）。

| フィールド | 型 | 説明 |
|---|---|---|
| `name` | `str` | 記念日名（例: 「結婚記念日」） |
| `date` | `str` | `MM-DD` 形式（例: `06-15`） |
| `detected_at` | `str` | ISO8601 検出日時 |

---

### 7. CharacterReplyContext

character_reply.py へ渡すコンテキスト集約オブジェクト。

| フィールド | 型 | 説明 |
|---|---|---|
| `user_message` | `str` | ユーザーのメッセージ |
| `intent` | `IntentType` | 分類済みIntent |
| `emotion` | `EmotionState` | 推定感情状態 |
| `tone` | `str` | 口調設定（Unit 2 では `friendly` 固定） |
| `recent_chat_log` | `list[ChatLogEntry]` | 直近 5 件の会話ログ |
| `user_profile` | `dict \| None` | ユーザープロフィール（未登録は None） |
