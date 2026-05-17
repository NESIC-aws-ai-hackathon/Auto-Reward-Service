# NFR Requirements — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16

---

## 1. パフォーマンス要件

### PERF-01: LINE Reply 応答時間（承継）
- **要件**: Webhook 受信から LINE Reply 送信まで **3秒以内**
- **対応策**: Webhook Handler タイムアウトを 10 秒に設定し、3秒到達前に Reply を優先送信するアーキテクチャを採用

### PERF-02: 画像解析の非同期化（承継）
- **要件**: レシート画像解析が 1 分を超える場合は非同期化
- **対応策**: Receipt Image Analyzer Lambda のタイムアウトを 60 秒に設定（Unit 3 で SQS キューによる非同期化を実装）

### PERF-03: Lambda Cold Start 対策（確定）
- **方式**: **EventBridge Scheduler によるウォームアップ ping**（5分毎）
- **対象関数**: Webhook Handler、Bedrock 呼び出し系（Intent Classifier、Character Reply）
- **実装方法**:
  - EventBridge Scheduler が `{"source": "warmup"}` イベントを Lambda に送信
  - 各ハンドラの先頭で warmup イベントを検出し即座に `200 OK` を返す
  - 実際のビジネスロジックは実行しない

```python
# ウォームアップハンドラパターン（全ハンドラ共通）
def lambda_handler(event, context):
    if event.get("source") == "warmup":
        return {"statusCode": 200, "body": "warm"}
    # ... 通常処理
```

### PERF-04: Lambda メモリ設定（確定）

| 関数グループ | 対象関数 | メモリ | 根拠 |
|------------|---------|--------|------|
| Webhook / ルーティング系 | WebhookHandler | 128MB | 軽量ルーティングのみ |
| Bedrock テキスト系 | IntentClassifier, CharacterReply, OnboardingFlow, ExpenseExtractor, PushNotifier | 256MB | Bedrock API 呼び出し + 中程度の処理 |
| 画像解析系 | ReceiptImageAnalyzer | 512MB | Nova Lite 大容量レスポンス処理 |
| バッチ系 | RewardPoolUpdater, PushNotifier | 256MB | 複数ユーザー処理 + 外部API呼び出し |
| LIFF API系 | LiffApi | 256MB | DynamoDB 複数操作 + Google OAuth |

### PERF-05: Lambda タイムアウト設定（確定）

| 関数グループ | タイムアウト | 根拠 |
|------------|------------|------|
| Webhook Handler | **10秒** | 3秒応答必須 + バッファ。タイムアウト前に Reply 送信を優先 |
| Bedrock テキスト系 | **30秒** | Nova Micro の通常応答時間（1〜5秒）+ バッファ |
| 画像解析系 | **60秒** | Nova Lite 画像解析（非同期化前の最大処理時間） |
| バッチ系（楽天API・Push通知） | **300秒** | 全ユーザー処理 + 外部API レート制限考慮 |
| LIFF API | **30秒** | DynamoDB 複数操作 + Google Calendar API 呼び出し |

---

## 2. スケーラビリティ要件

### SCAL-01: DynamoDB キャパシティモード（確定）
- **モード**: **オンデマンド（PAY_PER_REQUEST）**
- **根拠**: MVP 段階はユーザー数が少なく予測不能。スケーリング不要でシンプル。
- **注意**: ユーザー数が安定・増加した段階でプロビジョンドへの移行を検討

### SCAL-02: Lambda 同時実行数
- **設定**: 予約済み同時実行なし（デフォルト）
- **根拠**: MVP 段階は同時実行数が少ない。問題発生時に制限を追加

### SCAL-03: ウォームアップ対象スケジュール

| スケジュール名 | 対象 Lambda | 頻度 | 説明 |
|--------------|------------|------|------|
| `WarmupWebhookScheduler` | WebhookHandler | 5分毎 | LINE 応答品質確保 |
| `WarmupBedrockScheduler` | CharacterReply（代表） | 5分毎 | Bedrock 呼び出し系 代表1関数 |

---

## 3. セキュリティ要件（Functional Design 承継）

以下は `business-rules.md` で確定済み。Unit 0 コード生成時に実装を確認する。

| 要件ID | 内容 | 実装箇所 |
|--------|------|---------|
| SEC-01 | LINE Webhook X-Line-Signature 検証 | `line_service.verify_signature()` |
| SEC-02 | シークレット平文ハードコード禁止 | `secrets.py` + Secrets Manager |
| SEC-03 | DynamoDB 暗号化（AWS管理キー） | `template.yaml` ArsTable 定義 |
| SEC-04 | ログに PII 出力禁止 | `logger.py` PII マスク |
| SEC-06 | Lambda IAM 最小権限原則 | `template.yaml` IAM ポリシー |
| SEC-08 | カレンダーデータ非保存・ログ禁止 | `google_calendar_service.py` |
| SEC-09 | OAuth スコープ最小化 | `google_calendar_service.py` |

---

## 4. 可用性・信頼性要件

### AVAIL-01: Lambda エラーハンドリング
- DynamoDB / Bedrock / LINE API エラー → 独自例外（`DynamoDBError` 等）に変換
- Webhook Handler は例外をキャッチし、500 エラーではなく LINE エラーメッセージを返す

### AVAIL-02: DynamoDB バックアップ
- **方式**: AWS Backup による日次自動バックアップ（SAM で定義）
- **保持期間**: 7日

---

## 5. コスト要件（承継）

| 要件ID | 内容 | 対応 |
|--------|------|------|
| COST-01 | 1ユーザー1日 Nova Micro 50〜100会話まで | `character_reply.py` で制限管理 |
| COST-02 | 画像解析 標準5枚/日 | `receipt_analyzer.py` で制限管理 |
| COST-03 | Push 通知 月200通以内 | `push_notifier.py` で通数管理 |
| COST-04 | 制限到達時はキャラ退場演出 | テンプレート応答へフォールバック |

---

## 6. オブザーバビリティ要件

### OBS-01: ログ（確定）
- **方式**: `aws-lambda-powertools` Logger（JSON 構造化ログ）
- **保持期間**: **30日**（全 Lambda ロググループ統一）
- **PII マスク**: `logger.py` に集約（LINE userId、チャット内容、カレンダーデータ）

### OBS-02: トレーシング（確定）
- **方式**: **無効**（MVP 段階は CloudWatch Logs で十分）
- **移行**: ユーザー数増加時に X-Ray を追加予定

### OBS-03: メトリクス
- CloudWatch デフォルトメトリクスのみ（Lambda Duration / Error / Throttle）
- カスタムメトリクスは MVP 対象外
