import { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Navigation } from './Navigation';
import { NotificationPanel } from './NotificationPanel';
import { FortuneModal } from './FortuneModal';

export function AppLayout() {
  const navigate = useNavigate();
  const [showNotif, setShowNotif] = useState(false);
  const [showFortune, setShowFortune] = useState(false);

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
            <button className="icon-button" aria-label="今日のご褒美占い" onClick={() => setShowFortune(true)}>✨</button>
            <button className="icon-button" aria-label="通知" onClick={() => setShowNotif(v => !v)}>🔔<i className="dot"></i></button>
            <button className="icon-button" aria-label="設定" onClick={() => navigate('/settings')}>⚙️</button>
          </div>
        </header>

        {showNotif && <NotificationPanel onClose={() => setShowNotif(false)} />}
        {showFortune && <FortuneModal onClose={() => setShowFortune(false)} />}

        <main className="app-main">
          <Outlet />
        </main>
        <Navigation />
      </div>
    </div>
  );
}
