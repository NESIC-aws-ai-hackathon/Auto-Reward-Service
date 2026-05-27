import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState } from "react";
import type { ReactNode } from "react";
import type {
  DemoAction,
  DemoDailySummary,
  DemoDashboardMetrics,
  DemoExpense,
  DemoLifeLog,
  DemoMessage,
  DemoOnboardingStep,
  DemoPage,
  DemoReceiptResult,
  DemoReceiptStage,
  DemoRecommendation,
  DemoRewardCarryover,
  DemoScenario,
  DemoToast,
  DemoTranscript,
  DemoVoiceStatus,
  FuremaruEmotion,
} from "./demoTypes";
import { demoDashboardInitial } from "./demoData";
import { scenarios } from "./demoScenarios";

const STORAGE_KEY = "furemaru-demo-state";

type DemoProfile = {
  name: string;
  budget: number;
  interests: string[];
  diaryTime: string;
};

type DemoState = {
  page: DemoPage;
  emotion: FuremaruEmotion;
  voiceStatus: DemoVoiceStatus;
  messages: DemoMessage[];
  transcripts: DemoTranscript[];
  expenses: DemoExpense[];
  lifeLogs: DemoLifeLog[];
  dailySummary: DemoDailySummary | null;
  dashboardMetrics: DemoDashboardMetrics;
  receiptStage: DemoReceiptStage;
  receiptResult: DemoReceiptResult | null;
  recommendations: DemoRecommendation[];
  selectedRecommendationId: string | null;
  rewardCarryover: DemoRewardCarryover | null;
  onboardingStep: DemoOnboardingStep;
  profile: DemoProfile;
  toasts: DemoToast[];
  caption: string;
  scrollTarget: "top" | "bottom" | number | null;
};

const INITIAL_STATE: DemoState = {
  page: "chat",
  emotion: "neutral",
  voiceStatus: "idle",
  messages: [],
  transcripts: [],
  expenses: [],
  lifeLogs: [],
  dailySummary: null,
  dashboardMetrics: demoDashboardInitial,
  receiptStage: "hidden",
  receiptResult: null,
  recommendations: [],
  selectedRecommendationId: null,
  rewardCarryover: null,
  onboardingStep: "intro",
  profile: { name: "", budget: 0, interests: [], diaryTime: "" },
  toasts: [],
  caption: "",
  scrollTarget: null,
};

function reducer(state: DemoState, action: DemoAction | { type: "reset" } | { type: "removeToast"; id: string }): DemoState {
  switch (action.type) {
    case "reset":
      return { ...INITIAL_STATE };
    case "navigate":
      return { ...state, page: action.page };
    case "setVoiceState":
      return { ...state, voiceStatus: action.status };
    case "setEmotion":
      return { ...state, emotion: action.emotion };
    case "appendUserMessage":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: `msg-${Date.now()}-${Math.random()}`,
            role: "user",
            text: action.text,
            inputType: action.inputType,
            timestamp: new Date().toISOString(),
          },
        ],
      };
    case "appendAssistantMessage":
      return {
        ...state,
        emotion: action.emotion,
        messages: [
          ...state.messages,
          {
            id: `msg-${Date.now()}-${Math.random()}`,
            role: "assistant",
            text: action.text,
            emotion: action.emotion,
            timestamp: new Date().toISOString(),
            reco: action.reco,
            suggestion: action.suggestion,
          },
        ],
      };
    case "addTranscript":
      return {
        ...state,
        transcripts: [
          ...state.transcripts.filter((t) => t.role !== action.role || t !== state.transcripts[state.transcripts.length - 1]),
          { id: `tr-${Date.now()}-${Math.random()}`, role: action.role, text: action.text },
        ],
      };
    case "clearTranscripts":
      return { ...state, transcripts: [] };
    case "addExpense":
      return { ...state, expenses: [action.expense, ...state.expenses] };
    case "addLifeLog":
      return { ...state, lifeLogs: [...state.lifeLogs, action.lifeLog] };
    case "addDailySummary":
      return { ...state, dailySummary: action.summary };
    case "addRecoveryProposal":
      return { ...state, recommendations: [...state.recommendations, action.proposal] };
    case "setDashboardMetrics":
      return { ...state, dashboardMetrics: action.metrics };
    case "showReceiptUpload":
      return { ...state, receiptStage: "upload", receiptResult: null };
    case "showReceiptParsing":
      return { ...state, receiptStage: "parsing" };
    case "showReceiptResult":
      return { ...state, receiptStage: "result", receiptResult: action.result };
    case "confirmReceipt":
      return { ...state, receiptStage: "confirmed" };
    case "showRecommendationCandidates":
      return { ...state, recommendations: action.candidates };
    case "selectRecommendation":
      return { ...state, selectedRecommendationId: action.recommendationId };
    case "showRewardCarryover":
      return { ...state, rewardCarryover: action.carryover };
    case "setOnboardingStep":
      return { ...state, onboardingStep: action.step };
    case "setProfile":
      return {
        ...state,
        profile: {
          name: action.name ?? state.profile.name,
          budget: action.budget ?? state.profile.budget,
          interests: action.interests ?? state.profile.interests,
          diaryTime: action.diaryTime ?? state.profile.diaryTime,
        },
      };
    case "showToast":
      return {
        ...state,
        toasts: [
          ...state.toasts,
          { id: `t-${Date.now()}-${Math.random()}`, message: action.message, createdAt: Date.now() },
        ],
      };
    case "removeToast":
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) };
    case "showCaption":
      return { ...state, caption: action.text };
    case "clearCaption":
      return { ...state, caption: "" };
    case "scrollTo":
      return { ...state, scrollTarget: action.position };
    default:
      return state;
  }
}

type RunnerStatus = "idle" | "playing" | "paused" | "ended";

type DemoContextValue = {
  state: DemoState;
  scenarioId: string | null;
  scenario: DemoScenario | null;
  status: RunnerStatus;
  currentStepIndex: number;
  speed: number;
  setSpeed: (s: number) => void;
  loadScenario: (id: string, autoPlay?: boolean) => void;
  play: () => void;
  pause: () => void;
  restart: () => void;
  nextStep: () => void;
  prevStep: () => void;
};

const DemoContext = createContext<DemoContextValue | null>(null);

export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [status, setStatus] = useState<RunnerStatus>("idle");
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [speed, setSpeed] = useState(1);

  const scenario = useMemo(() => (scenarioId ? scenarios[scenarioId] ?? null : null), [scenarioId]);
  const timerRef = useRef<number | null>(null);

  // 永続化（key = furemaru-demo-state、本番データとは分離）
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          page: state.page,
          profile: state.profile,
          expensesCount: state.expenses.length,
          lifeLogsCount: state.lifeLogs.length,
          dashboardMetrics: state.dashboardMetrics,
          scenarioId,
          ts: Date.now(),
        }),
      );
    } catch {
      // ignore
    }
  }, [state, scenarioId]);

  // toast auto-dismiss
  useEffect(() => {
    if (state.toasts.length === 0) return;
    const ids = state.toasts.map((t) => t.id);
    const timer = window.setTimeout(() => {
      ids.forEach((id) => dispatch({ type: "removeToast", id }));
    }, 2600);
    return () => window.clearTimeout(timer);
  }, [state.toasts]);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const runStep = useCallback(
    (index: number) => {
      if (!scenario) return;
      if (index >= scenario.steps.length) {
        setStatus("ended");
        return;
      }
      const step = scenario.steps[index]!;
      const delay = Math.max(0, step.delayMs / speed);
      timerRef.current = window.setTimeout(() => {
        dispatch(step.action);
        if (step.caption) {
          dispatch({ type: "showCaption", text: step.caption });
        }
        setCurrentStepIndex(index + 1);
      }, delay);
    },
    [scenario, speed],
  );

  // play loop
  useEffect(() => {
    if (status !== "playing" || !scenario) {
      clearTimer();
      return;
    }
    if (currentStepIndex >= scenario.steps.length) {
      setStatus("ended");
      return;
    }
    runStep(currentStepIndex);
    return clearTimer;
  }, [status, currentStepIndex, scenario, runStep, clearTimer]);

  const autoPlayOnLoad = useRef(false);

  const loadScenario = useCallback(
    (id: string, autoPlay = false) => {
      clearTimer();
      dispatch({ type: "reset" });
      setScenarioId(id);
      setCurrentStepIndex(0);
      if (autoPlay) {
        autoPlayOnLoad.current = true;
      }
      setStatus("idle");
    },
    [clearTimer],
  );

  // autoPlayOnLoad が true なら scenario セット後に即 playing
  useEffect(() => {
    if (autoPlayOnLoad.current && scenario) {
      autoPlayOnLoad.current = false;
      setStatus("playing");
    }
  }, [scenario]);

  const play = useCallback(() => {
    if (!scenario) return;
    if (status === "ended") {
      dispatch({ type: "reset" });
      setCurrentStepIndex(0);
    }
    setStatus("playing");
  }, [scenario, status]);

  const pause = useCallback(() => {
    clearTimer();
    setStatus("paused");
  }, [clearTimer]);

  const restart = useCallback(() => {
    clearTimer();
    dispatch({ type: "reset" });
    setCurrentStepIndex(0);
    setStatus("playing");
  }, [clearTimer]);

  const nextStep = useCallback(() => {
    if (!scenario) return;
    clearTimer();
    const idx = currentStepIndex;
    if (idx >= scenario.steps.length) return;
    const step = scenario.steps[idx]!;
    dispatch(step.action);
    if (step.caption) dispatch({ type: "showCaption", text: step.caption });
    setCurrentStepIndex(idx + 1);
    if (status === "playing") {
      // keep playing
    } else {
      setStatus("paused");
    }
  }, [clearTimer, currentStepIndex, scenario, status]);

  const prevStep = useCallback(() => {
    if (!scenario) return;
    clearTimer();
    // 簡易実装: 最初からやり直して target-1 までステップ実行
    const target = Math.max(0, currentStepIndex - 1);
    dispatch({ type: "reset" });
    for (let i = 0; i < target; i++) {
      const step = scenario.steps[i]!;
      dispatch(step.action);
      if (step.caption) dispatch({ type: "showCaption", text: step.caption });
    }
    setCurrentStepIndex(target);
    setStatus("paused");
  }, [clearTimer, currentStepIndex, scenario]);

  const value = useMemo<DemoContextValue>(
    () => ({
      state,
      scenarioId,
      scenario,
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
    }),
    [state, scenarioId, scenario, status, currentStepIndex, speed, loadScenario, play, pause, restart, nextStep, prevStep],
  );

  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  const ctx = useContext(DemoContext);
  if (!ctx) throw new Error("useDemo must be used inside DemoProvider");
  return ctx;
}
