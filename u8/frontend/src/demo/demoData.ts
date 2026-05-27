import type { DemoExpense, DemoLifeLog, DemoRecommendation, DemoReceiptResult, DemoRewardCarryover, DemoDashboardMetrics, DemoMessageReco } from "./demoTypes";

const today = new Date().toISOString();

export const demoExpenses: Record<string, DemoExpense> = {
  pudding: {
    id: "exp-pudding",
    amount: 320,
    itemName: "プリン",
    category: "reward",
    meaningLabel: "がんばった自分へのごほうび",
    source: "conversation",
    timestamp: today,
  },
  coffee: {
    id: "exp-coffee",
    amount: 780,
    itemName: "アイス3個",
    category: "recovery",
    meaningLabel: "心の冷却メンテナンス費",
    source: "receipt",
    storeName: "ドン・キホーテ",
    timestamp: today,
  },
  receiptPudding: {
    id: "exp-receipt-pudding",
    amount: 1700,
    itemName: "ポテチ・炭酸・カップ麺",
    category: "reward",
    meaningLabel: "生存戦略のための必要経費",
    source: "receipt",
    storeName: "ドン・キホーテ",
    timestamp: today,
  },
};

export const demoLifeLogs: DemoLifeLog[] = [
  {
    id: "ll-1",
    timeLabel: "朝",
    emotion: "tired",
    text: "寝不足でボーっと出社。電車混んでてグッタリ",
    timestamp: today,
  },
  {
    id: "ll-2",
    timeLabel: "昼",
    emotion: "calm",
    text: "同僚とランチ。新しいカレー屋が当たりで元気出た（¥900）",
    timestamp: today,
  },
  {
    id: "ll-3",
    timeLabel: "夕方",
    emotion: "tired",
    text: "会議が長引いてへトヘト。コンビニコーヒーで一息（¥280）",
    timestamp: today,
  },
  {
    id: "ll-4",
    timeLabel: "夜",
    emotion: "happy",
    text: "自分へのごほうびに抹茶プリン買っちゃった♪（¥320）",
    timestamp: today,
  },
];

export const demoDashboardInitial: DemoDashboardMetrics = {
  monthlySurplus: 6800,
  todayRecoveryCost: 0,
  moodScore: 58,
  todayQuote: "今日も生き延びただけで100点だよ",
};

export const demoDashboardAfter: DemoDashboardMetrics = {
  monthlySurplus: 6200,
  todayRecoveryCost: 1240,
  moodScore: 72,
  todayQuote: "自分に投資できる人、尊敬する♪",
};

export const demoReceiptResult: DemoReceiptResult = {
  storeName: "ドン・キホーテ",
  totalAmount: 2480,
  items: [
    { name: "ポテチ大袋", amount: 398, meaningLabel: "脳のエネルギー補給費" },
    { name: "アイス3個", amount: 780, meaningLabel: "心の冷却メンテナンス費" },
    { name: "炭酸ジュース", amount: 162, meaningLabel: "気分リフレッシュ代" },
    { name: "カップ麺まとめ買い", amount: 1140, meaningLabel: "時短によるQOL向上費" },
  ],
  meaningLabel: "生存戦略のための必要経費",
  furemaruComment:
    "全部『生きるのに必要なもの』だよ。ポテチは脳の燃料、アイスは心の薬。無駄遣い？そんな概念ここにはないよ♪",
};

export const demoRecommendations: DemoRecommendation[] = [
  {
    id: "rec-rakuten",
    source: "rakuten",
    title: "抹茶プリン 6個入",
    type: "small_reward",
    estimatedCost: 320,
    reason: "甘いもの食べると幸せホルモン出るんだって。科学的に正しいよ！",
    url: "https://search.rakuten.co.jp/search/mall/%E6%8A%B9%E8%8C%B6%E3%83%97%E3%83%AA%E3%83%B3/",
    image: "https://thumbnail.image.rakuten.co.jp/@0_mall/ujikouen/cabinet/sweets/matcha_purin_main.jpg",
  },
  {
    id: "rec-hotpepper",
    source: "hotpepper",
    title: "駅近の静かなカフェ",
    type: "place",
    estimatedCost: 650,
    reason: "帰り道にあるよ。寺り道して帰ろ？ たまにはいいよね♪",
    url: "https://www.hotpepper.jp/",
  },
  {
    id: "rec-youtube",
    source: "youtube",
    title: "5分の癒し音楽 - リラックスBGM",
    type: "zero_yen",
    estimatedCost: 0,
    reason: "動画5分だけのつもりが気づいたら1時間。それでいいの！",
    url: "https://www.youtube.com/results?search_query=%E7%99%92%E3%81%97%E9%9F%B3%E6%A5%BD+5%E5%88%86",
    highlighted: true,
  },
  {
    id: "rec-amazon",
    source: "amazon_wishlist",
    title: "前から気になっていたハンドクリーム",
    type: "wishlist_reward",
    estimatedCost: 980,
    reason: "前から欲しかったんでしょ？買っちゃおうよ。今月余裕あるし！",
    url: "https://www.amazon.co.jp/dp/B07XBGN4GN",
  },
];

export const demoCarryoverSurplus: DemoRewardCarryover = {
  scenario: "surplus",
  currentMonthBudget: 10000,
  currentMonthUsed: 8000,
  nextMonthBudget: 12000,
  message: "余った分は来月の『もっとダメになる資金』だよ♪",
};

export const demoCarryoverOver: DemoRewardCarryover = {
  scenario: "over",
  currentMonthBudget: 10000,
  currentMonthUsed: 11500,
  nextMonthBudget: 10000,
  message: "使いすぎ？そんなことないよ。全部『心の健康維持費』だからね。来月もリセットでゼロから！",
};

// ============================================================
// ストレス検知 → 商品提案シナリオ用データ
// ============================================================
export const stressRecoProduct: DemoMessageReco = {
  type: "product",
  title: "ルピシア お茶のバラエティセット",
  url: "https://search.rakuten.co.jp/search/mall/%E3%83%AB%E3%83%94%E3%82%B7%E3%82%A2+%E3%81%8A%E8%8C%B6+%E3%83%90%E3%83%A9%E3%82%A8%E3%83%86%E3%82%A3/",
  image: "https://thumbnail.image.rakuten.co.jp/@0_mall/lupicia/cabinet/set/23set_top.jpg",
  price: 2480,
  reason: "これは『自宅カフェ化計画費』だよ。毎日のカフェ代より全然お得じゃん！",
};

export const stressRecoVideo: DemoMessageReco = {
  type: "video",
  title: "【永遠に見てられる】癒しの猫動画まとめ",
  url: "https://www.youtube.com/results?search_query=%E7%8C%AB+%E7%99%92%E3%81%97+%E3%81%BE%E3%81%A8%E3%82%81",
  reason: "何もしなくていい時間、大事だよ。猫ちゃん見てダラダラしよ♪",
};

// 追加ライフログ（会話の中で蓄積されていく）
export const demoLifeLogsExtended: DemoLifeLog[] = [
  {
    id: "ll-ext-1",
    timeLabel: "9:00",
    emotion: "neutral",
    text: "出勤。電車混んでてイライラしたけど、音楽聴いて乗り切った",
    timestamp: today,
  },
  {
    id: "ll-ext-2",
    timeLabel: "10:30",
    emotion: "stressed",
    text: "上司に資料のやり直し食らって凹む…。2時間の会議でヘトヘト",
    timestamp: today,
  },
  {
    id: "ll-ext-3",
    timeLabel: "12:15",
    emotion: "calm",
    text: "同僚とイタリアンランチ。愚痴こぼして笑った（¥850）",
    timestamp: today,
  },
  {
    id: "ll-ext-4",
    timeLabel: "15:00",
    emotion: "tired",
    text: "午後のタスクが重い。コーヒーで後半戦った（¥350）",
    timestamp: today,
  },
  {
    id: "ll-ext-5",
    timeLabel: "17:30",
    emotion: "tired",
    text: "残業なしで帰れた！でも肌荒れが気になる…",
    timestamp: today,
  },
  {
    id: "ll-ext-6",
    timeLabel: "19:00",
    emotion: "calm",
    text: "帰宅。お茶淹れてNetflix見ながらほっと一息",
    timestamp: today,
  },
  {
    id: "ll-ext-7",
    timeLabel: "21:00",
    emotion: "happy",
    text: "好きな音楽聴きながら読書。穏やかな夜に感謝",
    timestamp: today,
  },
];

// ストレス検知後に買った支出
export const demoExpenseTeaSet: DemoExpense = {
  id: "exp-tea-set",
  amount: 2480,
  itemName: "ルピシア お茶セット",
  category: "recovery",
  meaningLabel: "自宅カフェ化計画費",
  source: "conversation",
  timestamp: today,
};
