# U8-A: フロントエンドコンポーネント設計

---

## ページ構成

| パス | ページ | 認証 | 説明 |
|------|--------|------|------|
| `/login` | LoginPage | 不要 | サインイン + デモログイン |
| `/signup` | SignupPage | 不要 | サインアップ |
| `/chat` | ChatPage | 必要 | 音声チャット（U8-Bで実装、U8-Aはプレースホルダー） |
| `/dashboard` | DashboardPage | 必要 | ダッシュボード（U8-Eで実装） |
| `/diary` | DiaryPage | 必要 | 日記（U8-Eで実装） |
| `/recovery` | RecoveryPage | 必要 | 回復案（U8-Dで実装） |
| `/settings` | SettingsPage | 必要 | 設定画面 |

---

## コンポーネント階層

```
App
├── AuthProvider (Context)
│   ├── PublicRoute
│   │   ├── LoginPage
│   │   └── SignupPage
│   └── ProtectedRoute
│       ├── AppLayout
│       │   ├── Navigation (ボトムタブ)
│       │   └── <Outlet> (React Router)
│       │       ├── ChatPage (placeholder)
│       │       ├── DashboardPage (placeholder)
│       │       ├── DiaryPage (placeholder)
│       │       ├── RecoveryPage (placeholder)
│       │       └── SettingsPage ★
│       └── ServiceWorkerRegistration
└── ToastProvider (通知表示)
```

---

## 主要コンポーネント詳細

### AuthProvider

```typescript
interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  signOut: () => Promise<void>;
  getAccessToken: () => Promise<string>;
}

interface AuthUser {
  sub: string;       // Cognito sub
  email: string;
  userId: string;    // 内部ID (初回API呼び出しで取得)
}
```

**状態管理:**
- 初期化: localStorage の RefreshToken 有無を確認
- ある場合: トークンリフレッシュ試行 → 成功で自動ログイン
- ない場合: ログイン画面表示

### LoginPage

```typescript
// Props: なし
// State:
interface LoginState {
  email: string;
  password: string;
  error: string | null;
  isLoading: boolean;
}
```

**UI構成:**
- ロゴ + アプリ名（ふれまーるちゃん）
- メール入力欄
- パスワード入力欄
- 「ログイン」ボタン
- 「デモで試す」ボタン（目立つ色）
- 「アカウント作成」リンク

**インタラクション:**
- 「ログイン」→ `signIn(email, password)` → 成功で `/chat` へ
- 「デモで試す」→ `demoLogin()` → 成功で `/chat` へ
- エラー時: エラーメッセージ表示

### SettingsPage

```typescript
// Props: なし
// State:
interface SettingsState {
  displayName: string;
  diaryTime: string;
  notificationEnabled: boolean;
  monthlySurplus: number;
  isDirty: boolean;
  isSaving: boolean;
  errors: Record<string, string>;
}
```

**UI構成:**
- 「設定」ヘッダー
- ユーザー名入力欄
- 日記サマリ生成時刻選択（時刻ピッカー）
- 通知ON/OFFトグル
- 余剰金月額入力（数値入力 + 「円」ラベル）
- 「保存」ボタン（変更時のみアクティブ）
- 保存成功トースト

**バリデーション（クライアント側）:**
- display_name: 30文字以内
- diary_time: HH:MM形式
- monthly_surplus: 0〜999999 の整数

**APIコール:**
- マウント時: `GET /api/settings` → フォーム初期値
- 保存時: `PUT /api/settings` → 変更フィールドのみ送信

### Navigation (ボトムタブ)

```typescript
interface NavItem {
  path: string;
  icon: string;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { path: '/chat', icon: '🎙️', label: 'チャット' },
  { path: '/dashboard', icon: '📊', label: 'ダッシュボード' },
  { path: '/diary', icon: '📖', label: '日記' },
  { path: '/recovery', icon: '🎁', label: 'ご褒美' },
  { path: '/settings', icon: '⚙️', label: '設定' },
];
```

**UI:**
- 画面下部固定
- アクティブタブはアイコン+ラベルをハイライト
- PWA standalone モードで SafeArea 対応

---

## API クライアント

```typescript
// src/lib/api.ts
const API_BASE = import.meta.env.VITE_API_URL;

class ApiClient {
  private getToken: () => Promise<string>;

  constructor(getToken: () => Promise<string>) {
    this.getToken = getToken;
  }

  async request<T>(path: string, options?: RequestInit): Promise<T> {
    const token = await this.getToken();
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        ...options?.headers,
      },
    });
    if (res.status === 401) {
      // トークン期限切れ → サインアウト
      throw new AuthError('Session expired');
    }
    if (!res.ok) {
      const body = await res.json();
      throw new ApiError(res.status, body);
    }
    return res.json();
  }

  // Settings
  getSettings() { return this.request<Settings>('/api/settings'); }
  updateSettings(data: Partial<Settings>) {
    return this.request<{message: string}>('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }
}
```

---

## PWA マニフェスト

```json
{
  "name": "ふれまーるちゃん",
  "short_name": "ふれまーる",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#f8b4d9",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```
