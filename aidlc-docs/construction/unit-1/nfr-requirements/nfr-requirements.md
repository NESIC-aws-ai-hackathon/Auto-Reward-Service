# NFR Requirements — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**Unit**: Unit 1 — LINE Bot基盤  
**対応要件**: F1-01, F1-02, F1-03, F1-04, SEC-01

---

## 1. パフォーマンス要件

### PERF-01（継承）: LINE Reply 応答時間

| 項目 | 内容 |
|------|------|
| **要件** | Webhook 受信から LINE Reply 送信まで **3秒以内** を目標 |
| **実装** | WebhookHandler タイムアウト 10 秒。3 秒を超える処理が発生する場合は Unit 2 以降で Reply 先送り戦略を検討 |
| **Unit 1 での状況** | テキスト: エコー応答（即座）、画像: 固定応答（即座）、未対応: 固定テンプレート選択（即座）。3 秒超のリスクなし |

### PERF-03（継承）: Lambda コールドスタート対策

| 項目 | 内容 |
|------|------|
| **方式** | EventBridge Scheduler によるウォームアップ ping（5 分毎） |
| **ペイロード** | `{"source": "warmup"}` |
| **ハンドラ実装** | `if event.get("source") == "warmup": return {"statusCode": 200}` |
| **対象** | `WebhookHandlerFunction` |

### PERF-04（確定）: Lambda メモリ設定

| 関数名 | メモリ | 根拠 |
|--------|-------|------|
| `WebhookHandlerFunction` | **256 MB** | Unit 2 以降で Bedrock 呼び出しを追加するため、将来変更不要な値を採用 |

### PERF-05（継承）: Lambda タイムアウト設定

| 関数名 | タイムアウト | 根拠 |
|--------|------------|------|
| `WebhookHandlerFunction` | **10 秒** | LINE 応答 3 秒目標 + バッファ。LINE の Webhook タイムアウト（1 秒 / 5 秒）より長い |

---

## 2. スケーラビリティ要件

### SCAL-01（Unit 1 新規）: API Gateway スロットリング

| 項目 | 内容 |
|------|------|
| **設定** | カスタム制限（定常: 100 req/s、バースト: 200 req/s） |
| **根拠** | ハッカソン規模（テストユーザー数人）。誤爆・不正リクエストによるコスト過剰発生を防止 |
| **実装** | `template.yaml` の `WebhookApi` ステージ設定に `ThrottlingBurstLimit` / `ThrottlingRateLimit` を追加 |
| **LINE Platform への影響** | LINE Platform の Webhook 送信は通常 1 件/秒 未満。100 req/s は十分な余裕 |

### SCAL-02（継承）: Lambda 同時実行数

| 項目 | 内容 |
|------|------|
| **設定** | 予約済み同時実行なし（AWS アカウントデフォルト） |
| **根拠** | MVP 段階はユーザー数が少ない。必要に応じて追加 |

---

## 3. セキュリティ要件

### SEC-01（継承 + Unit 1 実装）: LINE Webhook 署名検証

| 項目 | 内容 |
|------|------|
| **要件** | すべての POST /webhook リクエストに `X-Line-Signature` ヘッダーの HMAC-SHA256 検証を必須とする |
| **失敗時** | HTTP 403 返却。処理なし |
| **ヘッダーなし** | 403 返却（ヘッダーなし = 検証失敗と同等） |
| **実装** | `line_service.verify_signature(body, signature)` |

### SEC-02（継承）: シークレット管理

| 項目 | 内容 |
|------|------|
| **要件** | チャネルシークレット・アクセストークンを Lambda 環境変数に平文保存禁止 |
| **実装** | `secrets.get_line_secrets()` → Secrets Manager `ars/line` から取得 |

### SEC-04（継承）: PII ログ保護

| 項目 | 内容 |
|------|------|
| **要件** | LINE ユーザー ID・メッセージ本文をログに出力禁止 |
| **実装** | `PIIMaskingLogger` による自動マスク（`line_user_id`, `message` フィールド） |

### SEC-06（継承）: IAM 最小権限

| 項目 | 内容 |
|------|------|
| **要件** | `WebhookHandlerFunction` に付与する IAM 権限は必要最小限 |
| **Unit 1 必要権限** | `secretsmanager:GetSecretValue` (`ars/line`) のみ |
| **不要権限** | DynamoDB アクセス不要（Unit 2 以降で追加） |

### SEC-07（Unit 1 新規）: API Gateway エンドポイント保護

| 項目 | 内容 |
|------|------|
| **要件** | `/webhook` エンドポイントへの不正アクセスは Lambda 内の署名検証で防御 |
| **WAF** | 不採用（ハッカソン規模のため）。スロットリング + 署名検証で代替 |
| **認証** | API Gateway レベルの認証なし（LINE Platform 署名検証で代替） |

---

## 4. 可用性・信頼性要件

### AVAIL-01（継承）: エラーハンドリング方針

| 項目 | 内容 |
|------|------|
| **方針** | WebhookHandler は未捕捉例外をキャッチし、LINE にエラーメッセージを Reply した上で HTTP 200 を返す |
| **理由** | 500 返却 → LINE Platform が Webhook リトライ → 重複処理発生を防ぐ |
| **二重障害** | Reply 送信失敗時もログのみ（例外を再 raise しない） |

### AVAIL-02（Unit 1 新規）: CloudWatch Logs 設定

| 項目 | 内容 |
|------|------|
| **ログ保持期間** | 30 日（ハッカソン期間中のデバッグに十分） |
| **ログレベル** | `INFO`（環境変数 `LOG_LEVEL=INFO`、Unit 0 Globals で設定済み） |

---

## 5. 監視要件

### MON-01: X-Ray トレーシング

| 項目 | 内容 |
|------|------|
| **設定** | **無効** |
| **根拠** | ハッカソン期間中は CloudWatch Logs で十分。コスト・実装シンプルさ優先 |

### MON-02: CloudWatch Metrics（標準）

| 項目 | 内容 |
|------|------|
| **設定** | AWS 提供の標準メトリクスのみ（Invocations, Errors, Duration, Throttles） |
| **カスタムアラーム** | なし（ハッカソン規模のため） |
