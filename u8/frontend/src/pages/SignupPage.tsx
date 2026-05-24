import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function SignupPage() {
  const { signUp, confirmSignUp } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [step, setStep] = useState<'register' | 'verify'>('register');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('パスワードが一致しません');
      return;
    }

    setLoading(true);
    try {
      await signUp(email, password);
      setStep('verify');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '登録に失敗しました';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await confirmSignUp(email, verificationCode);
      navigate('/login', { state: { message: '登録完了！ログインしてください。' } });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '確認コードが正しくありません';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  if (step === 'verify') {
    return (
      <div className="page login-page">
        <div className="login-header">
          <h1 className="login-title">📧 確認コード</h1>
          <p className="login-subtitle">{email} に送信されたコードを入力してね</p>
        </div>

        <form onSubmit={handleVerify} className="login-form">
          {error && <div className="error-message">{error}</div>}

          <div className="input-group">
            <label htmlFor="code">確認コード</label>
            <input
              id="code"
              type="text"
              inputMode="numeric"
              value={verificationCode}
              onChange={(e) => setVerificationCode(e.target.value)}
              placeholder="6桁のコード"
              required
              autoComplete="one-time-code"
              maxLength={6}
            />
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? '確認中...' : '確認する'}
          </button>
        </form>

        <p className="login-footer">
          <Link to="/signup" onClick={() => setStep('register')}>戻る</Link>
        </p>
      </div>
    );
  }

  return (
    <div className="page login-page">
      <div className="login-header">
        <h1 className="login-title">🎀 新規登録</h1>
        <p className="login-subtitle">ふれまーるちゃんと始めよう</p>
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
            placeholder="8文字以上（大小英数記号）"
            required
            autoComplete="new-password"
            minLength={8}
          />
        </div>

        <div className="input-group">
          <label htmlFor="confirm-password">パスワード（確認）</label>
          <input
            id="confirm-password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="もう一度入力"
            required
            autoComplete="new-password"
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? '登録中...' : '登録する'}
        </button>
      </form>

      <p className="login-footer">
        既にアカウントをお持ちの方は <Link to="/login">ログイン</Link>
      </p>
    </div>
  );
}
