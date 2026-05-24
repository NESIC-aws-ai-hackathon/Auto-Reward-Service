import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useApi } from '../hooks/useApi';
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
  const [settings, setSettings] = useState<Settings | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);

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

      {/* Logout */}
      <button className="logout-btn" onClick={signOut}>ログアウト</button>
    </div>
  );
}
