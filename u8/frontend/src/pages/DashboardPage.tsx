import { useState, useEffect, useCallback, useMemo } from 'react';
import { useApi } from '../hooks/useApi';
import './DashboardPage.css';

interface DashboardData {
  surplus: { monthly_budget: number; spent: number; remaining: number; ratio: number };
  stress: { level: number; mood: string; date: string } | null;
  recent_expenses: { description: string; amount: number; date: string }[];
  streak_days: number;
}

export function DashboardPage() {
  const api = useApi();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const result = await api.getDashboard();
      setData(result);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const budget = data?.surplus.monthly_budget ?? 0;
  const spent = data?.surplus.spent ?? 0;
  const remaining = data?.surplus.remaining ?? 0;
  const stressLevel = data?.stress?.level ?? 5;
  const mood = data?.stress?.mood || '';
  const recoveryPercent = Math.max(0, Math.min(100, 100 - stressLevel * 10));
  const expenses = data?.recent_expenses || [];

  const barHeights = useMemo(() => {
    if (expenses.length === 0) return [];
    const maxAmount = Math.max(...expenses.slice(-5).map(e => e.amount), 1);
    return expenses.slice(-5).map(e => Math.max(15, (e.amount / maxAmount) * 90));
  }, [expenses]);

  const getCategoryIcon = (desc: string): string => {
    if (desc.includes('カフェ') || desc.includes('コーヒー')) return '☕';
    if (desc.includes('ケーキ') || desc.includes('スイーツ') || desc.includes('プリン')) return '🍮';
    if (desc.includes('本') || desc.includes('読書')) return '📖';
    if (desc.includes('アロマ') || desc.includes('癒し')) return '🌿';
    return '👜';
  };

  return (
    <div className="page-content">
      {/* Hero */}
      <section className="compact-hero">
        <img src="/assets/furemaru-support.png" alt="ふれまーるちゃん" />
        <div className="speech-bubble">
          {data ? (
            <>
              <strong>{remaining > 0 ? 'いい感じ！' : 'ちょっと使いすぎかも…'}</strong>
              <span>{remaining > 0
                ? `今月あと¥${remaining.toLocaleString()}使えるよ♪ ${mood ? `気分: ${mood}` : ''}`
                : 'でも大丈夫、一緒に見直してこ？'}</span>
            </>
          ) : (
            <>
              <strong>こんにちは！</strong>
              <span>{loading ? '読み込み中...' : 'チャットで話しかけると、ここにデータが表示されるよ♪'}</span>
            </>
          )}
        </div>
      </section>

      {/* Budget Card */}
      <section className="budget-card">
        <div className="section-title-row">
          <h2>🌿 今月のごほうび予算</h2>
        </div>
        <div className="metrics three">
          <article><span className="icon">👛</span><small>今月の予算</small><strong>{budget > 0 ? `¥${budget.toLocaleString()}` : '—'}</strong></article>
          <article><span className="icon">🍮</span><small>使った金額</small><strong>{data ? `¥${spent.toLocaleString()}` : '—'}</strong></article>
          <article><span className="icon">✨</span><small>残りの金額</small><strong>{data ? `¥${remaining.toLocaleString()}` : '—'}</strong></article>
        </div>
      </section>

      {/* Charts */}
      <div className="dashboard-grid">
        <article className="chart-card">
          <h2>🌿 回復支出の推移</h2>
          <div className="bar-chart">
            {barHeights.length > 0 ? (
              barHeights.map((h, i) => (
                <b key={i} style={{ height: `${h}%` }} title={`¥${expenses[expenses.length - 5 + i]?.amount || 0}`} />
              ))
            ) : (
              <p style={{ margin: 'auto', fontSize: 12, color: '#a69c8c' }}>データなし</p>
            )}
          </div>
        </article>
        <article className="chart-card">
          <h2>🌿 ストレス・回復バランス</h2>
          {data?.stress ? (
            <>
              <div className="donut" style={{ background: `conic-gradient(#83c58c 0 ${recoveryPercent}%, #ffc784 ${recoveryPercent}% 100%)` }}>
                <span>{recoveryPercent}%</span>
              </div>
              <div className="legend">
                <p><i className="green"></i>回復 {recoveryPercent}%</p>
                <p><i className="orange"></i>ストレス {100 - recoveryPercent}%</p>
              </div>
            </>
          ) : (
            <p style={{ textAlign: 'center', padding: '2rem 0', fontSize: 12, color: '#a69c8c' }}>チャットで話すとストレスレベルが表示されるよ</p>
          )}
          <div className="mini-sloth"><img src="/assets/sloth-buddy.png" alt="" /></div>
        </article>
      </div>

      {/* Activity List */}
      <section className="activity-list">
        <div className="section-title-row">
          <h2>🦥 最近のアクティビティ</h2>
        </div>
        <ul>
          {expenses.length > 0 ? (
            expenses.slice(-5).reverse().map((e, i) => (
              <li key={i}>
                <span>{getCategoryIcon(e.description)}</span>
                <b>回復</b>
                <p>{e.description}</p>
                <em>¥{e.amount.toLocaleString()}</em>
              </li>
            ))
          ) : (
            <li>
              <span>📝</span>
              <b>待機中</b>
              <p>チャットで支出を報告すると、ここに表示されるよ♪</p>
              <em></em>
            </li>
          )}
        </ul>
      </section>

      {loading && <div className="loading-state">読み込み中...</div>}
    </div>
  );
}
