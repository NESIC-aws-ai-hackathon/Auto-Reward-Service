# U8-A: ドメインエンティティ

---

## エンティティ関係図

```
┌──────────────────┐         ┌────────────────────┐
│ CognitoIdentity  │────────▶│   UserProfile      │
│ (IDENTITY#       │  1:1    │   (USER#{id} /     │
│  COGNITO#{sub})  │         │    PROFILE#)       │
└──────────────────┘         └────────────────────┘
                                      │
                                      │ 1:N (後続Unit)
                                      ▼
                             ┌────────────────────┐
                             │ CONVERSATION_TURN  │
                             │ LIFE_LOG           │
                             │ EXPENSE            │
                             │ STRESS_SUMMARY     │
                             │ ...                │
                             └────────────────────┘
```

---

## エンティティ定義

### CognitoIdentity

外部認証プロバイダ（Cognito）と内部ユーザーIDのマッピング。

| 属性 | 型 | 必須 | 説明 |
|------|------|------|------|
| PK | string | ✓ | `IDENTITY#COGNITO#{sub}` |
| SK | string | ✓ | `META#` |
| user_id | string | ✓ | 内部ユーザーID (UUID v4) |
| provider | string | ✓ | `"cognito"` |
| created_at | string | ✓ | ISO 8601 UTC |

### UserProfile

ユーザーのプロフィールと設定。

| 属性 | 型 | 必須 | デフォルト | 説明 |
|------|------|------|---------|------|
| PK | string | ✓ | — | `USER#{user_id}` |
| SK | string | ✓ | — | `PROFILE#` |
| display_name | string | ✓ | `""` | 表示名 (1〜30文字) |
| diary_time | string | ✓ | `"22:00"` | 日記生成時刻 (HH:MM) |
| notification_enabled | boolean | ✓ | `true` | Push通知ON/OFF |
| monthly_surplus | integer | ✓ | `0` | 余剰金月額 (円) |
| created_at | string | ✓ | — | ISO 8601 UTC |
| updated_at | string | ✓ | — | ISO 8601 UTC |

---

## SK一覧（全Unit共通定義）

U8-A の DataAccess で定数として定義。実データ作成は各Unitで行う。

| SK パターン | エンティティ | 作成Unit | 説明 |
|------------|------------|---------|------|
| `PROFILE#` | UserProfile | U8-A | ユーザー設定 |
| `VOICE_SESSION#{sessionId}` | VoiceSession | U8-B | 音声セッション |
| `CONVERSATION_TURN#{timestamp}` | ConversationTurn | U8-B | 会話ターン |
| `LIFE_LOG#{date}#{seq}` | LifeLog | U8-C | ライフログ |
| `DAILY_FUREMARU_SUMMARY#{date}` | DiarySummary | U8-C | 日記サマリ |
| `STRESS_SUMMARY#{date}` | StressSummary | U8-D | ストレス判定 |
| `EXPENSE#{timestamp}` | Expense | U8-C/D | 支出記録 |
| `REWARD_PERMIT#{timestamp}` | RewardPermit | U8-D | 回復実行 |
| `REWARD_SKIP#{timestamp}` | RewardSkip | U8-D | 回復スキップ |
| `MONTHLY_SUMMARY#{yyyy-mm}` | MonthlySummary | U8-C | 月次集計 |
| `PUSH_SUBSCRIPTION#` | PushSubscription | U8-C | Push購読 |

**PK例外:**
| PK パターン | SK | 説明 |
|------------|------|------|
| `IDENTITY#COGNITO#{sub}` | `META#` | Cognito→内部ID |
| `ANALYSIS_JOB#{jobId}` | `META#` | 分析ジョブ |
