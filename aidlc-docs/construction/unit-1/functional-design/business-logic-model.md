# ビジネスロジックモデル — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**Unit**: Unit 1 — LINE Bot基盤  
**対応要件**: F1-01, F1-02, F1-03, F1-04, SEC-01

---

## 概要

WebhookHandler は LINE Platform からの Webhook を受信し、署名検証 → イベント解析 → メッセージルーティング → Reply 送信を **同期的に** 10 秒以内で完結する単一 Lambda 関数。

---

## 処理フロー

```
API Gateway POST /webhook
        │
        ▼
┌─────────────────────────────┐
│  1. ウォームアップ判定       │──→ warmup → 即 200 返却
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  2. 署名検証                │──→ 失敗 → 403 返却
│     X-Line-Signature        │
└─────────────────────────────┘
        │ 成功
        ▼
┌─────────────────────────────┐
│  3. Body パース             │──→ JSON パース失敗 → 200 返却（ログのみ）
│     events 配列取得          │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  4. イベントループ           │
│     for event in events:    │
│       route_event(event)     │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  5. 200 OK 返却             │
└─────────────────────────────┘
```

---

## 関数定義

### `handler(event, context) -> dict`

Lambda エントリポイント。API Gateway HTTP API v2 プロキシ統合イベントを受け取る。

**入力**:
- `event`: API Gateway HTTP API v2 プロキシイベント
- `context`: Lambda コンテキスト

**出力**:
- `{"statusCode": 200, "body": "OK"}` — 正常時
- `{"statusCode": 403, "body": "Forbidden"}` — 署名検証失敗時

**処理手順**:
1. ウォームアップ判定: `event.get("source") == "warmup"` なら即 `{"statusCode": 200}` 返却
2. `headers` から `x-line-signature` を取得（大文字小文字不問で検索）
3. `body` を取得（`isBase64Encoded` が `True` なら Base64 デコード）
4. `line_service.verify_signature(body, signature)` で署名検証 → 失敗時 403
5. `body` を JSON パース → `events` 配列を取得
6. 各 event に対して `_route_event(event)` を呼び出し
7. 例外発生時は `_handle_error(event, error)` でフォールバック
8. 最後に `{"statusCode": 200, "body": "OK"}` を返却

---

### `_route_event(event: dict) -> None`

イベント種別に応じて処理を振り分ける。

**処理手順**:
1. `event["type"]` を判定
2. `"message"` の場合 → `_route_message(event)` を呼び出し
3. `"follow"` の場合 → Unit 1 では無視（ログ出力のみ）。Unit 2 でオンボーディング追加
4. その他 → 無視（ログ出力のみ）

---

### `_route_message(event: dict) -> None`

メッセージ種別に応じて処理を振り分ける。Unit 1 時点ではスタブ実装（Unit 2 以降で実装を追加）。

**入力**:
- `event`: LINE Webhook メッセージイベント

**処理手順**:
1. `event["message"]["type"]` を判定
2. `"text"` の場合:
   - Unit 1 スタブ: エコー応答（受信テキストをそのまま Reply）
   - Unit 2 以降: `intent_classifier` → `character_reply` に差し替え
3. `"image"` の場合:
   - Unit 1 スタブ: 「画像を受け取ったよ！」と固定応答
   - Unit 3 以降: `receipt_analyzer` に差し替え
4. その他（`sticker`, `video`, `audio`, `file`, `location`）:
   - `UNSUPPORTED_REPLIES` リストからランダムに 1 つ選択して Reply

**UNSUPPORTED_REPLIES 定数**:
```python
UNSUPPORTED_REPLIES = [
    "スタンプかわいい〜！でもリワードちゃん、文字の方が得意なんだ😊",
    "ん〜それはまだ読めないかも！テキストで話しかけてくれると嬉しいな〜",
    "おっ、それ気になる！…けど今はテキストだけ対応してるんだ〜ごめんね🥲",
]
```

---

### `_handle_error(event: dict, error: Exception) -> None`

処理中に例外が発生した場合のフォールバック。ユーザーにはリワードちゃん口調でエラーを通知。

**入力**:
- `event`: 処理中の LINE Webhook イベント
- `error`: 発生した例外

**処理手順**:
1. `logger.exception()` でエラーログ出力（PII マスク付き）
2. `event` から `replyToken` を取得可能な場合:
   - `ERROR_REPLY` 固定文言を Reply 送信
   - Reply 送信自体が失敗した場合はログのみ（二重障害を防ぐ）
3. `replyToken` が取得できない場合:
   - ログ出力のみ

**ERROR_REPLY 定数**:
```python
ERROR_REPLY = "ちょっと調子が悪いみたい…またあとで話しかけてね🥲"
```

---

## LineService 利用パターン

Unit 1 では Unit 0 で実装済みの `LineService` を以下のように利用する。

| 操作 | メソッド | 引数 |
|------|---------|------|
| 署名検証 | `line_service.verify_signature(body, signature)` | body: str, signature: str |
| Reply 送信 | `line_service.reply_message(reply_token, messages)` | reply_token: str, messages: list[TextMessage] |

### LineService インスタンス管理

```python
# モジュールレベルでキャッシュ（コールドスタート時のみ初期化）
_line_service: LineService | None = None

def _get_line_service() -> LineService:
    global _line_service
    if _line_service is None:
        secrets = get_line_secrets()
        _line_service = LineService(
            channel_secret=secrets["channel_secret"],
            channel_access_token=secrets["channel_access_token"],
        )
    return _line_service
```

---

## 同期処理フロー（Q1 回答反映）

Webhook → 署名検証 → メッセージルーティング → ビジネスロジック → Reply 送信 を **同一 Lambda 実行内で同期的に** 処理する。

**理由**:
- タイムアウト 10 秒で Bedrock 2 回呼び出し（Intent + Reply）は十分収まる
- 非同期 invoke にすると Reply Token の管理が複雑になるだけ
- LINE Platform は Webhook に対して 200 を返すだけで Reply Token の有効期限は別管理（1 分間有効）

---

## 将来拡張ポイント

| 拡張内容 | 追加 Unit | 変更箇所 |
|---------|----------|---------|
| Intent 分類・キャラ応答 | Unit 2 | `_route_message()` の text 分岐 |
| レシート解析 | Unit 3 | `_route_message()` の image 分岐 |
| follow イベントでオンボーディング | Unit 2 | `_route_event()` の follow 分岐 |
