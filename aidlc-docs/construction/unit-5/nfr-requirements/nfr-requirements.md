# NFR 要件 — Unit 5: ご褒美提案 + 繰り越し機能

**Unit**: Unit 5 — ご褒美提案（F6 対応）+ 繰り越し機能（F2-07）  
**作成日**: 2026-05-16

---

## 1. パフォーマンス要件

| ID | 要件 | 目標値 | 根拠 |
|---|---|---|---|
| NFR-5-P1 | LINE メッセージ受信〜返信までの P99 レイテンシ | ≤ 5 秒 | LINE Reply API の 30 秒タイムアウト内で十分な余裕 |
| NFR-5-P2 | DynamoDB GetItem（PROFILE#, REWARD_POOL#, MONTHLY_SUMMARY#）| ≤ 50 ms/リクエスト | DynamoDB のプロビジョニング済み読み取りで十分 |
| NFR-5-P3 | Bedrock Nova Micro 推論レイテンシ | ≤ 3 秒 / 500 トークン | Nova Micro の実測値 |
| NFR-5-P4 | 繰り越し計算（`calculate_monthly_budget` 純関数） | ≤ 1 ms | CPU バウンドのみ |

---

## 2. セキュリティ要件

| ID | 要件 | 対応 |
|---|---|---|
| NFR-5-S1 | カレンダーコンテキストはイベントサマリーのみ（SEC-08） | `_build_calendar_context()` でサマリー以外を除外 |
| NFR-5-S2 | Bedrock プロンプトにユーザーの個人識別情報（氏名・住所・電話番号）を含めない | プロンプトテンプレートで除外 |
| NFR-5-S3 | DynamoDB の項目は LINE ユーザー ID でのみアクセス（クロスユーザーアクセス禁止） | PK=USER#{id} による単一ユーザー分離 |
| NFR-5-S4 | 繰り越し計算は Lambda 内で完結（外部 API 呼び出しなし） | `calculate_monthly_budget()` は純関数 |

---

## 3. 信頼性要件

| ID | 要件 | 対応 |
|---|---|---|
| NFR-5-R1 | Bedrock 障害時でもユーザーに応答を返す | フォールバックメッセージ（3 口調対応） |
| NFR-5-R2 | DynamoDB 障害時も余裕額算出を継続（支出 0 円として処理） | `get_monthly_spending()` の例外ハンドリング |
| NFR-5-R3 | 先月サマリー未取得でも提案フロー継続（繰り越し 0 扱い） | `get_last_month_remaining()` の例外ハンドリング |
| NFR-5-R4 | 提案履歴保存失敗は処理継続（非クリティカル） | `_save_suggestion()` の例外ハンドリング |
| NFR-5-R5 | Google Calendar 障害時も提案フロー継続 | `calendar_context = None` で続行 |

---

## 4. スケーラビリティ要件

| ID | 要件 | 対応 |
|---|---|---|
| NFR-5-SC1 | Lambda コールドスタートを最小化 | モジュールレベルシングルトン（BedrockService, GoogleCalendarService） |
| NFR-5-SC2 | 同時接続ユーザー数 ≤ 100 人（ハッカソンスコープ） | AWS Lambda デフォルトの同時実行数で対応 |

---

## 5. 観測性要件

| ID | 要件 | 対応 |
|---|---|---|
| NFR-5-O1 | 余裕額・繰り越し額・支出をすべてログ出力 | `calculate_slack()` で structured logging |
| NFR-5-O2 | 提案停止・フォールバック発生時は INFO/WARNING ログを出力 | `propose_reward()` 内で明示的ログ |
| NFR-5-O3 | Bedrock 呼び出し失敗は WARNING（サービス継続可能なエラー） | `BedrockError` ハンドリング |
