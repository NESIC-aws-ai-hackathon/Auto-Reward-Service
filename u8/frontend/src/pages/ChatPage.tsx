import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useVoiceChat } from '../hooks/useVoiceChat';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';
import './ChatPage.css';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  emotion?: string;
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

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { state, startSession, endSession } = useVoiceChat();
  const { status, transcripts, error, duration } = state;
  const api = useApi();
  const { user } = useAuth();
  const userId = user?.sub || 'anonymous';
  const [textInput, setTextInput] = useState('');
  const [showTextInput, setShowTextInput] = useState(false);
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevTranscriptLen = useRef(0);

  // Fetch proactive messages
  useEffect(() => {
    fetchNewMessages();
    const interval = setInterval(fetchNewMessages, 60000);
    return () => clearInterval(interval);
  }, []);

  // Auto-start voice when navigated with ?voice=1 (center button)
  useEffect(() => {
    if (searchParams.get('voice') === '1' && status === 'idle') {
      startSession();
      setSearchParams({}, { replace: true });
    }
  }, [searchParams]);

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

  // Sync voice transcripts
  useEffect(() => {
    if (transcripts.length > prevTranscriptLen.current) {
      const newMsgs = transcripts.slice(prevTranscriptLen.current).map((t, i) => ({
        id: `voice-${Date.now()}-${i}`,
        role: t.role as 'user' | 'assistant',
        content: t.content,
        timestamp: new Date().toISOString(),
        emotion: t.role === 'assistant' ? 'support' : undefined,
      }));
      const updated = [...chatHistory, ...newMsgs];
      setChatHistory(updated);
      saveChatHistory(userId, updated);
    }
    prevTranscriptLen.current = transcripts.length;
  }, [transcripts]);

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

  const formatDuration = (sec: number) => `${Math.floor(sec / 60)}:${(sec % 60).toString().padStart(2, '0')}`;

  const handleSendText = async () => {
    const text = textInput.trim();
    if (!text || isSending) return;
    setTextInput('');
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
      };
      const withReply = [...updated, assistantMsg];
      setChatHistory(withReply);
      saveChatHistory(userId, withReply);
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
  };

  const handleQuickFill = (text: string) => {
    setShowTextInput(true);
    setTextInput(text);
  };

  const handleMicClick = () => {
    if (status === 'idle') startSession();
    else if (status === 'connected' || status === 'speaking' || status === 'listening') endSession();
  };

  const isVoiceActive = status !== 'idle' && status !== 'ending';

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
      <section className="quick-section">
        <h2>🌿 話してみる？</h2>
        <div className="quick-grid">
          <button className="quick-card" onClick={() => handleQuickFill('今日はちょっと疲れた。回復費を考えたい')}>
            <span>👛</span><strong>回復費</strong><small>心がラクになる使い方を考えよう</small>
          </button>
          <button className="quick-card" onClick={() => handleQuickFill('今日の気分を記録したい')}>
            <span>💗</span><strong>今日の気分</strong><small>いまの気持ちを教えてね</small>
          </button>
          <button className="quick-card" onClick={() => handleQuickFill('今日あった出来事をライフログにしたい')}>
            <span>📒</span><strong>ライフログ</strong><small>習慣や出来事を記録しよう</small>
          </button>
        </div>
      </section>

      {/* Error */}
      {error && <div className="error-message">{error}</div>}

      {/* Voice Panel - bottom */}
      <section className={`voice-panel${isVoiceActive ? ' active' : ''}`}>
        <button className={`mic-button${isVoiceActive ? ' recording' : ''}`} onClick={handleMicClick}>
          <span>{isVoiceActive ? '⏹' : '🎙'}</span>
        </button>
        <div className="voice-status">
          {isVoiceActive ? (
            <>
              <p><span className="pulse-dot"></span>
                {status === 'listening' ? '話してるよ' : status === 'speaking' ? '聞いてるよ' : '接続中...'}
                {duration > 0 && <span style={{ marginLeft: 'auto', fontSize: 11, color: '#a69c8c' }}>{formatDuration(duration)}</span>}
              </p>
              <div className="wave-bar">
                {Array.from({ length: 11 }).map((_, i) => (
                  <i key={i} style={{ height: `${8 + Math.random() * 22}px`, animationDelay: `${i * 0.1}s` }} />
                ))}
              </div>
            </>
          ) : (
            <>
              <p>🎙 タップして話しかけてね</p>
              <label className="text-toggle">
                <span>文字で入力する</span>
                <input type="checkbox" checked={showTextInput} onChange={(e) => setShowTextInput(e.target.checked)} />
                <b></b>
              </label>
            </>
          )}
        </div>
      </section>

      {/* Text Input Panel */}
      {showTextInput && (
        <section className="text-input-panel">
          <div className="chat-input-row">
            <textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendText(); } }}
              placeholder="今日あったこと、買ったもの、気分などを入力してね"
              rows={2}
              disabled={isSending}
            />
            <button className="send-btn" onClick={handleSendText} disabled={!textInput.trim() || isSending}>
              ➤
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
