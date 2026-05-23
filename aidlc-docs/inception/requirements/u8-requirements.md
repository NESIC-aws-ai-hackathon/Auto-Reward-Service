# Unit 8: PWA ダッシュボード強化 — 要件定義書

## 1. Intent Analysis Summary

| 項目 | 内容 |
|------|------|
| **Request Type** | New Feature（Unit 8 機能拡張） |
| **Scope** | System-wide（PWAフロントエンド + バックエンド + 認証基盤 + LLM連携 + 新データモデル） |
| **Complexity** | Complex |
| **Change Classification** | SPEC_CHANGE（アーキテクチャ・ピボット: LINE Bot → PWA 統合） |

## 2. アーキテクチャ方針（U7以前との差分）

### 2.1 主要な方針転換

| 項目 | U0〜U7（旧） | U8（新） |
|------|-------------|---------|
| **メインUI** | LINE Bot + LIFF | PWA 単体アプリ |
| **認証** | LIFF ID Token + LINE userId | Amazon Cognito |
| **会話エンジン** | Bedrock (Nova) | OpenAI Realtime API |
| **分析LLM** | Bedrock (Nova Lite/Micro) | Claude Sonnet 級（高品質優先） |
| **Push通知** | LINE Push（1日1回制限） | PWA Web Push（制限なし） |
| **ユーザーID体系** | `USER#{lineUserId}` | `USER#{internalUserId}` + 外部ID連携 |

### 2.2 LINE Bot の扱い

- Unit 8 では LINE Bot / LIFF を **主導線から外す**
- 既存 LINE Bot 機能は legacy 扱い（削除はしないが新機能追加なし）
- 将来 LINE 再連携する場合は外部ID連携: `IDENTITY#LINE#{lineUserId}` → `USER#{internalUserId}`

---

## 3. 機能要件

### FR-8-01: 音声チャット（リアルタイム会話）

| 項目 | 仕様 |
|------|------|
| **実装方式** | OpenAI Realtime API（WebRTC） |
| **接続方式（第一候補）** | PWA → バックエンド（ephemeral key発行）→ PWA が WebRTC でOpenAI接続 |
| **接続方式（代替）** | サーバー中継が必要な場合は WebSocket |
| **認証設計** | ブラウザにOpenAI API Keyを持たせない。バックエンドで ephemeral client secret を発行 |
| **会話キャラクター** | ふれまーるちゃん（既存キャラ設定を継承） |
| **音声入力** | VAD（Voice Activity Detection）で自動検出 |
| **音声出力** | OpenAI Realtime API の音声レスポンス |
| **テキスト補助** | ボタン/入力欄でテキストチャットに切り替え可能 |
| **Transcript保存** | 会話テキストをバックエンドに保存（非同期分析用） |

**接続フロー:**
1. PWA → バックエンド API: セッション開始リクエスト（Cognito JWT認証）
2. バックエンド → OpenAI: ephemeral client secret を発行
3. バックエンド → PWA: ephemeral client secret を返却
4. PWA → OpenAI: ephemeral secret を使って WebRTC セッション確立
5. 音声データは PWA ↔ OpenAI 間で直接送受信（サーバー中継なし）
6. Transcript はOpenAI → PWA → バックエンドへ非同期保存

**UI構成:**
- PWA トップ画面 = 音声チャット画面
- アバター表示エリア（静止画、将来3D差し替え）
- 音声波形/アニメーション表示
- テキストチャット切り替えボタン
- 会話履歴表示エリア

### FR-8-02: ライフログ機能

| 項目 | 仕様 |
|------|------|
| **データソース** | ふれまーるちゃんとの会話 Transcript |
| **抽出方式** | 高品質LLM による非同期分析 |
| **抽出タイミング** | 会話終了後 or 定期バッチ（数分遅延許容） |
| **抽出粒度** | 詳細（C相当）だが会話から自然に読み取れる範囲のみ |

**記録対象:**

| カテゴリ | 記録項目 |
|---------|---------|
| 場所 | 訪問場所、外出先 |
| 活動 | 仕事/学校/外出/趣味/休息 |
| 運動 | 運動量、歩数（会話から推定） |
| 食事 | 食事内容（言及があれば） |
| 睡眠 | 睡眠時間、質（申告ベース） |
| 対人交流 | 誰と会ったか、コミュニケーション |
| 気分・感情 | 感情スコア、疲労度、ストレス度 |
| 支出 | 買い物、出費（金額含む） |
| ご褒美 | 自分へのご褒美、0円回復 |

**制約:**
- LLMが事実を補完しない（会話に出てきたもののみ）
- 無理に聞き出さない（自然な会話フロー維持）
- 不確実な情報には確信度を付与

### FR-8-03: 日記サマリ

| 項目 | 仕様 |
|------|------|
| **生成タイミング** | 1日の終わり（設定可能、デフォルト 22:00） |
| **生成方式** | 高品質LLMがライフログから日記調テキスト生成 |
| **配信方式** | PWA Web Push 通知 + PWA ダッシュボード表示 + 音声読み上げ |
| **音声読み上げ** | ふれまーるちゃんが PWA 上で読み上げる演出 |
| **履歴** | 過去の日記サマリをPWA上で閲覧可能 |
| **LINE Push** | 使用しない |

### FR-8-04: 余剰金支出管理ダッシュボード（既存強化）

| 項目 | 仕様 |
|------|------|
| **基本方針** | 既存家計簿機能を「余剰金の支出管理」として再定義 |
| **表示内容** | 余剰金残高、甘やかし枠残額、支出推移、カテゴリ別内訳 |
| **データソース** | 会話からの支出記録 + 手動入力 |
| **PWA表示** | 簡易ダッシュボードカード（トップ画面からアクセス） |

### FR-8-05: ストレス判定

| 項目 | 仕様 |
|------|------|
| **判定方式** | 会話 + 余剰金 + ライフログの複合判定 |
| **判定タイミング** | 会話中リアルタイム（軽量）+ 日次バッチ（詳細） |
| **判定材料** | 下表参照 |
| **出力** | ストレスレベル（5段階）+ 推奨アクション |

**判定材料:**

| カテゴリ | シグナル |
|---------|---------|
| 会話 | 疲労表現、ネガティブ発言の頻度 |
| 支出 | 衝動買い傾向、やけくそ費の有無 |
| 余剰金 | 甘やかし枠の残額、余剰金状況 |
| 運動 | 運動量低下 |
| 外出 | 外出頻度の減少 |
| 睡眠 | 睡眠不足の申告 |
| 回復 | 0円回復の頻度 |

### FR-8-06: 段階的ご褒美誘導

| 項目 | 仕様 |
|------|------|
| **誘導方式** | 段階的アプローチ（広告的に見せない） |
| **トリガー** | ストレス高 + 余剰金あり + 会話の自然なタイミング |
| **対象** | 0円回復・休息・散歩・動画・記事・サービス・商品すべて含む |
| **表示名** | 「今日の回復案」（商品広告に見せない） |

**段階的フロー:**

1. **共感** — 「今日は疲れたね」（気持ちを受け止める）
2. **提案示唆** — 「少し回復に使ってもよさそう」
3. **具体提案** — 反応があれば「今日の回復案」として提案を表示
4. **外部確認** — 商品の場合は「外部サイトで確認」リンク（カート誘導は主導線から外す）
5. **0円回復優先** — 休息・散歩・動画・深呼吸・入浴なども積極的に選択肢に含む

**UI方針:**
- 画面タイトル: 「今日の甘やかし枠の使い道」
- 提案カード: 0円回復案と有料回復案を区別なく並列表示
- Amazon連携: 将来拡張扱い（Unit 8主導線から外す）

### FR-8-07: PWA Web Push 通知

| 項目 | 仕様 |
|------|------|
| **用途** | 日記サマリ完成通知、ご褒美提案タイミング通知 |
| **技術** | Web Push API + Service Worker |
| **制限** | LINE Push の代替。制限なし |
| **ユーザー許可** | ブラウザの通知許可フローに従う |

### FR-8-08: 認証基盤（Cognito）

| 項目 | 仕様 |
|------|------|
| **認証プロバイダ** | Amazon Cognito User Pool |
| **サインアップ** | メールアドレス or ソーシャルログイン |
| **MVP対応** | デモログイン（ワンクリックで体験可能） |
| **ユーザーID** | Cognito sub → 内部 `USER#{internalUserId}` |
| **セッション管理** | Cognito Token（JWT） |
| **将来LINE連携** | Cognito Identity Provider として LINE Login 追加可能 |

### FR-8-09: アバター表示

| 項目 | 仕様 |
|------|------|
| **Unit 8 初期** | ふれまーるちゃん静止画 |
| **軽微アニメ** | 音声再生中の軽い揺れ、表情差分（あれば） |
| **将来拡張** | 3Dモデル (VRM)、Live2D、口パク連動 |
| **UI配置** | チャット画面上部にアバター表示エリアを予約 |

---

## 4. 非機能要件

### NFR-8-01: パフォーマンス

| 項目 | 目標 |
|------|------|
| PWA 初回ロード | 3秒以内（LTE環境） |
| 音声レスポンス遅延 | 500ms以内（OpenAI Realtime API依存） |
| ライフログ分析遅延 | 5分以内（非同期許容） |
| 日記サマリ生成 | 設定時刻から10分以内 |

### NFR-8-02: コスト方針

| 項目 | 方針 |
|------|------|
| **LLMコスト** | 体験品質を最優先。コスト制約は緩和 |
| **OpenAI Realtime API** | 音声会話の品質重視で採用 |
| **分析LLM** | Claude Sonnet 級を使用 |
| **インフラ** | AWS Lambda + API Gateway（既存踏襲） |

### NFR-8-03: セキュリティ

| 項目 | 方針 |
|------|------|
| 認証 | Cognito JWT 検証 |
| API 保護 | Authorization ヘッダー必須 |
| データ暗号化 | DynamoDB 暗号化（既存踏襲） |
| 音声データ | サーバー保存しない（Transcript のみ保存） |
| 個人情報 | ライフログは本人のみアクセス可能 |

### NFR-8-04: 可用性

| 項目 | 方針 |
|------|------|
| オフライン | 非対応（オンライン前提） |
| Service Worker | 静的ファイルキャッシュ + PWA起動体験改善のみ |
| フォールバック | OpenAI API ダウン時はテキストチャット（Bedrock fallback） |

---

## 5. LLMモデル構成

| 用途 | モデル | 呼び出し方式 |
|------|--------|------------|
| リアルタイム音声会話 | OpenAI Realtime API (GPT-4o-realtime) | WebRTC（PWA→OpenAI直接、ephemeral key認証） |
| ライフログ分析 | Claude 3.5 Sonnet (Bedrock) | 非同期Lambda |
| ストレス判定 | Claude 3.5 Sonnet (Bedrock) | 非同期Lambda |
| 日記サマリ生成 | Claude 3.5 Sonnet (Bedrock) | 非同期Lambda |
| 意図分類（軽量） | Amazon Nova Micro (Bedrock) | 同期Lambda |
| ご褒美回復案選定 | 既存Provider chain | 同期Lambda |

---

## 6. データモデル（DynamoDB 拡張）

### エンティティ一覧（統一命名）

| PK | SK | 用途 |
|----|-----|------|
| `USER#{id}` | `PROFILE#` | ユーザープロフィール（Cognito連携） |
| `USER#{id}` | `CONVERSATION_TURN#{timestamp}` | 会話Transcript（ターン単位） |
| `USER#{id}` | `LIFE_LOG#{date}#{seq}` | ライフログエントリ |
| `USER#{id}` | `DAILY_FUREMARU_SUMMARY#{date}` | 日記サマリ（ふれまーるちゃんの日記） |
| `USER#{id}` | `STRESS_SUMMARY#{date}` | ストレス判定結果 |
| `USER#{id}` | `EXPENSE#{timestamp}` | 支出記録 |
| `USER#{id}` | `REWARD_PERMIT#{timestamp}` | ご褒美許可（実行したご褒美） |
| `USER#{id}` | `REWARD_SKIP#{timestamp}` | ご褒美スキップ（見送ったご褒美） |
| `USER#{id}` | `MONTHLY_SUMMARY#{yyyy-mm}` | 月次サマリ |
| `USER#{id}` | `PUSH_SUBSCRIPTION#` | Web Push サブスクリプション |
| `USER#{id}` | `VOICE_SESSION#{sessionId}` | 音声セッション管理（active/completed/aborted） |
| `ANALYSIS_JOB#{jobId}` | `META#` | 非同期分析ジョブ管理（queued/running/completed/failed） |
| `IDENTITY#COGNITO#{sub}` | `META#` | Cognito → 内部ID マッピング |
| `IDENTITY#LINE#{lineUid}` | `META#` | LINE → 内部ID マッピング（将来） |

> **命名規則:** SK は `UPPER_SNAKE_CASE#{パラメータ}` で統一。旧 `SK_PREFIX_*` 形式は使用しない。

---

## 7. 画面構成（PWA）

```
PWA トップ（音声チャット）
├── アバター表示エリア（ふれまーるちゃん静止画）
├── 音声会話エリア（波形表示 + VAD インジケーター）
├── テキストチャット切り替え
├── 会話履歴スクロール
└── ナビゲーションバー
    ├── 🎙️ チャット（トップ）
    ├── 📊 ダッシュボード
    │   ├── 余剰金・甘やかし枠
    │   ├── 支出推移グラフ
    │   └── ストレスレベル表示
    ├── 📖 日記
    │   ├── 今日の日記サマリ
    │   └── 過去の日記一覧
    ├── 🎁 ご褒美（今日の甘やかし枠の使い道）
    │   ├── 今日の回復案（0円回復・有料回復を並列表示）
    │   └── 外部サイトで確認（将来拡張）
    └── ⚙️ 設定
        ├── プロフィール
        ├── 通知設定
        └── 日記サマリ時刻設定
```

---

## 8. 技術スタック（Unit 8 追加分）

| 項目 | 技術 |
|------|------|
| フロントエンド | PWA (HTML/CSS/JS) → 将来 React/Next.js 移行検討 |
| 音声会話 | OpenAI Realtime API (WebRTC + ephemeral key) |
| 認証 | Amazon Cognito |
| バックエンド | AWS Lambda (Python) + API Gateway |
| DB | DynamoDB（既存テーブル拡張） |
| 分析LLM | Claude 3.5 Sonnet (Bedrock) |
| Web Push | Web Push API + VAPID keys |
| 定期ジョブ | EventBridge → Lambda |

---

## 9. Unit 8 スコープ外（将来課題）

- 3Dモデル（VRM/Live2D）実装
- 音声カスタマイズ（声質変更）
- マルチデバイス同期
- LINE Bot 完全廃止（legacy として残す）
- カレンダー連携のPWA移行
- Apple Watch / Fitbit 連携（運動データ自動取得）
