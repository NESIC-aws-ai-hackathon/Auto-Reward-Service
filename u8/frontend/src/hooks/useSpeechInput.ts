import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * 音声入力フック（AGENTS.md準拠：話すだけで記録される体験を確実にする）
 *
 * 設計:
 *  - ブラウザ標準SpeechRecognition のみ使用（Nova Sonic / WebSocket には依存しない）
 *  - continuous=true で「タップ→話す→確定したら自動送信→停止するまで聞き続ける」モデル
 *  - 確定テキスト(final)を onFinal で渡し、通常チャット送信パイプラインに流す
 *  - これで Chat → Transcript → LifeLog/Expense → Dashboard/Diary の縦串が音声からも動く
 */

type RecognitionStatus = 'idle' | 'listening' | 'error';

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((e: SpeechRecognitionResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onstart: (() => void) | null;
}

interface SpeechRecognitionResultEvent {
  results: ArrayLike<{
    0: { transcript: string };
    isFinal: boolean;
  }>;
  resultIndex: number;
}

function getRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as Record<string, unknown>;
  return ((w.SpeechRecognition as new () => SpeechRecognitionLike) ||
    (w.webkitSpeechRecognition as new () => SpeechRecognitionLike) ||
    null);
}

interface UseSpeechInputOptions {
  onFinal: (text: string) => void;
  onInterim?: (text: string) => void;
  lang?: string;
}

export function useSpeechInput({ onFinal, onInterim, lang = 'ja-JP' }: UseSpeechInputOptions) {
  const [status, setStatus] = useState<RecognitionStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [isSupported] = useState<boolean>(() => getRecognitionCtor() !== null);
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const onFinalRef = useRef(onFinal);
  const onInterimRef = useRef(onInterim);
  const shouldRestartRef = useRef(false);
  const userStopRef = useRef(false);

  useEffect(() => { onFinalRef.current = onFinal; }, [onFinal]);
  useEffect(() => { onInterimRef.current = onInterim; }, [onInterim]);

  const createRecognition = useCallback((): SpeechRecognitionLike | null => {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return null;
    const rec = new Ctor();
    rec.lang = lang;
    rec.continuous = true;
    rec.interimResults = true;

    rec.onstart = () => {
      setStatus('listening');
      setError(null);
    };

    rec.onresult = (e: SpeechRecognitionResultEvent) => {
      let interim = '';
      let final = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (!r) continue;
        const txt = r[0].transcript;
        if (r.isFinal) final += txt;
        else interim += txt;
      }
      if (onInterimRef.current) onInterimRef.current(interim);
      if (final.trim()) {
        onFinalRef.current(final.trim());
      }
    };

    rec.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        setError('マイクが許可されてないみたい…ブラウザのアドレスバー左の鍵マークから「マイク」を許可してね♪');
        setStatus('error');
        shouldRestartRef.current = false;
      } else if (e.error === 'no-speech' || e.error === 'audio-capture') {
        // 無音タイムアウトは onend → restart で復帰
      } else if (e.error === 'aborted') {
        // ユーザー停止 or 内部リセット
      } else if (e.error === 'network') {
        setError('ネットワークが届かないみたい…通信状況を確認してね');
      } else {
        setError(`音声入力エラー（${e.error}）…もう一回試してね`);
      }
    };

    rec.onend = () => {
      // ブラウザは数秒無音で自動停止するので、ユーザー停止でなければ再起動
      if (shouldRestartRef.current && !userStopRef.current) {
        try {
          rec.start();
        } catch { /* ignore */ }
      } else {
        setStatus('idle');
      }
    };

    return rec;
  }, [lang]);

  const stop = useCallback(() => {
    userStopRef.current = true;
    shouldRestartRef.current = false;
    const rec = recRef.current;
    if (rec) {
      try { rec.stop(); } catch { /* ignore */ }
    }
    setStatus('idle');
  }, []);

  const start = useCallback(async () => {
    setError(null);
    if (!getRecognitionCtor()) {
      setError('お使いのブラウザは音声入力に対応していないみたい…Chrome / Edge / iOS Safari で開いてみてね♪');
      setStatus('error');
      return;
    }

    try {
      if (navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(t => t.stop());
      }
    } catch {
      setError('マイクの使用が許可されてないみたい…ブラウザの設定で「マイク」を許可してね♪');
      setStatus('error');
      return;
    }

    if (recRef.current) {
      shouldRestartRef.current = false;
      try { recRef.current.abort(); } catch { /* ignore */ }
      recRef.current = null;
    }

    const rec = createRecognition();
    if (!rec) {
      setError('音声入力を準備できなかったよ…');
      setStatus('error');
      return;
    }

    userStopRef.current = false;
    shouldRestartRef.current = true;

    try {
      rec.start();
      recRef.current = rec;
    } catch {
      setError('音声入力を開始できなかったよ…もう一回タップしてみてね');
      setStatus('error');
      shouldRestartRef.current = false;
    }
  }, [createRecognition]);

  useEffect(() => {
    return () => {
      shouldRestartRef.current = false;
      userStopRef.current = true;
      const rec = recRef.current;
      if (rec) {
        try { rec.abort(); } catch { /* ignore */ }
      }
    };
  }, []);

  return { status, error, isSupported, start, stop };
}
