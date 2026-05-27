import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../hooks/useApi';
import './OnboardingPage.css';

type Step = 'welcome' | 'name' | 'income' | 'fixed_costs' | 'confirm_budget' | 'bonus' | 'interests' | 'time' | 'done';

const STEPS: Step[] = ['welcome', 'name', 'income', 'fixed_costs', 'confirm_budget', 'bonus', 'interests', 'time'];

// オンボーディングで選べる興味カテゴリ
const INTEREST_OPTIONS = [
  { id: 'coffee', emoji: '☕', label: 'コーヒー・カフェ', keyword: 'コーヒー 豆 ドリップ' },
  { id: 'sweets', emoji: '🍰', label: 'スイーツ・お菓子', keyword: 'スイーツ ご褒美' },
  { id: 'bath', emoji: '🛁', label: 'お風呂・温泉', keyword: 'バスソルト 入浴剤' },
  { id: 'music', emoji: '🎵', label: '音楽・ライブ', keyword: 'ヒーリング音楽 リラックス' },
  { id: 'movie', emoji: '🎬', label: '映画・動画', keyword: 'おすすめ映画' },
  { id: 'reading', emoji: '📚', label: '読書・漫画', keyword: '話題の本' },
  { id: 'yoga', emoji: '🧘', label: 'ヨガ・運動', keyword: 'ヨガ リラックス' },
  { id: 'aroma', emoji: '🧴', label: 'アロマ・香り', keyword: 'アロマ リラックス' },
  { id: 'animal', emoji: '🐱', label: '動物・ペット', keyword: '癒し 動物 動画' },
  { id: 'cooking', emoji: '🍳', label: '料理・グルメ', keyword: '簡単レシピ ご褒美' },
  { id: 'travel', emoji: '✈️', label: '旅行・おでかけ', keyword: '旅行 リフレッシュ' },
  { id: 'stationery', emoji: '✏️', label: '文房具・手帳', keyword: '文房具 ご褒美' },
] as const;

function calcRewardBudget(income: number, fixedCosts: number): number {
  const surplus = Math.max(0, income - fixedCosts);
  return Math.max(3000, Math.min(Math.floor(surplus * 0.15), 30000));
}

export function OnboardingPage() {
  const api = useApi();
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('welcome');
  const [name, setName] = useState('');
  const [income, setIncome] = useState('');
  const [fixedCosts, setFixedCosts] = useState('');
  const [customBudget, setCustomBudget] = useState('');
  const [bonusAmount, setBonusAmount] = useState('');
  const [bonusMonths, setBonusMonths] = useState('');
  const [diaryTime, setDiaryTime] = useState('22:00');
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const incomeNum = parseInt(income) || 0;
  const fixedNum = parseInt(fixedCosts) || 0;
  const suggestedBudget = calcRewardBudget(incomeNum, fixedNum);
  const finalBudget = customBudget ? parseInt(customBudget) || suggestedBudget : suggestedBudget;

  const handleFinish = async (e?: FormEvent) => {
    e?.preventDefault();
    setSaving(true);
    try {
      await api.updateSettings({
        display_name: name.trim(),
        monthly_surplus: finalBudget,
        diary_time: diaryTime,
        notification_enabled: true,
      });
      // Save financial profile
      await api.submitOnboarding({
        monthly_income: incomeNum,
        fixed_costs: fixedNum,
        reward_budget: finalBudget,
        bonus_amount: parseInt(bonusAmount) || 0,
        bonus_months: bonusMonths,
        interests: selectedInterests,
      });
      setStep('done');
      setTimeout(() => navigate('/chat', { replace: true }), 2500);
    } catch {
      navigate('/chat', { replace: true });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="onboarding-page">
      {/* Step: Welcome */}
      {step === 'welcome' && (
        <div className="onboarding-step fade-in">
          <img src="/assets/furemaru-fullbody.png" alt="" className="onboarding-avatar-img" />
          <h1 className="onboarding-title">はじめまして！</h1>
          <p className="onboarding-text">
            わたしは<strong>ふれまーるちゃん</strong>。<br />
            あなたの毎日をちょっとだけ甘やかすパートナーだよ♪
          </p>
          <p className="onboarding-text-sub">
            お財布をやさしく見守りながら、<br />
            ちゃんと甘やかしも楽しめるようサポートするね〜🌿
          </p>
          <button className="btn btn-primary" onClick={() => setStep('name')}>
            よろしくね！
          </button>
        </div>
      )}

      {/* Step: Name */}
      {step === 'name' && (
        <div className="onboarding-step fade-in">
          <img src="/assets/furemaru-happy.png" alt="" className="onboarding-avatar-img small" />
          <p className="onboarding-bubble">
            まず教えて〜♪<br />なんて呼んだらいい？
          </p>
          <div className="onboarding-input-area">
            <input
              type="text"
              className="onboarding-input"
              placeholder="ニックネーム"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={20}
              autoFocus
            />
            <button className="btn btn-primary" onClick={() => setStep('income')} disabled={!name.trim()}>
              次へ
            </button>
          </div>
        </div>
      )}

      {/* Step: Income */}
      {step === 'income' && (
        <div className="onboarding-step fade-in">
          <img src="/assets/furemaru-happy.png" alt="" className="onboarding-avatar-img small" />
          <p className="onboarding-bubble">
            {name}ちゃん、いいね〜♪<br />
            毎月の手取り収入を教えてくれるかな？<br />
            <span className="bubble-hint">（おおよそでOKだよ〜）</span>
          </p>
          <div className="onboarding-input-area">
            <div className="budget-input-wrap">
              <span className="budget-prefix">¥</span>
              <input
                type="number"
                className="onboarding-input budget-input"
                placeholder="250000"
                value={income}
                onChange={(e) => setIncome(e.target.value)}
                min={0}
              />
            </div>
            <div className="budget-presets">
              {[150000, 200000, 250000, 300000, 400000].map((v) => (
                <button key={v} className={`preset-btn ${income === String(v) ? 'active' : ''}`} onClick={() => setIncome(String(v))}>
                  {v >= 10000 ? `${v / 10000}万` : `¥${v.toLocaleString()}`}
                </button>
              ))}
            </div>
            <button className="btn btn-primary" onClick={() => setStep('fixed_costs')} disabled={!income || incomeNum < 10000}>
              次へ
            </button>
          </div>
        </div>
      )}

      {/* Step: Fixed Costs */}
      {step === 'fixed_costs' && (
        <div className="onboarding-step fade-in">
          <img src="/assets/furemaru-happy.png" alt="" className="onboarding-avatar-img small" />
          <p className="onboarding-bubble">
            次に、毎月の固定費を教えてね〜🌱<br />
            家賃・スマホ代・サブスクの合計でOKだよ<br />
            <span className="bubble-hint">（ざっくりで大丈夫〜）</span>
          </p>
          <div className="onboarding-input-area">
            <div className="budget-input-wrap">
              <span className="budget-prefix">¥</span>
              <input
                type="number"
                className="onboarding-input budget-input"
                placeholder="120000"
                value={fixedCosts}
                onChange={(e) => setFixedCosts(e.target.value)}
                min={0}
              />
            </div>
            <div className="budget-presets">
              {[80000, 100000, 120000, 150000, 200000].map((v) => (
                <button key={v} className={`preset-btn ${fixedCosts === String(v) ? 'active' : ''}`} onClick={() => setFixedCosts(String(v))}>
                  {v >= 10000 ? `${v / 10000}万` : `¥${v.toLocaleString()}`}
                </button>
              ))}
            </div>
            <button className="btn btn-primary" onClick={() => setStep('confirm_budget')} disabled={!fixedCosts}>
              次へ
            </button>
          </div>
        </div>
      )}

      {/* Step: Confirm Budget */}
      {step === 'confirm_budget' && (
        <div className="onboarding-step fade-in">
          <img src="/assets/furemaru-happy.png" alt="" className="onboarding-avatar-img small" />
          <p className="onboarding-bubble">
            計算してみたよ〜🌿
          </p>
          <div className="budget-summary">
            <div className="budget-summary-row"><span>毎月の手取り</span><strong>¥{incomeNum.toLocaleString()}</strong></div>
            <div className="budget-summary-row"><span>固定費合計</span><strong>¥{fixedNum.toLocaleString()}</strong></div>
            <div className="budget-summary-row"><span>自由に使えるお金</span><strong>¥{Math.max(0, incomeNum - fixedNum).toLocaleString()}</strong></div>
            <div className="budget-summary-row highlight"><span>✨ おすすめご褒美枠</span><strong>¥{suggestedBudget.toLocaleString()}/月</strong></div>
          </div>
          <p className="onboarding-text-sub" style={{ marginTop: 8 }}>
            変えたい場合は金額を入力してね
          </p>
          <div className="onboarding-input-area">
            <div className="budget-input-wrap">
              <span className="budget-prefix">¥</span>
              <input
                type="number"
                className="onboarding-input budget-input"
                placeholder={String(suggestedBudget)}
                value={customBudget}
                onChange={(e) => setCustomBudget(e.target.value)}
                min={0}
              />
            </div>
            <button className="btn btn-primary" onClick={() => setStep('bonus')}>
              {customBudget ? `¥${(parseInt(customBudget) || suggestedBudget).toLocaleString()}でOK` : 'このままでOK♪'}
            </button>
          </div>
        </div>
      )}

      {/* Step: Bonus */}
      {step === 'bonus' && (
        <div className="onboarding-step fade-in">
          <img src="/assets/furemaru-happy.png" alt="" className="onboarding-avatar-img small" />
          <p className="onboarding-bubble">
            ボーナスはあるかなぁ？🌸<br />
            <span className="bubble-hint">（なければスキップでOK〜）</span>
          </p>
          <div className="onboarding-input-area">
            <div className="budget-input-wrap">
              <span className="budget-prefix">¥</span>
              <input
                type="number"
                className="onboarding-input budget-input"
                placeholder="600000 (年間合計)"
                value={bonusAmount}
                onChange={(e) => setBonusAmount(e.target.value)}
                min={0}
              />
            </div>
            <input
              type="text"
              className="onboarding-input"
              placeholder="支給月（例: 6月,12月）"
              value={bonusMonths}
              onChange={(e) => setBonusMonths(e.target.value)}
              style={{ marginTop: 8 }}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button className="btn btn-secondary" onClick={() => setStep('interests')}>
                スキップ
              </button>
              <button className="btn btn-primary" onClick={() => setStep('interests')} disabled={!bonusAmount}>
                次へ
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step: Interests */}
      {step === 'interests' && (
        <div className="onboarding-step fade-in">
          <img src="/assets/furemaru-happy.png" alt="" className="onboarding-avatar-img small" />
          <p className="onboarding-bubble">
            {name}ちゃんの好きなこと教えて～♪<br />
            <span className="bubble-hint">（あとでご褒美の提案に使うよ！）</span>
          </p>
          <div className="onboarding-input-area">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {INTEREST_OPTIONS.map(opt => (
                <button
                  key={opt.id}
                  className={`preset-btn ${selectedInterests.includes(opt.id) ? 'active' : ''}`}
                  onClick={() => setSelectedInterests(prev =>
                    prev.includes(opt.id) ? prev.filter(x => x !== opt.id) : [...prev, opt.id]
                  )}
                  style={{ padding: '10px 4px', fontSize: 12, textAlign: 'center', lineHeight: 1.3 }}
                >
                  <span style={{ fontSize: 20, display: 'block' }}>{opt.emoji}</span>
                  {opt.label}
                </button>
              ))}
            </div>
            <p style={{ fontSize: 11, color: '#8e8270', margin: '8px 0', textAlign: 'center' }}>
              {selectedInterests.length > 0 ? `${selectedInterests.length}個選択中` : 'いくつでもOKだよ～'}
            </p>
            <button className="btn btn-primary" onClick={() => setStep('time')}>
              {selectedInterests.length > 0 ? '次へ' : 'スキップ'}
            </button>
          </div>
        </div>
      )}

      {/* Step: Diary Time */}
      {step === 'time' && (
        <div className="onboarding-step fade-in">
          <img src="/assets/furemaru-happy.png" alt="" className="onboarding-avatar-img small" />
          <p className="onboarding-bubble">
            最後に〜♪ 毎日の終わりに日記をまとめるね。<br />
            何時ごろがいい？
          </p>
          <div className="onboarding-input-area">
            <input
              type="time"
              className="onboarding-input time-input"
              value={diaryTime}
              onChange={(e) => setDiaryTime(e.target.value)}
            />
            <button className="btn btn-primary" onClick={handleFinish} disabled={saving}>
              {saving ? '設定中...' : 'はじめる！🌿'}
            </button>
          </div>
        </div>
      )}

      {/* Step: Done */}
      {step === 'done' && (
        <div className="onboarding-step fade-in">
          <img src="/assets/furemaru-fullbody.png" alt="" className="onboarding-avatar-img" />
          <h2 className="onboarding-done-title">準備できたよ！🌿</h2>
          <p className="onboarding-text">
            {name}ちゃんのこと、これからよろしくね♪<br />
            いつでも話しかけてね〜
          </p>
          <p className="onboarding-text-sub">
            ご褒美枠: ¥{finalBudget.toLocaleString()}/月
          </p>
        </div>
      )}

      {/* Progress */}
      <div className="onboarding-progress">
        {STEPS.map((s, i) => (
          <div key={s} className={`progress-dot ${step === s ? 'active' : STEPS.indexOf(step) > i || step === 'done' ? 'completed' : ''}`} />
        ))}
      </div>
    </div>
  );
}
