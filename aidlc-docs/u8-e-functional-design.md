# U8-E 機能設計書: ダッシュボード統合

## 概要

全機能をダッシュボードUIに統合し、5タブナビゲーションのPWAを完成させる。
ダッシュボード画面で余剰金・支出推移・ストレスレベルを可視化し、日記画面で過去の日記を閲覧できるようにする。

---

## 機能一覧

| ID | 機能名 | 説明 |
|----|--------|------|
| FD-E01 | ダッシュボードAPI | GET /api/dashboard — 余剰金・支出・ストレスサマリ返却 |
| FD-E02 | 日記API | GET /api/diary — 日記一覧、GET /api/diary/{date} — 特定日 |
| FD-E03 | DashboardPage | 余剰金バー・支出推移・ストレスレベル表示 |
| FD-E04 | DiaryPage | 日記一覧・個別日記表示 |
| FD-E05 | ナビゲーション統合 | 5タブ（チャット/ダッシュボード/日記/ご褒美/設定） |

---

## FD-E01: ダッシュボードAPI

### GET /api/dashboard
```json
{
  "surplus": {
    "monthly_budget": 10000,
    "spent": 3200,
    "remaining": 6800,
    "ratio": 0.68
  },
  "stress": {
    "level": 3,
    "mood": "疲れ",
    "date": "2026-05-24"
  },
  "recent_expenses": [
    { "description": "コーヒー", "amount": 450, "date": "2026-05-24" },
    { "description": "ランチ", "amount": 980, "date": "2026-05-23" }
  ],
  "streak_days": 5
}
```

### 実装
1. プロフィールから `monthly_surplus` を取得
2. 今月の `EXPENSE#` を集計
3. 最新の `STRESS_SUMMARY#` を取得
4. 直近7日間の支出リストを取得
5. 連続会話日数（streak）を計算

---

## FD-E02: 日記API

### GET /api/diary
直近の日記一覧を返却（最新7日間）
```json
{
  "entries": [
    { "date": "2026-05-24", "content": "今日の太郎は...", "life_log_count": 3 },
    { "date": "2026-05-23", "content": "今日の太郎は...", "life_log_count": 5 }
  ]
}
```

### GET /api/diary/{date}
特定日の詳細日記を返却
```json
{
  "date": "2026-05-24",
  "content": "今日の太郎はカフェに行って...",
  "life_log_count": 3,
  "life_logs": [
    { "category": "場所", "content": "カフェ" },
    { "category": "支出", "content": "コーヒー 450円" }
  ],
  "stress": { "level": 3, "mood": "疲れ" }
}
```

---

## FD-E03: DashboardPage

### UI構成
1. **余剰金バー**: プログレスバー（残り/予算）+ 金額表示
2. **ストレスインジケーター**: 今日のレベル + 気分タグ
3. **直近支出リスト**: 最新5件の支出表示
4. **連続日数バッジ**: 「🔥 5日連続」

---

## FD-E04: DiaryPage

### UI構成
1. **日記リスト**: 日付ごとのカード表示
2. **個別日記**: タップで展開 → 全文表示
3. **ライフログタグ**: 日記下部にカテゴリタグ表示

---

## FD-E05: ナビゲーション

### 5タブ構成
| タブ | アイコン | ページ | パス |
|------|---------|--------|------|
| チャット | 🎙️ | ChatPage | /chat |
| ダッシュボード | 📊 | DashboardPage | /dashboard |
| 日記 | 📖 | DiaryPage | /diary |
| ご褒美 | 🎁 | RecoveryPage | /recovery |
| 設定 | ⚙️ | SettingsPage | /settings |

### ルーティング
- `/` → `/chat` にリダイレクト
- `/login` → 認証前のみ
- 認証後: 5タブナビ + 各ページ
