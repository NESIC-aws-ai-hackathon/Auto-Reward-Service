import { useState, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { usePushSubscription } from '../hooks/usePushSubscription';
import './NotificationPanel.css';

interface Notification {
  id: string;
  title: string;
  body: string;
  time: string;
  read: boolean;
  type: 'reminder' | 'reward' | 'diary' | 'system';
}

export function NotificationPanel({ onClose }: { onClose: () => void }) {
  const api = useApi();
  const { subscribe } = usePushSubscription(api);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [pushEnabled, setPushEnabled] = useState(false);
  const [requesting, setRequesting] = useState(false);

  useEffect(() => {
    // Check current push permission
    if ('Notification' in window) {
      setPushEnabled(Notification.permission === 'granted');
    }
    // Load recent notifications from local or mock
    loadNotifications();
  }, []);

  const loadNotifications = () => {
    // Load from localStorage (saved from push events) or show defaults
    const stored = localStorage.getItem('ars_notifications');
    if (stored) {
      try {
        setNotifications(JSON.parse(stored));
      } catch {
        setNotifications(getDefaultNotifications());
      }
    } else {
      setNotifications(getDefaultNotifications());
    }
  };

  const getDefaultNotifications = (): Notification[] => {
    const now = new Date();
    return [
      {
        id: '1',
        title: '🌙 おやすみ前のふりかえり',
        body: '今日もお疲れさま！ 日記を書いて今日をふりかえってみない？',
        time: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(),
        read: false,
        type: 'diary',
      },
      {
        id: '2',
        title: '🎁 ご褒美の時間だよ',
        body: '今週がんばったね！自分へのご褒美、何にする？',
        time: new Date(now.getTime() - 8 * 60 * 60 * 1000).toISOString(),
        read: true,
        type: 'reward',
      },
      {
        id: '3',
        title: '💰 今月の予算状況',
        body: '今月の残り予算は ¥2,400。ペース順調だよ♪',
        time: new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString(),
        read: true,
        type: 'reminder',
      },
    ];
  };

  const enablePush = async () => {
    setRequesting(true);
    try {
      if ('Notification' in window && Notification.permission === 'default') {
        const perm = await Notification.requestPermission();
        if (perm === 'granted') {
          await subscribe();
          setPushEnabled(true);
        }
      } else if (Notification.permission === 'granted') {
        await subscribe();
        setPushEnabled(true);
      }
    } catch { /* ignore */ }
    setRequesting(false);
  };

  const markRead = (id: string) => {
    const updated = notifications.map(n =>
      n.id === id ? { ...n, read: true } : n
    );
    setNotifications(updated);
    localStorage.setItem('ars_notifications', JSON.stringify(updated));
  };

  const clearAll = () => {
    setNotifications([]);
    localStorage.removeItem('ars_notifications');
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffH = Math.floor(diffMs / (1000 * 60 * 60));
    if (diffH < 1) return 'たった今';
    if (diffH < 24) return `${diffH}時間前`;
    const diffD = Math.floor(diffH / 24);
    return `${diffD}日前`;
  };

  const typeIcon = (type: string) => {
    switch (type) {
      case 'diary': return '📖';
      case 'reward': return '🎁';
      case 'reminder': return '💰';
      default: return '📢';
    }
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="notif-overlay" onClick={onClose}>
      <div className="notif-panel" onClick={e => e.stopPropagation()}>
        <div className="notif-header">
          <h3>🔔 お知らせ {unreadCount > 0 && <span className="notif-badge">{unreadCount}</span>}</h3>
          <button className="notif-close" onClick={onClose}>✕</button>
        </div>

        {!pushEnabled && (
          <div className="notif-push-banner">
            <p>プッシュ通知をONにすると、ふれまーるちゃんからリマインダーが届くよ♪</p>
            <button onClick={enablePush} disabled={requesting}>
              {requesting ? '設定中...' : '通知をONにする 🔔'}
            </button>
          </div>
        )}

        <div className="notif-list">
          {notifications.length === 0 ? (
            <div className="notif-empty">
              <p>📭 通知はまだないよ</p>
              <p className="sub">ふれまーるちゃんからメッセージが届くとここに表示されるよ</p>
            </div>
          ) : (
            <>
              {notifications.map(n => (
                <div
                  key={n.id}
                  className={`notif-item${n.read ? '' : ' unread'}`}
                  onClick={() => markRead(n.id)}
                >
                  <span className="notif-type-icon">{typeIcon(n.type)}</span>
                  <div className="notif-content">
                    <strong>{n.title}</strong>
                    <p>{n.body}</p>
                    <small>{formatTime(n.time)}</small>
                  </div>
                </div>
              ))}
              <button className="notif-clear" onClick={clearAll}>すべてクリア</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
