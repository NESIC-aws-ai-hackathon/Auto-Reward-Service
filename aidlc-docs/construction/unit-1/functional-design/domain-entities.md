# ドメインエンティティ — Unit 1: LINE Bot基盤

**作成日**: 2026-05-16  
**Unit**: Unit 1 — LINE Bot基盤  
**対応要件**: F1-01, F1-02, F1-03, F1-04, SEC-01

---

## 概要

Unit 1 は新規ドメインエンティティを追加しない。  
LINE Webhook イベントの受信・検証・ルーティングに特化し、既存の Unit 0 サービス（`line_service`, `logger`, `secrets`）を利用する。

以下は Unit 1 で扱う **入出力データ構造** の定義。

---

## 入力データ構造

### WebhookEvent（API Gateway Proxy Event）

API Gateway HTTP API v2 から Lambda に渡されるイベントオブジェクト。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `headers` | `dict[str, str]` | HTTP ヘッダー（`x-line-signature` を含む） |
| `body` | `str` | LINE Webhook リクエストボディ（JSON 文字列） |
| `isBase64Encoded` | `bool` | ボディが Base64 エンコードされているか |
| `requestContext` | `dict` | API Gateway リクエストコンテキスト |

### LINE Webhook Body（パース後）

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `destination` | `str` | Bot のユーザー ID |
| `events` | `list[WebhookMessageEvent]` | イベント配列（通常 1 件） |

### WebhookMessageEvent

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `type` | `str` | `"message"` / `"follow"` / `"unfollow"` 等 |
| `replyToken` | `str` | Reply 用トークン（有効期限あり） |
| `source.userId` | `str` | LINE ユーザー ID（PII — ログ出力禁止） |
| `source.type` | `str` | `"user"` / `"group"` / `"room"` |
| `message.type` | `str` | `"text"` / `"image"` / `"sticker"` / `"video"` / `"audio"` / `"file"` / `"location"` |
| `message.text` | `str` | テキストメッセージの場合のみ |
| `message.id` | `str` | メッセージ ID |
| `timestamp` | `int` | ミリ秒タイムスタンプ |

---

## 出力データ構造

### Lambda レスポンス

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `statusCode` | `int` | `200`（正常）/ `403`（署名検証失敗） |
| `body` | `str` | `"OK"` または `"Forbidden"` |

---

## メッセージ種別分類

| message.type | Unit 1 での処理 | 将来ルーティング先 |
|-------------|----------------|-------------------|
| `text` | ルーティング対象 | Unit 2: `intent_classifier` → `character_reply` |
| `image` | ルーティング対象 | Unit 3: `receipt_analyzer` |
| `sticker` | 未対応応答 | — |
| `video` | 未対応応答 | — |
| `audio` | 未対応応答 | — |
| `file` | 未対応応答 | — |
| `location` | 未対応応答 | — |

---

## イベント種別分類

| event.type | Unit 1 での処理 |
|-----------|----------------|
| `message` | メッセージ種別ルーティング |
| `follow` | 将来 Unit 2 オンボーディング（Unit 1 では無視） |
| `unfollow` | 無視（200 返却のみ） |
| その他 | 無視（200 返却のみ） |
