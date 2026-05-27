# インフラ設計 — Unit 7: LIFFダッシュボード

**Unit**: Unit 7  
**作成日**: 2026-05-16

---

## 1. 新規 Lambda 関数

### LiffApiFunction

| 項目 | 値 |
|---|---|
| FunctionName | LiffApiFunction |
| Handler | handlers.liff_api.handler |
| CodeUri | src/ |
| MemorySize | 256 |
| Timeout | 10 |
| Role | ArsLambdaRole（既存共有） |

### 環境変数

| 変数名 | 値 | 説明 |
|---|---|---|
| LIFF_CHANNEL_ID | （LINE Developers Console で取得） | ID Token の aud 検証用 |

---

## 2. API Gateway 追加ルート

既存の `WebhookApi` (HttpApi) にルートを追加:

```yaml
Events:
  LiffDashboard:
    Type: HttpApi
    Properties:
      ApiId: !Ref WebhookApi
      Path: /api/{proxy+}
      Method: ANY
```

`{proxy+}` で全 `/api/*` パスをキャッチし、Lambda 側でルーティング。

### CORS 設定

```yaml
WebhookApi:
  Type: AWS::Serverless::HttpApi
  Properties:
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

---

## 3. LIFF 静的ファイル配信

### 方式A: S3 + CloudFront（推奨、ただしハッカソンスコープ外）

S3 バケットに `liff/` ディレクトリの内容をデプロイし、CloudFront で HTTPS 配信。LIFF URL にこの CloudFront ドメインを設定。

### 方式B: Lambda レスポンス直接配信（ハッカソンスコープ）

`GET /liff` で HTML を直接返す方式。追加インフラ不要。

```python
# liff_api.py に追加
def _serve_liff_html() -> dict:
    html = (Path(__file__).parent / "liff" / "index.html").read_text()
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": html,
    }
```

**採用方式**: 方式B（Lambda 直接配信）。ハッカソンの速度感を優先。`liff/` ディレクトリを `src/handlers/liff/` に配置。

---

## 4. template.yaml 差分

```yaml
  # ─────────────────────────────────────────
  # Lambda Functions（Unit 7）
  # ─────────────────────────────────────────
  LiffApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: LiffApiFunction
      Handler: handlers.liff_api.handler
      CodeUri: src/
      MemorySize: 256
      Timeout: 10
      Role: !GetAtt ArsLambdaRole.Arn
      Environment:
        Variables:
          LIFF_CHANNEL_ID: "YOUR_LIFF_CHANNEL_ID"
      Events:
        LiffApiProxy:
          Type: HttpApi
          Properties:
            ApiId: !Ref WebhookApi
            Path: /api/{proxy+}
            Method: ANY
        LiffPage:
          Type: HttpApi
          Properties:
            ApiId: !Ref WebhookApi
            Path: /liff
            Method: GET

  LiffApiFunctionLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub "/aws/lambda/${LiffApiFunction}"
      RetentionInDays: 30
```

### Outputs 追加

```yaml
  LiffApiEndpoint:
    Description: LIFF Dashboard URL
    Value: !Join
      - ""
      - - !GetAtt WebhookApi.ApiEndpoint
        - "/liff"
  LiffApiFunctionArn:
    Description: LIFF API Lambda ARN
    Value: !GetAtt LiffApiFunction.Arn
```

---

## 5. SchedulerExecutionRole 更新

LiffApiFunction の Arn は Scheduler 対象外のため変更不要。

---

## 6. IAM ポリシー

既存 `ArsLambdaRole` でカバー済み（DynamoDB CRUD + Secrets Manager）。追加変更なし。

---

## 7. LINE Developers Console 設定（手動）

LIFF App デプロイ後に手動設定が必要:

1. LINE Developers Console → LIFF アプリ追加
2. エンドポイント URL: `{WebhookApi.ApiEndpoint}/liff`
3. サイズ: Full（全画面）
4. LIFF ID を取得 → `template.yaml` の `LIFF_CHANNEL_ID` に設定
5. 再デプロイ
