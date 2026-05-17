# NFR 設計 — Unit 7: LIFFダッシュボード

**Unit**: Unit 7  
**作成日**: 2026-05-16

---

## 1. LIFF ID Token 検証設計

### 簡易検証方式（ハッカソンスコープ）

LINE LIFF の ID Token は JWT 形式。完全な署名検証には LINE の JWK エンドポイントへのリクエストが必要だが、ハッカソンスコープでは以下の簡易方式を採用:

1. `liff.getIDToken()` で取得した JWT をデコード（base64）
2. ペイロードの `sub`（LINE ユーザー ID）を抽出
3. `aud`（audience）が自アプリの LIFF Channel ID と一致することを確認
4. `exp`（有効期限）が現在時刻より未来であることを確認

```python
def _extract_user_id(event: dict) -> str | None:
    token = event.get("headers", {}).get("authorization", "").replace("Bearer ", "")
    if not token:
        return None
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        # aud 検証
        if payload.get("aud") != os.environ.get("LIFF_CHANNEL_ID"):
            return None
        # exp 検証
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("sub")  # LINE ユーザー ID
    except Exception:
        return None
```

**注意**: `verify_signature=False` はハッカソンスコープの暫定措置。本番環境では LINE の公開鍵による署名検証が必要。

---

## 2. CORS 設計

API Gateway の CORS 設定:

```yaml
CorsConfiguration:
  AllowOrigins:
    - "https://liff.line.me"
  AllowMethods:
    - GET
    - PUT
    - OPTIONS
  AllowHeaders:
    - Authorization
    - Content-Type
  MaxAge: 86400
```

Lambda 側でも CORS ヘッダーを返す（API Gateway の自動設定が不十分な場合のフォールバック）。

---

## 3. レスポンスヘルパー設計

```python
def _make_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "https://liff.line.me",
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
        },
        "body": json.dumps(body, ensure_ascii=False, default=str),
    }
```

---

## 4. Decimal → int/str 変換設計

DynamoDB の Decimal 型は JSON シリアライズ不可。全レスポンスで以下の変換を適用:

```python
def _decimal_to_json(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
```

`json.dumps(body, default=_decimal_to_json)` で統一。
