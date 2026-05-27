// Demo Mode 専用の型定義 — 本番コードとは独立
export type FuremaruEmotion =
  | "neutral"
  | "happy"
  | "support"
  | "shy"
  | "excited"
  | "listening";

export type DemoPage =
  | "onboarding"
  | "chat"
  | "dashboard"
  | "diary"
  | "recovery"
  | "settings";

export type DemoExpense = {
  id: string;
  amount: number;
  itemName: string;
  category: "recovery" | "startup" | "maintenance" | "investment" | "social" | "reward" | "other";
  meaningLabel: string;
  source: "conversation" | "receipt" | "manual";
  storeName?: string;
  timestamp: string;
};

export type DemoLifeLog = {
  id: string;
  timeLabel: string; // 「朝」「昼」「夕方」「夜」
  emotion: "happy" | "tired" | "stressed" | "calm" | "sad" | "neutral";
  text: string;
  timestamp: string;
};

export type DemoDailySummary = {
  date: string;
  content: string;
};

export type DemoRecoveryProposal = {
  id: string;
  source: "rakuten" | "hotpepper" | "youtube" | "amazon_wishlist" | "zero_yen";
  title: string;
  type: "zero_yen" | "small_reward" | "place" | "wishlist_reward";
  estimatedCost: number;
  reason: string;
  url?: string;
  image?: string;
  highlighted?: boolean;
};

export type DemoDashboardMetrics = {
  monthlySurplus: number;
  todayRecoveryCost: number;
  moodScore: number;
  todayQuote: string;
};

export type DemoReceiptResult = {
  storeName: string;
  totalAmount: number;
  items: { name: string; amount: number; meaningLabel: string }[];
  meaningLabel: string;
  furemaruComment: string;
};

export type DemoRecommendation = DemoRecoveryProposal;

export type DemoRewardCarryover = {
  currentMonthBudget: number;
  currentMonthUsed: number;
  nextMonthBudget: number;
  message: string;
  scenario: "surplus" | "over";
};

export type DemoMessageReco = {
  type: "product" | "video" | "wishlist" | "restaurant";
  title: string;
  url: string;
  image?: string;
  price?: number;
  reason?: string;
};

export type DemoMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  inputType?: "voice" | "text";
  emotion?: FuremaruEmotion;
  timestamp: string;
  reco?: DemoMessageReco;
  suggestion?: { to: string; label: string };
};

export type DemoTranscript = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

export type DemoToast = {
  id: string;
  message: string;
  createdAt: number;
};

export type DemoVoiceStatus = "idle" | "listening" | "thinking" | "speaking" | "error";

export type DemoReceiptStage =
  | "hidden"
  | "upload"
  | "parsing"
  | "result"
  | "confirmed";

export type DemoOnboardingStep =
  | "intro"
  | "name"
  | "budget"
  | "interests"
  | "diary_time"
  | "done";

export type DemoAction =
  | { type: "navigate"; page: DemoPage }
  | { type: "setVoiceState"; status: DemoVoiceStatus }
  | { type: "appendUserMessage"; text: string; inputType: "voice" | "text" }
  | { type: "appendAssistantMessage"; text: string; emotion: FuremaruEmotion; reco?: DemoMessageReco; suggestion?: { to: string; label: string } }
  | { type: "addTranscript"; text: string; role: "user" | "assistant" }
  | { type: "clearTranscripts" }
  | { type: "addExpense"; expense: DemoExpense }
  | { type: "addLifeLog"; lifeLog: DemoLifeLog }
  | { type: "addDailySummary"; summary: DemoDailySummary }
  | { type: "addRecoveryProposal"; proposal: DemoRecoveryProposal }
  | { type: "setDashboardMetrics"; metrics: DemoDashboardMetrics }
  | { type: "setEmotion"; emotion: FuremaruEmotion }
  | { type: "showReceiptUpload" }
  | { type: "showReceiptParsing" }
  | { type: "showReceiptResult"; result: DemoReceiptResult }
  | { type: "confirmReceipt" }
  | { type: "showRecommendationCandidates"; candidates: DemoRecommendation[] }
  | { type: "selectRecommendation"; recommendationId: string }
  | { type: "showRewardCarryover"; carryover: DemoRewardCarryover }
  | { type: "setOnboardingStep"; step: DemoOnboardingStep; payload?: Record<string, unknown> }
  | { type: "setProfile"; name?: string; budget?: number; interests?: string[]; diaryTime?: string }
  | { type: "showToast"; message: string }
  | { type: "showCaption"; text: string }
  | { type: "clearCaption" }
  | { type: "scrollTo"; position: "top" | "bottom" | number };

export type DemoStep = {
  id: string;
  label: string;
  delayMs: number;
  action: DemoAction;
  caption?: string;
};

export type DemoScenario = {
  id: string;
  title: string;
  description: string;
  durationMs: number;
  steps: DemoStep[];
};
