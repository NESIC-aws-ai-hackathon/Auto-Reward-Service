# ビジネスロジックモデル — Unit 7: LIFFダッシュボード

**Unit**: Unit 7 — LIFFダッシュボード（F8 対応）+ カレンダー連携UI（F9-02）  
**作成日**: 2026-05-16  
**対応要件**: F8-01〜F8-04, F9-02

---

## 1. アーキテクチャ概要

```
LINE アプリ
  │  ← LIFF URL (liff.init + getProfile)
  └──► S3 Static Website ← CloudFront (HTTPS)
          │
          │ fetch("/api/...")
          └──► API Gateway (HttpApi) ──► LiffApiFunction (Lambda)
                                              │
                                              ├─ GET /api/dashboard   → ダッシュボード統合
                                              ├─ GET /api/history     → ご褒美提案履歴
                                              ├─ GET /api/expenses    → 支出履歴
                                              ├─ GET /api/pool        → ご褒美候補一覧
                                              ├─ GET /api/settings    → 設定取得
                                              ├─ PUT /api/settings    → 設定更新
                                              ├─ GET /api/calendar/status → カレンダー連携状態
                                              ├─ POST /api/calendar/connect → OAuth開始URL生成
                                              ├─ POST /api/calendar/disconnect → 連携解除
                                              └─► DynamoDB (ArsTable)
```

**LIFF認証フロー:**
1. ユーザーが LINE アプリ内で LIFF URL を開く
2. `liff.init()` → `liff.getProfile()` → LINE ユーザー ID 取得
3. `liff.getIDToken()` → ID Token を HTTP ヘッダーに付与してAPI呼び出し
4. Lambda 側で ID Token を検証し、LINE ユーザー ID を抽出

---

## 2. 主要フロー

### 2-A: ダッシュボード取得フロー（GET /api/dashboard）

```
LiffApiFunction.handle_dashboard(user_id)
  │
  ├─[1] プロファイル取得: DDB.get_item(USER#{id}, PROFILE#) → tone, nickname
  │
  ├─[2] 今月サマリー取得: DDB.get_item(USER#{id}, MONTHLY_SUMMARY#{YYYY-MM})
  │       → total_amount, total_budget, carryover_amount, remaining
  │
  ├─[3] 今月の支出件数: summary.expense_count
  │
  ├─[4] 最新提案取得: DDB.query(USER#{id}, REWARD_SUGGESTION#, limit=3, desc=True)
  │
  └─[5] レスポンス構築:
          {
            "nickname": str,
            "tone": str,
            "monthly_summary": {
              "total_budget": int,
              "total_spent": int,
              "remaining": int,
              "carryover_amount": int,
              "expense_count": int,
            },
            "recent_suggestions": [
              {"item_name": str, "price": int, "proposed_at": str, "outcome": str},
            ]
          }
```

### 2-B: 支出履歴取得フロー（GET /api/expenses）

```
LiffApiFunction.handle_expenses(user_id, month=None)
  │
  ├─[1] month = request.query["month"] or 今月の "YYYY-MM"
  │
  ├─[2] DDB.query(USER#{id}, EXPENSE#{month}, desc=True, limit=50)
  │
  └─[3] レスポンス: { "month": str, "expenses": [{item_name, amount, ars_category, created_at}] }
```

### 2-C: ご褒美提案履歴取得フロー（GET /api/history）

```
LiffApiFunction.handle_history(user_id, limit=20)
  │
  ├─[1] DDB.query(USER#{id}, REWARD_SUGGESTION#, desc=True, limit=20)
  │
  └─[2] レスポンス: { "suggestions": [{item_name, price, proposed_at, outcome}] }
```

### 2-D: ご褒美候補一覧取得フロー（GET /api/pool）

```
LiffApiFunction.handle_pool(user_id)
  │
  ├─[1] DDB.get_item(USER#{id}, REWARD_POOL#)
  │       → items をスコア降順ソート
  │
  └─[2] レスポンス: { "items": [{name, price, category, score, type, image_url, source_url}] }
```

### 2-E: 設定取得フロー（GET /api/settings）

```
LiffApiFunction.handle_get_settings(user_id)
  │
  ├─[1] DDB.get_item(USER#{id}, PROFILE#)
  │
  └─[2] レスポンス: {
          "tone": str,                    # friendly / polite / devilish
          "reward_budget_monthly": int,
          "bonus_months": [int],
          "bonus_amount": int,
          "carryover_rate": float,
          "nickname": str,
        }
```

### 2-F: 設定更新フロー（PUT /api/settings）

```
LiffApiFunction.handle_update_settings(user_id, body)
  │
  ├─[1] リクエストバリデーション:
  │       tone: must be in ["friendly", "polite", "devilish"]
  │       reward_budget_monthly: int > 0 (optional)
  │       carryover_rate: 0.0 <= x <= 1.0 (optional)
  │       nickname: str, 1-20文字 (optional)
  │
  ├─[2] DDB.update_item(USER#{id}, PROFILE#, {validated fields})
  │
  └─[3] レスポンス: { "updated": true }
```

### 2-G: カレンダー連携状態（GET /api/calendar/status）

```
LiffApiFunction.handle_calendar_status(user_id)
  │
  ├─[1] DDB.get_item(USER#{id}, GOOGLE_OAUTH#)
  │
  └─[2] レスポンス: { "connected": bool, "connected_at": str | null }
```

### 2-H: カレンダー連携開始（POST /api/calendar/connect）

```
LiffApiFunction.handle_calendar_connect(user_id)
  │
  ├─[1] Google OAuth 同意画面 URL を生成
  │       scope: calendar.events.readonly
  │       redirect_uri: LIFF Callback URL
  │       state: user_id の暗号化トークン
  │
  └─[2] レスポンス: { "auth_url": str }
```

### 2-I: カレンダー連携解除（POST /api/calendar/disconnect）

```
LiffApiFunction.handle_calendar_disconnect(user_id)
  │
  ├─[1] DDB.get_item(USER#{id}, GOOGLE_OAUTH#)
  │       → refresh_token を取得
  │
  ├─[2] Google Token Revoke API を呼び出し（best-effort）
  │
  ├─[3] DDB.delete_item(USER#{id}, GOOGLE_OAUTH#)
  │
  └─[4] レスポンス: { "disconnected": true }
```

---

## 3. LIFF フロントエンド構成

### SPA 構成（最小 HTML + Vanilla JS）

```
liff/
  ├── index.html       # メインページ（SPA ルーター）
  ├── style.css        # スタイルシート
  └── app.js           # LIFF SDK 初期化 + API 呼び出し + DOM 操作
```

**画面遷移（タブ切り替え）:**

| タブ | 画面 | API |
|---|---|---|
| ホーム | 今月のサマリー + 最新提案 | GET /api/dashboard |
| 支出 | 支出履歴リスト | GET /api/expenses |
| ご褒美 | 提案履歴 + 候補一覧 | GET /api/history, GET /api/pool |
| 設定 | 口調・予算変更 + カレンダー連携 | GET/PUT /api/settings, GET/POST /api/calendar/* |

**LIFF SDK 利用メソッド:**
- `liff.init({liffId})` — 初期化
- `liff.isLoggedIn()` — ログイン状態チェック
- `liff.login()` — 未ログイン時にリダイレクト
- `liff.getProfile()` — 表示名・アイコン取得
- `liff.getIDToken()` — API 認証用 ID Token 取得
