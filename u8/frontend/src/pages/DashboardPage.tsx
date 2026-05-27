import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import { getJstMonthString } from '../lib/datetime';
import './DashboardPage.css';

interface DashboardData {
  surplus: { monthly_budget: number; spent: number; remaining: number; ratio: number };
  stress: { level: number; mood: string; date: string } | null;
  recent_expenses: { description: string; amount: number; date: string }[];
  streak_days: number;
}

interface ExpenseItem {
  id: string;
  item: string;
  amount: number;
  category: string;
  category_label?: string;
  excuse_tag?: string;
  source: string;
  store: string;
  timestamp: string;
}

interface TrendItem {
  month: string;
  total_spent: number;
  expense_count: number;
  monthly_surplus: number;
  carryover_in: number;
  balance: number;
  balance_for_chart: number;
  carryover_out: number;
}

const CATEGORY_OPTIONS = [
  { value: 'recovery', label: '回復費' },
  { value: 'startup', label: '起動費' },
  { value: 'maintenance', label: '維持費' },
  { value: 'investment', label: '自己投資' },
  { value: 'social', label: 'つながり費' },
  { value: 'other', label: 'その他' },
];

function categoryIcon(cat: string): string {
  switch (cat) {
    case 'recovery': return '💆';
    case 'startup': return '✨';
    case 'maintenance': return '🏠';
    case 'investment': return '🌱';
    case 'social': return '🤝';
    default: return '🎁';
  }
}

export function DashboardPage() {
  const api = useApi();
  const [data, setData] = useState<DashboardData | null>(null);
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof api.getExpenseSummary>> | null>(null);
  const [expenses, setExpenses] = useState<ExpenseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<ExpenseItem | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [groupByCategory, setGroupByCategory] = useState(true);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['recovery']));

  const currentMonth = getJstMonthString();
  const [month, setMonth] = useState<string>(currentMonth);
  const isCurrentMonth = month === currentMonth;

  const shiftMonth = (delta: number) => {
    const parts = month.split('-').map(Number);
    const y = parts[0] ?? new Date().getFullYear();
    const m = parts[1] ?? new Date().getMonth() + 1;
    const d = new Date(y, m - 1 + delta, 1);
    const next = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    // 未来月には進めない
    if (next > currentMonth) return;
    setMonth(next);
  };

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [d, s, ex] = await Promise.all([
        api.getDashboard().catch(() => null),
        api.getExpenseSummary(month).catch(() => null),
        api.getExpenses(50, month).catch(() => ({ expenses: [] })),
      ]);
      if (d) setData(d);
      if (s) setSummary(s);
      setExpenses((ex?.expenses as ExpenseItem[]) || []);
    } finally {
      setLoading(false);
    }
  }, [api, month]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const trend: TrendItem[] = useMemo(() => (summary?.trend as TrendItem[]) || [], [summary]);
  const surplusBudget = summary?.monthly_surplus ?? data?.surplus.monthly_budget ?? 0;
  const spent = summary?.total_spent ?? data?.surplus.spent ?? 0;
  const carryIn = summary?.carryover_in ?? 0;
  const balance = summary?.balance ?? Math.max(0, surplusBudget - spent);
  const totalBudget = surplusBudget + carryIn;
  const stressLevel = data?.stress?.level ?? 5;
  const mood = data?.stress?.mood || '';
  const recoveryPercent = Math.max(0, Math.min(100, 100 - stressLevel * 10));

  const handleDelete = async (id: string) => {
    if (!confirm('この支出を削除する？')) return;
    try {
      await api.deleteExpense(id);
      await fetchAll();
    } catch { alert('削除に失敗しました'); }
  };

  return (
    <div className="page-content">
      {/* Hero */}
      <section className="compact-hero">
        <img src="/assets/furemaru-support.png" alt="ふれまーるちゃん" />
        <div className="speech-bubble">
          {summary ? (
            <>
              <strong>{balance >= 0 ? 'いい感じ！' : 'ちょっと使いすぎかも…'}</strong>
              <span>
                {balance >= 0
                  ? `今月あと¥${balance.toLocaleString()}使えるよ♪ ${mood ? `気分: ${mood}` : ''}`
                  : `${Math.abs(balance).toLocaleString()}円オーバーだけど、来月リセットだから大丈夫🌱`}
              </span>
            </>
          ) : (
            <>
              <strong>こんにちは！</strong>
              <span>{loading ? '読み込み中...' : 'チャットで話しかけると、ここにデータが表示されるよ♪'}</span>
            </>
          )}
        </div>
      </section>

      {/* Month Navigator */}
      <section className="budget-card" style={{ padding: '10px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <button
            onClick={() => shiftMonth(-1)}
            style={{ border: '1px solid #e3dac1', background: '#fff', borderRadius: 10, padding: '6px 12px', cursor: 'pointer', fontSize: 13 }}
          >‹ 前の月</button>
          <div style={{ textAlign: 'center', flex: 1 }}>
            <b style={{ fontSize: 15, color: '#4a4135' }}>{month.replace('-', '年')}月</b>
            {!isCurrentMonth && (
              <button
                onClick={() => setMonth(currentMonth)}
                style={{ marginLeft: 8, fontSize: 11, color: '#7fa05f', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
              >今月へ</button>
            )}
          </div>
          <button
            onClick={() => shiftMonth(1)}
            disabled={isCurrentMonth}
            style={{ border: '1px solid #e3dac1', background: '#fff', borderRadius: 10, padding: '6px 12px', cursor: isCurrentMonth ? 'not-allowed' : 'pointer', fontSize: 13, opacity: isCurrentMonth ? 0.4 : 1 }}
          >次の月 ›</button>
        </div>
      </section>

      {/* Budget Card */}
      <section className="budget-card">
        <div className="section-title-row">
          <h2>🌿 {isCurrentMonth ? '今月' : month.replace('-', '年') + '月'}のごほうび予算</h2>
          <Link to="/" className="chat-back-link" style={{ fontSize: 12 }}>💬 話す</Link>
        </div>
        <div className="metrics three">
          <article>
            <span className="icon">👛</span>
            <small>使える金額</small>
            <strong>{totalBudget > 0 ? `¥${totalBudget.toLocaleString()}` : '—'}</strong>
            {carryIn > 0 && <em style={{ fontSize: 10, color: '#7fa05f', display: 'block' }}>うち繰越 ¥{carryIn.toLocaleString()}</em>}
          </article>
          <article><span className="icon">🍮</span><small>使った金額</small><strong>{`¥${spent.toLocaleString()}`}</strong></article>
          <article>
            <span className="icon">✨</span>
            <small>{balance >= 0 ? '残り' : 'オーバー'}</small>
            <strong style={{ color: balance < 0 ? '#d97757' : undefined }}>
              {`¥${Math.abs(balance).toLocaleString()}`}
            </strong>
          </article>
        </div>
        {/* Progress bar */}
        {totalBudget > 0 && (
          <div style={{ marginTop: 12, padding: '0 4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#8e8270', marginBottom: 4 }}>
              <span>¥0</span>
              <span>{Math.min(100, Math.round((spent / totalBudget) * 100))}% 使用</span>
              <span>¥{totalBudget.toLocaleString()}</span>
            </div>
            <div style={{ height: 10, borderRadius: 5, background: '#f0ebe3', overflow: 'hidden', position: 'relative' }}>
              <div style={{
                height: '100%', borderRadius: 5, transition: 'width 0.5s ease',
                width: `${Math.min(100, (spent / totalBudget) * 100)}%`,
                background: spent / totalBudget > 1 ? 'linear-gradient(90deg, #f5b8a6, #d97757)' :
                  spent / totalBudget > 0.8 ? 'linear-gradient(90deg, #ffd58a, #e8a040)' :
                  'linear-gradient(90deg, #a4d99a, #83c58c)',
              }} />
            </div>
          </div>
        )}
      </section>

      {/* Monthly Trend Chart — 支出 vs 余り 比較 */}
      {trend.length > 0 && (
        <section className="chart-card" style={{ padding: 16 }}>
          <h2>📊 月別 支出 vs 余り</h2>
          <p style={{ fontSize: 11, color: '#8e8270', margin: '4px 0 12px' }}>
            棒をタップで月を切替・マイナスは翌月に繰り越しません🌱
          </p>
          <MonthlyCompareChart trend={trend} onSelectMonth={(m) => setMonth(m)} selectedMonth={month} />
        </section>
      )}

      {/* Stress Donut */}
      <div className="dashboard-grid">
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
            <p style={{ textAlign: 'center', padding: '2rem 0', fontSize: 12, color: '#a69c8c' }}>
              チャットで話すとストレスレベルが表示されるよ
            </p>
          )}
        </article>
        <article className="chart-card">
          <h2>🔥 連続日数</h2>
          <div style={{ textAlign: 'center', padding: '2rem 0' }}>
            <div style={{ fontSize: 48, fontWeight: 'bold', color: '#83c58c' }}>{data?.streak_days ?? 0}</div>
            <p style={{ fontSize: 12, color: '#8e8270' }}>日連続で記録中♪</p>
          </div>
        </article>
      </div>

      {/* Expense List with edit/delete - グループ化表示 */}
      <section className="activity-list">
        <div className="section-title-row">
          <h2>🦥 {isCurrentMonth ? '今月' : month.replace('-', '年') + '月'}の支出 ({expenses.length}件)</h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn-add-expense"
              style={{ background: '#f0e6d2', color: '#5a4d3a' }}
              onClick={() => setGroupByCategory(v => !v)}
            >
              {groupByCategory ? '時系列' : 'カテゴリ別'}
            </button>
            <button className="btn-add-expense" onClick={() => setShowAdd(true)}>＋ 追加</button>
          </div>
        </div>

        {/* カテゴリ別ドーナツ + 内訳 */}
        {expenses.length > 0 && (() => {
          const total = expenses.reduce((a, b) => a + b.amount, 0) || 1;
          const catData = CATEGORY_OPTIONS.map(opt => ({
            ...opt,
            sum: expenses.filter(e => e.category === opt.value).reduce((a, b) => a + b.amount, 0),
          })).filter(c => c.sum > 0);
          const colors: Record<string, string> = {
            recovery: '#f4b8b8', startup: '#ffd58a', maintenance: '#d6c5a8',
            investment: '#a8d6a8', social: '#b8c8f4', other: '#cfcfcf',
          };
          let acc = 0;
          const gradientStops = catData.map(c => {
            const start = acc;
            acc += (c.sum / total) * 100;
            return `${colors[c.value] || '#ccc'} ${start}% ${acc}%`;
          }).join(', ');
          return (
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 8px 16px' }}>
              {/* Mini donut */}
              <div style={{
                width: 80, height: 80, borderRadius: '50%', flexShrink: 0,
                background: `conic-gradient(${gradientStops})`,
                display: 'grid', placeItems: 'center',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              }}>
                <div style={{ width: 48, height: 48, borderRadius: '50%', background: '#fffdf7', display: 'grid', placeItems: 'center' }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#4a4135' }}>¥{total.toLocaleString()}</span>
                </div>
              </div>
              {/* Category labels */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 12 }}>
                {catData.map(c => (
                  <div key={c.value} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 3, background: colors[c.value], flexShrink: 0 }} />
                    <span style={{ color: '#6e6450', flex: 1 }}>{categoryIcon(c.value)} {c.label}</span>
                    <strong style={{ color: '#4a4135' }}>¥{c.sum.toLocaleString()}</strong>
                    <span style={{ fontSize: 10, color: '#a69c8c' }}>({Math.round((c.sum / total) * 100)}%)</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}

        {groupByCategory ? (
          <div className="expense-groups">
            {CATEGORY_OPTIONS.map(opt => {
              const items = expenses.filter(e => e.category === opt.value);
              if (items.length === 0) return null;
              const sum = items.reduce((a, b) => a + b.amount, 0);
              const open = expandedCategories.has(opt.value);
              return (
                <details
                  key={opt.value}
                  open={open}
                  onToggle={(e) => {
                    const isOpen = (e.target as HTMLDetailsElement).open;
                    setExpandedCategories(prev => {
                      const n = new Set(prev);
                      if (isOpen) n.add(opt.value); else n.delete(opt.value);
                      return n;
                    });
                  }}
                  style={{ background: '#fff', borderRadius: 12, marginBottom: 8, padding: '8px 12px', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}
                >
                  <summary style={{ cursor: 'pointer', listStyle: 'none', display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                    <span style={{ fontSize: 20 }}>{categoryIcon(opt.value)}</span>
                    <strong style={{ flex: 1 }}>{opt.label}</strong>
                    <em style={{ fontStyle: 'normal', color: '#8e7e5e', fontSize: 12 }}>{items.length}件</em>
                    <strong>¥{sum.toLocaleString()}</strong>
                    <span style={{ fontSize: 12, color: '#aaa' }}>{open ? '▾' : '▸'}</span>
                  </summary>
                  <ul className="expense-list" style={{ marginTop: 8 }}>
                    {items.map(e => (
                      <li key={e.id} className="expense-item">
                        <span className="exp-icon">{categoryIcon(e.category)}</span>
                        <div className="exp-main">
                          <b className="exp-item-name">{e.item}</b>
                          {e.excuse_tag && <span className="exp-excuse">{e.excuse_tag}</span>}
                          <small className="exp-meta">{e.timestamp.slice(5, 10)}</small>
                        </div>
                        <em className="exp-amount">¥{e.amount.toLocaleString()}</em>
                        <div className="exp-actions">
                          <button onClick={() => setEditing(e)} aria-label="編集">✎</button>
                          <button onClick={() => handleDelete(e.id)} aria-label="削除">🗑</button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </details>
              );
            })}
            {expenses.length === 0 && (
              <p style={{ fontSize: 12, color: '#8e8270', textAlign: 'center', padding: 16 }}>
                チャットで支出を報告するか、＋ボタンから追加してね♪
              </p>
            )}
          </div>
        ) : (
          <ul className="expense-list">
            {expenses.length > 0 ? expenses.map((e) => (
              <li key={e.id} className="expense-item">
                <span className="exp-icon">{categoryIcon(e.category)}</span>
                <div className="exp-main">
                  <b className="exp-item-name">{e.item}</b>
                  {e.excuse_tag && <span className="exp-excuse">{e.excuse_tag}</span>}
                  <small className="exp-meta">
                    {e.timestamp.slice(5, 10)} · {e.category_label || e.category}
                    {e.source === 'chat' ? ' · 💬' : e.source === 'receipt' ? ' · 🧾' : ' · ✍️'}
                  </small>
                </div>
                <em className="exp-amount">¥{e.amount.toLocaleString()}</em>
                <div className="exp-actions">
                  <button onClick={() => setEditing(e)} aria-label="編集">✎</button>
                  <button onClick={() => handleDelete(e.id)} aria-label="削除">🗑</button>
                </div>
              </li>
            )) : (
              <li className="expense-item empty">
                <span>📝</span>
                <p>チャットで支出を報告するか、＋ボタンから追加してね♪</p>
              </li>
            )}
          </ul>
        )}
      </section>

      {/* Wishlist link */}
      <section className="budget-card">
        <div className="section-title-row">
          <h2>💝 ほしいものリスト</h2>
          <Link to="/settings" className="chat-back-link" style={{ fontSize: 12 }}>設定へ</Link>
        </div>
        <p style={{ fontSize: 12, color: '#8e8270', padding: '8px 0' }}>
          Amazonの公開ほしい物リストURLを登録すると、ふれまーるちゃんがチャットでそっと提案してくれるよ✨
        </p>
      </section>

      {loading && <div className="loading-state">読み込み中...</div>}

      {editing && (
        <ExpenseEditModal
          expense={editing}
          onClose={() => setEditing(null)}
          onSave={async (updates) => {
            try {
              await api.updateExpense(editing.id, updates);
              setEditing(null);
              await fetchAll();
            } catch { alert('更新に失敗しました'); }
          }}
        />
      )}

      {showAdd && (
        <ExpenseAddModal
          onClose={() => setShowAdd(false)}
          onSave={async (data) => {
            try {
              await api.postExpense(data);
              setShowAdd(false);
              await fetchAll();
            } catch { alert('追加に失敗しました'); }
          }}
        />
      )}
    </div>
  );
}

function MonthlyCompareChart({ trend, onSelectMonth, selectedMonth }: { trend: TrendItem[]; onSelectMonth?: (m: string) => void; selectedMonth?: string }) {
  const maxVal = Math.max(1, ...trend.map(t => Math.max(t.total_spent, Math.abs(t.balance_for_chart), t.monthly_surplus)));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {/* Legend */}
      <div style={{ display: 'flex', gap: 14, fontSize: 11, color: '#6b6258', marginBottom: 6, justifyContent: 'center' }}>
        <span><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: '#ffc784', marginRight: 4 }} />支出</span>
        <span><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: '#83c58c', marginRight: 4 }} />余り</span>
        <span style={{ borderBottom: '2px dashed #c5b89a', paddingBottom: 1 }}>予算</span>
      </div>
      <div className="trend-chart" style={{ height: 150 }}>
        {trend.map((t) => {
          const spentPct = Math.max(4, (t.total_spent / maxVal) * 85);
          const balPct = Math.max(4, (Math.abs(t.balance_for_chart) / maxVal) * 85);
          const isNeg = t.balance_for_chart < 0;
          const isSelected = t.month === selectedMonth;
          return (
            <div
              key={t.month}
              className="trend-col"
              onClick={() => onSelectMonth?.(t.month)}
              style={{ cursor: 'pointer', opacity: selectedMonth && !isSelected ? 0.5 : 1, flex: 1, gap: 2 }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 110, width: '100%', justifyContent: 'center' }}>
                {/* 支出バー */}
                <div
                  style={{
                    width: '38%', height: `${spentPct}%`, borderRadius: '4px 4px 0 0',
                    background: 'linear-gradient(180deg, #ffd58a, #ffc784)',
                    outline: isSelected ? '2px solid #e8a040' : undefined,
                  }}
                  title={`支出 ¥${t.total_spent.toLocaleString()}`}
                />
                {/* 余りバー */}
                <div
                  style={{
                    width: '38%', height: `${balPct}%`, borderRadius: '4px 4px 0 0',
                    background: isNeg ? 'linear-gradient(180deg, #f5b8a6, #d97757)' : 'linear-gradient(180deg, #a4d99a, #83c58c)',
                    outline: isSelected ? '2px solid #7fa05f' : undefined,
                  }}
                  title={`余り ¥${t.balance_for_chart.toLocaleString()}`}
                />
              </div>
              <small style={{ fontSize: 10, color: '#8e8270', marginTop: 3 }}>{t.month.slice(5)}月</small>
              <em style={{ fontSize: 9, color: isNeg ? '#d97757' : '#6b6258', fontStyle: 'normal' }}>
                {isNeg ? '−' : ''}¥{Math.abs(t.balance_for_chart).toLocaleString()}
              </em>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ExpenseEditModal({
  expense,
  onClose,
  onSave,
}: {
  expense: ExpenseItem;
  onClose: () => void;
  onSave: (updates: { item?: string; amount?: number; category?: string; excuse_tag?: string }) => void;
}) {
  const [item, setItem] = useState(expense.item);
  const [amount, setAmount] = useState(String(expense.amount));
  const [category, setCategory] = useState(expense.category);
  const [excuseTag, setExcuseTag] = useState(expense.excuse_tag || '');

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3>✏️ 支出を編集</h3>
        <label>項目<input value={item} onChange={(e) => setItem(e.target.value)} /></label>
        <label>金額<input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
        <label>カテゴリ
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORY_OPTIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </label>
        <label>言い訳タグ<input value={excuseTag} onChange={(e) => setExcuseTag(e.target.value)} placeholder="☕ 朝の起動儀式費" /></label>
        <div className="modal-actions">
          <button onClick={onClose}>キャンセル</button>
          <button className="primary" onClick={() => onSave({ item, amount: Number(amount), category, excuse_tag: excuseTag })}>保存</button>
        </div>
      </div>
    </div>
  );
}

function ExpenseAddModal({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: (data: { item: string; amount: number; category?: string }) => void;
}) {
  const [item, setItem] = useState('');
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('recovery');

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3>➕ 支出を追加</h3>
        <label>項目<input value={item} onChange={(e) => setItem(e.target.value)} placeholder="コーヒー" /></label>
        <label>金額<input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="500" /></label>
        <label>カテゴリ
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORY_OPTIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </label>
        <p style={{ fontSize: 11, color: '#8e8270' }}>言い訳タグはふれまーるちゃんが自動でつけてくれるよ✨</p>
        <div className="modal-actions">
          <button onClick={onClose}>キャンセル</button>
          <button
            className="primary"
            disabled={!item || !amount}
            onClick={() => onSave({ item, amount: Number(amount), category })}
          >追加</button>
        </div>
      </div>
    </div>
  );
}
