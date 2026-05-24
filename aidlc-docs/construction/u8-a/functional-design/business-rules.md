# U8-A: ビジネスルール

---

## 1. 認証ルール

| ルールID | ルール | 条件 | アクション |
|---------|--------|------|----------|
| AUTH-01 | 全API認証必須 | Authorization ヘッダーなし or 無効 | 401 返却 |
| AUTH-02 | トークン有効期限 | AccessToken 期限切れ | 401 返却（クライアントでリフレッシュ） |
| AUTH-03 | デモログイン制限 | demo@example.com ユーザー | 書き込み許可（デモ体験のため） |
| AUTH-04 | ユーザーID解決 | Cognito sub → IDENTITY# 不在 | 新規ユーザー自動作成 |

---

## 2. 設定バリデーションルール

| ルールID | フィールド | ルール | エラーメッセージ |
|---------|-----------|--------|---------------|
| SET-01 | display_name | 1〜30文字（空文字列OK = 未設定） | "1〜30文字で入力してください" |
| SET-02 | display_name | トリム後に検証 | — |
| SET-03 | diary_time | HH:MM形式 (正規表現: `^([01]\d|2[0-3]):[0-5]\d$`) | "HH:MM形式で入力してください" |
| SET-04 | notification_enabled | boolean のみ | "true/false で指定してください" |
| SET-05 | monthly_surplus | 整数、0〜999999 | "0〜999999の整数で入力してください" |
| SET-06 | 部分更新 | リクエストに含まれるフィールドのみ更新 | — |
| SET-07 | 未知フィールド | リクエストに含まれる未知フィールドは無視 | — |

---

## 3. ユーザー作成ルール

| ルールID | ルール | 詳細 |
|---------|--------|------|
| USR-01 | 初回ログインで自動作成 | IDENTITY#COGNITO#{sub} が存在しなければ新規作成 |
| USR-02 | 内部ID形式 | UUID v4 |
| USR-03 | プロフィール初期値 | display_name="", diary_time="22:00", notification_enabled=true, monthly_surplus=0 |
| USR-04 | 冪等性 | 同一subでの再呼び出しは既存user_idを返す（重複作成しない） |
| USR-05 | タイムスタンプ | created_at, updated_at を ISO 8601 (UTC) で記録 |

---

## 4. API共通ルール

| ルールID | ルール | 詳細 |
|---------|--------|------|
| API-01 | レスポンス形式 | JSON (Content-Type: application/json) |
| API-02 | 日時形式 | ISO 8601 UTC (例: "2026-05-24T10:00:00Z") |
| API-03 | CORS | CloudFront オリジン + localhost:5173 (開発) |
| API-04 | リクエストボディ上限 | 1MB |
| API-05 | レート制限 | API Gateway デフォルト（10,000 req/s）で十分 |

---

## 5. Cognito User Pool ルール

| ルールID | ルール | 設定値 |
|---------|--------|--------|
| COG-01 | パスワードポリシー | 最小8文字、大文字+小文字+数字+記号 |
| COG-02 | MFA | 無効（MVP） |
| COG-03 | メール確認 | 必要（デモユーザーは事前確認済み） |
| COG-04 | セルフサインアップ | 有効 |
| COG-05 | ユーザー名属性 | email |
| COG-06 | App Client | パブリック（client secret なし、SRP認証） |
| COG-07 | トークン有効期限 | Access: 1h, ID: 1h, Refresh: 30d |
