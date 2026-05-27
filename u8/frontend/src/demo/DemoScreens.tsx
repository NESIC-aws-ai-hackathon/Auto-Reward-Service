import { useDemo } from "./demoState";
import type { FuremaruEmotion, DemoExpense, DemoRecommendation } from "./demoTypes";
// 本番ページのCSSを使用
import "../pages/ChatPage.css";
import "../pages/DashboardPage.css";
import "../pages/DiaryPage.css";
import "../pages/RecoveryPage.css";

const emotionImage: Record<FuremaruEmotion, string> = {
  neutral: "/assets/emotions/neutral.png",
  happy: "/assets/emotions/happy.png",
  support: "/assets/emotions/support.png",
  shy: "/assets/emotions/shy.png",
  excited: "/assets/emotions/excited.png",
  listening: "/assets/emotions/listening.png",
};

const yen = (n: number) => `¥${n.toLocaleString()}`;

const sourceLabel: Record<string, string> = {
  rakuten: "🛍 楽天で見てみる",
  hotpepper: "🍴 お店をチェック",
  youtube: "▶ YouTubeで見る",
  amazon_wishlist: "💝 ほしいものリストから",
  zero_yen: "🌿 0円回復",
};

function categoryIcon(cat: string): string {
  switch (cat) {
    case "recovery": return "💆";
    case "startup": return "✨";
    case "maintenance": return "🏠";
    case "investment": return "🌱";
    case "social": return "🤝";
    case "reward": return "🎁";
    default: return "🎁";
  }
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    return `${d.getHours()}:${d.getMinutes().toString().padStart(2, "0")}`;
  } catch {
    return "";
  }
}

// ============================================================
// チャット画面 — 本番の ChatPage と完全同一の HTML/CSS 構造
// ============================================================
export function DemoChatScreen() {
  const { state } = useDemo();
  const isVoice = state.voiceStatus !== "idle";

  return (
    <div className="page-content">
      {/* Hero Card - 本番と完全同一 */}
      <section className="chat-hero">
        <div className="hero-character">
          <img src="/assets/furemaru-fullbody.png" alt="ふれまーるちゃん" />
        </div>
        <div className="speech-bubble">
          <strong>こんにちは！</strong>
          <span>ふれまーるちゃんだよ〜！</span>
          <span>今日も生き延びてえらいね。がんばらなくていいんだよ？ 🍀</span>
        </div>
      </section>

      {/* Memory Panel - 本番と同じ「ふれまーるちゃんの記憶」 */}
      {state.messages.length > 0 && (
        <section style={{
          margin: '12px 0', padding: '12px 14px', borderRadius: 14,
          background: 'linear-gradient(135deg, #fff7f9 0%, #f3f8ec 100%)',
          border: '1px solid #f0d8e0', fontSize: 13, color: '#5a4a52',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 18 }}>💭</span>
            <strong style={{ flex: 1 }}>ふれまーるちゃんの記憶</strong>
          </div>
          <div style={{ marginTop: 6, lineHeight: 1.5 }}>スイーツが好きだったよね / もゆ12日も一緒だよ♪ / 最近疲れ気味かも…動画見る？</div>
        </section>
      )}

      {/* Chat Thread - 本番と完全同一の構造 */}
      {state.messages.length > 0 && (
        <section className="chat-thread">
          {state.messages.map((msg) => (
            <article key={msg.id} className={`message ${msg.role === "user" ? "user" : "assistant"}`}>
              {msg.role === "assistant" && (
                <img src={emotionImage[msg.emotion || "support"]} alt="" className="emotion-avatar" />
              )}
              {msg.role === "assistant" ? (
                <div className="msg-wrap">
                  <small>ふれまーるちゃん</small>
                  <p>{msg.text}</p>
                  {msg.reco && msg.reco.url && (
                    <a
                      href={msg.reco.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`chat-reco-card chat-reco-${msg.reco.type}`}
                    >
                      {msg.reco.image && <img src={msg.reco.image} alt="" />}
                      <div className="reco-body">
                        <small className="reco-type">
                          {msg.reco.type === "product" && "🛍 楽天で見てみる"}
                          {msg.reco.type === "video" && "▶ YouTubeで見る"}
                          {msg.reco.type === "wishlist" && "💝 ほしいものリストから"}
                          {msg.reco.type === "restaurant" && "🍴 お店をチェック"}
                        </small>
                        <b>{msg.reco.title}</b>
                        {msg.reco.price ? <em>¥{msg.reco.price.toLocaleString()}</em> : null}
                        {msg.reco.reason && <p className="reco-reason">{msg.reco.reason}</p>}
                      </div>
                    </a>
                  )}
                  {msg.suggestion && (
                    <span className="chat-suggestion-link">{msg.suggestion.label}</span>
                  )}
                </div>
              ) : (
                <p>{msg.text}</p>
              )}
              <time>{formatTime(msg.timestamp)}</time>
            </article>
          ))}
          {/* Typing indicator - 本番と同一 */}
          {state.voiceStatus === "thinking" && (
            <article className="message assistant">
              <img src={emotionImage["listening"]} alt="" className="emotion-avatar" />
              <div className="msg-wrap">
                <div className="typing-indicator"><span></span><span></span><span></span></div>
              </div>
            </article>
          )}
        </section>
      )}

      {/* Quick Section (初回表示用 - 本番と同一) */}
      {state.messages.length === 0 && !isVoice && (
        <section className="quick-section">
          <h2>🌿 話してみる？</h2>
          <div className="quick-grid">
            <button className="quick-card">
              <span>😮‍💨</span><strong>疲れた</strong>
            </button>
            <button className="quick-card">
              <span>☕</span><strong>支出を記録</strong>
            </button>
            <button className="quick-card">
              <span>🍮</span><strong>ご褒美</strong>
            </button>
          </div>
        </section>
      )}

      {/* Receipt overlay (demo用) */}
      {state.receiptStage !== "hidden" && state.receiptStage !== "confirmed" && (
        <div className="demo-receipt-overlay">
          {state.receiptStage === "upload" && (
            <div className="demo-receipt-card glass-card">
              <div style={{ fontSize: 32, textAlign: "center" }}>📷</div>
              <div style={{ fontWeight: 800, color: "#2f7c51", fontSize: 14, textAlign: "center" }}>レシートをアップロード中…</div>
              <div className="demo-receipt-bar"><div className="demo-receipt-bar-fill" style={{ width: "30%" }} /></div>
            </div>
          )}
          {state.receiptStage === "parsing" && (
            <div className="demo-receipt-card glass-card">
              <div style={{ fontSize: 32, textAlign: "center" }}>🔍</div>
              <div style={{ fontWeight: 800, color: "#2f7c51", fontSize: 14, textAlign: "center" }}>OCRで読み取り中…</div>
              <div className="demo-receipt-bar"><div className="demo-receipt-bar-fill" style={{ width: "70%" }} /></div>
            </div>
          )}
          {state.receiptStage === "result" && state.receiptResult && (
            <div className="demo-receipt-card glass-card">
              <div style={{ fontWeight: 800, color: "#2f7c51", fontSize: 14, marginBottom: 8 }}>📋 解析結果</div>
              <div className="demo-receipt-row"><span>店舗</span><span>{state.receiptResult.storeName}</span></div>
              <div className="demo-receipt-row"><span>合計</span><span>{yen(state.receiptResult.totalAmount)}</span></div>
              <div style={{ margin: "8px 0", borderTop: "1px solid rgba(143,196,155,0.3)" }} />
              <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>品目 → 意味づけ変換</div>
              {state.receiptResult.items.map((item, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", fontSize: 12, borderBottom: "1px solid rgba(0,0,0,0.04)" }}>
                  <span style={{ color: "#555" }}>{item.name} ({yen(item.amount)})</span>
                  <span className="demo-tag" style={{ fontSize: 10 }}>{item.meaningLabel}</span>
                </div>
              ))}
              <div style={{ marginTop: 10, background: "rgba(143,196,155,0.18)", padding: "8px 12px", borderRadius: 12, fontSize: 12, color: "#2f7c51" }}>
                💭 {state.receiptResult.furemaruComment}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Input Area - 本番と完全同一 (常にbottomに固定) */}
      <section className="input-area">
        {/* Voice indicator inline - 本番と同一構造 */}
        {isVoice && (
          <div className="voice-active-bar">
            <span className="pulse-dot"></span>
            <span>
              {state.voiceStatus === "listening" && (
                state.transcripts.length > 0
                  ? `「${state.transcripts[state.transcripts.length - 1]?.text}」`
                  : "話してね…聞いてるよ♪"
              )}
              {state.voiceStatus === "thinking" && "ふれまーるちゃん考え中…♪"}
              {state.voiceStatus === "speaking" && "返事するね♪"}
            </span>
            <div className="wave-bar">
              {Array.from({ length: 7 }).map((_, i) => (
                <i key={i} style={{ animationDelay: `${i * 0.08}s` }} />
              ))}
            </div>
          </div>
        )}
        <div className="chat-input-row">
          <button className="input-action-btn receipt-btn">📷</button>
          <textarea placeholder="話しかけてみてね♪" rows={1} readOnly />
          <button className={`input-action-btn ${isVoice ? "mic-btn active" : "mic-btn"}`}>
            {isVoice ? "⏹" : "🎙"}
          </button>
        </div>
      </section>
    </div>
  );
}

// ============================================================
// ダッシュボード — 本番の DashboardPage と完全同一の構造
// ============================================================
export function DemoDashboardScreen() {
  const { state } = useDemo();
  const m = state.dashboardMetrics;
  const budget = 10000;
  const spent = budget - m.monthlySurplus;
  const balance = m.monthlySurplus;
  const recoveryPercent = Math.max(0, Math.min(100, m.moodScore));
  const totalBudget = budget;
  const spentRatio = Math.min(100, Math.round((spent / totalBudget) * 100));

  const month = new Date();
  const monthLabel = `${month.getFullYear()}年${month.getMonth() + 1}月`;

  return (
    <div className="page-content">
      {/* Hero - 本番と完全同一 */}
      <section className="compact-hero">
        <img src="/assets/furemaru-support.png" alt="ふれまーるちゃん" />
        <div className="speech-bubble">
          <strong>{balance >= 0 ? "いい感じ！" : "ちょっと使いすぎかも…"}</strong>
          <span>
            {balance >= 0
              ? `今月あと${yen(balance)}使えるよ♪`
              : `${yen(Math.abs(balance))}オーバーだけど、来月リセットだから大丈夫🌱`}
          </span>
        </div>
      </section>

      {/* Month Navigator - 本番と同一 */}
      <section className="budget-card" style={{ padding: '10px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <button style={{ border: '1px solid #e3dac1', background: '#fff', borderRadius: 10, padding: '6px 12px', cursor: 'pointer', fontSize: 13 }}>‹ 前の月</button>
          <div style={{ textAlign: 'center', flex: 1 }}>
            <b style={{ fontSize: 15, color: '#4a4135' }}>{monthLabel}</b>
          </div>
          <button style={{ border: '1px solid #e3dac1', background: '#fff', borderRadius: 10, padding: '6px 12px', cursor: 'not-allowed', fontSize: 13, opacity: 0.4 }}>次の月 ›</button>
        </div>
      </section>

      {/* Budget Card - 本番と完全同一 (metrics three 構造) */}
      <section className="budget-card">
        <div className="section-title-row">
          <h2>🌿 今月のごほうび予算</h2>
          <span className="chat-back-link" style={{ fontSize: 12 }}>💬 話す</span>
        </div>
        <div className="metrics three">
          <article>
            <span className="icon">👛</span>
            <small>使える金額</small>
            <strong>{yen(totalBudget)}</strong>
          </article>
          <article>
            <span className="icon">🍮</span>
            <small>使った金額</small>
            <strong>{yen(spent)}</strong>
          </article>
          <article>
            <span className="icon">✨</span>
            <small>{balance >= 0 ? "残り" : "オーバー"}</small>
            <strong style={{ color: balance < 0 ? '#d97757' : undefined }}>{yen(Math.abs(balance))}</strong>
          </article>
        </div>
        {/* Progress bar - 本番と同一 */}
        <div style={{ marginTop: 12, padding: '0 4px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#8e8270', marginBottom: 4 }}>
            <span>¥0</span>
            <span>{spentRatio}% 使用</span>
            <span>{yen(totalBudget)}</span>
          </div>
          <div style={{ height: 10, borderRadius: 5, background: '#f0ebe3', overflow: 'hidden', position: 'relative' }}>
            <div style={{
              height: '100%', borderRadius: 5, transition: 'width 0.5s ease',
              width: `${spentRatio}%`,
              background: spentRatio > 100 ? 'linear-gradient(90deg, #f5b8a6, #d97757)' :
                spentRatio > 80 ? 'linear-gradient(90deg, #ffd58a, #e8a040)' :
                'linear-gradient(90deg, #a4d99a, #83c58c)',
            }} />
          </div>
        </div>
      </section>

      {/* Stress Donut + Streak - 本番と完全同一 */}
      <div className="dashboard-grid">
        <article className="chart-card">
          <h2>🌿 ストレス・回復バランス</h2>
          <div className="donut" style={{ background: `conic-gradient(#83c58c 0 ${recoveryPercent}%, #ffc784 ${recoveryPercent}% 100%)` }}>
            <span>{recoveryPercent}%</span>
          </div>
          <div className="legend">
            <p><i className="green"></i>回復 {recoveryPercent}%</p>
            <p><i className="orange"></i>ストレス {100 - recoveryPercent}%</p>
          </div>
        </article>
        <article className="chart-card">
          <h2>🔥 連続日数</h2>
          <div style={{ textAlign: "center", padding: "2rem 0" }}>
            <div style={{ fontSize: 48, fontWeight: "bold", color: "#83c58c" }}>12</div>
            <p style={{ fontSize: 12, color: "#8e8270" }}>日連続で記録中♪</p>
          </div>
        </article>
      </div>

      {/* Monthly History Chart - デモ用豪華グラフ */}
      <MonthlyHistoryChart />
      <MonthlyMoodChart />

      {/* Expense List - 本番と同一構造 */}
      {state.expenses.length > 0 && (
        <section className="activity-list">
          <div className="section-title-row">
            <h2>🦥 今月の支出 ({state.expenses.length}件)</h2>
          </div>
          {/* Mini donut chart - 本番と同一 */}
          <ExpenseMiniChart expenses={state.expenses} />
          {/* カテゴリ別グループ */}
          <div className="expense-groups">
            {(() => {
              const categories = [...new Set(state.expenses.map(e => e.category))];
              return categories.map(cat => {
                const items = state.expenses.filter(e => e.category === cat);
                const sum = items.reduce((a, b) => a + b.amount, 0);
                return (
                  <details key={cat} open style={{ background: '#fff', borderRadius: 12, marginBottom: 8, padding: '8px 12px', boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}>
                    <summary style={{ cursor: 'pointer', listStyle: 'none', display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                      <span style={{ fontSize: 20 }}>{categoryIcon(cat)}</span>
                      <strong style={{ flex: 1 }}>{items[0]?.meaningLabel || cat}</strong>
                      <em style={{ fontStyle: 'normal', color: '#8e7e5e', fontSize: 12 }}>{items.length}件</em>
                      <strong>{yen(sum)}</strong>
                      <span style={{ fontSize: 12, color: '#aaa' }}>▾</span>
                    </summary>
                    <ul className="expense-list" style={{ marginTop: 8 }}>
                      {items.map(e => (
                        <li key={e.id} className="expense-item">
                          <span className="exp-icon">{categoryIcon(e.category)}</span>
                          <div className="exp-main">
                            <b className="exp-item-name">{e.itemName}</b>
                            <span className="exp-excuse">{e.meaningLabel}</span>
                            <small className="exp-meta">{e.timestamp.slice(5, 10)}{e.source === 'receipt' ? ' · 🧾' : ' · 💬'}</small>
                          </div>
                          <em className="exp-amount">{yen(e.amount)}</em>
                        </li>
                      ))}
                    </ul>
                  </details>
                );
              });
            })()}
          </div>
        </section>
      )}

      {/* Reward Carryover - 本番と同一 */}
      {state.rewardCarryover && (
        <section className="chart-card" style={{ padding: 16, marginTop: 12 }}>
          <h2>{state.rewardCarryover.scenario === "surplus" ? "🎁 ごほうび予算の繰越" : "🌱 来月リスタート"}</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span style={{ color: "#8e8270" }}>今月の予算</span><span>{yen(state.rewardCarryover.currentMonthBudget)}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span style={{ color: "#8e8270" }}>使った金額</span><span>{yen(state.rewardCarryover.currentMonthUsed)}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 16, fontWeight: 900, color: "#2f7c51", paddingTop: 8, borderTop: "1px dashed rgba(0,0,0,0.1)" }}>
              <span>来月の予算</span><span>{yen(state.rewardCarryover.nextMonthBudget)}</span>
            </div>
            <div style={{ marginTop: 8, background: "rgba(143,196,155,0.15)", padding: "10px 14px", borderRadius: 12, fontSize: 13, fontWeight: 600, color: "#4a4538" }}>
              💭 {state.rewardCarryover.message}
            </div>
          </div>
        </section>
      )}

      {/* Wishlist link - 本番と同一 */}
      <section className="budget-card" style={{ marginTop: 12 }}>
        <div className="section-title-row">
          <h2>💝 ほしいものリスト</h2>
          <span className="chat-back-link" style={{ fontSize: 12 }}>設定へ</span>
        </div>
        <p style={{ fontSize: 12, color: '#8e8270', padding: '8px 0' }}>
          Amazonのほしい物リストと連携して、タイミングよくご褒美を提案するよ♪
        </p>
      </section>
    </div>
  );
}

function MonthlyHistoryChart() {
  const months = ["1月", "2月", "3月", "4月", "5月"];
  const budgets = [10000, 10000, 12000, 12000, 10000];
  const spents = [8200, 9500, 7800, 11200, 3200];
  const maxVal = 14000;
  const barW = 28;
  const gap = 12;
  const chartH = 120;
  const totalW = months.length * (barW * 2 + gap) + gap * (months.length - 1) + 20;

  return (
    <section className="chart-card" style={{ padding: 16, marginTop: 12 }}>
      <h2>📊 月別ごほうび予算の推移</h2>
      <p style={{ fontSize: 11, color: "#8e8270", margin: "4px 0 12px" }}>過去5ヶ月分の予算 vs 使用額</p>
      <div style={{ overflowX: "auto", padding: "0 4px" }}>
        <svg width={totalW} height={chartH + 40} viewBox={`0 0 ${totalW} ${chartH + 40}`} style={{ display: "block", margin: "0 auto" }}>
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((r, i) => (
            <g key={i}>
              <line x1={0} y1={chartH * (1 - r)} x2={totalW} y2={chartH * (1 - r)} stroke="#e8e2d8" strokeWidth={0.5} strokeDasharray={i === 0 ? "0" : "3,3"} />
              <text x={totalW - 2} y={chartH * (1 - r) - 2} fontSize={8} fill="#bbb" textAnchor="end">¥{Math.round(maxVal * r / 1000)}k</text>
            </g>
          ))}
          {months.map((m, i) => {
            const x = i * (barW * 2 + gap + 10) + 10;
            const bH = (budgets[i]! / maxVal) * chartH;
            const sH = (spents[i]! / maxVal) * chartH;
            const isOver = spents[i]! > budgets[i]!;
            return (
              <g key={m}>
                {/* Budget bar */}
                <rect x={x} y={chartH - bH} width={barW} height={bH} rx={4} fill="url(#gradBudget)" opacity={0.7} />
                {/* Spent bar */}
                <rect x={x + barW + 2} y={chartH - sH} width={barW} height={sH} rx={4} fill={isOver ? "url(#gradOver)" : "url(#gradSpent)"} />
                {/* Value labels */}
                <text x={x + barW / 2} y={chartH - bH - 3} fontSize={8} fill="#83c58c" textAnchor="middle" fontWeight="bold">¥{(budgets[i]! / 1000).toFixed(0)}k</text>
                <text x={x + barW + 2 + barW / 2} y={chartH - sH - 3} fontSize={8} fill={isOver ? "#d97757" : "#e8a040"} textAnchor="middle" fontWeight="bold">¥{(spents[i]! / 1000).toFixed(1)}k</text>
                {/* Month label */}
                <text x={x + barW + 1} y={chartH + 16} fontSize={11} fill="#6e6450" textAnchor="middle" fontWeight="bold">{m}</text>
                {i === months.length - 1 && <text x={x + barW + 1} y={chartH + 28} fontSize={9} fill="#83c58c" textAnchor="middle">今月</text>}
              </g>
            );
          })}
          {/* Gradient defs */}
          <defs>
            <linearGradient id="gradBudget" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#a4d99a" />
              <stop offset="100%" stopColor="#83c58c" />
            </linearGradient>
            <linearGradient id="gradSpent" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#ffd58a" />
              <stop offset="100%" stopColor="#e8a040" />
            </linearGradient>
            <linearGradient id="gradOver" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f5b8a6" />
              <stop offset="100%" stopColor="#d97757" />
            </linearGradient>
          </defs>
        </svg>
      </div>
      <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 8, fontSize: 11 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: "linear-gradient(#a4d99a, #83c58c)" }} />予算</span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: "linear-gradient(#ffd58a, #e8a040)" }} />使用額</span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}><span style={{ width: 10, height: 10, borderRadius: 3, background: "linear-gradient(#f5b8a6, #d97757)" }} />超過</span>
      </div>
    </section>
  );
}

function MonthlyMoodChart() {
  const days = Array.from({ length: 27 }, (_, i) => i + 1);
  const moodData = [62, 58, 65, 55, 48, 52, 70, 72, 60, 55, 50, 45, 58, 63, 68, 72, 75, 70, 65, 60, 68, 72, 78, 74, 70, 72, 72];
  const chartW = 320;
  const chartH = 80;
  const maxMood = 100;
  const padding = 8;

  const points = days.map((_d, i) => {
    const x = padding + (i / (days.length - 1)) * (chartW - padding * 2);
    const y = chartH - padding - (moodData[i]! / maxMood) * (chartH - padding * 2);
    return `${x},${y}`;
  });
  const areaPoints = [...points, `${padding + (chartW - padding * 2)},${chartH - padding}`, `${padding},${chartH - padding}`];

  return (
    <section className="chart-card" style={{ padding: 16, marginTop: 12 }}>
      <h2>😊 今月の気分スコア推移</h2>
      <p style={{ fontSize: 11, color: "#8e8270", margin: "4px 0 8px" }}>毎日の記録から自動計算</p>
      <svg width={chartW} height={chartH + 20} viewBox={`0 0 ${chartW} ${chartH + 20}`} style={{ display: "block", width: "100%" }}>
        {/* Background gradient area */}
        <defs>
          <linearGradient id="moodAreaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#83c58c" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#83c58c" stopOpacity="0.02" />
          </linearGradient>
          <linearGradient id="moodLineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#a4d99a" />
            <stop offset="50%" stopColor="#83c58c" />
            <stop offset="100%" stopColor="#5bab6e" />
          </linearGradient>
        </defs>
        {/* Grid */}
        {[25, 50, 75].map(v => {
          const y = chartH - padding - (v / maxMood) * (chartH - padding * 2);
          return <line key={v} x1={padding} y1={y} x2={chartW - padding} y2={y} stroke="#e8e2d8" strokeWidth={0.5} strokeDasharray="3,3" />;
        })}
        {/* Area fill */}
        <polygon points={areaPoints.join(" ")} fill="url(#moodAreaGrad)" />
        {/* Line */}
        <polyline points={points.join(" ")} fill="none" stroke="url(#moodLineGrad)" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
        {/* Today dot */}
        <circle cx={points[points.length - 1]!.split(",")[0]} cy={points[points.length - 1]!.split(",")[1]} r={5} fill="#5bab6e" stroke="#fff" strokeWidth={2} />
        {/* Labels */}
        <text x={padding} y={chartH + 14} fontSize={9} fill="#8e8270">1日</text>
        <text x={chartW / 2} y={chartH + 14} fontSize={9} fill="#8e8270" textAnchor="middle">15日</text>
        <text x={chartW - padding} y={chartH + 14} fontSize={9} fill="#8e8270" textAnchor="end">27日(今日)</text>
        <text x={chartW - padding} y={padding + 2} fontSize={9} fill="#5bab6e" textAnchor="end" fontWeight="bold">72pt</text>
      </svg>
      <div style={{ marginTop: 8, background: "rgba(143,196,155,0.12)", padding: "8px 12px", borderRadius: 10, fontSize: 11, color: "#4a6b50" }}>
        💡 先週より平均+8pt！最近いい調子だね♪ 回復に使ったお金がちゃんと効いてるよ
      </div>
    </section>
  );
}

function ExpenseMiniChart({ expenses }: { expenses: DemoExpense[] }) {
  const total = expenses.reduce((a, b) => a + b.amount, 0) || 1;
  const colors: Record<string, string> = {
    recovery: "#f4b8b8", startup: "#ffd58a", maintenance: "#d6c5a8",
    investment: "#a8d6a8", social: "#b8c8f4", reward: "#ffb3ae", other: "#cfcfcf",
  };
  const catMap: Record<string, { label: string; sum: number }> = {};
  for (const e of expenses) {
    if (!catMap[e.category]) catMap[e.category] = { label: e.meaningLabel, sum: 0 };
    catMap[e.category]!.sum += e.amount;
  }
  let acc = 0;
  const stops = Object.entries(catMap).map(([cat, d]) => {
    const start = acc;
    acc += (d.sum / total) * 100;
    return `${colors[cat] || "#ccc"} ${start}% ${acc}%`;
  }).join(", ");

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "12px 8px 16px" }}>
      <div style={{
        width: 80, height: 80, borderRadius: "50%", flexShrink: 0,
        background: `conic-gradient(${stops})`,
        display: "grid", placeItems: "center",
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
      }}>
        <div style={{ width: 48, height: 48, borderRadius: "50%", background: "#fffdf7", display: "grid", placeItems: "center" }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "#4a4135" }}>{yen(total)}</span>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 12 }}>
        {Object.entries(catMap).map(([cat, d]) => (
          <div key={cat} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: colors[cat], flexShrink: 0 }} />
            <span style={{ color: "#6e6450", flex: 1 }}>{categoryIcon(cat)} {d.label}</span>
            <strong style={{ color: "#4a4135" }}>{yen(d.sum)}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// 日記 — 本番 DiaryPage と完全同一の構造
// ============================================================
const emotionEmoji: Record<string, string> = {
  happy: "😊", tired: "😪", stressed: "😣", calm: "😌", sad: "🥲", neutral: "🙂",
};

const MOOD_EMOJIS = ['😢', '😟', '😐', '🙂', '😊'];

export function DemoDiaryScreen() {
  const { state } = useDemo();
  const today = new Date();
  const dateStr = `${today.getFullYear()}.${String(today.getMonth() + 1).padStart(2, '0')}.${String(today.getDate()).padStart(2, '0')}`;
  const dayNames = ['日', '月', '火', '水', '木', '金', '土'];

  // デモ用のストレスレベル(moodScoreから逆算)
  const moodScore = state.dashboardMetrics.moodScore;
  const stressLevel = Math.round(10 - moodScore / 10);
  const furePercent = Math.max(0, 100 - stressLevel * 10);
  const mood = moodScore >= 70 ? "穏やか" : moodScore >= 50 ? "ちょっと疲れ気味" : "お疲れモード";

  const diaryContent = state.dailySummary?.content || null;

  return (
    <div className="page-content">
      {/* Diary Hero - 本番と完全同一 */}
      <section className="diary-hero">
        <div>
          <time>{dateStr} {dayNames[today.getDay()]}</time>
          <h2>今日のダイアリー🌿</h2>
          <p>{diaryContent || 'まだ今日のダイアリーは生成されていないよ。チャットで話しかけてね♪'}</p>
          <div className="diary-stats">
            <span>💗 今日の気分<br /><b>{mood}</b></span>
            <span>🌿 ふれまーる度<br /><b>{furePercent}%</b></span>
          </div>
        </div>
        <img src="/assets/furemaru-happy.png" alt="ふれまーるちゃん" />
      </section>

      {/* Mood Card - 本番と同一構造 */}
      <section className="mood-card">
        <h2>🌿 気分のうつろい</h2>
        {state.lifeLogs.length > 0 ? (
          <div className="mood-timeline">
            <div className="mood-chart">
              {state.lifeLogs.map((log, i) => {
                const emotionLevel: Record<string, number> = { happy: 9, calm: 7, neutral: 5, tired: 3, stressed: 2, sad: 1 };
                const level = emotionLevel[log.emotion] ?? 5;
                return (
                  <div key={log.id} className="mood-point" style={{ left: `${(i / Math.max(state.lifeLogs.length - 1, 1)) * 100}%`, bottom: `${(level / 10) * 100}%` }}>
                    <span className="mood-dot">{emotionEmoji[log.emotion] ?? "🙂"}</span>
                    <small>{log.timeLabel}</small>
                  </div>
                );
              })}
            </div>
            <div className="mood-labels"><span>😢 低い</span><span>😊 高い</span></div>
          </div>
        ) : (
          <div className="mood-line">
            {MOOD_EMOJIS.map((emoji, i) => {
              const moodIdx = stressLevel <= 2 ? 4 : stressLevel <= 4 ? 3 : stressLevel <= 6 ? 2 : stressLevel <= 8 ? 1 : 0;
              return <span key={i} style={{ opacity: i === moodIdx ? 1 : 0.3, transform: i === moodIdx ? 'scale(1.4)' : 'none', transition: 'all 0.3s' }}>{emoji}</span>;
            })}
          </div>
        )}
        {mood && <p>今日の気分：{mood}</p>}
      </section>

      {/* Life Log - 本番と完全同一構造 (articles with grid) — リッチ表示 */}
      <section className="life-log-list">
        <div className="section-title-row">
          <h2>🌿 会話から生まれたライフログ</h2>
          <span className="life-log-cta">💬 もっと話す</span>
        </div>
        {state.lifeLogs.length > 0 ? (
          state.lifeLogs.map((log) => {
            const emotionColor: Record<string, string> = {
              happy: "#e8f5e4", tired: "#fdf0e8", stressed: "#fde8e8",
              calm: "#e8f0fd", sad: "#f0e8fd", neutral: "#f5f3ef",
            };
            const emotionBorder: Record<string, string> = {
              happy: "#b8e0b0", tired: "#f0c8a0", stressed: "#f0a8a8",
              calm: "#a8c8f0", sad: "#c8a8f0", neutral: "#e0dcd4",
            };
            const categoryLabel = log.emotion === "tired" || log.emotion === "stressed" ? "回復シグナル" :
              log.emotion === "happy" ? "ポジティブ" : "記録";
            const categoryEmoji = log.emotion === "tired" || log.emotion === "stressed" ? "⚡" :
              log.emotion === "happy" ? "✨" : "📝";
            return (
              <article key={log.id} style={{
                background: emotionColor[log.emotion] || "#f5f3ef",
                border: `1px solid ${emotionBorder[log.emotion] || "#e0dcd4"}`,
                borderRadius: 16, padding: '10px 12px', marginTop: 8,
                display: 'grid', gridTemplateColumns: '36px 1fr 50px', gap: 8, alignItems: 'center',
              }}>
                <span style={{ fontSize: 22, textAlign: 'center' }}>{emotionEmoji[log.emotion] ?? "🙂"}</span>
                <div>
                  <span style={{
                    display: 'inline-block', fontSize: 10, fontWeight: 700,
                    background: `${emotionBorder[log.emotion]}44`, color: '#5a5040',
                    padding: '2px 7px', borderRadius: 8, marginBottom: 3,
                  }}>{categoryEmoji} {categoryLabel}</span>
                  <p style={{ margin: 0, fontSize: 12, lineHeight: 1.5, color: '#3e3a32' }}>{log.text}</p>
                </div>
                <em style={{ fontSize: 11, color: '#8e8270', fontStyle: 'normal', textAlign: 'right' }}>{log.timeLabel}</em>
              </article>
            );
          })
        ) : (
          <article>
            <img src="/assets/emotions/support.png" alt="" />
            <p>まだライフログがないよ。<br /><span className="hl">→ チャットで話しかけると、自動でログが生成されるよ♪</span></p>
            <em></em>
          </article>
        )}
      </section>

      {/* Health Highlights - 本番と完全同一構造 */}
      <section className="highlight-grid">
        <h2>🌿 今日のハイライト</h2>
        <div>
          <span>👟<b>6,432歩</b><small>歩数</small></span>
          <span>😴<b>6.5時間</b><small>睡眠</small></span>
          <span>🔥<b>245kcal</b><small>消費カロリー</small></span>
          <span>💓<b>72bpm</b><small>平均心拍</small></span>
          <span>🧘<b>5分</b><small>マインドフル</small></span>
          <span>📝<b>{state.lifeLogs.length}件</b><small>ライフログ</small></span>
        </div>
      </section>

      {/* Daily Summary — ふれまーるちゃんの日記（リッチ表示） */}
      {state.dailySummary && (
        <section style={{
          padding: 18, marginTop: 12, borderRadius: 22,
          background: "linear-gradient(135deg, #fffbe6 0%, #f8f4e8 40%, #f0faf2 100%)",
          border: "1px solid rgba(200, 180, 120, 0.25)",
          boxShadow: "0 4px 20px rgba(180, 160, 100, 0.08)",
          position: "relative", overflow: "hidden",
        }}>
          <div style={{ position: "absolute", top: 8, right: 14, fontSize: 32, opacity: 0.15 }}>📖</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <img src="/assets/emotions/happy.png" alt="" style={{ width: 28, height: 28, borderRadius: "50%" }} />
            <h2 style={{ margin: 0, fontSize: 15, color: "#5a4a30" }}>ふれまーるちゃんの日記</h2>
          </div>
          <time style={{ fontSize: 11, color: "#a09070", fontWeight: 600 }}>{state.dailySummary.date}</time>
          <p style={{
            fontSize: 13, lineHeight: 2, color: "#3e3a32", margin: "10px 0 0",
            padding: "12px 14px", background: "rgba(255,255,255,0.7)", borderRadius: 14,
            borderLeft: "3px solid rgba(143,196,155,0.6)",
          }}>{state.dailySummary.content}</p>
          <div style={{
            marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap",
          }}>
            {state.lifeLogs.length > 0 && (
              <span style={{ fontSize: 10, padding: "3px 8px", borderRadius: 8, background: "rgba(143,196,155,0.2)", color: "#4a7a4d", fontWeight: 600 }}>
                📊 ログ {state.lifeLogs.length}件から生成
              </span>
            )}
            <span style={{ fontSize: 10, padding: "3px 8px", borderRadius: 8, background: "rgba(233,166,67,0.15)", color: "#8a6020", fontWeight: 600 }}>
              🤖 AI自動生成
            </span>
          </div>
        </section>
      )}
    </div>
  );
}

// ============================================================
// リカバリー — 本番 RecoveryPage と完全同一の構造
// ============================================================
export function DemoRecoveryScreen() {
  const { state } = useDemo();

  return (
    <div className="page-content">
      {/* Recovery Hero - 本番と完全同一 */}
      <section className="recovery-hero">
        <img src="/assets/furemaru-happy.png" alt="ふれまーるちゃん" />
        <div>
          <small>今の気分: ちょっと疲れ気味</small>
          <h2>ねぇ、今日がんばったんだから、もう休んでよくない？</h2>
          <p>動画見ながらダラダラしよ〜🌿</p>
          <button className="primary-btn">今日はいいかな</button>
          <span className="chat-back-link">💬 ふれまーるちゃんと話す</span>
        </div>
      </section>

      {/* 実データ統合：商品・動画・ほしいもの — 本番の RecoveryIntegrations と同一 */}
      {state.recommendations.length > 0 && (
        <section className="chart-card" style={{ padding: 16, marginTop: 16 }}>
          <h2 style={{ marginTop: 0 }}>✨ 今日のゴホウビ候補</h2>
          <p style={{ fontSize: 11, color: "#8e8270", margin: "4px 0 8px" }}>
            あなたの好みから探したよ🌱
          </p>
          {/* キーワードチップ - 本番と同一 */}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            {["スイーツ", "カフェ", "癒し動画"].map((kw, i) => (
              <button
                key={kw}
                style={{
                  padding: '4px 10px', borderRadius: 14, border: '1px solid #e3dac1',
                  background: i === 0 ? '#f4b8b8' : '#fffdf6',
                  color: i === 0 ? '#fff' : '#4a4135',
                  fontSize: 11, cursor: 'pointer', fontWeight: i === 0 ? 'bold' : 'normal',
                }}
              >{kw}</button>
            ))}
          </div>
          {/* タブ - 本番と同一 */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
            {[
              { key: 'rakuten', label: '商品を探す', icon: '🛍️' },
              { key: 'youtube', label: '癒し動画', icon: '🎧' },
              { key: 'wishlist', label: 'ほしいもの', icon: '💝' },
            ].map((t, i) => (
              <button
                key={t.key}
                style={{
                  flex: 1, padding: '8px 4px',
                  border: '1px solid #e3dac1',
                  background: i === 0 ? '#f4b8b8' : '#fff',
                  color: i === 0 ? '#fff' : '#4a4135',
                  borderRadius: 10, cursor: 'pointer', fontSize: 12,
                  fontWeight: i === 0 ? 'bold' : 'normal',
                }}
              >{t.icon} {t.label}</button>
            ))}
          </div>
          {/* 商品カード - 本番と同一構造 */}
          {state.recommendations.map((r) => (
            <RecCard key={r.id} rec={r} selected={state.selectedRecommendationId === r.id} />
          ))}
        </section>
      )}

      {/* 0円回復メニュー - 本番と同一 */}
      <h2 className="section-heading">🌿 0円回復メニュー</h2>
      <section className="recovery-grid">
        <article>
          <span>☁️</span><h3>深呼吸</h3><p>呼吸</p>
          <button className="primary-btn small">やってみる</button>
        </article>
        <article>
          <span>🎵</span><h3>やさしい音楽</h3><p>音楽</p>
          <button className="primary-btn small">やってみる</button>
        </article>
        <article>
          <span>🚶</span><h3>5分散歩</h3><p>運動</p>
          <button className="primary-btn small">やってみる</button>
        </article>
        <article>
          <span>🧘</span><h3>ストレッチ</h3><p>運動</p>
          <button className="primary-btn small">やってみる</button>
        </article>
      </section>

      {/* 小さなご褒美 - 本番と同一 */}
      <h2 className="section-heading">💗 小さなご褒美</h2>
      <section className="recovery-grid">
        <article>
          <span>🍮</span><h3>プリン</h3><p>ごほうび (〜¥400)</p>
          <button className="primary-btn small">買ってもいい？</button>
        </article>
        <article>
          <span>☕</span><h3>ご褒美コーヒー</h3><p>回復費 (〜¥500)</p>
          <button className="primary-btn small">買ってもいい？</button>
        </article>
      </section>

      {/* Route Card - 本番と完全同一 */}
      <section className="route-card">
        <h2>今日の回復ルート</h2>
        <div className="route">
          {[
            { emoji: "☁️", label: "深呼吸", time: "1分" },
            { emoji: "🍵", label: "あたたかい飲み物", time: "5分" },
            { emoji: "🎵", label: "やさしい音楽", time: "10分" },
            { emoji: "💗", label: "自分をほめる", time: "3分" },
          ].map((step, i) => (
            <span key={i}>
              <div className="step">
                {step.emoji}<small>{step.label}<br />{step.time}</small>
              </div>
              {i < 3 && <div className="connector"></div>}
            </span>
          ))}
          <div className="total">合計<br />19分</div>
        </div>
        <button className="start-btn">はじめる</button>
        <p className="route-footer">今日も、あなたのペースで大丈夫だよ〜🌿</p>
      </section>
    </div>
  );
}

function RecCard({ rec, selected }: { rec: DemoRecommendation; selected: boolean }) {
  return (
    <a
      href={rec.url || "#"}
      target="_blank"
      rel="noopener noreferrer"
      className={`chat-reco-card chat-reco-${rec.type === "zero_yen" ? "video" : rec.type === "place" ? "restaurant" : "product"}`}
      style={{
        display: "block", marginBottom: 10, textDecoration: "none",
        ...(selected ? { boxShadow: "0 0 0 3px #68a977, 0 6px 18px rgba(104,169,119,0.3)", transform: "scale(1.02)" } : {}),
        ...(rec.highlighted ? { boxShadow: "0 4px 14px rgba(233,166,67,0.4)", border: "2px solid #e9a643" } : {}),
        transition: "all 0.3s ease",
      }}
    >
      {rec.image && <img src={rec.image} alt="" />}
      <div className="reco-body">
        <small className="reco-type">{sourceLabel[rec.source] ?? rec.source}</small>
        <b>{rec.title}</b>
        {rec.estimatedCost > 0 && <em>{yen(rec.estimatedCost)}</em>}
        {rec.reason && <p className="reco-reason">💭 {rec.reason}</p>}
      </div>
      {selected && <div style={{ background: "#68a977", color: "#fff", padding: "6px 12px", borderRadius: 8, fontSize: 12, fontWeight: 800, textAlign: "center", marginTop: 6 }}>✓ これを選んだよ</div>}
    </a>
  );
}

// ============================================================
// オンボーディング — 本番 OnboardingPage 構造
// ============================================================
export function DemoOnboardingScreen() {
  const { state } = useDemo();
  const p = state.profile;

  return (
    <div className="page-content" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100%", padding: "30px 18px" }}>
      <img src="/assets/furemaru-fullbody.png" alt="" style={{ width: 160, height: 160, objectFit: "contain", marginBottom: 20 }} />
      <div className="glass-card" style={{ width: "100%", padding: "22px 18px", textAlign: "center", borderRadius: 22 }}>
        {state.onboardingStep === "intro" && (
          <>
            <h2 style={{ color: "#2f7c51", fontSize: 20, marginBottom: 10 }}>はじめまして！</h2>
            <p style={{ fontSize: 14, color: "#4a4538", lineHeight: 1.7 }}>ふれまーるちゃんだよ。あなたの毎日を、やさしく見守るね。</p>
            <button className="primary-btn" style={{ marginTop: 16 }}>はじめる</button>
          </>
        )}
        {state.onboardingStep === "name" && (
          <>
            <h2 style={{ color: "#2f7c51", fontSize: 18, marginBottom: 12 }}>お名前を教えて</h2>
            <div style={{ background: "#f8f4ee", borderRadius: 14, padding: "12px 16px", fontSize: 18, fontWeight: 800, color: "#2f7c51" }}>
              {p.name || <span style={{ color: "#bbb" }}>入力中...</span>}
            </div>
          </>
        )}
        {state.onboardingStep === "budget" && (
          <>
            <h2 style={{ color: "#2f7c51", fontSize: 18, marginBottom: 12 }}>毎月のごほうび予算は？</h2>
            <div style={{ background: "#f8f4ee", borderRadius: 14, padding: "12px 16px", fontSize: 22, fontWeight: 900, color: "#2f7c51" }}>
              {p.budget ? yen(p.budget) : <span style={{ color: "#bbb" }}>選択中...</span>}
            </div>
            <p style={{ fontSize: 11, color: "#8e8270", marginTop: 8 }}>使いすぎない金額を設定しよう</p>
          </>
        )}
        {state.onboardingStep === "interests" && (
          <>
            <h2 style={{ color: "#2f7c51", fontSize: 18, marginBottom: 12 }}>好きなものを教えて</h2>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", marginTop: 8 }}>
              {(p.interests.length === 0 ? ["スイーツ", "カフェ", "音楽", "読書", "散歩"] : p.interests).map((tag) => (
                <span key={tag} style={{
                  padding: "6px 14px", borderRadius: 999, fontSize: 13, fontWeight: 700,
                  background: p.interests.includes(tag) ? "#f4b8b8" : "#fff",
                  color: p.interests.includes(tag) ? "#fff" : "#4a4538",
                  border: "1px solid #e3dac1",
                }}>{tag}</span>
              ))}
            </div>
          </>
        )}
        {state.onboardingStep === "diary_time" && (
          <>
            <h2 style={{ color: "#2f7c51", fontSize: 18, marginBottom: 12 }}>日記は何時に書く？</h2>
            <div style={{ background: "#f8f4ee", borderRadius: 14, padding: "12px 16px", fontSize: 22, fontWeight: 900, color: "#2f7c51" }}>
              {p.diaryTime || <span style={{ color: "#bbb" }}>選択中...</span>}
            </div>
          </>
        )}
        {state.onboardingStep === "done" && (
          <>
            <h2 style={{ color: "#2f7c51", fontSize: 20, marginBottom: 10 }}>準備できたよ！ 🎉</h2>
            <p style={{ fontSize: 14, color: "#4a4538", lineHeight: 1.7 }}>これから一緒にやっていこうね。</p>
            <button className="primary-btn" style={{ marginTop: 16 }}>はじめる</button>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================
// 設定画面
// ============================================================
export function DemoSettingsScreen() {
  const { state } = useDemo();
  return (
    <div className="page-content">
      <section className="chart-card" style={{ padding: 16 }}>
        <h2>⚙️ 設定</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid #f0e6d2", fontSize: 14 }}>
            <span style={{ color: "#8e8270" }}>表示名</span><span style={{ fontWeight: 700 }}>{state.profile.name || "なまけもの"}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid #f0e6d2", fontSize: 14 }}>
            <span style={{ color: "#8e8270" }}>ごほうび予算</span><span style={{ fontWeight: 700 }}>{yen(state.profile.budget || 10000)}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid #f0e6d2", fontSize: 14 }}>
            <span style={{ color: "#8e8270" }}>日記の時間</span><span style={{ fontWeight: 700 }}>{state.profile.diaryTime || "22:00"}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", fontSize: 14 }}>
            <span style={{ color: "#8e8270" }}>プッシュ通知</span><span style={{ fontWeight: 700, color: "#2f7c51" }}>ON</span>
          </div>
        </div>
      </section>
    </div>
  );
}

// ============================================================
// 画面切替
// ============================================================
export function DemoScreenSwitch() {
  const { state } = useDemo();
  switch (state.page) {
    case "onboarding": return <DemoOnboardingScreen />;
    case "chat": return <DemoChatScreen />;
    case "dashboard": return <DemoDashboardScreen />;
    case "diary": return <DemoDiaryScreen />;
    case "recovery": return <DemoRecoveryScreen />;
    case "settings": return <DemoSettingsScreen />;
    default: return <DemoChatScreen />;
  }
}

// ============================================================
// オーバーレイ（トースト/キャプション）
// ============================================================
export function DemoOverlay() {
  const { state } = useDemo();
  return (
    <>
      {state.caption && <div className="demo-caption">{state.caption}</div>}
      {state.toasts.length > 0 && (
        <div className="demo-toasts">
          {state.toasts.map((t) => (
            <div key={t.id} className="demo-toast">{t.message}</div>
          ))}
        </div>
      )}
    </>
  );
}
