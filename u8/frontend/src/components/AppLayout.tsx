import { Outlet } from 'react-router-dom';
import { Navigation } from './Navigation';

export function AppLayout() {
  return (
    <div className="phone-shell">
      <div className="phone-inner">
        <header className="app-header">
          <div className="brand">
            <img src="/assets/furemaru-avatar.png" alt="" className="brand-avatar" />
            <div>
              <h1>ふれまーる</h1>
              <p>あなたの"回復"パートナー 🌿</p>
            </div>
          </div>
          <div className="header-actions">
            <button className="icon-button" aria-label="通知">🔔<i className="dot"></i></button>
            <button className="icon-button" aria-label="メニュー">✨</button>
          </div>
        </header>
        <main className="app-main">
          <Outlet />
        </main>
        <Navigation />
      </div>
    </div>
  );
}
