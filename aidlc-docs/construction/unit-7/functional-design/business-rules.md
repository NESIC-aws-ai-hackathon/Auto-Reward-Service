# ビジネスルール — Unit 7: LIFFダッシュボード

**Unit**: Unit 7 — LIFFダッシュボード（F8 対応）+ カレンダー連携UI（F9-02）  
**作成日**: 2026-05-16

---

## 1. 認証・認可ルール

| ID | ルール | 実装箇所 |
|---|---|---|
| BR-7-01 | LIFF ID Token を Authorization ヘッダーで受け取り、LINE ユーザー ID を抽出 | `_extract_user_id()` |
| BR-7-02 | ID Token 未送信 / 無効な場合は 401 Unauthorized を返す | `_extract_user_id()` |
| BR-7-03 | ユーザーは自身のデータのみ参照・更新可能（PK=USER#{自分のID}） | 全 API ハンドラー |

---

## 2. 設定更新ルール

| ID | ルール | 値 | 実装箇所 |
|---|---|---|---|
| BR-7-04 | tone は `friendly`, `polite`, `devilish` のいずれか | 3値のみ許可 | `handle_update_settings()` |
| BR-7-05 | reward_budget_monthly は正の整数（0 以下は拒否） | > 0 | `handle_update_settings()` |
| BR-7-06 | carryover_rate は 0.0〜1.0 の範囲 | [0.0, 1.0] | `handle_update_settings()` |
| BR-7-07 | nickname は 1〜20 文字 | len 1-20 | `handle_update_settings()` |
| BR-7-08 | バリデーション違反は 400 Bad Request を返す | — | `handle_update_settings()` |
| BR-7-09 | 許可されていないフィールドは無視する（ホワイトリスト方式） | — | `handle_update_settings()` |

---

## 3. データ表示ルール

| ID | ルール | 実装箇所 |
|---|---|---|
| BR-7-10 | 支出履歴は直近 50 件まで（パフォーマンス制約） | `handle_expenses()` |
| BR-7-11 | ご褒美提案履歴は直近 20 件まで | `handle_history()` |
| BR-7-12 | ご褒美候補プールはスコア降順で返す | `handle_pool()` |
| BR-7-13 | MonthlyExpenseSummary が存在しない月は全項目 0 を返す | `handle_dashboard()` |
| BR-7-14 | DynamoDB 金額は int にキャストして JSON 返却（Decimal は JSON 非対応） | 全 API レスポンス |

---

## 4. カレンダー連携ルール

| ID | ルール | 実装箇所 |
|---|---|---|
| BR-7-15 | Google OAuth scope は `calendar.events.readonly` のみ | `handle_calendar_connect()` |
| BR-7-16 | OAuth state パラメータに user_id を含める（CSRF 防止） | `handle_calendar_connect()` |
| BR-7-17 | 連携解除時は Google Token Revoke API を呼び出す（best-effort） | `handle_calendar_disconnect()` |
| BR-7-18 | 連携解除時は DynamoDB から GOOGLE_OAUTH# を削除 | `handle_calendar_disconnect()` |
| BR-7-19 | Revoke 失敗は WARNING ログのみ（DynamoDB 削除は実行） | `handle_calendar_disconnect()` |

---

## 5. エラーハンドリングルール

| ID | ルール | 実装箇所 |
|---|---|---|
| BR-7-20 | DynamoDB エラーは 500 Internal Server Error を返す | 全ハンドラー |
| BR-7-21 | 未対応ルートは 404 Not Found を返す | `handler()` ルーター |
| BR-7-22 | CORS ヘッダーを全レスポンスに付与 | `_make_response()` |
| BR-7-23 | JSON パースエラーは 400 Bad Request を返す | PUT ハンドラー |

---

## 6. フロントエンドルール

| ID | ルール | 実装箇所 |
|---|---|---|
| BR-7-24 | LIFF 初期化失敗時はエラーメッセージを表示 | `app.js` |
| BR-7-25 | 未ログイン時は `liff.login()` にリダイレクト | `app.js` |
| BR-7-26 | API 呼び出し時は ID Token を Authorization Bearer ヘッダーに付与 | `app.js` |
| BR-7-27 | 金額表示は ¥ + カンマ区切り（例: ¥24,000） | `app.js` |
