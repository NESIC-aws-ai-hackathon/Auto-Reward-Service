import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useApi } from '../hooks/useApi';
import { usePushSubscription } from '../hooks/usePushSubscription';
import './SettingsPage.css';

interface Settings {
  display_name: string;
  diary_time: string;
  notification_enabled: boolean;
  monthly_surplus: number;
}

export function SettingsPage() {
  const { user, signOut } = useAuth();
  const api = useApi();
  const { subscribe } = usePushSubscription(api);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [notifTestStatus, setNotifTestStatus] = useState<string>('');

  const testNotification = async () => {
    setNotifTestStatus('送信中...');
    try {
      // Request permission if not granted
      if ('Notification' in window && Notification.permission === 'default') {
        const perm = await Notification.requestPermission();
        if (perm !== 'granted') {
          setNotifTestStatus('❌ 通知が許可されていません');
          return;
        }
      }
      if ('Notification' in window && Notification.permission === 'denied') {
        setNotifTestStatus('❌ 通知がブロックされています。ブラウザ設定で許可してください');
        return;
      }

      // Subscribe to push if not already
      await subscribe();

      // Show local notification immediately
      if ('serviceWorker' in navigator) {
        const reg = await navigator.serviceWorker.ready;
        await reg.showNotification('🧪 テスト通知', {
          body: 'ふれまーるちゃんからのお知らせが届くよ♪ この通知が見えたら成功！',
          icon: '/icon-192x192.png',
          badge: '/icon-96x96.png',
          tag: 'test-notification',
        });
      } else {
        new Notification('🧪 テスト通知', {
          body: 'ふれまーるちゃんからのお知らせが届くよ♪',
          icon: '/icon-192x192.png',
        });
      }
      setNotifTestStatus('✅ テスト通知を送信しました！');
    } catch (e) {
      setNotifTestStatus(`❌ エラー: ${e instanceof Error ? e.message : '不明'}`);
    }
    setTimeout(() => setNotifTestStatus(''), 5000);
  };

  const fetchSettings = useCallback(async () => {
    try {
      const s = await api.getSettings();
      setSettings(s);
    } catch { /* ignore */ }
  }, [api]);

  useEffect(() => { fetchSettings(); }, [fetchSettings]);

  const displayName = settings?.display_name || user?.email?.split('@')[0] || 'ゲスト';
  const diaryTime = settings?.diary_time || '21:00';
  const budget = settings?.monthly_surplus || 3000;
  const notifEnabled = settings?.notification_enabled ?? true;

  const startEdit = (field: string, currentValue: string) => {
    setEditing(field);
    setEditValue(currentValue);
  };

  const saveEdit = async () => {
    if (!editing || saving) return;
    setSaving(true);
    try {
      let payload: Partial<Settings> = {};
      if (editing === 'display_name') payload = { display_name: editValue };
      else if (editing === 'diary_time') payload = { diary_time: editValue };
      else if (editing === 'monthly_surplus') payload = { monthly_surplus: parseInt(editValue) || 3000 };
      else if (editing === 'notification_enabled') payload = { notification_enabled: editValue === 'true' };

      await api.updateSettings(payload);
      setSettings(prev => prev ? { ...prev, ...payload } : prev);
      setEditing(null);
    } catch { /* ignore */ }
    finally { setSaving(false); }
  };

  const toggleNotification = async () => {
    const newVal = !notifEnabled;
    try {
      await api.updateSettings({ notification_enabled: newVal });
      setSettings(prev => prev ? { ...prev, notification_enabled: newVal } : prev);
    } catch { /* ignore */ }
  };

  return (
    <div className="page-content">
      {/* Edit Modal */}
      {editing && (
        <div className="edit-overlay" onClick={() => setEditing(null)}>
          <div className="edit-modal" onClick={e => e.stopPropagation()}>
            <h3>{editing === 'display_name' ? '名前を変更' : editing === 'diary_time' ? 'まとめ時間を設定' : '予算を設定'}</h3>
            {editing === 'diary_time' ? (
              <input type="time" value={editValue} onChange={e => setEditValue(e.target.value)} />
            ) : editing === 'monthly_surplus' ? (
              <div className="budget-input">
                <span>¥</span>
                <input type="number" value={editValue} onChange={e => setEditValue(e.target.value)} min="0" step="500" inputMode="numeric" />
              </div>
            ) : (
              <input type="text" value={editValue} onChange={e => setEditValue(e.target.value)} maxLength={20} />
            )}
            <div className="edit-actions">
              <button onClick={() => setEditing(null)}>キャンセル</button>
              <button className="primary-btn" onClick={saveEdit} disabled={saving}>{saving ? '保存中...' : '保存'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Profile Card */}
      <section className="profile-card">
        <img src="/assets/furemaru-shy.png" alt="ふれまーるちゃん" />
        <div>
          <small>プロフィール</small>
          <h2 onClick={() => startEdit('display_name', displayName)}>{displayName} ✎</h2>
          <p>一緒に楽しくお金のことを学ぼうね♪</p>
          <p style={{ fontSize: 11, color: '#a69c8c' }}>{user?.email || ''}</p>
        </div>
      </section>

      {/* Settings List */}
      <section className="settings-list">
        <button type="button" onClick={toggleNotification}>
          <span className="s-icon">🔔</span>
          <span><span className="s-label">通知設定</span><span className="s-desc">リマインダーやお知らせの受け取りを設定</span></span>
          <span className="s-value">{notifEnabled ? 'ON' : 'OFF'}</span>
          <em className="s-arrow">›</em>
        </button>
        <button type="button" onClick={testNotification}>
          <span className="s-icon">🧪</span>
          <span><span className="s-label">通知テスト</span><span className="s-desc">{notifTestStatus || 'テスト通知を送信して動作を確認'}</span></span>
          <span></span>
          <em className="s-arrow">›</em>
        </button>
        <button type="button" onClick={() => startEdit('diary_time', diaryTime)}>
          <span className="s-icon">⏰</span>
          <span><span className="s-label">ダイアリーのまとめ時間</span><span className="s-desc">毎日のふりかえり時間を設定</span></span>
          <span className="s-value">{diaryTime}</span>
          <em className="s-arrow">›</em>
        </button>
        <button type="button" onClick={() => startEdit('monthly_surplus', String(budget))}>
          <span className="s-icon">👛</span>
          <span><span className="s-label">今月のごほうび予算</span><span className="s-desc">ごほうびに使える金額の上限</span></span>
          <span className="s-value">¥{budget.toLocaleString()}</span>
          <em className="s-arrow">›</em>
        </button>
        <button type="button">
          <span className="s-icon">🎨</span>
          <span><span className="s-label">テーマ</span><span className="s-desc">アプリの見た目をカスタマイズ</span></span>
          <span></span>
          <em className="s-arrow">›</em>
        </button>
      </section>

      {/* Cards */}
      <section className="settings-cards">
        <article>
          <h3>🛡 プライバシー</h3>
          <p>プライバシーポリシー</p>
          <p>利用規約</p>
        </article>
        <article>
          <h3>🧸 アバターカスタマイズ</h3>
          <p>ふれまーるちゃんの見た目や衣装を変更できるよ♪</p>
          <button className="action-btn">カスタマイズする</button>
        </article>
      </section>

      <WishlistSection />

      <ApiConnectionTestSection />

      {/* Logout */}
      <button className="logout-btn" onClick={signOut}>ログアウト</button>
    </div>
  );
}

function ApiConnectionTestSection() {
  const api = useApi();
  type ServiceKey = 'bedrock' | 'rakuten' | 'hotpepper' | 'youtube';
  const services: { key: ServiceKey; label: string; icon: string; description: string }[] = [
    { key: 'bedrock', label: 'Bedrock (AI)', icon: '🤖', description: 'ふれまーるちゃんの会話エンジン' },
    { key: 'rakuten', label: '楽天市場', icon: '🛍️', description: 'ご褒美商品検索' },
    { key: 'hotpepper', label: 'ホットペッパー', icon: '🍽️', description: 'お店検索' },
    { key: 'youtube', label: 'YouTube', icon: '🎧', description: '癒し動画検索' },
  ];
  const [results, setResults] = useState<Record<string, { ok?: boolean; msg?: string; loading?: boolean }>>({});

  const runTest = async (key: ServiceKey) => {
    setResults(r => ({ ...r, [key]: { loading: true } }));
    try {
      const res = await api.testConnection(key);
      const msg = res.ok
        ? (res.sample ? `✅ OK · ${res.sample.substring(0, 50)}` : '✅ OK')
        : `❌ ${res.error || '応答が空です'}`;
      setResults(r => ({ ...r, [key]: { ok: res.ok, msg } }));
    } catch (e) {
      setResults(r => ({ ...r, [key]: { ok: false, msg: `❌ ${e instanceof Error ? e.message : 'error'}` } }));
    }
  };

  const runAll = async () => {
    for (const s of services) {
      await runTest(s.key);
    }
  };

  return (
    <section className="settings-cards" style={{ marginTop: 16 }}>
      <article style={{ gridColumn: '1 / -1' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>🔌 API接続テスト</h3>
          <button className="action-btn" onClick={runAll}>全部テスト</button>
        </div>
        <p style={{ fontSize: 12, color: '#8e8270', marginBottom: 8 }}>
          各サービスへの接続を個別に確認できます
        </p>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
          {services.map(s => {
            const r = results[s.key];
            return (
              <li
                key={s.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 10px',
                  background: '#fff',
                  borderRadius: 10,
                  boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                }}
              >
                <span style={{ fontSize: 20 }}>{s.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <b style={{ fontSize: 13 }}>{s.label}</b>
                  <small style={{ display: 'block', color: '#8e8270', fontSize: 11 }}>
                    {r?.loading ? 'テスト中...' : (r?.msg || s.description)}
                  </small>
                </div>
                <button
                  className="action-btn"
                  style={{ minWidth: 60, fontSize: 12, padding: '4px 10px' }}
                  onClick={() => runTest(s.key)}
                  disabled={r?.loading}
                >
                  {r?.loading ? '...' : 'テスト'}
                </button>
              </li>
            );
          })}
        </ul>
      </article>
    </section>
  );
}

interface WishlistSource { wishlist_source_id: string; wishlist_url: string; display_name?: string; item_count?: number; last_sync_at?: string }

function WishlistSection() {
  const api = useApi();
  const [sources, setSources] = useState<WishlistSource[]>([]);
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const resp = await api.getWishlistSources();
      setSources((resp.sources as WishlistSource[]) || []);
    } catch { /* ignore */ }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  const handleRegister = async () => {
    if (!url) return;
    setBusy(true);
    setStatus('登録中...');
    try {
      const r = await api.registerWishlist(url, name || undefined);
      if (r.error) {
        setStatus(`❌ ${r.message || '登録できませんでした'}`);
      } else {
        setStatus('✅ 登録したよ！同期中...');
        await api.syncWishlist(r.source_id);
        setStatus('✅ 登録＆同期完了！');
        setUrl(''); setName('');
        await load();
      }
    } catch { setStatus('❌ エラーが発生しました'); }
    finally { setBusy(false); setTimeout(() => setStatus(''), 5000); }
  };

  const handleSync = async (id: string) => {
    setBusy(true); setStatus('同期中...');
    try {
      const r = await api.syncWishlist(id);
      setStatus(`✅ ${r.items ?? 0}件を同期しました`);
      await load();
    } catch { setStatus('❌ 同期に失敗'); }
    finally { setBusy(false); setTimeout(() => setStatus(''), 4000); }
  };

  return (
    <section className="settings-cards">
      <article style={{ gridColumn: '1 / -1' }}>
        <h3>💝 ほしいものリスト連携</h3>
        <p style={{ fontSize: 12, color: '#8e8270' }}>
          ほしいものリストURLを登録すると、ふれまーるちゃんがチャットで自然におすすめしてくれるよ✨<br/>
          Amazon・楽天・その他ECサイトのURLが使えるよ
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
          <input
            type="url"
            placeholder="https://www.amazon.co.jp/hz/wishlist/ls/... など"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid #e3dac1', fontSize: 13 }}
          />
          <input
            type="text"
            placeholder="リスト名（任意・例: 趣味用）"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid #e3dac1', fontSize: 13 }}
          />
          <button
            onClick={handleRegister}
            disabled={busy || !url}
            className="action-btn"
            style={{ alignSelf: 'flex-start' }}
          >登録して同期</button>
          {status && <small style={{ color: '#7fa05f' }}>{status}</small>}
        </div>

        {sources.length > 0 && (
          <ul style={{ listStyle: 'none', padding: 0, margin: '14px 0 0' }}>
            {sources.map((s) => (
              <li key={s.wishlist_source_id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid #f0e8d8' }}>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <b style={{ fontSize: 13, color: '#4a4135' }}>{s.display_name || 'ほしいものリスト'}</b>
                  <small style={{ display: 'block', fontSize: 10, color: '#a69c8c', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.wishlist_url}
                  </small>
                  {s.item_count !== undefined && <em style={{ fontSize: 10, color: '#7fa05f', fontStyle: 'normal' }}>{s.item_count}件 同期済み</em>}
                </span>
                <button onClick={() => handleSync(s.wishlist_source_id)} disabled={busy} style={{ padding: '6px 10px', border: '1px solid #e3dac1', borderRadius: 10, background: '#fff', cursor: 'pointer', fontSize: 11 }}>
                  🔄 同期
                </button>
              </li>
            ))}
          </ul>
        )}
      </article>
    </section>
  );
}
