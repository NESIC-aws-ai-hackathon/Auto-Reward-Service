import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import { getJstDateString } from '../lib/datetime';
import './DiaryPage.css';

interface DiaryEntry {
  date: string;
  content: string;
  life_log_count: number;
  chat_count?: number;
}

interface DiaryDetail {
  date: string;
  content: string | null;
  life_log_count: number;
  chat_count?: number;
  life_logs: { category: string; content: string; emotion?: string; timestamp?: string }[];
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
      const todayStr = getJstDateString();
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

      {/* Mood Insight - 昨日との比較で因果を示す */}
      <MoodInsightCard todayStress={stressLevel} todayDate={getJstDateString()} />

      {/* Life Log */}
      <section className="life-log-list">
        <div className="section-title-row">
          <h2>🌿 会話から生まれたライフログ</h2>
          <Link to="/" className="life-log-cta">💬 もっと話す</Link>
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

      {/* Past Diaries */}
      <PastDiariesSection entries={entries} todayDate={getJstDateString()} />

      {loading && <div className="loading-state">読み込み中...</div>}
    </div>
  );
}

function PastDiariesSection({ entries, todayDate }: { entries: DiaryEntry[]; todayDate: string }) {
  const api = useApi();
  const past = entries.filter(e => e.date !== todayDate);
  const [openDate, setOpenDate] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, DiaryDetail | null>>({});

  const toggle = async (date: string) => {
    if (openDate === date) {
      setOpenDate(null);
      return;
    }
    setOpenDate(date);
    if (!details[date]) {
      try {
        const d = await api.getDiaryDetail(date);
        setDetails(prev => ({ ...prev, [date]: d }));
      } catch {
        setDetails(prev => ({ ...prev, [date]: null }));
      }
    }
  };

  if (past.length === 0) {
    return (
      <section className="life-log-list">
        <h2>📚 過去のダイアリー</h2>
        <p style={{ fontSize: 12, color: '#8e8270', padding: 12, textAlign: 'center' }}>
          過去の日記はまだないよ。話しかけ続けると、毎日の振り返りがここに溜まっていくよ📔
        </p>
      </section>
    );
  }

  return (
    <section className="life-log-list">
      <h2>📚 過去のダイアリー ({past.length}日分)</h2>
      <div style={{ display: 'grid', gap: 8 }}>
        {past.map(e => {
          const isOpen = openDate === e.date;
          const detail = details[e.date];
          return (
            <article key={e.date} style={{ display: 'block', padding: 0, background: '#fff' }}>
              <button
                onClick={() => toggle(e.date)}
                style={{
                  width: '100%',
                  border: 'none',
                  background: 'transparent',
                  textAlign: 'left',
                  padding: '12px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                }}
              >
                <span style={{ fontSize: 22 }}>📔</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <b style={{ fontSize: 13 }}>{e.date}</b>
                  <small style={{ display: 'block', color: '#8e8270', fontSize: 11, lineHeight: 1.4, marginTop: 2 }}>
                    {(e.content || '').slice(0, 60)}{(e.content || '').length > 60 ? '…' : ''}
                  </small>
                </div>
                <em style={{ fontStyle: 'normal', fontSize: 11, color: '#a69c8c' }}>
                  💬{e.chat_count ?? 0} / 📝{e.life_log_count}
                </em>
                <span style={{ fontSize: 12, color: '#aaa' }}>{isOpen ? '▾' : '▸'}</span>
              </button>
              {isOpen && (
                <div style={{ padding: '0 14px 14px', borderTop: '1px solid #f0e6d2' }}>
                  {detail === undefined ? (
                    <p style={{ fontSize: 12, color: '#8e8270', padding: 8 }}>読み込み中...</p>
                  ) : detail === null ? (
                    <p style={{ fontSize: 12, color: '#c08c5c', padding: 8 }}>日記を取得できませんでした</p>
                  ) : (
                    <>
                      <p style={{ fontSize: 13, lineHeight: 1.7, color: '#5a4d3a', padding: '8px 0', whiteSpace: 'pre-wrap' }}>
                        {detail.content || '(この日の日記はまだ生成されていません)'}
                      </p>
                      {detail.life_logs && detail.life_logs.length > 0 && (
                        <details style={{ marginTop: 4 }}>
                          <summary style={{ cursor: 'pointer', fontSize: 11, color: '#8e8270' }}>
                            ライフログ {detail.life_logs.length}件を見る
                          </summary>
                          <ul style={{ listStyle: 'none', padding: '8px 0 0', margin: 0, fontSize: 12 }}>
                            {detail.life_logs.map((l, idx) => (
                              <li key={idx} style={{ padding: '4px 0', borderBottom: '1px dashed #f0e6d2' }}>
                                <span style={{ marginRight: 6 }}>{getCategoryEmoji(l.category)}</span>
                                <b style={{ fontSize: 11, color: '#8e7e5e', marginRight: 6 }}>{l.category}</b>
                                {l.content}
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}
                    </>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

/**
 * MoodInsightCard - 昨日の気分・支出と今日を比較し、ふれまーるちゃんが因果を「実感させる」コメントを表示。
 * 沼ループの「ご褒美→気分改善」の物語化。
 */
function MoodInsightCard({ todayStress, todayDate }: { todayStress: number | undefined; todayDate: string }) {
  const api = useApi();
  const [comment, setComment] = useState<string | null>(null);

  useEffect(() => {
    if (todayStress === undefined) {
      setComment(null);
      return;
    }
    (async () => {
      try {
        // 昨日の日付を計算
        const d = new Date(todayDate + 'T00:00:00');
        d.setDate(d.getDate() - 1);
        const yesterdayStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        const yesterday = await api.getDiaryDetail(yesterdayStr);
        const ystress = yesterday.stress?.level;
        if (ystress === undefined || ystress === null) {
          setComment(null);
          return;
        }
        const diff = ystress - todayStress;  // 正なら気分↑（ストレス下がった）
        // 昨日の支出から「ご褒美っぽい」ものを探す
        let rewardItem = '';
        try {
          const exp = await api.getExpenses(20);
          const yExp = (exp.expenses || []).filter(e => (e.timestamp || '').startsWith(yesterdayStr));
          const rewardCats = ['ご褒美', '趣味', 'カフェ', '美容'];
          const matching = yExp.find(e => rewardCats.includes(e.category || '') || (e.item && /(プリン|ケーキ|スイーツ|アイス|コーヒー|お菓子)/.test(e.item)));
          if (matching) rewardItem = (matching.item || '').slice(0, 20);
        } catch { /* ignore */ }

        if (diff >= 2) {
          setComment(rewardItem
            ? `🌱 昨日の「${rewardItem}」のおかげかな？ 今日はストレスが${diff}も下がってるよ♪`
            : `🌿 昨日より気分がだいぶ上がってるね！ ストレス−${diff}。なんかいいことあった？`);
        } else if (diff >= 1) {
          setComment('🌷 昨日よりちょっと気分上向き♪ ゆっくりペースでいこ〜');
        } else if (diff <= -2) {
          setComment('😢 今日はちょっとお疲れみたい……。ご褒美いっとく？ ');
        } else if (diff <= -1) {
          setComment('🍃 昨日よりちょっとしんどそう。無理せずいこ〜');
        } else {
          setComment('🌼 昨日と同じくらいの気分。安定してるね♪');
        }
      } catch { setComment(null); }
    })();
  }, [todayStress, todayDate, api]);

  if (!comment) return null;
  return (
    <section style={{
      margin: '8px 16px', padding: '10px 14px', borderRadius: 12,
      background: 'linear-gradient(135deg, #f3f8ec 0%, #fff7f9 100%)',
      border: '1px solid #d8e8c4', fontSize: 13, color: '#5a6a4a', lineHeight: 1.6,
    }}>
      {comment}
    </section>
  );
}
