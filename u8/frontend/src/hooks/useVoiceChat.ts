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
const SILENCE_THRESHOLD = 0.01;
const SILENCE_DURATION_MS = 1500; // 1.5s silence = end of utterance
const WS_URL = import.meta.env.VITE_VOICE_WS_URL || '';

export function useVoiceChat() {
  const { getAccessToken } = useAuth();
  const [state, dispatch] = useReducer(reducer, initialState);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const audioBufferRef = useRef<Int16Array[]>([]);
  const silenceStartRef = useRef<number>(0);
  const isSpeakingRef = useRef(false);
  const durationTimerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const turnIndexRef = useRef<number>(0);
  const audioPlayQueueRef = useRef<string[]>([]);
  const isPlayingRef = useRef(false);
  const audioContextPlayRef = useRef<AudioContext | null>(null);

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
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(t => t.stop());
      mediaStreamRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (audioContextPlayRef.current) {
      audioContextPlayRef.current.close();
      audioContextPlayRef.current = null;
    }
    audioBufferRef.current = [];
    audioPlayQueueRef.current = [];
    isPlayingRef.current = false;
  }, []);

  const playNextAudioChunk = useCallback(async () => {
    if (isPlayingRef.current) return;
    if (audioPlayQueueRef.current.length === 0) return;

    isPlayingRef.current = true;

    if (!audioContextPlayRef.current) {
      audioContextPlayRef.current = new AudioContext({ sampleRate: 24000 });
    }

    while (audioPlayQueueRef.current.length > 0) {
      const chunk = audioPlayQueueRef.current.shift()!;
      try {
        const binaryStr = atob(chunk);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i++) {
          bytes[i] = binaryStr.charCodeAt(i);
        }
        const int16 = new Int16Array(bytes.buffer);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
          float32[i] = int16[i]! / 32768.0;
        }
        const audioBuffer = audioContextPlayRef.current.createBuffer(1, float32.length, 24000);
        audioBuffer.getChannelData(0).set(float32);
        const source = audioContextPlayRef.current.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContextPlayRef.current.destination);
        await new Promise<void>((resolve) => {
          source.onended = () => resolve();
          source.start();
        });
      } catch { /* skip corrupted chunks */ }
    }

    isPlayingRef.current = false;
    dispatch({ type: 'SET_STATUS', status: 'connected' });
  }, []);

  const sendAudioBuffer = useCallback(() => {
    if (audioBufferRef.current.length === 0) return;

    const totalLength = audioBufferRef.current.reduce((sum, arr) => sum + arr.length, 0);
    const combined = new Int16Array(totalLength);
    let offset = 0;
    for (const chunk of audioBufferRef.current) {
      combined.set(chunk, offset);
      offset += chunk.length;
    }
    audioBufferRef.current = [];

    // Convert to base64
    const uint8 = new Uint8Array(combined.buffer);
    let binaryStr = '';
    for (let i = 0; i < uint8.length; i++) {
      binaryStr += String.fromCharCode(uint8[i]!);
    }
    const base64 = btoa(binaryStr);

    sendToWs({ action: 'audioChunk', audio: base64, is_final: true });
    dispatch({ type: 'SET_STATUS', status: 'listening' });
  }, [sendToWs]);

  const processAudioFrame = useCallback((float32Data: Float32Array) => {
    const int16Data = new Int16Array(float32Data.length);
    for (let i = 0; i < float32Data.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Data[i]!));
      int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    let sum = 0;
    for (let i = 0; i < float32Data.length; i++) {
      sum += float32Data[i]! * float32Data[i]!;
    }
    const rms = Math.sqrt(sum / float32Data.length);
    const now = Date.now();

    if (rms > SILENCE_THRESHOLD) {
      if (!isSpeakingRef.current) {
        isSpeakingRef.current = true;
        dispatch({ type: 'SET_STATUS', status: 'speaking' });
      }
      silenceStartRef.current = now;
      audioBufferRef.current.push(int16Data);
    } else {
      if (isSpeakingRef.current) {
        audioBufferRef.current.push(int16Data);
        if (now - silenceStartRef.current > SILENCE_DURATION_MS) {
          isSpeakingRef.current = false;
          sendAudioBuffer();
        }
      }
    }
  }, [sendAudioBuffer]);

  const startMicrophone = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      mediaStreamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        processAudioFrame(inputData);
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
    } catch {
      dispatch({ type: 'SET_ERROR', error: 'マイクへのアクセスが許可されませんでした' });
    }
  }, [processAudioFrame]);

  const handleServerMessage = useCallback((data: Record<string, unknown>) => {
    const type = data.type as string;

    switch (type) {
      case 'sessionStarted':
        dispatch({ type: 'SET_SESSION', sessionId: data.session_id as string });
        dispatch({ type: 'SET_STATUS', status: 'connected' });
        startMicrophone();
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

      case 'audioResponse':
        dispatch({ type: 'SET_STATUS', status: 'listening' });
        if (data.audio) {
          audioPlayQueueRef.current.push(data.audio as string);
          playNextAudioChunk();
        }
        break;

      case 'transcript': {
        const role = data.role as 'user' | 'assistant';
        const content = data.content as string;
        if (role === 'user') {
          dispatch({
            type: 'ADD_TRANSCRIPT',
            turn: { role, content, timestamp: new Date().toISOString(), turnIndex: turnIndexRef.current++ },
          });
        } else if (role === 'assistant') {
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
  }, [startMicrophone, playNextAudioChunk, cleanup]);

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
        // If unexpectedly closed while active
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
