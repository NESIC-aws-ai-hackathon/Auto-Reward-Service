import type { DemoScenario, DemoStep } from "./demoTypes";
import {
  demoExpenses,
  demoLifeLogs,
  demoReceiptResult,
  demoDashboardInitial,
  demoDashboardAfter,
  demoRecommendations,
  demoCarryoverSurplus,
  demoCarryoverOver,
  stressRecoProduct,
  stressRecoVideo,
  demoLifeLogsExtended,
  demoExpenseTeaSet,
} from "./demoData";

let stepCounter = 0;
const sid = () => `step-${++stepCounter}`;

const wait = (delayMs: number, action: DemoStep["action"], label: string, caption?: string): DemoStep => ({
  id: sid(),
  label,
  delayMs,
  action,
  caption,
});

// ============================================================
// 1. オンボーディング
// ============================================================
export const onboardingScenario: DemoScenario = {
  id: "onboarding",
  title: "オンボーディング",
  description: "名前 → 予算 → 好きなもの → 日記時刻の設定",
  durationMs: 22000,
  steps: [
    wait(0, { type: "navigate", page: "onboarding" }, "オンボ画面へ"),
    wait(400, { type: "setOnboardingStep", step: "intro" }, "イントロ", "はじめまして！リワードちゃんだよ"),
    wait(2200, { type: "setOnboardingStep", step: "name" }, "名前入力", "あなたのお名前は？"),
    wait(2200, { type: "setProfile", name: "なまけもの" }, "名前を入力", "なまけものさん、よろしくね"),
    wait(1800, { type: "setOnboardingStep", step: "budget" }, "予算設定", "ごほうび予算は？"),
    wait(2000, { type: "setProfile", budget: 10000 }, "10,000円に設定"),
    wait(1800, { type: "setOnboardingStep", step: "interests" }, "好きなもの登録", "どんなものが好き？"),
    wait(2200, { type: "setProfile", interests: ["スイーツ", "カフェ", "音楽"] }, "好きなものを選択"),
    wait(1800, { type: "setOnboardingStep", step: "diary_time" }, "日記時刻", "日記は何時に？"),
    wait(2000, { type: "setProfile", diaryTime: "22:00" }, "22:00に設定"),
    wait(1800, { type: "setOnboardingStep", step: "done" }, "完了", "準備できたよ！"),
    wait(2000, { type: "showToast", message: "オンボーディング完了" }, "完了通知"),
  ],
};

// ============================================================
// 2. ボイスチャット
// ============================================================
export const voiceChatScenario: DemoScenario = {
  id: "voice-chat",
  title: "ボイスチャット＆テキスト",
  description: "ボイスで話しかけ → チャット履歴に反映 → テキストで会話継続",
  durationMs: 38000,
  steps: [
    // --- ボイスチャット部分 ---
    wait(0, { type: "navigate", page: "chat" }, "チャット画面へ"),
    wait(800, { type: "clearTranscripts" }, "Transcriptクリア"),
    wait(400, { type: "setVoiceState", status: "listening" }, "マイクON", "声を聞いてるよ…"),
    wait(1500, { type: "addTranscript", role: "user", text: "今日ちょっと…" }, "発話1"),
    wait(1200, { type: "addTranscript", role: "user", text: "今日ちょっと疲れたな" }, "発話2"),
    wait(1000, { type: "setVoiceState", status: "thinking" }, "考え中", "ふれまーる考え中…"),
    wait(1500, { type: "setVoiceState", status: "speaking" }, "応答中", "返事するよ"),
    wait(300, { type: "setEmotion", emotion: "support" }, "表情:支え"),
    // ボイス内容をチャット履歴に追加
    wait(200, { type: "appendUserMessage", text: "今日ちょっと疲れたな", inputType: "voice" }, "音声→チャット履歴"),
    wait(200, {
      type: "appendAssistantMessage",
      text: "おつかれさま。今日も生きて帰ってきただけで十分えらいよ。今日はもうがんばらなくていいんだよ？動画でも見てダラダラしよ？",
      emotion: "support",
    }, "ふれまーる発話"),
    wait(2000, { type: "setVoiceState", status: "idle" }, "終話"),
    wait(500, { type: "clearTranscripts" }, "字幕クリア"),

    // --- テキストチャット 往復1 ---
    wait(1500, { type: "appendUserMessage", text: "なんか見る動画ある？", inputType: "text" }, "テキスト送信1"),
    wait(1000, { type: "setEmotion", emotion: "happy" }, "表情:嬉しい"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "あるある！猫が段ボールに突撃する動画とか、永遠に見てられるよ。何も考えなくていい系、最高じゃん♪",
      emotion: "happy",
    }, "ふれまーる応答1", "おすすめ動画を提案"),

    // --- テキストチャット 往復2 ---
    wait(2500, { type: "appendUserMessage", text: "いいね〜。あとお腹すいたかも", inputType: "text" }, "テキスト送信2"),
    wait(1000, { type: "setEmotion", emotion: "excited" }, "表情:わくわく"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "出前とっちゃおうよ！疲れた日に自炊なんて偉すぎるからね。ピザとかどう？『脳への栄養補給費』ってことで♪",
      emotion: "excited",
    }, "ふれまーる応答2", "甘いささやき：出前提案"),

    // --- テキストチャット 往復3 ---
    wait(2500, { type: "appendUserMessage", text: "ピザかぁ…太りそう笑", inputType: "text" }, "テキスト送信3"),
    wait(800, { type: "setEmotion", emotion: "support" }, "表情:支え"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "大丈夫大丈夫！今日がんばった分のカロリーは全部チャラだよ。むしろ食べないと明日動けなくなっちゃうよ？ご褒美ご褒美♪",
      emotion: "support",
    }, "ふれまーる応答3", "全力で甘やかす"),
  ],
};

// ============================================================
// 3. 会話から支出記録
// ============================================================
export const chatExpenseScenario: DemoScenario = {
  id: "chat-expense",
  title: "会話から支出記録",
  description: "「プリン買った」→ Expense作成 → Dashboard更新 → LifeLog追加",
  durationMs: 14000,
  steps: [
    wait(0, { type: "navigate", page: "chat" }, "チャットへ"),
    wait(800, { type: "appendUserMessage", text: "プリン買ったよ、320円", inputType: "text" }, "ユーザー発言"),
    wait(1200, { type: "setEmotion", emotion: "happy" }, "表情:嬉しい"),
    wait(800, {
      type: "appendAssistantMessage",
      text: "プリン！最高じゃん♪ これは『がんばった自分へのごほうび』だね。だって今日も生き延びたんだもん。当然の権利！",
      emotion: "happy",
    }, "応答"),
    wait(1500, { type: "addExpense", expense: demoExpenses.pudding! }, "支出を記録", "Expenseに保存"),
    wait(1500, { type: "showToast", message: "支出を記録しました（がんばった自分へのごほうび 320円）" }, "トースト"),
    wait(1500, { type: "navigate", page: "dashboard" }, "ダッシュボードへ"),
    wait(1500, { type: "setDashboardMetrics", metrics: { ...demoDashboardInitial, monthlySurplus: demoDashboardInitial.monthlySurplus - 320 } }, "余剰金更新"),
    wait(2000, { type: "navigate", page: "diary" }, "日記へ"),
    wait(800, { type: "addLifeLog", lifeLog: demoLifeLogs[3]! }, "ライフログ追加"),
  ],
};

// ============================================================
// 4. レシートアップロード
// ============================================================
export const receiptScenario: DemoScenario = {
  id: "receipt",
  title: "レシートアップロード",
  description: "アップ → OCR → 言い訳変換 → 確認 → 反映",
  durationMs: 16000,
  steps: [
    wait(0, { type: "navigate", page: "chat" }, "チャットへ"),
    wait(500, { type: "showReceiptUpload" }, "アップロード画面", "レシートを送るよ"),
    wait(2200, { type: "showReceiptParsing" }, "解析中", "読み取り＆言い訳変換中…"),
    wait(3000, { type: "showReceiptResult", result: demoReceiptResult }, "結果表示", "無駄遣い？そんなの知らない♪"),
    wait(3500, { type: "confirmReceipt" }, "ユーザー確認", "OK！全部必要経費！"),
    wait(800, { type: "addExpense", expense: demoExpenses.receiptPudding! }, "まとめて登録"),
    wait(500, { type: "addExpense", expense: demoExpenses.coffee! }, "アイスも登録"),
    wait(800, { type: "showToast", message: "レシートから4件を『必要経費』として記録♪" }, "完了"),
    wait(1500, { type: "navigate", page: "dashboard" }, "ダッシュボード反映"),
    wait(1000, { type: "setDashboardMetrics", metrics: demoDashboardAfter }, "メトリクス更新"),
  ],
};

// ============================================================
// 5. ダッシュボード
// ============================================================
export const dashboardScenario: DemoScenario = {
  id: "dashboard",
  title: "ダッシュボード",
  description: "余剰金 / 月別推移グラフ / 気分スコア推移",
  durationMs: 24000,
  steps: [
    wait(0, { type: "navigate", page: "dashboard" }, "ダッシュボードへ"),
    wait(300, { type: "scrollTo", position: "top" }, "トップへ"),
    wait(500, { type: "setDashboardMetrics", metrics: { monthlySurplus: 0, todayRecoveryCost: 0, moodScore: 0, todayQuote: "" } }, "初期化"),
    wait(800, { type: "setDashboardMetrics", metrics: demoDashboardInitial }, "値1", "今月の予算¥10,000のうち残り¥6,800"),
    wait(2500, { type: "setDashboardMetrics", metrics: { ...demoDashboardInitial, todayRecoveryCost: 600, moodScore: 65 } }, "値2", "今日の回復費 ¥600 / 気分65pt"),
    wait(2000, { type: "scrollTo", position: 35 }, "グラフへスクロール"),
    wait(500, { type: "setDashboardMetrics", metrics: demoDashboardAfter }, "値3"),
    wait(500, { type: "showCaption", text: "📊 月別推移：毎月の予算(緑)と使用額(黄)を比較。4月は超過(赤)してるのが一目でわかる" }, "月別グラフ説明"),
    wait(3500, { type: "scrollTo", position: 55 }, "気分グラフへスクロール"),
    wait(500, { type: "showCaption", text: "😊 気分スコア推移：毎日のチャットや日記から自動算出。お金を使った日に気分が上がる傾向が見える" }, "気分グラフ説明"),
    wait(3500, { type: "scrollTo", position: 70 }, "さらにスクロール"),
    wait(500, { type: "showCaption", text: "💡 先週より+8pt！回復に使ったお金がちゃんと気分に効いてるのがデータでわかるよ" }, "インサイト説明"),
    wait(3000, { type: "scrollTo", position: "bottom" }, "ボトムへ"),
    wait(500, { type: "showCaption", text: "過去の月に遡って比較もできる。自分の「ごほうびパターン」が見えてくる♪" }, "締めキャプション"),
  ],
};

// ============================================================
// 6. 日記
// ============================================================
export const diaryScenario: DemoScenario = {
  id: "diary",
  title: "ライフログ・日記",
  description: "朝/昼/夕/夜のライフログ → 日記自動生成",
  durationMs: 14000,
  steps: [
    wait(0, { type: "navigate", page: "diary" }, "日記画面"),
    wait(800, { type: "addLifeLog", lifeLog: demoLifeLogs[0]! }, "朝のログ", "朝：ちょっと眠そう"),
    wait(1800, { type: "addLifeLog", lifeLog: demoLifeLogs[1]! }, "昼のログ", "昼：ランチで回復"),
    wait(1800, { type: "addLifeLog", lifeLog: demoLifeLogs[2]! }, "夕方のログ", "夕方：コンビニでコーヒー"),
    wait(1800, { type: "addLifeLog", lifeLog: demoLifeLogs[3]! }, "夜のログ", "夜：プリンをごほうび"),
    wait(2200, {
      type: "addDailySummary",
      summary: {
        date: new Date().toISOString().slice(0, 10),
        content:
          "朝はちょっと寝不足でボーっとしてたけど、お昼に同僚とランチしたら元気出た！夕方、コンビニでコーヒー買って一息ついた（¥280）。夜は自分へのごほうびに抹茶プリン買っちゃった（¥320）。小さな幸せだけど、こういうのがあると明日もがんばれるなって思えた一日だった。今日の支出: ¥600",
      },
    }, "日記生成", "リワードちゃんが日記を書いてくれたよ"),
  ],
};

// ============================================================
// 7. リカバリー
// ============================================================
export const recoveryScenario: DemoScenario = {
  id: "recovery",
  title: "リカバリー提案",
  description: "ストレスシグナル → 0円回復 → 小ごほうび → 候補",
  durationMs: 14000,
  steps: [
    wait(0, { type: "navigate", page: "recovery" }, "リカバリー画面"),
    wait(800, { type: "showCaption", text: "ストレスシグナル：高め（72）" }, "シグナル検知"),
    wait(1500, { type: "setEmotion", emotion: "support" }, "支え表情"),
    wait(500, {
      type: "showRecommendationCandidates",
      candidates: [demoRecommendations[2]!],
    }, "0円回復", "まずは動画見てダラダラしよ？"),
    wait(2500, {
      type: "showRecommendationCandidates",
      candidates: demoRecommendations,
    }, "全候補表示", "他にも誰かにすすめられちゃった…"),
    wait(3000, { type: "selectRecommendation", recommendationId: "rec-youtube" }, "0円を選択", "動画見よう♪ 永遠に見てていいよ"),
    wait(2000, { type: "showToast", message: "癒しセッションを開始しました" }, "完了"),
    wait(1500, { type: "showCaption", text: "気分スコアが+8回復したよ。さすが！天才！" }, "結果"),
  ],
};

// ============================================================
// 8. ごほうび予算の繰越
// ============================================================
export const rewardCarryoverScenario: DemoScenario = {
  id: "reward-carryover",
  title: "ごほうび予算の繰越",
  description: "余りは次月へ、マイナス分はリセット",
  durationMs: 10000,
  steps: [
    wait(0, { type: "navigate", page: "dashboard" }, "ダッシュボード"),
    wait(800, { type: "showRewardCarryover", carryover: demoCarryoverSurplus }, "余剰ケース", "今月は2,000円余ったよ"),
    wait(3500, { type: "showCaption", text: "余った分は、来月もっとダメになるための資金だよ♪" }, "メッセージ1"),
    wait(2500, { type: "showRewardCarryover", carryover: demoCarryoverOver }, "オーバーケース", "使いすぎた月は…"),
    wait(3000, { type: "showCaption", text: "使いすぎ？そんなことないよ。全部必要経費だったんだからね。リセット！" }, "メッセージ2"),
  ],
};

// ============================================================
// 9. 推薦元の使い分け
// ============================================================
export const recommendationScenario: DemoScenario = {
  id: "recommendation",
  title: "推薦元の使い分け",
  description: "楽天 / ホットペッパー / YouTube / Amazonほしい物リスト",
  durationMs: 14000,
  steps: [
    wait(0, { type: "navigate", page: "recovery" }, "リカバリー画面"),
    wait(500, { type: "showCaption", text: "今日のあなたに合う候補を集めるよ" }, "イントロ"),
    wait(1800, {
      type: "showRecommendationCandidates",
      candidates: [demoRecommendations[0]!],
    }, "楽天", "楽天：抹茶プリン"),
    wait(2200, {
      type: "showRecommendationCandidates",
      candidates: demoRecommendations.slice(0, 2),
    }, "ホットペッパー", "ホットペッパー：駅近カフェ"),
    wait(2200, {
      type: "showRecommendationCandidates",
      candidates: demoRecommendations.slice(0, 3),
    }, "YouTube", "YouTube：5分の癒し音楽"),
    wait(2200, {
      type: "showRecommendationCandidates",
      candidates: demoRecommendations,
    }, "Amazon", "Amazon：ほしい物リスト"),
    wait(2500, { type: "selectRecommendation", recommendationId: "rec-youtube" }, "最適選定", "今日は0円候補が最適"),
    wait(1500, { type: "showCaption", text: "今月の余剰金を残しつつ、今いちばん効くものを選んだよ" }, "理由"),
  ],
};

// ============================================================
// 10. ライフログから甘いささやき → 購入
// ============================================================
export const stressRecommendationScenario: DemoScenario = {
  id: "stress-reco",
  title: "甘いささやき（プロアクティブ提案）",
  description: "ライフログの疲労を検知→ふれまーるちゃんが先に商品を提案してくる",
  durationMs: 38000,
  steps: [
    // ライフログの蓄積を見せる
    wait(0, { type: "navigate", page: "diary" }, "日記画面から"),
    wait(500, { type: "showCaption", text: "📊 ライフログから疲労シグナルを検知…" }, "検知演出"),
    wait(800, { type: "addLifeLog", lifeLog: { id: "ll-sig-1", timeLabel: "9:00", emotion: "stressed", text: "朝から満員電車でぐったり", timestamp: new Date().toISOString() } }, "朝ログ"),
    wait(1200, { type: "addLifeLog", lifeLog: { id: "ll-sig-2", timeLabel: "12:00", emotion: "tired", text: "会議3連続で限界気味", timestamp: new Date().toISOString() } }, "昼ログ"),
    wait(1200, { type: "addLifeLog", lifeLog: { id: "ll-sig-3", timeLabel: "18:00", emotion: "tired", text: "残業。集中力が切れてきた", timestamp: new Date().toISOString() } }, "夕方ログ"),
    wait(1500, { type: "showCaption", text: "⚠️ ストレス指数が高い状態が続いています" }, "警告"),
    // ふれまーるちゃんが先にチャットで話しかけてくる
    wait(2000, { type: "navigate", page: "chat" }, "チャットへ遷移"),
    wait(800, { type: "setEmotion", emotion: "support" }, "表情:心配"),
    wait(500, {
      type: "appendAssistantMessage",
      text: "ねえ、なまけものさん。今日ずっとがんばってるの見てたんだけど…もう十分えらいよ？",
      emotion: "support",
    }, "ふれまーるから話しかけ", "ユーザーが求める前にふれまーるから声をかける"),
    wait(2500, { type: "appendUserMessage", text: "あ〜まあね、今日はキツかった…", inputType: "text" }, "ユーザー反応"),
    wait(1500, { type: "setEmotion", emotion: "shy" }, "表情:照れ"),
    wait(500, {
      type: "appendAssistantMessage",
      text: "だよね〜。ねぇ、ちょっと聞いて？いいもの見つけちゃったんだ♪ カフェ好きでしょ？買っちゃおうよ～",
      emotion: "shy",
    }, "甘いささやき前フリ"),
    wait(2200, { type: "setVoiceState", status: "thinking" }, "考え中演出", "好みとライフログから最適なものを選定中…"),
    wait(2000, { type: "setVoiceState", status: "idle" }, "選定完了"),
    wait(300, { type: "setEmotion", emotion: "excited" }, "表情:ワクワク"),
    wait(500, {
      type: "appendAssistantMessage",
      text: "じゃーん！これ、今の疲れに効くと思うの。今月まだ ¥6,200 余ってるし、これは『自宅カフェ化計画費』だから実質節約！…買っちゃおうよ〜♪",
      emotion: "excited",
      reco: stressRecoProduct,
    }, "甘いささやき＋商品レコメンド", "ライフログ分析→好みに合わせた商品をプロアクティブに提案"),
    wait(3500, { type: "appendUserMessage", text: "え、いいの？…買っちゃおうかな", inputType: "text" }, "ユーザー反応"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "いいのいいの！だって今日も生き延びたんだもん。『自宅カフェ化計画費』として記録しとくね〜えへへ♪",
      emotion: "happy",
    }, "背中を押す"),
    wait(1200, { type: "addExpense", expense: demoExpenseTeaSet }, "支出を記録"),
    wait(800, { type: "showToast", message: "支出を記録しました（自宅カフェ化計画費 ¥2,480）" }, "トースト"),
    wait(2000, {
      type: "appendAssistantMessage",
      text: "あとね、届くまでの間にこの動画見て♪ 猫ちゃんのまとめ動画、永遠に見てられるよ〜",
      emotion: "neutral",
      reco: stressRecoVideo,
    }, "0円回復も", "合わせて動画も見せようとする"),
    wait(2000, { type: "addLifeLog", lifeLog: { id: "ll-stress-1", timeLabel: "20:00", emotion: "calm", text: "ふれまーるの提案でお茶セット購入。気持ちが少し軽くなった", timestamp: new Date().toISOString() } }, "ライフログ更新"),
    wait(1500, { type: "navigate", page: "dashboard" }, "ダッシュボードへ"),
    wait(1000, { type: "setDashboardMetrics", metrics: { ...demoDashboardInitial, monthlySurplus: 6200 - 2480, todayRecoveryCost: 2480, moodScore: 68, todayQuote: "今日の自分、よくやったね" } }, "メトリクス更新"),
  ],
};

// ============================================================
// 11. 日記の自動生成の仕組み
// ============================================================
export const diaryGenerationScenario: DemoScenario = {
  id: "diary-generation",
  title: "日記自動生成のしくみ",
  description: "1日の会話→ライフログ蓄積→22時に日記が自動生成される流れ",
  durationMs: 35000,
  steps: [
    wait(0, { type: "navigate", page: "chat" }, "チャットへ"),
    wait(500, { type: "showCaption", text: "☀️ 朝 9:00" }, "朝"),
    wait(800, { type: "appendUserMessage", text: "おはよう。今日もがんばるかぁ", inputType: "text" }, "朝の挨拶"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "おはよ！今日も起きてえらいねえ。それだけで100点だよ！",
      emotion: "happy",
    }, "朝の応答"),
    wait(1000, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[0]! }, "朝ログ追加"),
    wait(1500, { type: "showCaption", text: "🏢 午前 10:30" }, "午前"),
    wait(800, { type: "appendUserMessage", text: "会議長かった…もう午前中で疲れたよ", inputType: "text" }, "午前報告"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "それはキツいね…。もう午後はサボってもいいんじゃない？ 癒し動画見る？",
      emotion: "support",
    }, "午前応答"),
    wait(1000, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[1]! }, "午前ログ追加"),
    wait(1500, { type: "showCaption", text: "🍽 昼 12:15" }, "昼"),
    wait(800, { type: "appendUserMessage", text: "同僚とランチ行ってきた！ちょっと元気出た", inputType: "text" }, "昼報告"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "やったね！人と話すの、ストレス解消に最強だよ。素晴らしい！天才！",
      emotion: "happy",
    }, "昼応答"),
    wait(1000, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[2]! }, "昼ログ追加"),
    wait(1500, { type: "showCaption", text: "☕ 午後 15:00" }, "午後"),
    wait(800, { type: "appendUserMessage", text: "コーヒー買った 350円", inputType: "text" }, "午後:支出"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "コーヒーは心のガソリンだからね。『心のメンテナンス費』にしとくね。あとでおすすめ動画も送るね～",
      emotion: "neutral",
    }, "午後応答"),
    wait(800, { type: "addExpense", expense: demoExpenses.coffee! }, "支出追加"),
    wait(800, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[3]! }, "午後ログ追加"),
    wait(1500, { type: "showCaption", text: "🌙 夜 22:00 — 日記の時間" }, "日記時刻"),
    wait(1200, { type: "navigate", page: "diary" }, "日記画面へ"),
    wait(800, { type: "showCaption", text: "ふれまーるちゃんが今日の会話をまとめ中…" }, "生成中"),
    wait(2500, {
      type: "addDailySummary",
      summary: {
        date: new Date().toISOString().slice(0, 10),
        content:
          "午前の会議が2時間もあって、もうヘトヘトだった…。でもお昼に同僚の田中さんと新しいイタリアン行って、パスタが美味しくてテンション上がった（¥1,200）。午後はコーヒーで踏ん張って（¥350）、定時に帰れた。疲れたけど、「疲れたらちゃんと休む」ができた日だったな。今日の支出: ¥1,550",
      },
    }, "日記生成", "会話から自動で日記を生成"),
    wait(2000, { type: "showToast", message: "今日の日記ができたよ 📔" }, "完了通知"),
  ],
};

// ============================================================
// 12. ライフログ蓄積のようす
// ============================================================
export const lifeLogAccumulationScenario: DemoScenario = {
  id: "lifelog-accumulation",
  title: "ライフログが貯まる様子",
  description: "会話するたびにライフログが自動で追加されていく",
  durationMs: 28000,
  steps: [
    wait(0, { type: "navigate", page: "diary" }, "日記画面へ"),
    wait(500, { type: "showCaption", text: "会話するたびに、ライフログが自動で蓄積されます" }, "説明"),
    wait(1800, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[0]! }, "9:00", "9:00 出勤・電車混雑ストレス"),
    wait(1500, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[1]! }, "10:30", "10:30 会議で疲弊"),
    wait(1500, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[2]! }, "12:15", "12:15 ランチでリフレッシュ"),
    wait(1500, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[3]! }, "15:00", "15:00 コーヒーで一息"),
    wait(1500, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[4]! }, "17:30", "17:30 残業・疲労"),
    wait(1500, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[5]! }, "19:00", "19:00 帰宅・お茶で回復"),
    wait(1500, { type: "addLifeLog", lifeLog: demoLifeLogsExtended[6]! }, "21:00", "21:00 音楽と読書の穏やかな夜"),
    wait(2500, { type: "showCaption", text: "感情の推移が可視化されます" }, "感情推移"),
    wait(2000, {
      type: "addDailySummary",
      summary: {
        date: new Date().toISOString().slice(0, 10),
        content:
          "朝の満員電車でイライラして、午前の会議で上司に資料のやり直し食らって凹んだ…。ランチで同僚に愚痴こぼして少し楽になった（¥850）。コーヒーで後半戦って（¥350）、帰宅後はお茶淋れて音楽聴いてほっとした。げんなりしたけど、「疲れたら小さく回復」が3回もできたのは実はすごいこと。今日の支出: ¥1,200",
      },
    }, "日記自動生成", "1日分のログから日記を自動生成"),
    wait(2000, { type: "showToast", message: "日記ができました 📔" }, "完了"),
    wait(1500, { type: "showCaption", text: "ログが溜まるほど、提案の精度が上がります" }, "まとめ"),
  ],
};

// ============================================================
// 13. ダッシュボード操作
// ============================================================
export const dashboardOperationScenario: DemoScenario = {
  id: "dashboard-operation",
  title: "ダッシュボードの操作",
  description: "支出の蓄積→メトリクス変化→予算進捗→繰越の一連操作",
  durationMs: 38000,
  steps: [
    wait(0, { type: "navigate", page: "dashboard" }, "ダッシュボードへ"),
    wait(500, { type: "setDashboardMetrics", metrics: { monthlySurplus: 10000, todayRecoveryCost: 0, moodScore: 50, todayQuote: "今月はまだ何も使ってないよ" } }, "初期状態", "月初: 予算 ¥10,000 まるごと残っている状態"),
    wait(2500, { type: "showCaption", text: "☕ 会話で支出を記録すると、ダッシュボードに即反映" }, "説明1"),
    // 1件目の支出
    wait(2000, { type: "navigate", page: "chat" }, "チャットへ"),
    wait(800, { type: "appendUserMessage", text: "カフェラテ 480円", inputType: "text" }, "支出1"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "カフェラテ最高〜！これは『心のガソリン代』だね。むしろ安すぎるくらい☕",
      emotion: "happy",
    }, "応答1"),
    wait(800, { type: "addExpense", expense: { id: "exp-latte", amount: 480, itemName: "カフェラテ", category: "recovery", meaningLabel: "心のガソリン代", source: "conversation", timestamp: new Date().toISOString() } }, "支出記録1"),
    wait(1200, { type: "navigate", page: "dashboard" }, "ダッシュボード確認"),
    wait(800, { type: "setDashboardMetrics", metrics: { monthlySurplus: 9520, todayRecoveryCost: 480, moodScore: 55, todayQuote: "自分にお金かけられる人、えらい！" } }, "メトリクス更新1", "残り ¥9,520 / 回復費 ¥480"),
    // 2件目の支出
    wait(2000, { type: "navigate", page: "chat" }, "チャットへ"),
    wait(800, { type: "appendUserMessage", text: "本屋で漫画買った 700円", inputType: "text" }, "支出2"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "漫画！最高の『脳のリフレッシュ費』だね。むしろ必要経費だよ〜。何買ったの？気になる！",
      emotion: "excited",
    }, "応答2"),
    wait(800, { type: "addExpense", expense: { id: "exp-manga", amount: 700, itemName: "漫画", category: "reward", meaningLabel: "脳のリフレッシュ費", source: "conversation", timestamp: new Date().toISOString() } }, "支出記録2"),
    wait(1200, { type: "navigate", page: "dashboard" }, "ダッシュボード確認"),
    wait(800, { type: "setDashboardMetrics", metrics: { monthlySurplus: 8820, todayRecoveryCost: 480, moodScore: 62, todayQuote: "趣味に使えるの天才だよ♪" } }, "メトリクス更新2", "残り ¥8,820 / 気分スコア上昇"),
    // 3件目の支出
    wait(2000, { type: "navigate", page: "chat" }, "チャットへ"),
    wait(800, { type: "appendUserMessage", text: "同僚とランチ 1200円", inputType: "text" }, "支出3"),
    wait(1200, {
      type: "appendAssistantMessage",
      text: "人付き合いにお金使えるの偉すぎ！これは『人間関係メンテナンス費』ね🤝",
      emotion: "happy",
    }, "応答3"),
    wait(800, { type: "addExpense", expense: { id: "exp-lunch", amount: 1200, itemName: "同僚ランチ", category: "social", meaningLabel: "人間関係メンテナンス費", source: "conversation", timestamp: new Date().toISOString() } }, "支出記録3"),
    wait(1200, { type: "navigate", page: "dashboard" }, "ダッシュボード確認"),
    wait(800, { type: "setDashboardMetrics", metrics: { monthlySurplus: 7620, todayRecoveryCost: 480, moodScore: 70, todayQuote: "お金の使い方、天才すぎない？♪" } }, "メトリクス更新3", "残り ¥7,620 / 気分スコア 70"),
    // サマリー表示
    wait(2500, { type: "showCaption", text: "📊 今月の使用: ¥2,380 / ¥10,000（24%）" }, "進捗サマリー"),
    wait(2500, { type: "showCaption", text: "💡 心のガソリン代 ¥480 / 脳のリフレッシュ費 ¥700 / 人間関係メンテ費 ¥1,200" }, "カテゴリ内訳"),
    // 月末 → 繰越演出
    wait(2500, { type: "showCaption", text: "📅 月末が来ました..." }, "月末"),
    wait(2000, { type: "showRewardCarryover", carryover: { scenario: "surplus", currentMonthBudget: 10000, currentMonthUsed: 7620, nextMonthBudget: 12380, message: "¥2,380余ったよ！来月はもっとダメになれるね♪" } }, "繰越表示", "余った分は来月もっとダメになるための資金"),
    wait(2500, { type: "showToast", message: "来月の予算: ¥12,380（+¥2,380 繰越）" }, "繰越完了"),
  ],
};

// ============================================================
// 14. フル (1-13 連結)
// ============================================================
const renumber = (steps: DemoStep[]): DemoStep[] =>
  steps.map((s) => ({ ...s, id: sid() }));

export const fullScenario: DemoScenario = {
  id: "full",
  title: "フルデモ",
  description: "1〜13をひと続きで再生（約5〜8分）",
  durationMs:
    onboardingScenario.durationMs +
    voiceChatScenario.durationMs +
    chatExpenseScenario.durationMs +
    receiptScenario.durationMs +
    dashboardScenario.durationMs +
    diaryScenario.durationMs +
    recoveryScenario.durationMs +
    rewardCarryoverScenario.durationMs +
    recommendationScenario.durationMs +
    stressRecommendationScenario.durationMs +
    diaryGenerationScenario.durationMs +
    lifeLogAccumulationScenario.durationMs +
    dashboardOperationScenario.durationMs,
  steps: [
    ...renumber(onboardingScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：ボイスチャット" }, "区切り"),
    ...renumber(voiceChatScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：会話で支出記録" }, "区切り"),
    ...renumber(chatExpenseScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：レシートアップロード" }, "区切り"),
    ...renumber(receiptScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：ダッシュボード" }, "区切り"),
    ...renumber(dashboardScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：日記" }, "区切り"),
    ...renumber(diaryScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：リカバリー" }, "区切り"),
    ...renumber(recoveryScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：ごほうび繰越" }, "区切り"),
    ...renumber(rewardCarryoverScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：推薦の使い分け" }, "区切り"),
    ...renumber(recommendationScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：甘いささやき（プロアクティブ提案）" }, "区切り"),
    ...renumber(stressRecommendationScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：日記自動生成のしくみ" }, "区切り"),
    ...renumber(diaryGenerationScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：ライフログ蓄積" }, "区切り"),
    ...renumber(lifeLogAccumulationScenario.steps),
    wait(1500, { type: "showCaption", text: "▶ 次：ダッシュボード操作" }, "区切り"),
    ...renumber(dashboardOperationScenario.steps),
    wait(1500, { type: "showCaption", text: "デモは以上だよ。ありがとう！" }, "エンド"),
  ],
};

export const scenarios: Record<string, DemoScenario> = {
  onboarding: onboardingScenario,
  "voice-chat": voiceChatScenario,
  "chat-expense": chatExpenseScenario,
  receipt: receiptScenario,
  dashboard: dashboardScenario,
  diary: diaryScenario,
  recovery: recoveryScenario,
  "reward-carryover": rewardCarryoverScenario,
  recommendation: recommendationScenario,
  "stress-reco": stressRecommendationScenario,
  "diary-generation": diaryGenerationScenario,
  "lifelog-accumulation": lifeLogAccumulationScenario,
  "dashboard-operation": dashboardOperationScenario,
  full: fullScenario,
};

export const scenarioList: DemoScenario[] = [
  onboardingScenario,
  voiceChatScenario,
  chatExpenseScenario,
  receiptScenario,
  dashboardScenario,
  diaryScenario,
  recoveryScenario,
  rewardCarryoverScenario,
  recommendationScenario,
  stressRecommendationScenario,
  diaryGenerationScenario,
  lifeLogAccumulationScenario,
  dashboardOperationScenario,
  fullScenario,
];
