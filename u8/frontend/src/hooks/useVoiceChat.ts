import { useCallback, useEffect, useRef, useReducer } from 'react';
import { useAuth } from './useAuth';

export interface TranscriptTurn {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  turnIndex?: number;
}

type VoiceStatus = 'idle' | 'connecting' | 'connected' | 'speaking' | 'listening' | 'ending';

interface VoiceChatState {
  status: VoiceStatus;
  sessionId: string | null;
  transcripts: TranscriptTurn[];
  error: string | null;
  duration: number;
}

type VoiceChatAction =
  | { type: 'SET_STATUS'; status: VoiceStatus }
  | { type: 'SET_SESSION'; sessionId: string }
  | { type: 'ADD_TRANSCRIPT'; turn: TranscriptTurn }
  | { type: 'UPDATE_LAST_TRANSCRIPT'; content: string }
  | { type: 'SET_ERROR'; error: string | null }
  | { type: 'SET_DURATION'; duration: number }
  | { type: 'RESET' };

const initialState: VoiceChatState = {
  status: 'idle',
  sessionId: null,
  transcripts: [],
  error: null,
  duration: 0,
};

function reducer(state: VoiceChatState, action: VoiceChatAction): VoiceChatState {
  switch (action.type) {
    case 'SET_STATUS':
      return { ...state, status: action.status, error: null };
    case 'SET_SESSION':
      return { ...state, sessionId: action.sessionId };
    case 'ADD_TRANSCRIPT':
      return { ...state, transcripts: [...state.transcripts, action.turn] };
    case 'UPDATE_LAST_TRANSCRIPT': {
      const updated = [...state.transcripts];
      const last = updated[updated.length - 1];
      if (updated.length > 0 && last) {
        updated[updated.length - 1] = { ...last, content: action.content };
      }
      return { ...state, transcripts: updated };
    }
    case 'SET_ERROR':
      return { ...state, error: action.error };
    case 'SET_DURATION':
      return { ...state, duration: action.duration };
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

const MAX_SESSION_DURATION = 30 * 60; // 30 minutes
const WS_URL = import.meta.env.VITE_VOICE_WS_URL || '';

// SpeechRecognition type
interface SpeechRecognitionEvent {
  results: { [index: number]: { [index: number]: { transcript: string }; isFinal: boolean }; length: number };
  resultIndex: number;
}

export function useVoiceChat() {
  const { getAccessToken } = useAuth();
  const [state, dispatch] = useReducer(reducer, initialState);

  const wsRef = useRef<WebSocket | null>(null);
  const recognitionRef = useRef<unknown>(null);
  const durationTimerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const turnIndexRef = useRef<number>(0);
  const isListeningRef = useRef(false);

  const sendToWs = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const cleanup = useCallback(() => {
    if (durationTimerRef.current) {
      clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try { (recognitionRef.current as { stop: () => void }).stop(); } catch { /* */ }
      recognitionRef.current = null;
    }
    isListeningRef.current = false;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const startSpeechRecognition = useCallback(() => {
    // Use browser Speech Recognition API
    const SpeechRecognition = (window as unknown as Record<string, unknown>).SpeechRecognition ||
      (window as unknown as Record<string, unknown>).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      dispatch({ type: 'SET_ERROR', error: 'このブラウザは音声認識に対応していません。Chrome/Edgeをお使いください。' });
      return;
    }

    const recognition = new (SpeechRecognition as new () => {
      lang: string; continuous: boolean; interimResults: boolean;
      onresult: ((e: SpeechRecognitionEvent) => void) | null;
      onend: (() => void) | null;
      onerror: ((e: { error: string }) => void) | null;
      start: () => void; stop: () => void;
    })();
    recognition.lang = 'ja-JP';
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interimText = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]!;
        const transcript = result[0]!.transcript;
        if (result.isFinal) {
          // Final transcript - send to server
          if (transcript.trim()) {
            dispatch({ type: 'SET_STATUS', status: 'listening' });
            dispatch({
              type: 'ADD_TRANSCRIPT',
              turn: { role: 'user', content: transcript.trim(), timestamp: new Date().toISOString(), turnIndex: turnIndexRef.current++ },
            });
            sendToWs({ action: 'textMessage', text: transcript.trim() });
          }
        } else {
          interimText += transcript;
        }
      }
      if (interimText) {
        dispatch({ type: 'SET_STATUS', status: 'speaking' });
      }
    };

    recognition.onend = () => {
      // Auto-restart if still in session
      if (isListeningRef.current && wsRef.current?.readyState === WebSocket.OPEN) {
        try { recognition.start(); } catch { /* */ }
      }
    };

    recognition.onerror = (e: { error: string }) => {
      if (e.error === 'not-allowed') {
        dispatch({ type: 'SET_ERROR', error: 'マイクへのアクセスが許可されませんでした' });
      }
      // 'no-speech' and 'aborted' are recoverable - onend will restart
    };

    try {
      recognition.start();
      recognitionRef.current = recognition;
      isListeningRef.current = true;
      dispatch({ type: 'SET_STATUS', status: 'connected' });
    } catch {
      dispatch({ type: 'SET_ERROR', error: '音声認識の開始に失敗しました' });
    }
  }, [sendToWs]);

  const handleServerMessage = useCallback((data: Record<string, unknown>) => {
    const type = data.type as string;

    switch (type) {
      case 'sessionStarted':
        dispatch({ type: 'SET_SESSION', sessionId: data.session_id as string });
        dispatch({ type: 'SET_STATUS', status: 'connected' });
        startSpeechRecognition();
        // Start duration timer
        startTimeRef.current = Date.now();
        durationTimerRef.current = window.setInterval(() => {
          const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
          dispatch({ type: 'SET_DURATION', duration: elapsed });
          if (elapsed >= MAX_SESSION_DURATION) {
            endSession();
          }
        }, 1000);
        break;

      case 'transcript': {
        const role = data.role as 'user' | 'assistant';
        const content = data.content as string;
        if (role === 'assistant') {
          if (data.partial) {
            dispatch({ type: 'UPDATE_LAST_TRANSCRIPT', content });
          } else {
            dispatch({
              type: 'ADD_TRANSCRIPT',
              turn: { role, content, timestamp: new Date().toISOString(), turnIndex: turnIndexRef.current++ },
            });
          }
        }
        break;
      }

      case 'turnComplete':
        dispatch({ type: 'SET_STATUS', status: 'connected' });
        break;

      case 'expenseSaved':
        // Could show a toast notification
        break;

      case 'conversationEndRequested':
        endSession();
        break;

      case 'error':
        dispatch({ type: 'SET_ERROR', error: data.message as string });
        break;

      case 'conversationEnded':
        cleanup();
        dispatch({ type: 'RESET' });
        break;
    }
  }, [startSpeechRecognition, cleanup]);

  const startSession = useCallback(async () => {
    dispatch({ type: 'SET_STATUS', status: 'connecting' });
    turnIndexRef.current = 0;

    try {
      const token = await getAccessToken();
      const wsUrl = `${WS_URL}?token=${encodeURIComponent(token)}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ action: 'startSession' }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleServerMessage(data);
        } catch { /* ignore */ }
      };

      ws.onerror = () => {
        dispatch({ type: 'SET_ERROR', error: '接続に失敗しました' });
        dispatch({ type: 'SET_STATUS', status: 'idle' });
      };

      ws.onclose = () => {
        if (wsRef.current) {
          cleanup();
          dispatch({ type: 'RESET' });
        }
      };

    } catch (err) {
      dispatch({ type: 'SET_ERROR', error: err instanceof Error ? err.message : '接続に失敗しました' });
      dispatch({ type: 'SET_STATUS', status: 'idle' });
    }
  }, [getAccessToken, handleServerMessage, cleanup]);

  const endSession = useCallback(() => {
    dispatch({ type: 'SET_STATUS', status: 'ending' });
    isListeningRef.current = false;
    sendToWs({ action: 'endSession' });
    setTimeout(() => {
      cleanup();
      dispatch({ type: 'RESET' });
    }, 3000);
  }, [sendToWs, cleanup]);

  const sendTextMessage = useCallback((text: string) => {
    if (!text.trim()) return;
    sendToWs({ action: 'textMessage', text: text.trim() });
    dispatch({
      type: 'ADD_TRANSCRIPT',
      turn: { role: 'user', content: text.trim(), timestamp: new Date().toISOString(), turnIndex: turnIndexRef.current++ },
    });
  }, [sendToWs]);

  useEffect(() => {
    return () => { cleanup(); };
  }, [cleanup]);

  return { state, startSession, endSession, sendTextMessage };
}
