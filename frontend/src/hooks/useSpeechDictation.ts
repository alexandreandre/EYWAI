import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Dictée vocale via l'API Web Speech du navigateur (zéro coût backend).
 * Renvoie le texte transcrit au fil de l'eau. Non supporté par tous les
 * navigateurs (Chrome/Edge OK, Firefox limité).
 */

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: { length: number; [index: number]: SpeechRecognitionResultLike };
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export interface UseSpeechDictationResult {
  isSupported: boolean;
  isListening: boolean;
  error: string | null;
  start: () => void;
  stop: () => void;
}

export function useSpeechDictation(
  onTranscript: (text: string) => void,
): UseSpeechDictationResult {
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  const ctor = getRecognitionCtor();
  const isSupported = ctor !== null;

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const start = useCallback(() => {
    if (!ctor) {
      setError("La dictée vocale n'est pas supportée par ce navigateur.");
      return;
    }
    setError(null);
    const recognition = new ctor();
    recognition.lang = 'fr-FR';
    recognition.continuous = true;
    recognition.interimResults = false;

    recognition.onresult = (event) => {
      let finalText = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        }
      }
      if (finalText.trim()) {
        onTranscriptRef.current(finalText.trim());
      }
    };
    recognition.onerror = (e) => {
      if (e.error !== 'aborted') {
        setError("La dictée vocale a échoué. Vérifiez l'accès au micro.");
      }
      setIsListening(false);
    };
    recognition.onend = () => setIsListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, [ctor]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  return { isSupported, isListening, error, start, stop };
}
