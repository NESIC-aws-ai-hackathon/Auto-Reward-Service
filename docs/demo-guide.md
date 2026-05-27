# Demo Mode 操作ガイド

## 概要

Demo Mode は、ハッカソンプレゼン動画撮影用の自動再生デモです。  
本番と同じ画面を表示しつつ、API を一切呼ばずモックデータでシナリオを自動再生します。

---

## アクセス方法

| 環境 | URL |
|------|-----|
| 本番 (CloudFront) | `https://d39spqovcq7od.cloudfront.net/demo` |
| ローカル | `http://localhost:5173/demo` |

認証（Cognito ログイン）不要で直接アクセスできます。

---

## URL パラメータ

| パラメータ | 値 | 説明 |
|---|---|---|
| `scenario` | シナリオID | 指定シナリオを自動ロード＆再生 |
| `hideControls` | `1` | コントロールパネルを非表示（録画向き） |

### 例

```
/demo?scenario=chat-expense&hideControls=1
```

---

## コントロールパネル操作

画面右に表示されるパネル（`hideControls=1` で非表示）:

| ボタン | 動作 |
|--------|------|
| **▶ 再生** | シナリオを最初から/一時停止位置から再生 |
| **⏸ 停止** | 一時停止（現在位置を保持） |
| **⟲ 最初から** | リセットして先頭から再生 |
| **◀ 前へ** | 1ステップ戻る（簡易: 先頭から再実行） |
| **次へ ▶** | 1ステップだけ進める |
| **速度** | 0.5x / 0.75x / 1x / 1.5x / 2x |
| **シナリオ** | ドロップダウンでシナリオ切替 |

---

## シナリオ一覧

| ID | タイトル | 内容 | 想定時間 |
|---|---|---|---|
| `onboarding` | オンボーディング | 名前→予算→好きなもの→日記時刻を設定 | 22秒 |
| `voice-chat` | ボイスチャット | マイク発光→文字起こし→応答演出 | 16秒 |
| `chat-expense` | 会話で支出記録 | 「プリン買った」→支出作成→ダッシュ更新→ライフログ | 14秒 |
| `receipt` | レシートアップロード | 撮影→OCR→解析結果→確認→反映 | 14秒 |
| `dashboard` | ダッシュボード | 余剰金/回復費/気分スコアのカウントアップ | 9秒 |
| `diary` | ライフログ・日記 | 朝/昼/夕/夜→日記自動生成 | 14秒 |
| `recovery` | リカバリー提案 | ストレス検知→0円回復→商品候補 | 14秒 |
| `reward-carryover` | ごほうび繰越 | 余剰持ち越し / マイナスリセット演出 | 10秒 |
| `recommendation` | 推薦元の使い分け | 楽天/ホットペッパー/YouTube/Amazon | 14秒 |
| `full` | フルデモ | 上記1-9を順番に連続再生 | 約3-5分 |

---

## 録画用URL一覧（コピペ用）

```
https://d39spqovcq7od.cloudfront.net/demo?scenario=onboarding&hideControls=1
https://d39spqovcq7od.cloudfront.net/demo?scenario=voice-chat&hideControls=1
https://d39spqovcq7od.cloudfront.net/demo?scenario=chat-expense&hideControls=1
https://d39spqovcq7od.cloudfront.net/demo?scenario=receipt&hideControls=1
https://d39spqovcq7od.cloudfront.net/demo?scenario=dashboard&hideControls=1
https://d39spqovcq7od.cloudfront.net/demo?scenario=diary&hideControls=1
https://d39spqovcq7od.cloudfront.net/demo?scenario=recovery&hideControls=1
https://d39spqovcq7od.cloudfront.net/demo?scenario=reward-carryover&hideControls=1
https://d39spqovcq7od.cloudfront.net/demo?scenario=recommendation&hideControls=1
https://d39spqovcq7od.cloudfront.net/demo?scenario=full&hideControls=1
```

---

## 録画のコツ

1. **ブラウザ**: Chrome を使い、DevTools は閉じておく
2. **画面録画**: 画面中央のスマホ枠だけキャプチャ（黒背景でトリミングしやすい）
3. **解像度**: 1080p で録画すると画面が見やすい
4. **速度調整**: `full` シナリオは速度1xで3-5分。急ぐなら1.5xで短縮
5. **ハードリロード**: Service Worker キャッシュが残る場合は `Ctrl+Shift+R`
6. **シナリオ別録画**: `full` で通しか、個別URLで1つずつ撮影してあとで結合

---

## 画面構成

```
┌─────────────────────────────────────────────┐
│  黒背景                                      │
│    ┌────────────────┐  ┌──────────────────┐  │
│    │  📱 Phone Shell │  │ Control Panel    │  │
│    │                 │  │ (hideControls=1  │  │
│    │  ヘッダー       │  │  で非表示)       │  │
│    │  ページ内容     │  │                  │  │
│    │  ナビゲーション │  │                  │  │
│    │  キャプション   │  │                  │  │
│    └────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────┘
```

スマホ枠は本番と同じ `430×932px` の phone-shell（丸角・影付き）。  
PC でも中央にモバイルサイズで表示されるので録画にそのまま使えます。

---

## 技術的注意点

- **APIは一切呼ばない**: Bedrock / DynamoDB / Cognito / 楽天 / ホットペッパー / YouTube の実APIは未使用
- **本番データとの分離**: localStorage キー `furemaru-demo-state` を使用。本番の `fremaru_chat_*` 等には触れない
- **状態は揮発**: リロードするとシナリオ状態はリセットされる
- **推薦URLは実際のもの**: 楽天検索URL、YouTube検索URL、Amazon商品URLを使用
- **ルーティング分離**: `/demo` は `ProtectedRoute` の外側。本番動作に影響なし

---

## トラブルシューティング

| 問題 | 解決策 |
|------|--------|
| 画面が真っ白 | ハードリロード (`Ctrl+Shift+R`) |
| シナリオが動かない | URLの `scenario=` パラメータのスペルを確認 |
| 前回のキャッシュが表示される | CloudFront invalidation を待つ（通常1-2分） |
| コントロールパネルが邪魔 | `?hideControls=1` を追加 |
