# Unit of Work 定義 — オートリワードサービス（v2）

**改訂日**: 2026-05-15 / コンセプト変更後版

## 実装サイクル方針（確定）

| 項目 | 決定内容 |
|------|---------|
| 実装粒度 | **機能スライス単位**（各 Unit の中の機能を小さく区切って実装） |
| 基盤 | **Unit 0 として最初のサイクルで実装**（SAMプロジェクト + DynamoDB + 共通Layer） |
| テスト | **コード生成と同じサイクル**（ユニットテスト + LLM品質テストを含める） |
| デプロイ | **AWS SAM**（`sam build && sam deploy`）で各Unitをデプロイ |

---

## プロジェクト コード構成方針

```
auto-reward-service/               ← SAM プロジェクトルート
├── src/
│   ├── handlers/
│   │   ├── webhook_handler.py     # Unit 1
│   │   ├── intent_classifier.py   # Unit 2
│   │   ├── character_reply.py     # Unit 2
│   │   ├── onboarding_flow.py     # Unit 2
│   │   ├── expense_extractor.py   # Unit 3
│   │   ├── receipt_analyzer.py    # Unit 3
│   │   ├── reward_pool_updater.py # Unit 4
│   │   ├── reward_proposal.py     # Unit 5
│   │   ├── push_notifier.py       # Unit 6
│   │   └── liff_api.py            # Unit 7
│   ├── services/
│   │   ├── dynamodb_service.py    # Unit 0
│   │   ├── bedrock_service.py     # Unit 0
│   │   ├── line_service.py        # Unit 0
│   │   ├── rakuten_service.py     # Unit 4
│   │   ├── google_calendar_service.py # Unit 0
│   │   ├── finance_engine.py      # Unit 5
│   │   └── reward_pool_service.py # Unit 4/5
│   ├── models/
│   │   └── schemas.py             # Unit 0
│   ├── prompts/
│   │   ├── intent_prompt.py       # Unit 2
│   │   ├── expense_prompt.py      # Unit 3
│   │   ├── character_prompts.py   # Unit 2
│   │   └── receipt_prompt.py      # Unit 3
│   └── utils/
│       ├── secrets.py             # Unit 0
│       └── logger.py              # Unit 0
├── tests/
│   ├── unit/
│   ├── integration/
│   └── llm/                       # LLM応答品質テスト
├── template.yaml                  # AWS SAM テンプレート
├── samconfig.toml
├── requirements.txt
├── requirements-dev.txt
└── Makefile
```

---

## Unit 一覧

### Unit 0: SAM基盤 + 共通Layer

**最初のサイクルで実装（先行必須）**

| 内容 | 詳細 |
|------|------|
| **スコープ** | SAMプロジェクト初期化、DynamoDBテーブル定義、共通Layerモジュール |
| **成果物** | `template.yaml`（骨格）, `dynamodb_service.py`, `bedrock_service.py`, `line_service.py`, `google_calendar_service.py`, `schemas.py`, `secrets.py`, `logger.py` |
| **完了条件** | `sam deploy` でDynamoDBテーブル作成成功; 共通Layerが各Lambdaからimportできる |

**機能スライス:**

| スライス | 内容 |
|---------|------|
| 0-1 | SAMプロジェクト初期化・`template.yaml`骨格・`samconfig.toml`・`Makefile` |
| 0-2 | `schemas.py`: DynamoDBスキーマ定数・Pydanticモデル定義 |
| 0-3 | `dynamodb_service.py`: put/get/query/update共通操作 |
| 0-4 | `bedrock_service.py`: Bedrockテキスト/画像呼び出し共通（モデルID設定ファイル化） |
| 0-5 | `line_service.py`: Reply/Push/署名検証/Content API |
| 0-6 | `secrets.py`: Secrets Manager/SSM取得ユーティリティ |
| 0-7 | `logger.py`: 構造化ログ（PII出力禁止） |
| 0-8 | DynamoDB `ArsTable` SAMリソース定義（PK/SK + GSI） |
| 0-9 | `google_calendar_service.py`: Google Calendar API連携（OAuth token管理 + イベント取得）。`GOOGLE_OAUTH#` SKスキーマ定義。カレンダーデータはDDBに保存しない（毎回フェッチ）。ログにカレンダー内容を出力しない |

---

### Unit 1: LINE Bot基盤（F1対応）

**対応要件**: F1-01〜F1-04

| 内容 | 詳細 |
|------|------|
| **スコープ** | Webhook受信・署名検証・メッセージルーティング |
| **依存** | Unit 0 |
| **完了条件** | LINE Webhookが受信できる; テキスト/画像/その他を正しくルーティングできる |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 1-1 | `webhook_handler.py`: API Gateway Lambda統合・LINEイベント受信 | F1-01 |
| 1-2 | 署名検証（`X-Line-Signature`検証）・失敗時403返却 | F1-01 |
| 1-3 | Message Router（text/image/sticker分岐）+ 各Lambdaへのルーティング | F1-02 |
| 1-4 | Reply送信（line_service）・エラー時フォールバック | F1-03 |
| 1-5 | SAMテンプレートに WebhookHandlerFunction + WebhookApi 追加 | — |
| 1-6 | Webhook署名検証のセキュリティテスト | SEC-01 |

---

### Unit 2: LINE Bot会話（F2/F3対応）— 更新版

**対応要件**: F2-01〜F2-06, F3-01〜F3-05

| 内容 | 詳細 |
|------|------|
| **スコープ** | キャラクター会話・Intent分類・オンボーディング（収入/固定費/ボーナス/誕生日/記念日） |
| **依存** | Unit 0, Unit 1 |
| **完了条件** | 「疲れた」でリワードちゃん口調の応答; オンボーディングで月収・固定費・ボーナス・誕生日を登録できる |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 2-1 | `intent_prompt.py` + `intent_classifier.py`: テキスト→Intent分類（Nova Micro）。Intent種別: EXPENSE / REWARD / GREET / CHAT / ONBOARDING / CONFIRM_YES / CONFIRM_NO / UNKNOWN | F3-01 |
| 2-2 | `character_prompts.py` + `character_reply.py`: Intent別のキャラクター応答生成（Nova Micro）。口調: friendly / polite / devilish。直近CHATログ参照によるコンテキスト維持 | F3-02, F3-03 |
| 2-3 | 感情・疲労度の間接推定（`_infer_emotion`）。チャット内容から emotion / fatigue_level を推定し、応答トーンに反映 | F3-04 |
| 2-4 | `onboarding_flow.py`: 初回登録チャットフロー。以下を段階的に収集: | F2-01〜F2-06 |
|       | **【Must: 初回で必ず聞く（3ステップ）】** | |
|       | ① 月収（手取り概算） | F2-02 |
|       | ② 固定費（家賃・通信費・サブスク等） | F2-03 |
|       | ③ ご褒美枠提示（月収 - 固定費 から算出） | F2-04 |
|       | **【Should: 初回でさらっと聞く】** | |
|       | ④ ボーナス月・金額（「ボーナスってある？何月にどれくらい？」） | F2-05 |
|       | ⑤ 誕生日（「ちなみに誕生日いつ？覚えておきたいな〜🎂」） | F2-06 |
|       | DynamoDB保存: PROFILE（月収/固定費/ご褒美枠/ボーナス/誕生日）/ FIXED_COSTS | |
| 2-5 | DynamoDB CHAT#{timestamp} 保存（会話ログ）。TTL 30日 | F3-05 |
| 2-6 | webhook_handler.py ルーティング統合（Intent別に各ハンドラーを呼び出し） | F1-02 |
| 2-7 | PREF_MEMORY 自動蓄積（会話中に「好き」「嫌い」等のキーワードから嗜好を抽出・保存） | F3-04 |
| 2-8 | LLM出力品質テスト（Intent分類精度 / キャラクター口調一貫性） | TEST-01 |
| 2-9 | 記念日の自然収集（会話中に「結婚記念日」「付き合って○年」等を検出 → PROFILE.anniversaries に保存）。PREF_MEMORY と同じパターンで会話から自然に拾う | F2-06 |

---

**対応要件 追加分:**

| 要件 ID | 内容 | 優先度 | 詳細 |
|--------|------|--------|------|
| F2-05 | ボーナス月・金額登録 | Should | オンボーディング時にボーナス支給月（例: 6月・12月）と概算額を聞く |
| F2-06 | 誕生日・記念日登録 | Should/Could | 誕生日はオンボーディングで聞く（Should）。記念日は会話から自然に拾う（Could） |

---

**schemas.py UserProfile 追加フィールド:**

```python
class UserProfile(BaseModel):
    # ... 既存フィールド（line_user_id, nickname, monthly_income, etc.） ...
    
    # ボーナス情報（F2-05）
    bonus_months: Optional[list[int]] = None      # [6, 12]
    bonus_amount: Optional[int] = None             # 1回あたりの概算額（円）
    
    # 誕生日・記念日（F2-06）
    birthday: Optional[str] = None                 # "MM-DD" 形式（年は聞かない）
    anniversaries: Optional[list[dict]] = None     # [{"name": "結婚記念日", "date": "06-15"}]
```

---

**オンボーディング会話フロー例:**

```
リワードちゃん: はじめまして〜！リワードちゃんだよ🎀
               まずざっくり教えて〜。毎月の手取りってどれくらい？

ユーザー: 30万くらい。

リワードちゃん: おっけー！家賃とかスマホ代とか、毎月決まって出ていくお金は？

ユーザー: 家賃8万、スマホ1万、サブスク5000円くらいかな

リワードちゃん: なるほど〜。じゃあ今月のごほうび枠、まず2万円くらいから始めよっか✨

リワードちゃん: ちなみにボーナスってある？あるなら何月にどれくらい？

ユーザー: 6月と12月に40万ずつくらい。

リワードちゃん: いいね〜！ボーナス月はちょっと多めに使えるようにしとくね😏

リワードちゃん: あと誕生日いつ？覚えておきたいな〜🎂

ユーザー: 9月15日

リワードちゃん: 9/15ね、メモった📝 その日は特別なご褒美用意するから楽しみにしてて！

リワードちゃん: おっけー準備完了！なんかあったらいつでも話しかけてね〜
```

---

**記念日の自然収集パターン（スライス 2-9）:**

```
ユーザー: 来月結婚記念日なんだよね

リワードちゃん: え〜おめでとう！🎉 何日？覚えておくね！

ユーザー: 6月15日

リワードちゃん: 6/15ね！その時期になったら何かいい感じの提案するね〜✨

→ PROFILE.anniversaries に {"name": "結婚記念日", "date": "06-15"} を追加
```

---

**設計上の注意:**

| 方針 | 理由 |
|------|------|
| 初回は 3ステップ（月収→固定費→ご褒美枠）で完了させる | 質問多すぎると初回離脱リスク |
| ボーナス・誕生日は「ちなみに」で聞く | 必須感を出さない。スキップ可能 |
| 記念日は会話中に自然に拾う | 初回で聞くと重い。PREF_MEMORY パターンで |
| 年齢は聞かない（誕生日は MM-DD のみ） | デリケートな情報。月日だけで特別提案に十分 |
| ボーナス情報は Unit 5 のご褒美提案で活用 | ボーナス月に枠を拡大 |

---

### Unit 3: 支出記録（F4対応）

**対応要件**: F4-01〜F4-05

| 内容 | 詳細 |
|------|------|
| **スコープ** | チャット支出抽出・確認フロー・レシート画像解析 |
| **依存** | Unit 0, Unit 1, Unit 2 |
| **完了条件** | 「プリン買った」で支出登録できる; レシート画像から支出JSON化できる |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 3-1 | `expense_prompt.py` + `expense_extractor.py`: テキスト→支出JSON化（Nova Micro） | F4-01 |
| 3-2 | 追加質問フロー（金額・商品名が不足時にリワードちゃんが聞く） | F4-02 |
| 3-3 | 確認・承認フロー（信頼度低→確認メッセージ→yes/noで保存） | F4-03 |
| 3-4 | DynamoDB EXPENSE保存（確定後） | F4-01 |
| 3-5 | `receipt_prompt.py` + `receipt_analyzer.py`: Nova Liteで画像→支出JSON | F4-04 |
| 3-6 | レシート解析時間チェック（3秒超→非同期化→Push or「結果を見る」ボタン）。非同期化には SQS キューを使用し、`template.yaml` への SQS リソース定義も本スライスに含める | PERF-02 |
| 3-7 | ARSカテゴリ分類（情緒安定費・回復費・緊急回復費等） | F4-05 |
| 3-8 | LLM出力品質テスト（支出抽出精度） | TEST-01 |

---

### Unit 4: ご褒美候補プール（F5対応）

**対応要件**: F5-01〜F5-05

| 内容 | 詳細 |
|------|------|
| **スコープ** | 嗜好記憶蓄積・楽天API連携・日次バッチでプール更新 |
| **依存** | Unit 0, Unit 2 |
| **完了条件** | 日次バッチが動作し、楽天APIの商品がDynamoDB reward_poolに格納される |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 4-1 | `rakuten_service.py`: 楽天ウェブサービスAPI商品検索（新ドメイン `openapi.rakuten.co.jp` 対応） | F5-03 |
| 4-2 | `reward_pool_service.py`: 嗜好×候補スコアリングロジック | F5-01 |
| 4-3 | `reward_pool_updater.py`: 全ユーザー嗜好取得→楽天API→プール更新 | F5-02 |
| 4-4 | EventBridge Scheduler SAMリソース定義（RewardPoolScheduler） | F5-02 |
| 4-5 | スルー・購入履歴によるスコア調整 | F5-04, F5-05 |
| 4-6 | 楽天APIモックテスト | TEST-04 |
| **4-7** *(Growth)* | `rakuten_service.search_hotels()`: 楽天トラベル施設検索（同一アプリID利用）+ `reward_pool_updater` への統合 | — |
| **4-8** *(Growth)* | `hotpepper_service.py`: ホットペッパーグルメAPI検索 + `reward_pool_updater` への統合 | — |
| **4-9** *(Growth)* | `schemas.py`: REWARD_POOL アイテムに `type: product/travel/restaurant` フィールド追加・`reward_pool_service` カテゴリ重みづけ対応 | — |

---

### Unit 5: ご褒美提案（F6対応）

**対応要件**: F6-01〜F6-05

| 内容 | 詳細 |
|------|------|
| **スコープ** | 状態推定・候補プールマッチング・余裕額チェック・キャラ口調での提案 |
| **依存** | Unit 0, Unit 2, Unit 3, Unit 4（※Unit 1: コード依存は Unit 0 の `line_service` で代替可。統合テスト時には Unit 1 の Webhook ルーティングが必要） |
| **完了条件** | 「疲れた」でご褒美提案がリワードちゃん口調で返る; 余裕額超過時はやんわり止める |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 5-1 | `finance_engine.py`: DynamoDBから余裕額算出（0以上・上限超えない） | F6-04 |
| 5-2 | `reward_proposal.py`: 状態ベクトル生成→候補プールマッチング | F6-01, F6-02 |
| 5-3 | 余裕額チェック→予算内候補のみ選択 | F6-04 |
| 5-4 | キャラ口調での提案メッセージ生成（Nova Micro） | F6-03 |
| 5-5 | 買いすぎストップ（余裕額≦0時のやんわり止めReply） | F6-05 |
| 5-6 | 提案履歴をDynamoDB REWARD_SUGGESTIONに保存 | F6-01 |
| 5-7 | finance_engineユニットテスト（余裕額常に0以上・上限超えない） | TEST-02 |
| 5-8 | Googleカレンダーコンテキスト活用: 連携済ユーザーの今日の予定を`google_calendar_service.get_today_events()`で取得し、`_build_calendar_context()`でLLMプロンプトに反映。「今日会議多かったでしょ？」等のコンテキスト対応提案。未連携時はスキップ（従来動作） | F9-01 |

---

### Unit 6: Push通知（F7対応）

**対応要件**: F7-01〜F7-03

| 内容 | 詳細 |
|------|------|
| **スコープ** | Push通知送信・1日1回上限管理・コンテンツ生成 |
| **依存** | Unit 0, Unit 2, Unit 5 |
| **完了条件** | EventBridgeからPush通知が送信される; 月200通超過しない |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 6-1 | `push_notifier.py`: 対象ユーザー取得・Push送信 | F7-01 |
| 6-2 | 通数管理（今日既にPush済みかDynamoDBで確認） | F7-01, F7-03 |
| 6-3 | Push通知コンテンツ生成（Nova Micro）「今日ちょっとだけ話したいことある〜」 | F7-02 |
| 6-4 | EventBridge Scheduler SAMリソース定義（PushNotifierScheduler） | F7-01 |
| 6-5 | 月200通上限チェックロジック（フリープラン保護） | COST-03 |

---

### Unit 7: LIFFダッシュボード（F8対応）

**対応要件**: F8-01〜F8-03

| 内容 | 詳細 |
|------|------|
| **スコープ** | LIFF用API + 最小限フロントエンド（HTML + LINE LIFF SDK） |
| **依存** | Unit 0, Unit 3（支出履歴）, Unit 4（候補一覧）, Unit 5（提案履歴）（Unit 1/2/6 とは直接依存なし） |
| **完了条件** | LINEアプリ内でLIFFが開き、履歴・設定が表示できる |

**機能スライス:**

| スライス | 機能 | 対応要件 |
|---------|------|---------|
| 7-1 | `liff_api.py`: 履歴取得API・設定取得/更新API | F8-01, F8-03 |
| 7-2 | LIFF App（最小HTML + LINE LIFF SDK）初期化 | F8-01 |
| 7-3 | ご褒美メモ・履歴表示（キャラの言葉で表現） | F8-01, F8-02 |
| 7-4 | 設定画面（口調選択・ご褒美枠変更） | F8-03 |
| 7-5 | SAMテンプレートに LiffApiFunction + LiffApi 追加 | — || 7-6 | Googleカレンダー連携 UI: LIFF設定画面に「カレンダー連携」ボタン追加。Google OAuth同意画面リダイレクト → コールバックでtoken交換 → DynamoDB `GOOGLE_OAUTH#` に refresh_token 保存。解除機能付き（revoke + 削除）。OAuth scope: `calendar.events.readonly` のみ | F9-02 |
---
