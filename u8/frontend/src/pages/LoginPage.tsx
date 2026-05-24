import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function LoginPage() {
  const { signIn, demoLogin } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await signIn(email, password);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'ログインに失敗しました';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setError('');
    setLoading(true);
    try {
      await demoLogin();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'デモログインに失敗しました';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page login-page">
      <div className="login-header">
        <h1 className="login-title">🎀 ふれまーるちゃん</h1>
        <p className="login-subtitle">あなたの毎日を甘やかすパートナー</p>
      </div>

      <form onSubmit={handleSubmit} className="login-form">
        {error && <div className="error-message">{error}</div>}

        <div className="input-group">
          <label htmlFor="email">メールアドレス</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email@example.com"
            required
            autoComplete="email"
          />
        </div>

        <div className="input-group">
          <label htmlFor="password">パスワード</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="パスワード"
            required
            autoComplete="current-password"
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'ログイン中...' : 'ログイン'}
        </button>
      </form>

      <div className="login-divider">
        <span>または</span>
      </div>

      <button
        className="btn btn-outline"
        onClick={handleDemoLogin}
        disabled={loading}
      >
        🎮 デモアカウントでお試し
      </button>

      <p className="login-footer">
        アカウントをお持ちでない方は <Link to="/signup">新規登録</Link>
      </p>
    </div>
  );
}
