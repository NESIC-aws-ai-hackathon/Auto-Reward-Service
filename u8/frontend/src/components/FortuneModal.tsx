import { useState, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { getJstDateString } from '../lib/datetime';
import './FortuneModal.css';

const FORTUNES = [
  { emoji: '🌟', level: '大吉', color: '#FFD700' },
  { emoji: '✨', level: '中吉', color: '#87CEEB' },
  { emoji: '🌸', level: '小吉', color: '#FFB7C5' },
  { emoji: '🍀', level: '吉', color: '#68a977' },
  { emoji: '🌈', level: '末吉', color: '#DDA0DD' },
];

const RECOVERY_TIPS = [
  { tip: '深呼吸を3回してみて。肩の力がふっと抜けるよ', category: '呼吸' },
  { tip: '好きな飲み物をゆっくり味わう時間を作ってみて☕', category: 'ティーブレイク' },
  { tip: '窓を開けて外の空気を吸ってみよう。風が気持ちいいよ🌿', category: '自然' },
  { tip: '今日一番うれしかったこと、小さくても思い出してみて💛', category: '振り返り' },
  { tip: '5分だけストレッチ！体がほぐれると心もほぐれるよ', category: 'ストレッチ' },
  { tip: '好きな音楽を1曲だけ聴いてみて。気分が変わるかも🎵', category: '音楽' },
  { tip: 'スマホを置いて、手を温かいもので包んでみて🫶', category: 'リラックス' },
  { tip: '今日の自分に「お疲れさま」って言ってあげてね', category: '自己肯定' },
  { tip: 'お散歩に出かけてみない？ 10分でも気分転換になるよ🚶', category: '散歩' },
  { tip: '大好きな人の顔を思い浮かべてみて。心があったかくなるよ💕', category: 'つながり' },
];

export function FortuneModal({ onClose }: { onClose: () => void }) {
  const api = useApi();
  const [fortune, setFortune] = useState<typeof FORTUNES[0] | null>(null);
  const [tip, setTip] = useState<typeof RECOVERY_TIPS[0] | null>(null);
  const [aiMessage, setAiMessage] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [animating, setAnimating] = useState(true);

  useEffect(() => {
    // Seeded random based on date so same fortune per day
    const today = getJstDateString();
    const seed = hashCode(today);
    const fortuneIdx = Math.abs(seed) % FORTUNES.length;
    const tipIdx = Math.abs(seed * 7) % RECOVERY_TIPS.length;

    setFortune(FORTUNES[fortuneIdx]!);
    setTip(RECOVERY_TIPS[tipIdx]!);

    // Show animation for 1.5s
    setTimeout(() => {
      setAnimating(false);
      setLoading(false);
    }, 1500);

    // Try to get AI message
    fetchAiMessage();
  }, []);

  const fetchAiMessage = async () => {
    try {
      const result = await api.sendChatMessage('今日のご褒美占いをして。一言で今日の回復アドバイスをちょうだい。30文字以内で。');
      setAiMessage(result.reply);
    } catch {
      // Fallback - use local tip
    }
  };

  const hashCode = (str: string) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash |= 0;
    }
    return hash;
  };

  return (
    <div className="fortune-overlay" onClick={onClose}>
      <div className="fortune-modal" onClick={e => e.stopPropagation()}>
        {animating ? (
          <div className="fortune-spinning">
            <div className="fortune-star">✨</div>
            <p>占い中...</p>
          </div>
        ) : (
          <div className="fortune-result">
            <div className="fortune-close" onClick={onClose}>✕</div>
            <div className="fortune-emoji">{fortune?.emoji}</div>
            <h2 style={{ color: fortune?.color }}>今日の運勢：{fortune?.level}</h2>
            <div className="fortune-card">
              <span className="fortune-category">💡 {tip?.category}</span>
              <p className="fortune-tip">{tip?.tip}</p>
            </div>
            {aiMessage && !loading && (
              <div className="fortune-ai">
                <img src="/assets/furemaru-avatar.png" alt="" className="fortune-avatar" />
                <p>{aiMessage}</p>
              </div>
            )}
            <button className="fortune-btn" onClick={onClose}>ありがとう♪</button>
          </div>
        )}
      </div>
    </div>
  );
}
