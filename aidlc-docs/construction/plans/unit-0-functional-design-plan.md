# Functional Design Plan — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16  
**ステータス**: 完了

---

## ユニット概要

| 項目 | 内容 |
|------|------|
| **Unit** | Unit 0: SAM基盤 + 共通Layer |
| **スコープ** | SAMプロジェクト初期化、DynamoDBテーブル定義、共通Layerモジュール全体 |
| **対応スライス** | 0-1〜0-9 |
| **主要成果物** | `template.yaml`, `dynamodb_service.py`, `bedrock_service.py`, `line_service.py`, `google_calendar_service.py`, `schemas.py`, `secrets.py`, `logger.py` |

---

## 実行計画チェックリスト

- [x] Step 1: ユニットコンテキスト分析（unit-of-work.md / unit-of-work-story-map.md 読み込み）
- [x] Step 2: Functional Design Plan 作成（本ファイル）
- [x] Step 3: 質問収集・回答受取
- [x] Step 4: 回答の曖昧さ解消（全問明確）
- [x] Step 5: Functional Design 成果物生成
  - [x] `domain-entities.md`
  - [x] `business-logic-model.md`
  - [x] `business-rules.md`
- [ ] Step 6: 承認・次ステージへ進行

---

## 質問一覧（[Answer]: タグで回答してください）

### Q1: DynamoDB テーブル構成

DynamoDB シングルテーブルの PK/SK 設計と GSI について確認します。

`unit-of-work.md` の スライス 0-2 / 0-8 では ArsTable のPK=`USER#{lineUserId}`、SKはエンティティ種別プレフィックスと定義されています。
ご褒美候補プール（`REWARD_POOL#`）のアクセスパターンとして、楽天API更新バッチが「全ユーザーの REWARD_POOL# を一括スキャン」する必要があります。

A) シングルテーブルのみ（全アクセスにPK必須、スキャンはしない設計）  
B) GSI-1 追加: `SK` をPartition Keyにして全ユーザーの特定エンティティを横断検索できるようにする  
C) GSI-1 追加: `entityType`（SK プレフィックス）をPartition Key にした専用GSI  
D) EventBridge バッチは DynamoDB スキャンを使う（コスト度外視で単純実装）  
E) その他（具体的に記述してください）

[Answer]: C
これで GSI1PK = "PREF_MEMORY" のQueryだけで全ユーザーの嗜好を取得可能。PROFILE にSTATUS属性を持たせれば、アクティブユーザーのフィルタリングもGSI上でできます。
ただしDynamoDB GSIの書き込みコスト（書き込みのたびにGSIも更新） は意識すべき。PREF_MEMORYやPROFILEは更新頻度が低いのでOK。CHAT#{timestamp}のような高頻度書き込みにはGSI属性を付けないこと。

---

### Q2: `schemas.py` の Pydantic モデル設計

DynamoDB に保存するデータを Python 側でどのレベルまで型定義するか選択してください。

A) 全エンティティを Pydantic v2 BaseModel で定義（厳密な型チェック）  
B) 主要エンティティのみ Pydantic モデル化、補助的な項目は dict のまま  
C) dataclass を使う（Pydantic 不要）  
D) TypedDict を使う（型ヒントのみ、バリデーションなし）  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q3: `bedrock_service.py` のモデル切り替え設計

Nova Micro / Nova Lite / Claude Haiku・Sonnet を切り替える設計について選択してください。

A) 環境変数（`BEDROCK_TEXT_MODEL_ID`, `BEDROCK_IMAGE_MODEL_ID`）で切り替え（SAM template.yaml の Parameters で定義）  
B) Secrets Manager / SSM Parameter Store に格納して実行時に取得  
C) `config.py` ファイルに定数として定義（変更時は再デプロイ）  
D) Lambda 呼び出し時のペイロードにモデルIDを含めて呼び出し元が指定  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q4: `line_service.py` の LINE SDK 利用方針

LINE Messaging API との通信に使うライブラリを選択してください。

A) `line-bot-sdk` Python 公式 SDK（v3）を使う  
B) `requests` で LINE API を直接呼ぶ（SDK不使用）  
C) `httpx`（非同期対応）で直接呼ぶ  
D) SDK v3 を使うが、薄いラッパー関数のみ（`reply_message`, `push_message`, `verify_signature`）に限定  
E) その他（具体的に記述してください）

[Answer]: D

---

### Q5: `secrets.py` の Secrets Manager 取得戦略

Lambda 起動時の Secrets Manager / SSM Parameter Store 取得方法を選択してください。

A) Lambdaハンドラ外（モジュールレベル）でキャッシュ取得（コールドスタート時のみ取得）  
B) AWS Lambda Extension（Parameter and Secrets Lambda Extension）を使ってローカルHTTPキャッシュ  
C) 毎回 Secrets Manager を呼ぶ（シンプルだがコスト高）  
D) A + B 組み合わせ（Extension優先、フォールバックでモジュールキャッシュ）  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q6: `logger.py` の構造化ログ設計

CloudWatch Logs への出力形式とPII保護の実装を選択してください。

A) `aws-lambda-powertools` の Logger を使う（JSON構造化ログ + correlation ID 自動付与）  
B) Python 標準 `logging` + JSON フォーマッタ（structlog 等）  
C) Python 標準 `logging` のテキストフォーマット（シンプル）  
D) `aws-lambda-powertools` Logger を使い、さらに LINE userId・チャット内容のマスク処理を `logger.py` に集約  
E) その他（具体的に記述してください）

[Answer]: D

---

### Q7: `google_calendar_service.py` の OAuth token リフレッシュ設計

Google OAuth の `refresh_token` から `access_token` を取得するフローについて確認します。
`access_token` は有効期限が1時間のため、毎回リフレッシュが必要になります。

A) 毎回 Google OAuth endpoint にリフレッシュリクエストを送る（シンプル）  
B) `access_token` を DynamoDB `GOOGLE_OAUTH#` SK に有効期限付きで一時キャッシュ（期限切れ時のみリフレッシュ）  
C) Lambda のメモリ内（グローバル変数）に `access_token` をキャッシュ（インスタンス生存中のみ有効）  
D) B + C 組み合わせ（まずメモリキャッシュ確認 → 期限切れなら DynamoDB → 期限切れなら Google へ）  
E) その他（具体的に記述してください）

[Answer]: A（毎回リフレッシュ）

---

### Q8: `google_calendar_service.py` のカレンダーイベント取得範囲

`get_today_events()` で取得する予定の時間範囲を選択してください。

A) 今日 0:00〜23:59（JST）の全イベント  
B) 現在時刻から±3時間（「今日の残り予定」に近い範囲）  
C) 今日の開始〜明日の開始（日単位でシンプルに）  
D) 今日 + 明日（翌日予定も考慮した提案ができるように）  
E) その他（具体的に記述してください）

[Answer]: D

---

### Q9: `dynamodb_service.py` のエラーハンドリング

DynamoDB 操作失敗時の挙動を選択してください。

A) `ClientError` をキャッチして独自例外（`DynamoDBError`）に変換し上位に伝播  
B) `ClientError` をキャッチしてログ出力後 `None` / 空リストを返す（呼び出し元で判断）  
C) `aws-lambda-powertools` の `Tracer` + リトライデコレータで自動リトライ（冪等性考慮）  
D) A + C 組み合わせ（リトライ後も失敗なら独自例外）  
E) その他（具体的に記述してください）

[Answer]: A

---

### Q10: `template.yaml` の Lambda Layer 設計

共通ライブラリ（`dynamodb_service`, `bedrock_service` 等）の配布方式を選択してください。

A) Lambda Layer として `src/` 全体をパッケージ化し、全 Lambda 関数がLayerを参照  
B) Lambda Layer を使わず、各 Lambda 関数のデプロイパッケージに共通コードを含める（単純だが重複）  
C) Lambda Layer を使う（`src/services/` + `src/utils/` + `src/models/` のみ Layer化）、`src/handlers/` は各関数のパッケージに含める  
D) Container Image Lambda（ECR）に統一してLayerは使わない  
E) その他（具体的に記述してください）

[Answer]: C

---

## 回答後の次ステップ

回答が完了したら以下の成果物を生成します:

1. `aidlc-docs/construction/unit-0/functional-design/domain-entities.md`
2. `aidlc-docs/construction/unit-0/functional-design/business-logic-model.md`  
3. `aidlc-docs/construction/unit-0/functional-design/business-rules.md`
