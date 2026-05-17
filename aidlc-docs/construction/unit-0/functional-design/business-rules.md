# Business Rules — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16

---

## R1: DynamoDB アクセスパターン規則

### R1-1: GSI 付与対象の制限
- `entityType` 属性は **PROFILE# と PREF_MEMORY# アイテムにのみ** 付与する
- 以下のエンティティには `entityType` 属性を **付与してはならない**:
  - `CHAT#{timestamp}` — 高頻度書き込み（1会話1アイテム）
  - `EXPENSE#{timestamp}` — 高頻度書き込み
  - `LIFELOG#{timestamp}` — 高頻度書き込み
  - `REWARD_SUGGESTION#{timestamp}` — 中頻度書き込み
  - `PENDING_EXPENSE#` — 一時データ

### R1-2: GSI クエリ対象
- `entityType-index` GSI は以下の用途にのみ使用する:
  - バッチ処理: 全ユーザーの `PREF_MEMORY` 取得（`entityType=PREF_MEMORY`）
  - バッチ処理: アクティブユーザー一覧（`entityType=PROFILE` + `status=ACTIVE` filter）

### R1-3: 主キー必須
- ハンドラが DynamoDB を操作する場合、PK（`USER#{lineUserId}`）は **必ず確定してから** 操作する
- PK 不明のままクエリ・スキャンは行わない（パフォーマンス劣化防止）

### R1-4: エラー伝播規則
- `boto3.ClientError` は必ず `DynamoDBError` に変換して上位へ raise する
- `dynamodb_service.py` 内で例外を握りつぶしてはならない

### R1-5: TTL 設定
- 以下のエンティティは `put_item` 時に `ttl` フィールド（Unix epoch int）を設定する:

| エンティティ | TTL | 計算方法 |
|-------------|-----|----------|
| ChatLog | 30日 | `int(datetime.now().timestamp()) + 30 * 86400` |
| LifeLog | 90日 | `int(datetime.now().timestamp()) + 90 * 86400` |
| PendingExpense | 24時間 | `int(datetime.now().timestamp()) + 86400` |

- `ttl` 値の計算は **呼び出し元ハンドラ** の責務とする（`dynamodb_service.py` は計算しない）
- `template.yaml` の `ArsTable` リソースに `TimeToLiveSpecification` を設定する:
  ```yaml
  TimeToLiveSpecification:
    AttributeName: ttl
    Enabled: true
  ```

---

## R2: Bedrock モデル切り替え規則

### R2-1: デフォルトモデル ID
| 用途 | 環境変数 | デフォルト値 |
|------|---------|-------------|
| テキスト推論 | `BEDROCK_TEXT_MODEL_ID` | `amazon.nova-micro-v1:0` |
| 画像推論 | `BEDROCK_IMAGE_MODEL_ID` | `amazon.nova-lite-v1:0` |

### R2-2: 明示的上書き
- 呼び出し元（ハンドラ等）が `model_id` 引数で上書きできる
- 品質不足時に Claude Haiku / Sonnet へ切り替える場合は引数で指定する

### R2-3: リージョン
- Bedrock クライアントは `AWS_REGION` 環境変数を参照する
- デフォルト: `ap-northeast-1`（東京）

---

## R3: LINE SDK 利用規則

### R3-1: 公開メソッドの制限
- `line_service.py` が公開するメソッドは以下の **4つのみ**:
  - `verify_signature(body, signature) → bool`
  - `reply_message(reply_token, messages)`
  - `push_message(user_id, messages)`
  - `get_message_content(message_id) → bytes`

### R3-2: 署名検証の強制
- **全ての** Webhook リクエスト処理は `verify_signature` を最初に呼び出す
- 検証失敗時は即座に 403 を返し、以降の処理を行わない（SEC-01 準拠）

### R3-3: メッセージ形式
- `messages` 引数は dict のリストとする（SDK 固有型をハンドラに漏洩させない）
- テキスト: `{"type": "text", "text": "..."}`
- Flex Message: `{"type": "flex", "altText": "...", "contents": {...}}`

---

## R4: Secrets Manager キャッシュ規則

### R4-1: モジュールレベルキャッシュ
- シークレット取得はモジュールレベルのグローバル変数にキャッシュする
- Lambda インスタンスのライフタイム中は再取得しない（コールドスタート時のみ取得）

### R4-2: キャッシュ無効化
- シークレットローテーション後はキャッシュが無効になる
- ローテーション後は Lambda 関数の再デプロイまたはコンテナ再起動で対応する

### R4-3: 平文保存禁止
- シークレット値（LINE_CHANNEL_SECRET 等）をソースコードにハードコードしてはならない（SEC-02 準拠）
- 環境変数にも平文で設定してはならない。Secrets Manager の秘密名のみ環境変数に設定する

---

## R5: ログ出力規則（PII保護）

### R5-1: 禁止事項（SEC-04 準拠）
以下の情報は CloudWatch Logs に **出力してはならない**:
- LINE userId（`Uxxxxxxxxxx` 形式）
- チャットメッセージ内容
- カレンダーイベントのタイトル・内容・参加者（SEC-08 準拠）
- `refresh_token` / `access_token`
- 個人を特定できるメールアドレス（完全形）

### R5-2: マスク処理
- `logger.py` の `get_logger()` で取得した Logger インスタンスを使用した場合、上記フィールドは自動マスクされる
- `logging.getLogger()` を直接使用してはならない（マスクが効かなくなる）

### R5-3: 相関 ID
- 各 Lambda 実行で `request_id`（Lambda の `context.aws_request_id`）をログに付与する
- `logger.append_keys(request_id=context.aws_request_id)` をハンドラの先頭で呼び出す

---

## R6: Google Calendar 規則

### R6-1: カレンダーデータの非保存（SEC-08 準拠）
- Google Calendar API から取得したイベントデータ（タイトル・説明・参加者・場所等）は
  DynamoDB に **保存してはならない**
- イベントデータはリクエスト処理中のメモリ内のみに存在する

### R6-2: access_token の非保存
- `_refresh_access_token()` で取得した `access_token` はローカル変数にのみ保持する
- DynamoDB・ログ・グローバル変数への保存を禁止する

### R6-3: 毎回リフレッシュ
- `get_today_events()` 呼び出し毎に `_refresh_access_token()` を実行する
- Google OAuth endpoint: `https://oauth2.googleapis.com/token`

### R6-4: スコープ制限（SEC-09 準拠）
- OAuth 認可時に要求するスコープは `https://www.googleapis.com/auth/calendar.events.readonly` のみ
- 書き込み・削除スコープを要求してはならない

### R6-5: カレンダーイベント取得範囲
- `timeMin`: 今日 00:00 JST（UTC変換後に使用）
- `timeMax`: 明後日 00:00 JST（= 今日 + 明日 の2日分）
- `maxResults`: 20（API 1回あたりの上限）
- `singleEvents`: True（繰り返しイベントを展開）
- `orderBy`: "startTime"

### R6-6: 非連携ユーザーの扱い
- `is_connected()` が `False` の場合、`get_today_events()` は空リスト `[]` を返す
- エラーを raise してはならない（カレンダー未連携は正常状態）

### R6-7: revoke 処理
- OAuthトークン解除時は以下の順序で実行する:
  1. Google OAuth revoke endpoint にリクエスト（`https://oauth2.googleapis.com/revoke`）
  2. DynamoDB から `GOOGLE_OAUTH#` アイテムを削除
  3. Google revoke が失敗した場合でも DynamoDB 削除は実行する（ベストエフォート）

---

## R7: Pydantic モデル規則

### R7-1: モデル設定
- 全モデルに `model_config = ConfigDict(extra='ignore')` を設定する
  （DynamoDB の将来的な属性追加に対する前方互換性確保）

### R7-2: 金額型
- 金額フィールド（amount, price 等）は `Decimal` 型を使用する（float は禁止）
- DynamoDB への保存時は `Decimal` のまま（boto3 は `Decimal` をネイティブサポート）

### R7-3: 日時型
- DynamoDB 保存値は ISO 8601 文字列（`"2026-05-16T12:00:00+09:00"` 形式）
- Python モデル内の型は `str`（パース/フォーマットは呼び出し元の責任）

---

## R8: Lambda Layer 構成規則

### R8-1: Layer 対象
以下のディレクトリを Lambda Layer としてパッケージ化する:
- `src/services/` — 共通サービスクラス
- `src/utils/` — ユーティリティ（secrets, logger, exceptions）
- `src/models/` — Pydantic モデル（schemas.py）

### R8-2: Layer 非対象
以下のディレクトリは Layer に含めない（各関数のデプロイパッケージに同梱）:
- `src/handlers/` — Lambda ハンドラ（関数毎に異なる）
- `src/prompts/` — LLM プロンプト定義（Unit 2/3 で追加）

### R8-3: Layer 内の依存ライブラリ
Layer の `requirements.txt` には以下のライブラリを含める:
- `pydantic` v2
- `line-bot-sdk` v3
- `aws-lambda-powertools`
- `requests`（Google Calendar API 呼び出し用）

> **注意**: `boto3` / `botocore` は Lambda ランタイムにプリインストール済みのため Layer に含めない。  
> `boto3` / `botocore` は `requirements-dev.txt`（ローカルテスト・型補完用）にのみ記載する。  
> Layer に含めるとパッケージサイズが約70MB増加し、デプロイ速度が低下する。

---

## R9: SAM プロジェクト構成規則

### R9-1: 環境変数の一元管理
- SAM `template.yaml` の `Globals > Function > Environment > Variables` に共通環境変数を定義する
- 関数固有の環境変数は各 Function リソースに定義する

### R9-2: 必須共通環境変数
| 変数名 | 説明 |
|--------|------|
| `DYNAMODB_TABLE_NAME` | DynamoDB テーブル名 |
| `SECRET_NAME` | Secrets Manager シークレット名 |
| `BEDROCK_TEXT_MODEL_ID` | Bedrock テキストモデル ID |
| `BEDROCK_IMAGE_MODEL_ID` | Bedrock 画像モデル ID |
| `AWS_REGION` | Lambda 実行リージョン |

### R9-3: デプロイ環境分離
- `samconfig.toml` に `dev` / `prod` 設定セクションを設ける
- テーブル名・シークレット名はスタック名サフィックスで分離する（例: `ArsTable-dev`, `ArsTable-prod`）
