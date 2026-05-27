import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { DemoProvider, useDemo } from "./demoState";
import { scenarioList } from "./demoScenarios";
import {
  DemoOverlay,
  DemoScreenSwitch,
} from "./DemoScreens";
import "./demo.css";

// 本番ナビと完全同一の5タブ構成 (center = ふれまーるちゃんアバター)
const NAV_ITEMS_LEFT = [
  { id: "chat", label: "Chat", icon: "💬" },
  { id: "dashboard", label: "家計簿", icon: "📊" },
] as const;
const NAV_ITEMS_RIGHT = [
  { id: "diary", label: "ダイアリー", icon: "📖" },
  { id: "recovery", label: "回復", icon: "💞" },
] as const;

function DemoHeader() {
  return (
    <header className="app-header">
      <div className="brand">
        <img src="/assets/furemaru-avatar.png" alt="" className="brand-avatar" />
        <div>
          <h1>ふれまーる</h1>
          <p>あなたの“回復”パートナー 🌿</p>
        </div>
      </div>
      <div className="header-actions">
        <button className="icon-button" aria-label="今日のご褒美占い">✨</button>
        <button className="icon-button" aria-label="通知">🔔<i className="dot"></i></button>
        <button className="icon-button" aria-label="設定">⚙️</button>
      </div>
    </header>
  );
}

function DemoNav() {
  const { state } = useDemo();
  return (
    <nav className="demo-tabbar">
      {NAV_ITEMS_LEFT.map((it) => (
        <div key={it.id} className={`demo-tab ${state.page === it.id ? "active" : ""}`}>
          <span>{it.icon}</span><small>{it.label}</small>
        </div>
      ))}
      <div className="demo-tab center">
        <img src="/assets/furemaru-avatar.png" alt="ふれまーるちゃん" />
      </div>
      {NAV_ITEMS_RIGHT.map((it) => (
        <div key={it.id} className={`demo-tab ${state.page === it.id ? "active" : ""}`}>
          <span>{it.icon}</span><small>{it.label}</small>
        </div>
      ))}
    </nav>
  );
}

function DemoControlPanel() {
  const {
    scenario,
    scenarioId,
    status,
    currentStepIndex,
    speed,
    setSpeed,
    loadScenario,
    play,
    pause,
    restart,
    nextStep,
    prevStep,
  } = useDemo();

  return (
    <div className="demo-control-panel">
      <div className="demo-control-title">Demo Control</div>
      <div className="demo-control-row">
        <label>シナリオ</label>
        <select
          value={scenarioId ?? ""}
          onChange={(e) => loadScenario(e.target.value)}
        >
          <option value="" disabled>— 選択 —</option>
          {scenarioList.map((s) => (
            <option key={s.id} value={s.id}>{s.title}</option>
          ))}
        </select>
      </div>
      <div className="demo-control-row">
        <button onClick={play} disabled={!scenario || status === "playing"}>▶ 再生</button>
        <button onClick={pause} disabled={status !== "playing"}>⏸ 停止</button>
        <button onClick={restart} disabled={!scenario}>⟲ 最初から</button>
      </div>
      <div className="demo-control-row">
        <button onClick={prevStep} disabled={!scenario || currentStepIndex === 0}>◀ 前へ</button>
        <button onClick={nextStep} disabled={!scenario || (scenario && currentStepIndex >= scenario.steps.length)}>次へ ▶</button>
      </div>
      <div className="demo-control-row">
        <label>速度</label>
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
          <option value={0.5}>0.5x</option>
          <option value={0.75}>0.75x</option>
          <option value={1}>1x</option>
          <option value={1.5}>1.5x</option>
          <option value={2}>2x</option>
        </select>
      </div>
      {scenario && (
        <div className="demo-control-info">
          <div>{scenario.title}</div>
          <div className="demo-control-progress">
            {currentStepIndex} / {scenario.steps.length} ・ {status}
          </div>
        </div>
      )}
      <div className="demo-control-hint">
        ?hideControls=1 でパネル非表示<br />
        ?scenario=xxx で自動再生
      </div>
    </div>
  );
}

function DemoBody() {
  const [params] = useSearchParams();
  const { loadScenario, scenarioId, state } = useDemo();
  const scenarioParam = params.get("scenario");
  const hideControls = params.get("hideControls") === "1";
  const scrollRef = useRef<HTMLDivElement>(null);

  // URLパラメータからシナリオ自動ロード＋自動再生
  useEffect(() => {
    if (scenarioParam && scenarioParam !== scenarioId) {
      loadScenario(scenarioParam, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarioParam]);

  // ステート変更時に自動スクロール（messages, expenses, lifeLogs, recommendations）
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    // 少し遅延してからスクロール（DOMレンダリング後）
    const t = setTimeout(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }, 80);
    return () => clearTimeout(t);
  }, [state.messages, state.expenses, state.lifeLogs, state.recommendations, state.receiptStage, state.rewardCarryover, state.dailySummary]);

  // scrollTo アクション対応
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || state.scrollTarget === null) return;
    const t = setTimeout(() => {
      if (state.scrollTarget === "top") {
        el.scrollTo({ top: 0, behavior: 'smooth' });
      } else if (state.scrollTarget === "bottom") {
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      } else if (typeof state.scrollTarget === "number") {
        const target = (state.scrollTarget / 100) * el.scrollHeight;
        el.scrollTo({ top: target, behavior: 'smooth' });
      }
    }, 80);
    return () => clearTimeout(t);
  }, [state.scrollTarget]);

  return (
    <div className="demo-root">
      <div className="phone-shell">
        <div className="phone-inner demo-phone">
          <DemoHeader />
          <DemoOverlay />
          <div className="demo-page-content" ref={scrollRef}>
            <DemoScreenSwitch />
          </div>
          <DemoNav />
        </div>
      </div>
      {!hideControls && <DemoControlPanel />}
    </div>
  );
}

export function DemoPage() {
  return (
    <DemoProvider>
      <DemoBody />
    </DemoProvider>
  );
}
