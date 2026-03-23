/**
 * hooks/useSpeechRecognition.ts
 * ------------------------------
 * Records audio via MediaRecorder and sends the blob to the backend
 * POST /speech/recognize, which handles transcription through the MCP
 * speech_to_text_tool and the full agent pipeline.
 *
 * Fallback: if MediaRecorder is unavailable (non-HTTPS env) the hook falls
 * back to the browser's native SpeechRecognition API so that text is still
 * captured and can be sent via the /speech/voice (text) endpoint.
 *
 * The Azure Cognitive Services SDK is NOT used in the frontend — all Azure
 * calls are centralised in the backend.
 */

import { useCallback, useRef, useState } from 'react';
import { recognizeAudio } from '../services/speechService';
import { type ChatMessage } from '../services/websocketService';

export type RecognitionState = 'idle' | 'listening' | 'error';

export interface UseSpeechRecognitionReturn {
    recognitionState: RecognitionState;
    transcript: string;
    startListening: () => void;
    stopListening: () => void;
    /** Register a callback invoked with the enriched ChatMessage after pipeline processing. */
    onTranscript: (cb: (msg: ChatMessage) => void) => void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const NativeSpeechRecognitionCtor: (new () => any) | undefined =
    (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;

export interface SpeechRecognitionOptions {
    sessionId: string;
    userId: string;
    processSpeech: (text: string, language?: string, targetLanguage?: string) => Promise<ChatMessage | null>;
}

export function useSpeechRecognition({
    sessionId,
    userId,
    processSpeech,
}: SpeechRecognitionOptions): UseSpeechRecognitionReturn {
    const [recognitionState, setRecognitionState] = useState<RecognitionState>('idle');
    const [transcript, setTranscript] = useState('');
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);
    const nativeRecRef = useRef<any>(null);
    const onTranscriptRef = useRef<((msg: ChatMessage) => void) | null>(null);
    const isListeningRef = useRef(false);
    const streamRef = useRef<MediaStream | null>(null);

    // Audio Chunking length (5 seconds per payload to the backend)
    const CHUNK_MS = 5000;

    const onTranscript = useCallback((cb: (msg: ChatMessage) => void) => {
        onTranscriptRef.current = cb;
    }, []);

    // ── Path A: MediaRecorder → POST /speech/recognize ───────────────────────

    const startWithMediaRecorder = useCallback(async () => {
        isListeningRef.current = true;
        let stream = streamRef.current;
        try {
            if (!stream) {
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                streamRef.current = stream;
            }
        } catch (err) {
            console.error('[useSpeechRecognition] Microphone access denied:', err);
            setRecognitionState('error');
            isListeningRef.current = false;
            setTimeout(() => setRecognitionState('idle'), 3000);
            return;
        }

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : 'audio/webm';

        let recorder: MediaRecorder;

        const recordCycle = () => {
            if (!isListeningRef.current || !stream) return;

            recorder = new MediaRecorder(stream, { mimeType });
            mediaRecorderRef.current = recorder;
            chunksRef.current = [];

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) chunksRef.current.push(e.data);
            };

            recorder.onstop = async () => {
                const blob = new Blob(chunksRef.current, { type: mimeType });
                chunksRef.current = [];

                // If still listening, immediately begin the next slice recording
                if (isListeningRef.current) recordCycle();

                if (blob.size === 0) return;

                const language = sessionStorage.getItem('language') ?? localStorage.getItem('preferredLanguage') ?? 'en-US';
                const targetLanguage = sessionStorage.getItem('targetLanguage') ?? localStorage.getItem('preferredLanguage') ?? 'en-US';
                console.log('[useSpeechRecognition] MediaRecorder slice ready — size=%d lang=%s target=%s', blob.size, language, targetLanguage);

                try {
                    const audioB64Result = await recognizeAudio(blob, sessionId, userId, language, targetLanguage);
                    const text = audioB64Result.text.trim();
                    if (text) {
                        setTranscript(text);
                        const msg = await processSpeech(text, language, targetLanguage);
                        if (msg) onTranscriptRef.current?.(msg);
                    }
                } catch (err) {
                    console.error('[useSpeechRecognition] Backend recognize failed:', err);
                }
            };

            recorder.start();

            // Stop this cycle after CHUNK_MS, triggering onstop -> sends data -> restarts
            setTimeout(() => {
                if (recorder.state === 'recording') recorder.stop();
            }, CHUNK_MS);
        };

        recordCycle();
        setRecognitionState('listening');
    }, [sessionId, userId, processSpeech]);

    // ── Path B: Native browser SpeechRecognition → POST /speech/voice ────────

    const startWithNative = useCallback(() => {
        if (!NativeSpeechRecognitionCtor) {
            console.error('[useSpeechRecognition] Neither MediaRecorder nor SpeechRecognition available.');
            setRecognitionState('error');
            setTimeout(() => setRecognitionState('idle'), 3000);
            return;
        }

        isListeningRef.current = true;
        const rec = new NativeSpeechRecognitionCtor();
        rec.lang = sessionStorage.getItem('language') ?? localStorage.getItem('preferredLanguage') ?? 'en-US';
        // continuous will send text slices mid-speech forever without cutting out
        rec.continuous = true;
        rec.interimResults = false;
        rec.maxAlternatives = 1;
        nativeRecRef.current = rec;

        rec.onstart = () => {
            console.log('[useSpeechRecognition] NativeSpeechRecognition started — lang=%s', rec.lang);
            setRecognitionState('listening');
        };

        rec.onresult = async (e: any) => {
            const index = e.resultIndex;
            const text: string = e.results[index]?.[0]?.transcript?.trim() ?? '';
            const confidence: number = e.results[index]?.[0]?.confidence ?? 0;
            console.log('[useSpeechRecognition] NativeSpeechRecognition slice result — text=%s confidence=%.2f', text || '(empty)', confidence);
            if (!text) return;

            const language = sessionStorage.getItem('language') ?? localStorage.getItem('preferredLanguage') ?? 'en-US';
            const targetLanguage = sessionStorage.getItem('targetLanguage') ?? localStorage.getItem('preferredLanguage') ?? 'en-US';
            console.log('[useSpeechRecognition] Calling processSpeech — text=%s lang=%s target=%s', text, language, targetLanguage);
            try {
                const msg = await processSpeech(text, language, targetLanguage);
                if (msg) {
                    console.log('[useSpeechRecognition] Pipeline response — id=%s features=%o', msg.id, msg.features_applied);
                    setTranscript(msg.content);
                    onTranscriptRef.current?.(msg);
                }
            } catch (err) {
                console.error('[useSpeechRecognition] processSpeech failed:', err);
            }
        };

        rec.onerror = (e: any) => {
            console.error('[useSpeechRecognition] NativeSpeechRecognition error:', e.error);
            nativeRecRef.current = null;
            setRecognitionState('error');
            setTimeout(() => setRecognitionState('idle'), 3000);
        };

        rec.onend = () => {
            // Only restart if the user still wants to listen AND this current instance (rec)
            // is still the actively managed one in the ref. This prevents old overlapping 
            // instances from hijacking and crashing new instances perfectly.
            if (isListeningRef.current && nativeRecRef.current === rec) {
                // Restart asynchronously to respect Chrome's microtask queue teardown
                setTimeout(() => {
                    if (isListeningRef.current && nativeRecRef.current === rec) {
                        try { rec.start(); } catch (e) { /* ignore overlapping start */ }
                    }
                }, 50);
            } else if (nativeRecRef.current === rec) {
                nativeRecRef.current = null;
                setRecognitionState('idle');
            }
        };

        try {
            rec.start();
        } catch (e) {
            console.error('[useSpeechRecognition] Failed to start native recognition:', e);
        }
    }, []);

    // ── Public API ────────────────────────────────────────────────────────────
    //
    // Priority:
    //   1. Native SpeechRecognition — browser-side transcription, no API keys needed
    //   2. MediaRecorder → POST /speech/recognize — fallback requiring Azure credentials

    const startListening = useCallback(() => {
        if (recognitionState !== 'idle') return;
        if (NativeSpeechRecognitionCtor) {
            console.log('[useSpeechRecognition] Using NativeSpeechRecognition path');
            startWithNative();
        } else if (typeof MediaRecorder !== 'undefined') {
            console.log('[useSpeechRecognition] Using MediaRecorder path (fallback)');
            void startWithMediaRecorder();
        } else {
            console.error('[useSpeechRecognition] No audio input method available.');
            setRecognitionState('error');
            setTimeout(() => setRecognitionState('idle'), 3000);
        }
    }, [startWithMediaRecorder, startWithNative]);

    const stopListening = useCallback(() => {
        isListeningRef.current = false;
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
            mediaRecorderRef.current.stop(); // triggers final slice upload
        } else if (nativeRecRef.current) {
            nativeRecRef.current.stop();
        }

        if (streamRef.current) {
            streamRef.current.getTracks().forEach(t => t.stop());
            streamRef.current = null;
        }
        setRecognitionState('idle');
    }, []);

    return { recognitionState, transcript, startListening, stopListening, onTranscript };
}
