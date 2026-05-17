# NFR 要件 — Unit 7: LIFFダッシュボード

**Unit**: Unit 7  
**作成日**: 2026-05-16

---

## 1. パフォーマンス

| ID | 要件 | 目標値 |
|---|---|---|
| NFR-7-P1 | API レスポンス P99 | ≤ 500 ms（DynamoDB GetItem/Query のみ） |
| NFR-7-P2 | LIFF 初期表示（FCP） | ≤ 2 秒（静的ファイル + 1 API 呼び出し） |
| NFR-7-P3 | フロントエンドバンドルサイズ | ≤ 100 KB（Vanilla JS、フレームワークなし） |

## 2. セキュリティ

| ID | 要件 | 対応 |
|---|---|---|
| NFR-7-S1 | LIFF ID Token 検証 | LINE Channel ID による aud 検証 |
| NFR-7-S2 | CORS 制限 | LIFF オリジンのみ許可 |
| NFR-7-S3 | 設定更新はホワイトリスト方式 | 許可フィールドのみ update |
| NFR-7-S4 | API Gateway スロットリング | burst=200, rate=100（既存設定） |
| NFR-7-S5 | Content-Security-Policy | script-src 'self' + LIFF SDK CDN のみ |

## 3. 信頼性

| ID | 要件 | 対応 |
|---|---|---|
| NFR-7-R1 | DynamoDB エラー時は 500 + エラーメッセージ | 全ハンドラー |
| NFR-7-R2 | LIFF 初期化失敗時のフォールバック | エラー画面表示 |
| NFR-7-R3 | Google Revoke 失敗時も DynamoDB 削除は実行 | best-effort revoke |

## 4. 観測性

| ID | 要件 | 対応 |
|---|---|---|
| NFR-7-O1 | 全 API リクエストを structured logging | Lambda handler |
| NFR-7-O2 | 認証失敗は WARNING ログ | `_extract_user_id()` |
