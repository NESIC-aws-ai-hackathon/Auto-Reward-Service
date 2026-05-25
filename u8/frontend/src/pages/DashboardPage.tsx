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
      </section>

      {/* Monthly Trend Chart */}
      {trend.length > 0 && (
        <section className="chart-card" style={{ padding: 16 }}>
          <h2>📊 月次の余り推移（6ヶ月）</h2>
          <p style={{ fontSize: 11, color: '#8e8270', margin: '4px 0 12px' }}>
            マイナスは翌月に繰り越しません（甘やかしモード🌱）・棒をタップで詳細
          </p>
          <MonthlyTrendChart trend={trend} onSelectMonth={(m) => setMonth(m)} selectedMonth={month} />
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
          <h2>🦥 今月の支出 ({expenses.length}件)</h2>
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

        {/* カテゴリ別円グラフ風バー */}
        {expenses.length > 0 && (
          <div className="category-breakdown" style={{ padding: '8px 4px 16px' }}>
            <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', boxShadow: 'inset 0 0 0 1px #efe7d6' }}>
              {CATEGORY_OPTIONS.map(opt => {
                const sum = expenses.filter(e => e.category === opt.value).reduce((a, b) => a + b.amount, 0);
                const total = expenses.reduce((a, b) => a + b.amount, 0) || 1;
                const w = (sum / total) * 100;
                if (w < 0.5) return null;
                const color = ({
                  recovery: '#f4b8b8', startup: '#ffd58a', maintenance: '#d6c5a8',
                  investment: '#a8d6a8', social: '#b8c8f4', other: '#cfcfcf',
                } as Record<string,string>)[opt.value];
                return <span key={opt.value} style={{ width: `${w}%`, background: color }} title={`${opt.label}: ¥${sum.toLocaleString()}`} />;
              })}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 12px', marginTop: 8, fontSize: 11, color: '#6e6450' }}>
              {CATEGORY_OPTIONS.map(opt => {
                const sum = expenses.filter(e => e.category === opt.value).reduce((a, b) => a + b.amount, 0);
                if (!sum) return null;
                return <span key={opt.value}>{categoryIcon(opt.value)} {opt.label} ¥{sum.toLocaleString()}</span>;
              })}
            </div>
          </div>
        )}

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
                  <small className="exp-meta">{e.timestamp.slice(5, 10)} · {e.category_label || e.category}</small>
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

function MonthlyTrendChart({ trend, onSelectMonth, selectedMonth }: { trend: TrendItem[]; onSelectMonth?: (m: string) => void; selectedMonth?: string }) {
  const values = trend.map((t) => t.balance_for_chart);
  const maxAbs = Math.max(1, ...values.map((v) => Math.abs(v)));
  return (
    <div className="trend-chart">
      {trend.map((t) => {
        const v = t.balance_for_chart;
        const pct = Math.max(8, (Math.abs(v) / maxAbs) * 80);
        const isNeg = v < 0;
        const isSelected = t.month === selectedMonth;
        return (
          <div
            key={t.month}
            className="trend-col"
            onClick={() => onSelectMonth?.(t.month)}
            style={{ cursor: onSelectMonth ? 'pointer' : undefined, opacity: selectedMonth && !isSelected ? 0.55 : 1 }}
          >
            <div className="trend-bar-wrap">
              <div
                className={`trend-bar ${isNeg ? 'neg' : 'pos'}`}
                style={{
                  height: `${pct}%`,
                  outline: isSelected ? '2px solid #7fa05f' : undefined,
                  outlineOffset: 1,
                }}
                title={`${t.month}: ¥${v.toLocaleString()} (タップで詳細)`}
              />
            </div>
            <small className="trend-label">{t.month.slice(5)}</small>
            <em className={`trend-val ${isNeg ? 'neg' : ''}`}>
              {isNeg ? '−' : ''}¥{Math.abs(v).toLocaleString()}
            </em>
          </div>
        );
      })}
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
