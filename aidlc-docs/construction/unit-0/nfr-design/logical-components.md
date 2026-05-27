# Logical Components — Unit 0: SAM基盤 + 共通Layer

**作成日**: 2026-05-16

---

## 1. コンポーネント構成図

```
┌─────────────────────────────────────────────────────────────┐
│  Lambda Execution Context（ウォームインボケーションで再利用）        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Module-Level Singletons（コールドスタート時に初期化）      │   │
│  │                                                     │   │
│  │  _secret_cache: dict        ← SecretsService       │   │
│  │  _dynamodb_service          ← DynamoDBService      │   │
│  │  _bedrock_service           ← BedrockService       │   │
│  │  _line_service              ← LineService          │   │
│  │  _google_calendar_service   ← GoogleCalendarService│   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Handler │  │  Handler │  │  Handler │  │  Handler │  │
│  │  Unit 1  │  │  Unit 2  │  │  Unit 3  │  │  Unit 5  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
  ┌──────────────────────────────────────────────────────────┐
  │  Lambda Layer（src/services/ + src/utils/ + src/models/）  │
  │                                                          │
  │  DynamoDBService    BedrockService    LineService         │
  │  GoogleCalendarService               SecretsService      │
  │  Logger(PII mask)   exceptions.py    schemas.py          │
  └──────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
  │ DynamoDB │  │ Bedrock  │  │ LINE API │  │  Secrets Mgr │
  │ ArsTable │  │Nova Micro│  │ Reply/   │  │  ars/line-*  │
  │ GSI:     │  │Nova Lite │  │ Push/    │  │  ars/google-*│
  │ entityType│ │          │  │ Verify   │  │  ars/rakuten*│
  └──────────┘  └──────────┘  └──────────┘  └──────────────┘
                                                    │
                                              ┌─────────────┐
                                              │ Google      │
                                              │ Calendar API│
                                              │ OAuth 2.0   │
                                              └─────────────┘
```

---

## 2. サービスシングルトン初期化シーケンス

```
Lambda コールドスタート
  │
  ├─ secrets.py モジュールロード
  │    └─ _secret_cache = {}  （初期化のみ、まだ取得しない）
  │
  ├─ dynamodb_service.py モジュールロード
  │    └─ _dynamodb_service = None
  │
  ├─ bedrock_service.py モジュールロード
  │    └─ _bedrock_service = None
  │
  ├─ line_service.py モジュールロード
  │    └─ _line_service = None
  │
  └─ google_calendar_service.py モジュールロード
       └─ _google_calendar_service = None

Lambda ハンドラ 初回呼び出し
  │
  ├─ warmup check → {"source":"warmup"} なら即 return
  │
  ├─ get_line_service()
  │    ├─ _line_service is None → 初期化開始
  │    ├─ get_secret("LINE_SECRET_NAME")
  │    │    └─ Secrets Manager: ars/line-{stage} 取得 → キャッシュ
  │    └─ LineService(channel_secret, access_token) 作成 → キャッシュ
  │
  ├─ get_dynamodb_service()
  │    └─ DynamoDBService(table_name=env["DYNAMODB_TABLE_NAME"]) 作成 → キャッシュ
  │
  └─ ハンドラ処理実行

Lambda ウォームインボケーション（2回目以降）
  │
  └─ 全シングルトンキャッシュ済み → Secrets Manager / boto3 初期化なし
```

---

## 3. Secrets Manager 論理コンポーネント

### シークレット定義

```
AWS Secrets Manager
├── ars/line-dev
│   ├── LINE_CHANNEL_SECRET: "..."
│   └── LINE_ACCESS_TOKEN: "..."
│
├── ars/line-prod
│   ├── LINE_CHANNEL_SECRET: "..."
│   └── LINE_ACCESS_TOKEN: "..."
│
├── ars/google-dev
│   ├── GOOGLE_CLIENT_ID: "..."
│   └── GOOGLE_CLIENT_SECRET: "..."
│
├── ars/google-prod
│   ├── GOOGLE_CLIENT_ID: "..."
│   └── GOOGLE_CLIENT_SECRET: "..."
│
├── ars/rakuten-dev
│   └── RAKUTEN_APP_ID: "..."
│
└── ars/rakuten-prod
    └── RAKUTEN_APP_ID: "..."
```

### Lambda 環境変数マッピング

```yaml
# SAM template.yaml — Globals > Function > Environment > Variables
LINE_SECRET_NAME:    !Sub "ars/line-${StageName}"
GOOGLE_SECRET_NAME:  !Sub "ars/google-${StageName}"
RAKUTEN_SECRET_NAME: !Sub "ars/rakuten-${StageName}"
```

---

## 4. リトライロジック論理コンポーネント

```
外部 API 呼び出し
  │
  ├─ Bedrock（指数バックオフ）
  │    attempt 1 ──失敗──► wait 0.5s
  │    attempt 2 ──失敗──► wait 1.0s
  │    attempt 3 ──失敗──► raise BedrockError
  │    attempt N ──成功──► return response
  │
  ├─ LINE API（リトライなし）
  │    attempt 1 ──失敗──► raise LineServiceError（即時）
  │    attempt 1 ──成功──► return
  │
  └─ Google Calendar（固定インターバル）
       attempt 1 ──失敗(5xx/429)──► wait 1.0s
       attempt 2 ──失敗(5xx/429)──► wait 1.0s
       attempt 3 ──失敗──► raise GoogleCalendarError
       attempt N ──成功──► return response
```

---

## 5. EventBridge ウォームアップ 論理コンポーネント

```
EventBridge Scheduler
  ├─ WarmupWebhookScheduler（5分毎）
  │    └─ payload: {"source": "warmup"}
  │         └─► WebhookHandlerFunction
  │               └─ if event["source"] == "warmup": return 200
  │
  └─ WarmupBedrockScheduler（5分毎）
       └─ payload: {"source": "warmup"}
            └─► CharacterReplyFunction（Bedrock系代表）
                  └─ if event["source"] == "warmup": return 200
```

---

## 6. DynamoDB テーブル論理コンポーネント

```
ArsTable（オンデマンドキャパシティ）
│
├─ Primary Key
│   PK: USER#{lineUserId}
│   SK: エンティティ種別プレフィックス
│
├─ TTL
│   属性名: ttl（Unix epoch）
│   対象: CHAT# (30日), LIFELOG# (90日), PENDING_EXPENSE# (24時間)
│
├─ GSI: entityType-index
│   GSI1PK: entityType（PROFILE / PREF_MEMORY のみ付与）
│   GSI1SK: PK
│   用途: バッチ処理での全ユーザー横断クエリ
│
└─ 暗号化: SSE（AWS 管理キー）
   バックアップ: PITR（Point-In-Time Recovery）有効
```

---

## 7. Lambda Layer 論理コンポーネント

```
ArsCommonLayer
├─ python/
│   └─ src/
│       ├─ services/
│       │   ├─ dynamodb_service.py   ← シングルトン + DynamoDBError
│       │   ├─ bedrock_service.py    ← シングルトン + 指数バックオフリトライ
│       │   ├─ line_service.py       ← シングルトン + リトライなし
│       │   └─ google_calendar_service.py ← シングルトン + 固定インターバルリトライ
│       ├─ utils/
│       │   ├─ secrets.py    ← 複数シークレットキャッシュ
│       │   ├─ logger.py     ← PII マスク付き Powertools Logger
│       │   └─ exceptions.py ← 独自例外クラス
│       └─ models/
│           └─ schemas.py    ← Pydantic v2 全エンティティモデル
│
└─ requirements.txt
    ├─ pydantic>=2.0.0
    ├─ line-bot-sdk>=3.0.0
    ├─ aws-lambda-powertools>=3.0.0
    └─ requests>=2.31.0
```
