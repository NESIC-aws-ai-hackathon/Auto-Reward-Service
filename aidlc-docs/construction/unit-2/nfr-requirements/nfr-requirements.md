# NFR Requirements — Unit 2: リワードちゃんキャラクター

**作成日**: 2026-05-16  
**Unit**: Unit 2 — LINE Bot会話  
**対応要件**: F2-01〜F2-06, F3-01〜F3-05

---

## 1. パフォーマンス要件

### PERF-01（継承 + Unit 2 最重要）: LINE Reply 応答時間

| 項目 | 内容 |
|------|------|
| **要件** | Webhook 受信から LINE Reply 送信まで **3秒以内** を目標 |
| **Unit 2 リスク** | Bedrock Nova Micro 呼び出し（Intent分類 + 応答生成）が 2 回発生する可能性あり |
| **測定ターゲット** | `intent_classifier` (Nova Micro) < 0.8秒 / `character_reply` (Nova Micro) < 1.2秒 / DynamoDB 読み書き < 0.2秒 / 合計 < 2.5秒 |
| **超過リスク対応** | Intent分類と感情推定はルールベースを優先し LLM は応答生成のみ。Intent分類の LLM 呼び出しは同期。全体 3 秒超の場合は Lambda タイムアウト前に固定フォールバック「ちょっと考えすぎちゃった〜😅 もう一度話しかけてね」を返す |

### PERF-03（継承）: Lambda コールドスタート対策

| 項目 | 内容 |
|------|------|
| **方式** | `WarmupWebhookScheduler` が継続（5 分毎 ping） |
| **Unit 2 影響** | Bedrock SDK のインポートが追加されるが、既存 Layer に含まれているため初回インポートの大幅増加なし |

### PERF-06（Unit 2 新規）: Bedrock Nova Micro レイテンシ上限

| 項目 | 内容 |
|------|------|
| **要件** | 1 回の Nova Micro 呼び出しは **2 秒以内** を期待値とする |
| **根拠** | Nova Micro は軽量モデル。短いプロンプト（< 500 トークン）では 0.5〜1.5 秒が典型値 |
| **タイムアウト設定** | `bedrock_service.invoke_text()` の read_timeout = 5 秒、connect_timeout = 3 秒 |
| **超過時の対応** | `bedrock_service` が `BedrockServiceError` を raise → `webhook_handler` のフォールバック文言を返す |

### PERF-07（Unit 2 新規）: DynamoDB CHAT ログ書き込みの非同期化

| 項目 | 内容 |
|------|------|
| **方針** | CHAT ログ保存は **LINE Reply 送信後** に実行する（応答遅延に影響させない） |
| **実装** | `line_service.reply_message()` 完了 → `_save_chat_log()` → `_detect_preferences()` の順序 |
| **失敗時** | CHAT ログ保存失敗は WARNING ログのみ。LINE Reply は成功として返す |

---

## 2. スケーラビリティ要件

### SCAL-01（継承）: API Gateway スロットリング

Unit 1 設定を継承（定常 100 req/s、バースト 200 req/s）。Unit 2 での変更なし。

### SCAL-03（Unit 2 新規）: DynamoDB アクセスパターン追加

| 新規アクセスパターン | 操作 | 頻度 |
|---|---|---|
| `CHAT#{timestamp}` put | PutItem | 全メッセージ × 2（user + assistant） |
| `CHAT#{timestamp}` query | Query (SK begins_with CHAT, Limit=5) | 全メッセージ受信時 |
| `ONBOARDING_STATE` get/put/delete | GetItem / PutItem / DeleteItem | オンボーディング中のみ |
| `PREF_MEMORY#*` put | PutItem | キーワード検出時のみ |
| `DAILY_COUNT#{date}` update | UpdateItem (ADD 1) | 全メッセージ受信時 |
| `PROFILE` get | GetItem | 全メッセージ受信時 |

**DynamoDB キャパシティ**: PAY_PER_REQUEST（Unit 0 設定継承）。ハッカソン規模では問題なし。

---

## 3. セキュリティ要件

### SEC-01（継承）: LINE Webhook 署名検証

Unit 1 実装を継承。Unit 2 での変更なし。

### SEC-02（継承）: シークレット管理

Secrets Manager `ars/line` 継続使用。Unit 2 で新規シークレット追加なし。

### SEC-04（継承）: PII ログ保護

CHAT ログ保存時も logger.py の PII フィルタを通す。メッセージ本文はログに出力しない。

### SEC-2-01（Unit 2 新規・FD BR より）: Bedrock プロンプトインジェクション対策

| 項目 | 内容 |
|------|------|
| **要件** | ユーザー入力を `<user_message>` タグで囲んでプロンプトに埋め込む |
| **実装** | `intent_prompt.py` / `character_prompts.py` のプロンプトテンプレートで境界明示 |

### SEC-2-02（Unit 2 新規・FD BR より）: 入力長の上限チェック

| 項目 | 内容 |
|------|------|
| **上限** | 1,000 文字 |
| **超過時** | Bedrock 呼び出しをスキップし固定返答 |
| **実装場所** | `webhook_handler.py` の `_route_message()` 入口 |

### SEC-2-03（Unit 2 新規）: Bedrock IAM 最小権限

| 項目 | 内容 |
|------|------|
| **追加権限** | `bedrock:InvokeModel` |
| **対象リソース** | `arn:aws:bedrock:ap-northeast-1::foundation-model/amazon.nova-micro-v1:0` のみ |
| **根拠** | Nova Lite（画像解析）は Unit 3 で追加予定。Unit 2 では Nova Micro のみ |

---

## 4. 可用性・信頼性要件

### AVAIL-01（継承）: Lambda 障害分離

Unit 1 設定継承。全例外を封じ込め → 200 返却（LINE の Webhook 再送防止）。

### AVAIL-03（Unit 2 新規）: Bedrock 呼び出し失敗時のフォールバック

| 状況 | フォールバック動作 |
|---|---|
| Intent 分類失敗 | `UNKNOWN` として `character_reply` のフォールバック文言を返す |
| character_reply 生成失敗 | 固定文言「ちょっとうまく答えられなかったよ〜😅 もう一回話しかけてね！」を返す |
| オンボーディング中の Bedrock 失敗 | 「少し混乱しちゃった😅 もう一度教えてね！」で同ステップを維持 |

### AVAIL-04（Unit 2 新規）: DynamoDB DAILY_COUNT のアトミック更新

| 項目 | 内容 |
|------|------|
| **要件** | 1日会話制限カウンタは `UpdateItem` の `ADD 1` でアトミック更新する |
| **競合状態** | Lambda の並行実行でもカウントの整合性を保つ |
| **TTL** | 翌日 0 時（JST）の Unix タイムスタンプを `ttl` フィールドに設定 |

---

## 5. コスト要件

### COST-01（Unit 2 新規）: Bedrock Nova Micro 呼び出しコスト管理

| 項目 | 内容 |
|------|------|
| **要件** | 1 ユーザーあたり 1 日最大 **50 回** の会話（BR-2-12 で実装済み） |
| **上限値** | 環境変数 `DAILY_CHAT_LIMIT`（デフォルト 50） |
| **コスト見積** | Nova Micro: 約 $0.000035/1K input tokens, $0.00014/1K output tokens。50回×500トークン ≒ $0.001/ユーザー/日 |
| **根拠** | ハッカソン期間（数日）× 数十ユーザー = $1 未満に収める |

### COST-02（継承）: Lambda 呼び出しコスト

Unit 0/1 設定継承。ウォームアップ ping + 実リクエスト。ハッカソン規模では無視可能。

---

## 6. 保守性要件

### MAINT-01（継承）: 構造化ログ

全 Lambda で aws-lambda-powertools の構造化ログを使用。Unit 2 では以下のログポイントを追加:

| ログポイント | レベル | 内容 |
|---|---|---|
| `intent_classified` | INFO | `intent`, `confidence` |
| `emotion_inferred` | DEBUG | `emotion`, `fatigue_level` |
| `onboarding_step_changed` | INFO | `from_step`, `to_step` |
| `chat_log_saved` | DEBUG | `sk` のみ（本文は除く） |
| `daily_limit_reached` | WARNING | `user_id_hash`, `count` |
| `pref_detected` | INFO | `category`, `keyword`, `sentiment` |
