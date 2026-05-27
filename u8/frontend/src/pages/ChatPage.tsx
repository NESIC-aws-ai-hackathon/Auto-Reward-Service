import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useSpeechInput } from '../hooks/useSpeechInput';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';
import type { ChatSuggestion } from '../lib/api';
import './ChatPage.css';

/**
 * Resize image to max dimension while keeping aspect ratio.
 * Returns base64 string (without data: prefix) in JPEG format.
 */
function compressImage(file: File, maxDim = 1280, quality = 0.8): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      let { width, height } = img;
      if (width > maxDim || height > maxDim) {
        if (width > height) {
          height = Math.round(height * (maxDim / width));
          width = maxDim;
        } else {
          width = Math.round(width * (maxDim / height));
          height = maxDim;
        }
      }
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d')!;
      ctx.drawImage(img, 0, 0, width, height);
      const dataUrl = canvas.toDataURL('image/jpeg', quality);
      const base64 = dataUrl.split(',')[1] || dataUrl;
      resolve(base64);
    };
    img.onerror = reject;
    img.src = url;
  });
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  emotion?: string;
  suggestion?: { to: string; label: string };
  reco?: ChatSuggestion;
}

const MAX_HISTORY = 200;

function getChatStorageKey(userId: string) { return `fremaru_chat_${userId}`; }
function getLastFetchKey(userId: string) { return `fremaru_fetch_${userId}`; }

function loadChatHistory(userId: string): ChatMessage[] {
  try {
    const stored = localStorage.getItem(getChatStorageKey(userId));
    return stored ? JSON.parse(stored) : [];
  } catch { return []; }
}

function saveChatHistory(userId: string, messages: ChatMessage[]) {
  localStorage.setItem(getChatStorageKey(userId), JSON.stringify(messages.slice(-MAX_HISTORY)));
}

const GREETING_MESSAGES = [
  "おはよ〜♪ 今日はどんな一日になるかな？ なんでも話してね。",
  "やっほ〜！ 会えてうれしいな♪ 今日はどんな気分？",
  "こんにちは〜♪ ゆっくりしていってね。なんかあった？",
  "おつかれさま〜。今日もよくがんばったね♪ 話したいことある？",
];

function getGreetingForTime(): string {
  const hour = new Date().getHours();
  if (hour < 11) return GREETING_MESSAGES[0]!;
  if (hour < 14) return GREETING_MESSAGES[2]!;
  if (hour < 18) return GREETING_MESSAGES[1]!;
  return GREETING_MESSAGES[3]!;
}

/**
 * 「ふれまーるちゃんの記憶」パネル — 過去のLIFE_LOGや支出パターンから
 * 「あなたのことを覚えてるよ」を可視化する。沼ループの「記憶される」中核UI。
 */
type MemoryData = {
  topics: { name: string; count: number }[];
  favorite_items: { name: string; count: number }[];
  episodes: { content: string; category: string; date: string; topic: string }[];
  total_chat_days: number;
  total_life_logs: number;
  days_since_last_chat: number;
};

function MemoryPanel({ userId }: { userId: string }) {
  const api = useApi();
  const [data, setData] = useState<MemoryData | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getMemories().then((d: MemoryData) => {
      if (cancelled) return;
      setData(d);
      setLoaded(true);
    }).catch(() => setLoaded(true));
    return () => { cancelled = true; };
  }, [userId]);

  if (!loaded || !data) return null;
  const hasMemory = (data.total_life_logs > 0 || data.favorite_items.length > 0 || data.topics.length > 0);
  if (!hasMemory) return null;

  // 1行プレビューを生成（友達っぽいトーン）
  const previewParts: string[] = [];
  if (data.favorite_items[0]) previewParts.push(`${data.favorite_items[0].name}が好きだったよね`);
  else if (data.topics[0]) previewParts.push(`${data.topics[0].name}の話、最近よく聞いてる気がする`);
  if (data.total_chat_days >= 7) previewParts.push(`もう${data.total_chat_days}日も一緒だよ♪`);
  else if (data.total_chat_days >= 1) previewParts.push(`これで${data.total_chat_days}日目だね`);
  const preview = previewParts.join(' / ') || 'ちょっとずつ、あなたのこと覚えてきたよ';

  return (
    <section style={{
      margin: '12px 16px', padding: '12px 14px', borderRadius: 14,
      background: 'linear-gradient(135deg, #fff7f9 0%, #f3f8ec 100%)',
      border: '1px solid #f0d8e0', fontSize: 13, color: '#5a4a52',
    }}>
      <button
        onClick={() => setExpanded(v => !v)}
        style={{ width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: '#5a4a52', fontSize: 13 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>💭</span>
          <strong style={{ flex: 1 }}>ふれまーるちゃんの記憶</strong>
          <span style={{ fontSize: 11, color: '#a08891' }}>{expanded ? '閉じる' : 'もっと見る'}</span>
        </div>
        <div style={{ marginTop: 6, lineHeight: 1.5 }}>{preview}</div>
      </button>
      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px dashed #e8c8d0', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {data.favorite_items.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: '#a08891', marginBottom: 4 }}>🛒 よく買ってるもの</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {data.favorite_items.slice(0, 5).map(item => (
                  <span key={item.name} style={{ background: '#fff', padding: '3px 10px', borderRadius: 12, border: '1px solid #f0d8e0' }}>
                    {item.name} <small style={{ color: '#a08891' }}>×{item.count}</small>
                  </span>
                ))}
              </div>
            </div>
          )}
          {data.topics.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: '#a08891', marginBottom: 4 }}>💬 よく話してくれること</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {data.topics.slice(0, 6).map(t => (
                  <span key={t.name} style={{ background: '#fff', padding: '3px 10px', borderRadius: 12, border: '1px solid #d8e8c4' }}>
                    {t.name}
                  </span>
                ))}
              </div>
            </div>
          )}
          {data.episodes.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: '#a08891', marginBottom: 4 }}>📌 覚えてるエピソード</div>
              <ul style={{ margin: 0, padding: '0 0 0 18px', lineHeight: 1.6 }}>
                {data.episodes.slice(0, 4).map((ep, i) => (
                  <li key={i} style={{ fontSize: 12 }}>
                    <span style={{ color: '#9fa080' }}>{ep.date || ''}</span> {ep.content}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div style={{ fontSize: 11, color: '#a08891', textAlign: 'right' }}>
            記録: 会話{data.total_chat_days}日 / 出来事{data.total_life_logs}件
          </div>
        </div>
      )}
    </section>
  );
}

function getEmotionAvatar(emotion?: string): string {
  const map: Record<string, string> = {
    happy: '/assets/emotions/happy.png',
    support: '/assets/emotions/support.png',
    shy: '/assets/emotions/shy.png',
    excited: '/assets/emotions/excited.png',
    neutral: '/assets/emotions/neutral.png',
    listening: '/assets/emotions/listening.png',
  };
  return map[emotion || 'support'] || map['support']!;
}

/**
 * 会話の話題から、Dashboard / Diary への自然な導線を提案する。
 * Recovery は reco カード（商品/動画URL）で直接提案するため、ここからは外す。
 * AGENTS.md「広告っぽくしない、友達の自然な提案」に沿い、押し付けず1つだけ出す。
 */
type Suggestion = { to: string; label: string };
function pickSuggestion(userText: string, replyText: string, hasReco: boolean): Suggestion | null {
  // reco カードが既に出ているなら追加の導線は出さない（くどさを避ける）
  if (hasReco) return null;
  const text = `${userText}\n${replyText}`;
  const dashboard = /円|お金|家計|予算|貯金|余裕|無駄遣い|使いすぎ|支出|余剰/;
  const diary = /今日|振り返|記録|日記|まとめ|ログ/;
  if (dashboard.test(text)) return { to: '/dashboard', label: '👛 今月の余裕をのぞいてみる' };
  if (diary.test(text)) return { to: '/diary', label: '📖 今日のダイアリーを見る' };
  return null;
}

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const api = useApi();
  const { user } = useAuth();
  const userId = user?.sub || 'anonymous';
  const [textInput, setTextInput] = useState('');
  const [interimText, setInterimText] = useState('');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>(() => {
    const saved = loadChatHistory(userId);
    const lastMsg = saved[saved.length - 1];
    const now = Date.now();
    const lastTime = lastMsg ? new Date(lastMsg.timestamp).getTime() : 0;
    if (saved.length === 0 || (now - lastTime > 30 * 60 * 1000)) {
      const greeting: ChatMessage = {
        id: `greeting-${now}`,
        role: 'assistant',
        content: getGreetingForTime(),
        timestamp: new Date().toISOString(),
        emotion: 'happy',
      };
      const updated = [...saved, greeting];
      saveChatHistory(userId, updated);
      return updated;
    }
    return saved;
  });
  const [isSending, setIsSending] = useState(false);
  const [isUploadingReceipt, setIsUploadingReceipt] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch proactive messages
  useEffect(() => {
    fetchNewMessages();
    const interval = setInterval(fetchNewMessages, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchNewMessages = useCallback(async () => {
    try {
      const lastFetch = localStorage.getItem(getLastFetchKey(userId)) || '';
      const resp = await api.getChatMessages(lastFetch, 50);
      if (resp.messages.length > 0) {
        const newMsgs: ChatMessage[] = resp.messages
          .filter(m => m.content)
          .map((m, i) => ({
            id: `srv-${m.timestamp}-${i}`,
            role: m.role as 'user' | 'assistant',
            content: m.content,
            timestamp: m.timestamp,
            emotion: 'support',
          }));
        setChatHistory(prev => {
          const existingTs = new Set(prev.map(m => m.timestamp));
          const unique = newMsgs.filter(m => !existingTs.has(m.timestamp));
          if (unique.length === 0) return prev;
          const merged = [...prev, ...unique].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
          saveChatHistory(userId, merged);
          return merged;
        });
        const latest = resp.messages[resp.messages.length - 1];
        if (latest) localStorage.setItem(getLastFetchKey(userId), latest.timestamp);
      }
    } catch { /* silent */ }
  }, [api, userId]);

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [chatHistory]);

  const formatTime = (iso: string) => {
    try {
      const d = new Date(iso);
      return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
    } catch { return ''; }
  };

  const sendMessage = useCallback(async (rawText: string) => {
    const text = rawText.trim();
    if (!text || isSending) return;
    setIsSending(true);

    const userMsg: ChatMessage = { id: `user-${Date.now()}`, role: 'user', content: text, timestamp: new Date().toISOString() };
    const updated = [...chatHistory, userMsg];
    setChatHistory(updated);
    saveChatHistory(userId, updated);

    try {
      const resp = await api.sendChatMessage(text);
      const assistantMsg: ChatMessage = {
        id: `asst-${Date.now()}`, role: 'assistant', content: resp.reply,
        timestamp: resp.timestamp, emotion: 'support',
        suggestion: pickSuggestion(text, resp.reply, !!resp.suggestion?.url) || undefined,
        reco: resp.suggestion,
      };
      const withReply = [...updated, assistantMsg];
      setChatHistory(withReply);
      saveChatHistory(userId, withReply);
      // Update lastFetch to prevent fetchNewMessages from re-fetching this message
      localStorage.setItem(getLastFetchKey(userId), resp.timestamp);
    } catch {
      const fallback = ['えへへ、ちょっと電波が届かなかったみたい……♪', 'あれれ、お返事がうまく届かなかったかも……。', 'ん〜、森の奥まで電波が来てないみたい。'];
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`, role: 'assistant',
        content: fallback[Math.floor(Math.random() * fallback.length)]!,
        timestamp: new Date().toISOString(), emotion: 'shy',
      };
      const withError = [...updated, errorMsg];
      setChatHistory(withError);
      saveChatHistory(userId, withError);
    } finally { setIsSending(false); }
  }, [api, chatHistory, isSending, userId]);

  const handleSendText = async () => {
    const text = textInput.trim();
    if (!text) return;
    setTextInput('');
    await sendMessage(text);
  };

  const handleReceiptUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || isUploadingReceipt) return;
    e.target.value = '';

    setIsUploadingReceipt(true);
    const userMsg: ChatMessage = {
      id: `user-receipt-${Date.now()}`, role: 'user',
      content: '📷 レシートを送信中...',
      timestamp: new Date().toISOString(),
    };
    const updated = [...chatHistory, userMsg];
    setChatHistory(updated);
    saveChatHistory(userId, updated);

    try {
      const base64 = await compressImage(file, 1280, 0.75);
      const resp = await api.uploadReceipt(base64, 'image/jpeg');
      const replyContent = resp.success
        ? resp.reply
        : 'ごめんね、レシートがうまく読み取れなかった……。もう一度撮ってみてくれる？♪';
      const assistantMsg: ChatMessage = {
        id: `asst-receipt-${Date.now()}`, role: 'assistant',
        content: replyContent,
        timestamp: new Date().toISOString(), emotion: resp.success ? 'happy' : 'shy',
      };
      // Update user message to show summary
      const finalUserMsg = { ...userMsg, content: `📷 レシート送信${resp.success ? `（${resp.items.length}品）` : ''}` };
      const withReply = [...chatHistory, finalUserMsg, assistantMsg];
      setChatHistory(withReply);
      saveChatHistory(userId, withReply);
    } catch {
      const errorMsg: ChatMessage = {
        id: `err-receipt-${Date.now()}`, role: 'assistant',
        content: 'あれれ、レシートの処理でエラーになっちゃった……もう一度試してみてね♪',
        timestamp: new Date().toISOString(), emotion: 'shy',
      };
      const withErr = [...updated, errorMsg];
      setChatHistory(withErr);
      saveChatHistory(userId, withErr);
    } finally {
      setIsUploadingReceipt(false);
    }
  };

  const handleQuickFill = (text: string) => {
    setTextInput(text);
  };

  // 音声入力（ブラウザSpeechRecognition直結）
  // 確定した認識テキストをそのまま通常のチャットAPIに流して、
  // Chat → LifeLog/Expense/Stress → Dashboard/Diary の縦串を確実に動かす。
  const speech = useSpeechInput({
    onFinal: (text) => {
      setInterimText('');
      void sendMessage(text);
    },
    onInterim: (text) => setInterimText(text),
  });
  const voiceStatus = speech.status;
  const voiceError = speech.error;

  const handleMicClick = () => {
    if (voiceStatus === 'listening') {
      speech.stop();
    } else {
      void speech.start();
    }
  };

  // ?voice=1 付きで開かれたら自動でマイク起動
  useEffect(() => {
    if (searchParams.get('voice') === '1' && voiceStatus === 'idle' && speech.isSupported) {
      void speech.start();
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const isVoiceActive = voiceStatus === 'listening';

  return (
    <div className="page-content" ref={scrollRef}>
      {/* Hero Card */}
      <section className="chat-hero">
        <div className="hero-character">
          <img src="/assets/furemaru-fullbody.png" alt="ふれまーるちゃん" />
        </div>
        <div className="speech-bubble">
          <strong>こんにちは！</strong>
          <span>ふれまーるちゃんだよ〜！</span>
          <span>今日も一緒に、お金のことをやさしく整えてこ？ 🍀</span>
        </div>
      </section>

      {/* Memory Panel - 「あなたのこと覚えてるよ」演出 */}
      <MemoryPanel userId={userId} />

      {/* Chat Thread */}
      {chatHistory.length > 0 && (
        <section className="chat-thread">
          {chatHistory.slice(-30).map((msg) => (
            <article key={msg.id} className={`message ${msg.role === 'user' ? 'user' : 'assistant'}`}>
              {msg.role === 'assistant' && (
                <img src={getEmotionAvatar(msg.emotion)} alt="" className="emotion-avatar" />
              )}
              {msg.role === 'assistant' ? (
                <div className="msg-wrap">
                  <small>ふれまーるちゃん</small>
                  <p>{msg.content}</p>
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
                          {msg.reco.type === 'product' && '🛍 楽天で見てみる'}
                          {msg.reco.type === 'video' && '▶ YouTubeで見る'}
                          {msg.reco.type === 'wishlist' && '💝 ほしいものリストから'}
                          {msg.reco.type === 'restaurant' && '🍴 お店をチェック'}
                        </small>
                        <b>{msg.reco.title}</b>
                        {msg.reco.price ? <em>¥{msg.reco.price.toLocaleString()}</em> : null}
                        {msg.reco.reason && <p className="reco-reason">{msg.reco.reason}</p>}
                      </div>
                    </a>
                  )}
                  {msg.suggestion && (
                    <Link to={msg.suggestion.to} className="chat-suggestion-link">{msg.suggestion.label}</Link>
                  )}
                </div>
              ) : (
                <p>{msg.content}</p>
              )}
              <time>{formatTime(msg.timestamp)}</time>
            </article>
          ))}
          {isSending && (
            <article className="message assistant">
              <img src={getEmotionAvatar('listening')} alt="" className="emotion-avatar" />
              <div className="msg-wrap">
                <div className="typing-indicator"><span></span><span></span><span></span></div>
              </div>
            </article>
          )}
        </section>
      )}

      {/* Quick Section - bottom */}
      {chatHistory.length <= 3 && (
        <section className="quick-section">
          <h2>🌿 話してみる？</h2>
          <div className="quick-grid">
            <button className="quick-card" onClick={() => handleQuickFill('今日はちょっと疲れた')}>
              <span>😮‍💨</span><strong>疲れた</strong>
            </button>
            <button className="quick-card" onClick={() => handleQuickFill('コーヒー買った 200円')}>
              <span>☕</span><strong>支出を記録</strong>
            </button>
            <button className="quick-card" onClick={() => handleQuickFill('甘いもの食べたい')}>
              <span>🍮</span><strong>ご褒美</strong>
            </button>
          </div>
        </section>
      )}

      {/* Error */}
      {voiceError && <div className="error-message">{voiceError}</div>}

      {/* Input Area - always visible at bottom */}
      <section className="input-area">
        {/* Voice indicator */}
        {isVoiceActive && (
          <div className="voice-active-bar">
            <span className="pulse-dot"></span>
            <span>
              {voiceStatus === 'listening' && (interimText ? `「${interimText}」` : '話してね…聞いてるよ♪')}
            </span>
            <div className="wave-bar">
              {Array.from({ length: 7 }).map((_, i) => (
                <i key={i} style={{ animationDelay: `${i * 0.08}s` }} />
              ))}
            </div>
          </div>
        )}

        {/* Main input row */}
        <div className="chat-input-row">
          <button
            className="input-action-btn receipt-btn"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploadingReceipt}
            title="レシート撮影"
          >
            📷
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            style={{ display: 'none' }}
            onChange={handleReceiptUpload}
          />
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendText(); } }}
            placeholder="話しかけてみてね♪"
            rows={1}
            disabled={isSending || isUploadingReceipt}
          />
          {textInput.trim() ? (
            <button className="input-action-btn send-btn" onClick={handleSendText} disabled={isSending}>
              ➤
            </button>
          ) : (
            <button
              className={`input-action-btn mic-btn${isVoiceActive ? ' active' : ''}`}
              onClick={handleMicClick}
              title={isVoiceActive ? '音声停止' : '音声入力'}
            >
              {isVoiceActive ? '⏹' : '🎙'}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
