import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import './RecoveryPage.css';

interface RecoveryItem {
  id: string;
  text: string;
  category: string;
  budget_hint?: string;
}

interface RecoveryData {
  stress_level: number | null;
  mood: string | null;
  free_recovery: RecoveryItem[];
  paid_recovery: RecoveryItem[];
  message: string;
}

export function RecoveryPage() {
  const api = useApi();
  const [data, setData] = useState<RecoveryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [permitDone, setPermitDone] = useState<Set<string>>(new Set());
  const [routeStarted, setRouteStarted] = useState(false);
  const [routeStep, setRouteStep] = useState(0);

  const fetchData = useCallback(async () => {
    try {
      const result = await api.getRecovery();
      setData(result);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handlePermit = async (item: RecoveryItem, type: string) => {
    try {
      await api.recordPermit(item.id, type);
      setPermitDone(prev => new Set(prev).add(item.id));
    } catch { /* ignore */ }
  };

  const handleSkip = async () => {
    try { await api.recordSkip('今日はいいかな'); } catch { /* ignore */ }
  };

  const heroMessage = data?.message || 'つかれた日は、甘いプリンでほっと一息っこ?';
  const freeItems = data?.free_recovery || [];
  const paidItems = data?.paid_recovery || [];

  const routeSteps = [
    { emoji: '☁️', label: '深呼吸', time: '1分' },
    { emoji: '🍵', label: 'あたたかい飲み物', time: '5分' },
    { emoji: '🎵', label: 'やさしい音楽', time: '10分' },
    { emoji: '💗', label: '自分をほめる', time: '3分' },
  ];

  const handleRouteStart = () => {
    setRouteStarted(true);
    setRouteStep(0);
  };

  const handleRouteNext = () => {
    if (routeStep < routeSteps.length - 1) {
      setRouteStep(routeStep + 1);
    } else {
      setRouteStarted(false);
      setRouteStep(0);
    }
  };

  return (
    <div className="page-content">
      {/* Recovery Hero */}
      <section className="recovery-hero">
        <img src="/assets/furemaru-happy.png" alt="ふれまーるちゃん" />
        <div>
          <small>{data?.mood ? `今の気分: ${data.mood}` : 'おすすめの回復を提案するよ♪'}</small>
          <h2>{heroMessage}</h2>
          <p>心がふわっとゆるむよ〜🌿</p>
          <button className="primary-btn" onClick={handleSkip}>今日はいいかな</button>
        </div>
      </section>

      {/* 0円回復 */}
      {freeItems.length > 0 && (
        <>
          <h2 className="section-heading">🌿 0円回復メニュー</h2>
          <section className="recovery-grid">
            {freeItems.map(item => (
              <article key={item.id} className={permitDone.has(item.id) ? 'done' : ''}>
                <span>{item.category === '呼吸' ? '☁️' : item.category === '運動' ? '🚶' : item.category === '音楽' ? '🎵' : '🌿'}</span>
                <h3>{item.text}</h3>
                <p>{item.category}</p>
                {!permitDone.has(item.id) ? (
                  <button className="primary-btn small" onClick={() => handlePermit(item, 'free')}>やってみる</button>
                ) : (
                  <p className="done-text">✅ やったよ！</p>
                )}
              </article>
            ))}
          </section>
        </>
      )}

      {/* 有料回復 */}
      {paidItems.length > 0 && (
        <>
          <h2 className="section-heading">💗 小さなご褒美</h2>
          <section className="recovery-grid">
            {paidItems.map(item => (
              <article key={item.id} className={permitDone.has(item.id) ? 'done' : ''}>
                <span>🍮</span>
                <h3>{item.text}</h3>
                <p>{item.category}{item.budget_hint ? ` (${item.budget_hint})` : ''}</p>
                {!permitDone.has(item.id) ? (
                  <button className="primary-btn small" onClick={() => handlePermit(item, 'paid')}>買ってもいい？</button>
                ) : (
                  <p className="done-text">✅ 許可しました♪</p>
                )}
              </article>
            ))}
          </section>
        </>
      )}

      {/* データなし時のフォールバック */}
      {!loading && freeItems.length === 0 && paidItems.length === 0 && (
        <>
          <h2 className="section-heading">🌿 かんたん回復メニュー</h2>
          <section className="recovery-grid">
            <article>
              <span>👛</span>
              <h3>0円回復</h3>
              <p>チャットで「疲れた」と話しかけると、あなたに合った回復案が表示されるよ♪</p>
            </article>
            <article>
              <span>💗</span>
              <h3>小さなご褒美</h3>
              <p>がんばった自分にやさしいごほうびをプレゼント♪</p>
            </article>
          </section>
        </>
      )}

      {/* Route Card */}
      <section className="route-card">
        <h2>今日の回復ルート</h2>
        <div className="route">
          {routeSteps.map((step, i) => (
            <span key={i}>
              <div className={`step${routeStarted && i === routeStep ? ' current' : ''}${routeStarted && i < routeStep ? ' completed' : ''}`}>
                {step.emoji}<small>{step.label}<br />{step.time}</small>
              </div>
              {i < routeSteps.length - 1 && <div className="connector"></div>}
            </span>
          ))}
          <div className="total">合計<br />19分</div>
        </div>
        {!routeStarted ? (
          <button className="start-btn" onClick={handleRouteStart}>はじめる</button>
        ) : (
          <button className="start-btn" onClick={handleRouteNext}>
            {routeStep < routeSteps.length - 1 ? '次のステップへ →' : '完了！おつかれさま 🎉'}
          </button>
        )}
        <p className="route-footer">今日も、あなたのペースで大丈夫だよ〜🌿</p>
      </section>

      {loading && <div className="loading-state">読み込み中...</div>}
    </div>
  );
}
