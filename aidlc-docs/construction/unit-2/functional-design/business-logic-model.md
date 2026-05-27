# ビジネスロジックモデル — Unit 2: リワードちゃんキャラクター

**Unit**: Unit 2 — LINE Bot会話  
**作成日**: 2026-05-16

---

## 主要ビジネスプロセス

### プロセス 1: メッセージ処理メインフロー

```
webhook_handler.py (テキストメッセージ受信)
  │
  ├─① intent_classifier.handle(text, line_user_id)
  │      └─ Nova Micro でIntent分類 → IntentClassificationResult
  │
  ├─② _infer_emotion(text) → EmotionState
  │
  ├─③ ルーティング分岐
  │      ├─ ONBOARDING → onboarding_flow.handle(event, state)
  │      ├─ GREET (未登録ユーザー) → onboarding_flow.start(event)
  │      ├─ GREET (登録済み) → character_reply.handle(context)
  │      ├─ EXPENSE → [Unit 3 に委譲。Unit 2 では CHAT 扱いのフォールバック]
  │      ├─ REWARD → [Unit 5 に委譲。Unit 2 では CHAT 扱いのフォールバック]
  │      ├─ CONFIRM_YES / CONFIRM_NO → onboarding_flow.handle（オンボーディング中の場合）
  │      ├─ CHAT / UNKNOWN → character_reply.handle(context)
  │      └─ image メッセージ → [Unit 3 に委譲。Unit 2 では「画像が届いたよ〜」固定返答]
  │
  ├─④ CHAT ログ保存（全メッセージ対象）
  │      └─ dynamodb_service.put_item(CHAT#{timestamp})
  │
  └─⑤ PREF_MEMORY / 記念日 自動検出（character_reply 後に非同期的に実施）
         └─ _detect_preferences(text, line_user_id)
         └─ _detect_anniversaries(text, line_user_id)
```

---

### プロセス 2: Intent 分類

**入力**: ユーザーテキスト  
**処理**: Nova Micro に intent_prompt.py のプロンプトを使用してリクエスト  
**出力**: `IntentClassificationResult`

```
intent_classifier.classify(text: str) -> IntentClassificationResult:
  1. intent_prompt.build_prompt(text) でプロンプト生成
  2. bedrock_service.invoke_text(prompt, model="nova-micro") 呼び出し
  3. JSON レスポンスをパース → { intent: str, confidence: float }
  4. confidence < 0.5 → UNKNOWN に強制
  5. IntentClassificationResult を返す
```

**UNKNOWN のフォールバック**: character_reply に渡し LLM が雑談として応答する（固定テンプレートなし）

---

### プロセス 3: キャラクター応答生成

**入力**: `CharacterReplyContext`  
**処理**: Nova Micro に character_prompts.py のプロンプトを使用してリクエスト  
**出力**: 返信テキスト（文字列）

```
character_reply.generate(ctx: CharacterReplyContext) -> str:
  1. 直近 5 件の CHAT ログを DynamoDB から取得（コンテキスト維持）
  2. character_prompts.build_prompt(ctx) でプロンプト生成
     - システムプロンプト: リワードちゃんキャラクター設定（tone=friendly 固定）
     - 感情状態を反映（fatigue_level に応じてトーン調整）
     - 直近 CHAT ログをコンテキストとして含める
  3. bedrock_service.invoke_text(prompt, model="nova-micro") 呼び出し
  4. 応答テキストを返す
```

**口調ガイドライン（friendly 固定）:**
- 語尾: 「〜だよ」「〜だね」「〜しよっか」
- 絵文字: 1〜2個/メッセージ（感情表現に使用）
- 長さ: 1〜3文程度（LINE に最適化）
- 疲労高時 (level 4-5): 労いフレーズを優先

---

### プロセス 4: オンボーディングフロー

**状態機械設計:**

```
[WAITING_INCOME]
  → ユーザーが金額を返答
  → LLM で月収を数値抽出
  → PROFILE.monthly_income 更新
  → 次のメッセージ「家賃とかスマホ代...は？」送信
  → 状態 → [WAITING_FIXED_COSTS]

[WAITING_FIXED_COSTS]
  → ユーザーが固定費を返答
  → LLM で固定費リストと合計を抽出
  → PROFILE.fixed_costs, FIXED_COSTS アイテム群を保存
  → ご褒美枠を算出（月収 - 固定費の 10〜20%、最低 3,000円）
  → 枠提示メッセージ送信
  → 状態 → [CONFIRM_REWARD_BUDGET]

[CONFIRM_REWARD_BUDGET]
  → CONFIRM_YES → 状態 → [WAITING_BONUS]
  → CONFIRM_NO または金額変更 → 再算出 or ユーザー指定値を採用
  → 状態 → [WAITING_BONUS]

[WAITING_BONUS]
  → 「ボーナスってある？」質問送信
  → ユーザーが回答
  → ある場合: LLM で月・金額抽出 → PROFILE.bonus_months, bonus_amount 保存
  → ない・スキップ: そのまま次へ
  → 状態 → [WAITING_BIRTHDAY]

[WAITING_BIRTHDAY]
  → 「ちなみに誕生日いつ？」質問送信
  → ユーザーが回答
  → 日付抽出（MM-DD 形式）→ PROFILE.birthday 保存
  → スキップ: そのまま次へ
  → 完了メッセージ送信
  → 状態 → [COMPLETED]
  → ONBOARDING_STATE アイテム削除（クリーンアップ）
```

**ご褒美枠算出ロジック:**
```
余剰 = monthly_income - sum(fixed_costs)
reward_budget = max(3000, min(余剰 * 0.15, 30000))
# 最低 3,000円、最高 30,000円、デフォルト 余剰の 15%
```

---

### プロセス 5: 感情・疲労度推定（_infer_emotion）

**入力**: ユーザーテキスト  
**処理**: ルールベースのキーワードマッチング  
**出力**: `EmotionState`

```python
FATIGUE_HIGH = ["もう限界", "つらい", "しんどい", "死にそう", "疲弊", "ヘトヘト"]
FATIGUE_MED  = ["疲れた", "眠い", "だるい", "やる気ない", "しんどめ"]
POSITIVE     = ["楽しい", "嬉しい", "最高", "幸せ", "ありがとう", "よかった"]

def _infer_emotion(text: str) -> EmotionState:
    if any(kw in text for kw in FATIGUE_HIGH):
        return EmotionState(emotion="negative", fatigue_level=4, ...)
    if any(kw in text for kw in FATIGUE_MED):
        return EmotionState(emotion="negative", fatigue_level=2, ...)
    if any(kw in text for kw in POSITIVE):
        return EmotionState(emotion="positive", fatigue_level=0, ...)
    return EmotionState(emotion="neutral", fatigue_level=0, ...)
```

---

### プロセス 6: PREF_MEMORY 自動蓄積

**入力**: ユーザーテキスト  
**処理**: キーワードマッチング + カテゴリ分類

```python
PREF_POSITIVE_PATTERNS = [
    (r"(.+)が好き", "positive"),
    (r"(.+)好きなんだ", "positive"),
    (r"(.+)が大好き", "positive"),
]
PREF_NEGATIVE_PATTERNS = [
    (r"(.+)が嫌い", "negative"),
    (r"(.+)苦手", "negative"),
    (r"(.+)は無理", "negative"),
]

def _detect_preferences(text: str, line_user_id: str):
    for pattern, sentiment in PREF_POSITIVE_PATTERNS + PREF_NEGATIVE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            keyword = match.group(1)
            category = _classify_pref_category(keyword)  # 簡易カテゴリ分類
            dynamodb_service.put_item(PrefMemoryEntry(...))
```

---

### プロセス 7: 記念日の自然収集（スライス 2-9）

**入力**: ユーザーテキスト  
**処理**: キーワードマッチング + 日付抽出

```python
ANNIVERSARY_PATTERNS = [
    r"(結婚記念日|付き合い記念日|誕生日|創業記念日|入学記念日).*?(\d{1,2})月(\d{1,2})日",
    r"来月(.+記念日)",  # → フォローアップ質問トリガー
]

def _detect_anniversaries(text: str, line_user_id: str):
    for pattern in ANNIVERSARY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            # 日付が取れた場合 → 直接保存
            # 日付が不足の場合 → フォローアップ質問を次のターンで返す
            ...
```

---

## CHAT ログ保存フロー

全てのメッセージ交換（ユーザー発言 + Bot 応答）を保存:

```
1. ユーザーメッセージ受信時:
   put_item(PK=USER#{id}, SK=CHAT#{now_iso}, role="user", content=text, intent=intent)

2. Bot 応答送信後:
   put_item(PK=USER#{id}, SK=CHAT#{now_iso}, role="assistant", content=reply_text)

3. TTL = int((datetime.now() + timedelta(days=30)).timestamp())
```

**注意**: PII マスク対象（logger.py の PII フィルタを通す）
