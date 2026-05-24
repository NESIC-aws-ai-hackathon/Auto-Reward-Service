import { useState, useEffect, useCallback } from 'react';
import { useApi } from '../hooks/useApi';
import './DiaryPage.css';

interface DiaryEntry {
  date: string;
  content: string;
  life_log_count: number;
}

interface DiaryDetail {
  date: string;
  content: string | null;
  life_log_count: number;
  life_logs: { category: string; content: string }[];
  stress: { level: number; mood: string } | null;
}

interface HealthData {
  date: string;
  steps: number | null;
  sleep_hours: number | null;
  active_energy: number | null;
  heart_rate_avg: number | null;
  mindful_minutes: number | null;
  mood_history: { time: string; level: number; note?: string }[];
}

const MOOD_EMOJIS = ['😢', '😟', '😐', '🙂', '😊'];

function getMoodEmoji(level: number): string {
  if (level <= 2) return MOOD_EMOJIS[0]!;
  if (level <= 4) return MOOD_EMOJIS[1]!;
  if (level <= 6) return MOOD_EMOJIS[2]!;
  if (level <= 8) return MOOD_EMOJIS[3]!;
  return MOOD_EMOJIS[4]!;
}

function getCategoryEmoji(category: string): string {
  const map: Record<string, string> = {
    '支出': '👛', '回復': '💗', '感情': '😊', '習慣': '🪴',
    '運動': '👟', '食事': '🍽️', '仕事': '💼', '趣味': '🎮',
    'ヘルスケア': '❤️‍🩹',
  };
  return map[category] || '📝';
}

export function DiaryPage() {
  const api = useApi();
  const [entries, setEntries] = useState<DiaryEntry[]>([]);
  const [todayDetail, setTodayDetail] = useState<DiaryDetail | null>(null);
  const [healthData, setHealthData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const todayStr = new Date().toISOString().slice(0, 10);
      const [listResult, detailResult, healthResult] = await Promise.allSettled([
        api.getDiaryList(),
        api.getDiaryDetail(todayStr),
        api.getHealthData(todayStr),
      ]);
      if (listResult.status === 'fulfilled') setEntries(listResult.value.entries || []);
      if (detailResult.status === 'fulfilled') setTodayDetail(detailResult.value);
      if (healthResult.status === 'fulfilled') setHealthData(healthResult.value);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const today = new Date();
  const dateStr = `${today.getFullYear()}.${String(today.getMonth() + 1).padStart(2, '0')}.${String(today.getDate()).padStart(2, '0')}`;
  const dayNames = ['日', '月', '火', '水', '木', '金', '土'];

  const stressLevel = todayDetail?.stress?.level;
  const mood = todayDetail?.stress?.mood || '';
  const furePercent = stressLevel !== undefined ? Math.max(0, 100 - stressLevel * 10) : null;
  const lifeLogs = todayDetail?.life_logs || [];
  const diaryContent = todayDetail?.content || entries[0]?.content || null;
  const moodHistory = healthData?.mood_history || [];

  return (
    <div className="page-content">
      {/* Diary Hero */}
      <section className="diary-hero">
        <div>
          <time>{dateStr} {dayNames[today.getDay()]}</time>
          <h2>今日のダイアリー🌿</h2>
          <p>{diaryContent || 'まだ今日のダイアリーは生成されていないよ。チャットで話しかけてね♪'}</p>
          <div className="diary-stats">
            <span>💗 今日の気分<br /><b>{mood || '—'}</b></span>
            <span>🌿 ふれまーる度<br /><b>{furePercent !== null ? `${furePercent}%` : '—'}</b></span>
          </div>
        </div>
        <img src="/assets/furemaru-happy.png" alt="ふれまーるちゃん" />
      </section>

      {/* Mood Timeline Card */}
      <section className="mood-card">
        <h2>🌿 気分のうつろい</h2>
        {moodHistory.length > 0 ? (
          <div className="mood-timeline">
            <div className="mood-chart">
              {moodHistory.map((entry, i) => (
                <div key={i} className="mood-point" style={{ left: `${(i / Math.max(moodHistory.length - 1, 1)) * 100}%`, bottom: `${(entry.level / 10) * 100}%` }}>
                  <span className="mood-dot">{getMoodEmoji(entry.level)}</span>
                  <small>{entry.time.slice(11, 16)}</small>
                </div>
              ))}
              <svg className="mood-line-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                <polyline
                  fill="none" stroke="var(--green)" strokeWidth="2" strokeLinecap="round"
                  points={moodHistory.map((e, i) => `${(i / Math.max(moodHistory.length - 1, 1)) * 100},${100 - (e.level / 10) * 100}`).join(' ')}
                />
              </svg>
            </div>
            <div className="mood-labels"><span>😢 低い</span><span>😊 高い</span></div>
          </div>
        ) : stressLevel !== undefined ? (
          <div className="mood-line">
            {MOOD_EMOJIS.map((emoji, i) => {
              const moodIdx = stressLevel <= 2 ? 4 : stressLevel <= 4 ? 3 : stressLevel <= 6 ? 2 : stressLevel <= 8 ? 1 : 0;
              return <span key={i} style={{ opacity: i === moodIdx ? 1 : 0.3, transform: i === moodIdx ? 'scale(1.4)' : 'none', transition: 'all 0.3s' }}>{emoji}</span>;
            })}
          </div>
        ) : (
          <div className="mood-line">
            <p style={{ margin: 'auto', fontSize: 12, color: '#a69c8c' }}>チャットで気分を教えてね♪</p>
          </div>
        )}
        {mood && <p>今日の気分：{mood}</p>}
      </section>

      {/* Life Log */}
      <section className="life-log-list">
        <div className="section-title-row">
          <h2>🌿 会話から生まれたライフログ</h2>
        </div>
        {lifeLogs.length > 0 ? (
          lifeLogs.map((log, i) => (
            <article key={i}>
              <img src={i % 2 === 0 ? '/assets/emotions/happy.png' : '/assets/emotions/support.png'} alt="" />
              <p><span className="hl">{getCategoryEmoji(log.category)} {log.category}</span><br />{log.content}</p>
              <em></em>
            </article>
          ))
        ) : entries.length > 0 ? (
          entries.slice(0, 5).map((entry, i) => (
            <article key={i}>
              <img src={i % 2 === 0 ? '/assets/emotions/happy.png' : '/assets/emotions/support.png'} alt="" />
              <p>{entry.content}<br /><span className="hl">→ ログ {entry.life_log_count}件記録 🍀</span></p>
              <em>{entry.date?.slice(5) || ''}</em>
            </article>
          ))
        ) : (
          <article>
            <img src="/assets/emotions/support.png" alt="" />
            <p>まだライフログがないよ。<br /><span className="hl">→ チャットで話しかけると、自動でログが生成されるよ♪</span></p>
            <em></em>
          </article>
        )}
      </section>

      {/* Health Highlights */}
      <section className="highlight-grid">
        <h2>🌿 今日のハイライト</h2>
        <div>
          <span>👟<b>{healthData?.steps != null ? healthData.steps.toLocaleString() + '歩' : '—'}</b><small>歩数</small></span>
          <span>😴<b>{healthData?.sleep_hours != null ? healthData.sleep_hours.toFixed(1) + '時間' : '—'}</b><small>睡眠</small></span>
          <span>🔥<b>{healthData?.active_energy != null ? healthData.active_energy + 'kcal' : '—'}</b><small>消費カロリー</small></span>
          <span>💓<b>{healthData?.heart_rate_avg != null ? healthData.heart_rate_avg + 'bpm' : '—'}</b><small>平均心拍</small></span>
          <span>🧘<b>{healthData?.mindful_minutes != null ? healthData.mindful_minutes + '分' : '—'}</b><small>マインドフル</small></span>
          <span>📝<b>{todayDetail?.life_log_count ?? 0}件</b><small>ライフログ</small></span>
        </div>
        {!healthData?.steps && (
          <p className="health-hint">iPhoneのショートカットからヘルスケア情報を送ると表示されるよ♪</p>
        )}
      </section>

      {loading && <div className="loading-state">読み込み中...</div>}
    </div>
  );
}
