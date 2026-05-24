# U8-A: ビジネスロジックモデル

## 概要

U8-A は Unit 8 全体の土台を構築する。認証付きPWAが動作する最小構成。

---

## 1. 認証フロー

### 1.1 通常サインイン

```
ユーザー → サインイン画面 → email/password入力
  → Cognito authenticateUser
  → 成功: AccessToken + IdToken + RefreshToken 取得
  → AuthContext に保存 → トップ画面（/chat）へリダイレクト
  → 失敗: エラーメッセージ表示
```

### 1.2 デモログイン

```
ユーザー → 「デモで試す」ボタン押下
  → 内部的に email=demo@example.com, password=DemoPass123! で Cognito サインイン
  → 以降は通常サインインと同じ
```

**デモユーザー仕様:**
- メール: `demo@example.com`
- パスワード: `DemoPass123!`（Cognito User Pool 作成時に事前登録、確認済み状態）
- 内部ID: `IDENTITY#COGNITO#{demo-sub}` → `USER#{demo-user-id}`
- デモデータ初期化: 将来拡張（U8-A では保存のみ）

### 1.3 トークン管理

| トークン | 用途 | 保存先 | 有効期限 |
|---------|------|--------|---------|
| AccessToken | API認証 (Authorization ヘッダー) | メモリ (React state) | 1時間 |
| IdToken | ユーザー情報取得 | メモリ | 1時間 |
| RefreshToken | トークン再発行 | localStorage (暗号化不要、Cognito SDK管理) | 30日 |

**自動リフレッシュ:**
- API呼び出し前にAccessToken有効期限チェック
- 期限切れ5分前で自動リフレッシュ
- RefreshToken期限切れ → サインイン画面へリダイレクト

---

## 2. ユーザーID解決

### 2.1 初回ログイン

```
1. Cognito認証成功 → sub (UUID) 取得
2. DynamoDB: GetItem(PK="IDENTITY#COGNITO#{sub}", SK="META#")
3. 存在しない場合:
   a. 新規内部ID生成 (UUID v4)
   b. PutItem(PK="IDENTITY#COGNITO#{sub}", SK="META#", {user_id: "..."})
   c. PutItem(PK="USER#{user_id}", SK="PROFILE#", {display_name: "", ...})
4. 存在する場合: user_id を返却
```

### 2.2 データモデル

**IDENTITY#COGNITO#{sub} / META#:**
```json
{
  "PK": "IDENTITY#COGNITO#{sub}",
  "SK": "META#",
  "user_id": "uuid-v4",
  "created_at": "2026-05-24T10:00:00Z",
  "provider": "cognito"
}
```

**USER#{user_id} / PROFILE#:**
```json
{
  "PK": "USER#{user_id}",
  "SK": "PROFILE#",
  "display_name": "",
  "diary_time": "22:00",
  "notification_enabled": true,
  "monthly_surplus": 0,
  "created_at": "2026-05-24T10:00:00Z",
  "updated_at": "2026-05-24T10:00:00Z"
}
```

---

## 3. 設定管理

### 3.1 設定項目

| 項目 | フィールド名 | 型 | デフォルト | バリデーション |
|------|------------|------|---------|-------------|
| ユーザー名（表示名） | `display_name` | string | "" | 1〜30文字 |
| 日記サマリ生成時刻 | `diary_time` | string | "22:00" | HH:MM形式、00:00〜23:59 |
| 通知ON/OFF | `notification_enabled` | boolean | true | — |
| 余剰金月額設定 | `monthly_surplus` | integer | 0 | 0〜999999（円） |

### 3.2 設定API

**GET /api/settings**
```json
// Response 200
{
  "display_name": "たろう",
  "diary_time": "22:00",
  "notification_enabled": true,
  "monthly_surplus": 30000
}
```

**PUT /api/settings**
```json
// Request Body（部分更新可能）
{
  "display_name": "たろう",
  "diary_time": "23:00",
  "notification_enabled": false,
  "monthly_surplus": 25000
}

// Response 200
{
  "message": "ok",
  "updated_fields": ["display_name", "diary_time", "notification_enabled", "monthly_surplus"]
}
```

**バリデーションエラー:**
```json
// Response 400
{
  "error": "validation_error",
  "details": [
    {"field": "display_name", "message": "1〜30文字で入力してください"},
    {"field": "monthly_surplus", "message": "0〜999999の整数で入力してください"}
  ]
}
```

---

## 4. API Gateway ルーティング基盤

### 4.1 認証ミドルウェア

```
1. リクエスト受信
2. Authorization ヘッダーから Bearer token 抽出
3. Cognito JWT 検証（署名 + 有効期限 + issuer + audience）
4. claims["sub"] 取得
5. resolve_user_id(sub) → user_id
6. ハンドラーに user_id を渡す
```

### 4.2 エラーレスポンス標準

| HTTP Status | error code | 用途 |
|-------------|-----------|------|
| 400 | `validation_error` | バリデーション失敗 |
| 401 | `unauthorized` | 認証失敗/トークン無効 |
| 403 | `forbidden` | 権限なし |
| 404 | `not_found` | リソース不在 |
| 500 | `internal_error` | サーバーエラー |

### 4.3 CORS設定

```
Access-Control-Allow-Origin: CloudFront URL (本番) / localhost:5173 (開発)
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
```

---

## 5. DataAccess Layer

### 5.1 SK定数定義

全Unitで使用するSKフォーマットをU8-Aで確定する。

```python
# SK定数
SK_PROFILE = "PROFILE#"
SK_VOICE_SESSION = "VOICE_SESSION#{session_id}"
SK_ANALYSIS_JOB_META = "META#"  # PK=ANALYSIS_JOB#{job_id} と組み合わせ
SK_CONVERSATION_TURN = "CONVERSATION_TURN#{timestamp}"
SK_LIFE_LOG = "LIFE_LOG#{date}#{seq}"
SK_DAILY_FUREMARU_SUMMARY = "DAILY_FUREMARU_SUMMARY#{date}"
SK_STRESS_SUMMARY = "STRESS_SUMMARY#{date}"
SK_EXPENSE = "EXPENSE#{timestamp}"
SK_REWARD_PERMIT = "REWARD_PERMIT#{timestamp}"
SK_REWARD_SKIP = "REWARD_SKIP#{timestamp}"
SK_MONTHLY_SUMMARY = "MONTHLY_SUMMARY#{yyyy_mm}"
SK_PUSH_SUBSCRIPTION = "PUSH_SUBSCRIPTION#"
```

### 5.2 ヘルパーメソッド

| メソッド | 用途 |
|---------|------|
| `put_item(pk, sk, data)` | アイテム作成/上書き |
| `get_item(pk, sk)` | 単一アイテム取得 |
| `query_by_prefix(pk, sk_prefix, limit)` | SK前方一致クエリ |
| `query_between(pk, sk_start, sk_end)` | SK範囲クエリ |
| `update_item(pk, sk, updates)` | 部分更新 |
| `delete_item(pk, sk)` | アイテム削除 |
| `batch_put(items)` | バッチ書き込み |
| `resolve_user_id(cognito_sub)` | Cognito sub → 内部ID |
| `get_or_create_profile(user_id)` | プロフィール取得/初期作成 |

---

## 6. PWA Service Worker

### 6.1 責務（U8-A時点）

- 静的ファイルキャッシュ（App Shell戦略）
- PWA インストールプロンプト対応
- Push通知受信の骨格（U8-Cで有効化）

### 6.2 キャッシュ戦略

| リソース | 戦略 |
|---------|------|
| HTML/JS/CSS (ビルド済み) | Cache First (ハッシュ付きファイル名で自動更新) |
| API レスポンス | Network First (キャッシュなし) |
| 画像 (アバター等) | Cache First |
