import { Brain, Camera, CameraOff, Hand, Loader } from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useMeeting } from '../context/MeetingContext';
import { useHandLandmarker } from '../hooks/useHandLandmarker';
import { translate, useTranslation } from '../hooks/useTranslation';
import type { GestureFrameResult } from '../services/gestureService';
import { sendFrame, sendLandmarks } from '../services/gestureService';
import { classifyGesture } from '../utils/gestureClassifier';

const DEBOUNCE_FRAMES = 3;
const DEBOUNCE_MS = 800;
const AI_FALLBACK_INTERVAL_MS = 4000;
const CONFIDENCE_THRESHOLD = 0.6;

interface GestureCameraProps {
    onGestureDetected?: (gestureLabel: string) => void;
    onGestureResult?: (result: GestureFrameResult) => void;
    disabled?: boolean;
    /** When true, start the camera automatically on mount. */
    autoStart?: boolean;
}

type CameraState = 'idle' | 'active' | 'error';

const GestureCamera: React.FC<GestureCameraProps> = ({
    onGestureDetected,
    onGestureResult,
    disabled = false,
    autoStart = false,
}) => {
    const { sessionId, userId } = useMeeting();
    const { status: modelStatus, detect } = useHandLandmarker();
    const { t } = useTranslation();
    const [state, setState] = useState<CameraState>('idle');
    const [lastGesture, setLastGesture] = useState<string | null>(null);
    const [confidence, setConfidence] = useState<number>(0);
    const [handCount, setHandCount] = useState(0);
    const [useAiFallback, setUseAiFallback] = useState(false);
    const [isAiAnalysing, setIsAiAnalysing] = useState(false);

    const videoRef = useRef<HTMLVideoElement>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const rafRef = useRef<number | null>(null);
    const handCountRef = useRef(0);
    const lastEmitTimeRef = useRef<number>(0);
    const lastEmitLabelRef = useRef<string>('');
    const consecutiveRef = useRef<number>(0);
    const lastLabelRef = useRef<string>('');
    const lastAiFallbackRef = useRef<number>(0);

    const onGestureDetectedRef = useRef(onGestureDetected);
    const onGestureResultRef = useRef(onGestureResult);
    useEffect(() => { onGestureDetectedRef.current = onGestureDetected; }, [onGestureDetected]);
    useEffect(() => { onGestureResultRef.current = onGestureResult; }, [onGestureResult]);

    // Auto-start camera when consent has been given (autoStart flag)
    useEffect(() => {
        if (autoStart) startCamera();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);  // intentionally once on mount

    const startCamera = useCallback(async () => {
        if (state !== 'idle' || disabled) return;
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            streamRef.current = stream;
            if (videoRef.current) videoRef.current.srcObject = stream;
            setState('active');
        } catch (err) {
            console.error('[GestureCamera] Camera access denied:', err);
            setState('error');
            setTimeout(() => setState('idle'), 3000);
        }
    }, [state, disabled]);

    const stopCamera = useCallback(() => {
        if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        if (videoRef.current) videoRef.current.srcObject = null;
        setState('idle');
        setLastGesture(null);
        setHandCount(0);
        handCountRef.current = 0;
    }, []);

    useEffect(() => {
        if (state !== 'active' || modelStatus !== 'ready') return;

        let active = true;

        const loop = () => {
            if (!active) return;
            rafRef.current = requestAnimationFrame(loop);

            const video = videoRef.current;
            if (!video || video.readyState < 2) return;

            const result = detect(video);
            const newCount = result?.landmarks.length ?? 0;

            if (newCount !== handCountRef.current) {
                handCountRef.current = newCount;
                setHandCount(newCount);
            }

            if (!result || newCount === 0) {
                consecutiveRef.current = 0;
                lastLabelRef.current = '';
                return;
            }

            const lm = result.landmarks[0];
            const handedness = result.handednesses[0]?.[0]?.categoryName as 'Left' | 'Right' ?? 'Right';
            const classified = classifyGesture(lm, handedness);

            if (classified.confidence < CONFIDENCE_THRESHOLD || classified.label === 'unknown') {
                if (useAiFallback) {
                    const now = Date.now();
                    if (now - lastAiFallbackRef.current > AI_FALLBACK_INTERVAL_MS) {
                        lastAiFallbackRef.current = now;
                        const landmarks21 = lm.map((p) => ({ x: p.x, y: p.y, z: p.z }));
                        sendLandmarks(landmarks21, sessionId, userId)
                            .then((res) => {
                                if (res.gloss_sequence?.length > 0) {
                                    onGestureResultRef.current?.(res as unknown as GestureFrameResult);
                                }
                            })
                            .catch(() => { });
                    }
                }
                consecutiveRef.current = 0;
                return;
            }

            if (classified.label === lastLabelRef.current) {
                consecutiveRef.current++;
            } else {
                consecutiveRef.current = 1;
                lastLabelRef.current = classified.label;
            }
            if (consecutiveRef.current < DEBOUNCE_FRAMES) return;

            const now = Date.now();
            if (classified.label === lastEmitLabelRef.current && now - lastEmitTimeRef.current < DEBOUNCE_MS) return;

            lastEmitTimeRef.current = now;
            lastEmitLabelRef.current = classified.label;
            consecutiveRef.current = 0;

            setLastGesture(classified.label);
            setConfidence(classified.confidence);
            onGestureDetectedRef.current?.(classified.label);
            onGestureResultRef.current?.({
                message_id: '',
                text: classified.text,
                gesture_label: classified.label,
                confidence: classified.confidence,
                source: 'gesture',
                features_applied: ['mediapipe'],
                gloss_sequence: [{ gloss: classified.label.replace(/_/g, ' ').toUpperCase(), duration_ms: 800 }],
            });
        };

        rafRef.current = requestAnimationFrame(loop);
        return () => {
            active = false;
            if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
        };
    }, [state, modelStatus, detect, useAiFallback, sessionId, userId]);

    useEffect(() => {
        if (state !== 'active' || !useAiFallback) return;

        const interval = setInterval(async () => {
            if (!videoRef.current || isAiAnalysing) return;
            const video = videoRef.current;
            if (!video.videoWidth) return;

            const canvas = document.createElement('canvas');
            canvas.width = Math.min(video.videoWidth, 320);
            canvas.height = Math.round(canvas.width * video.videoHeight / video.videoWidth);
            const ctx = canvas.getContext('2d');
            if (!ctx) return;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const frameB64 = canvas.toDataURL('image/jpeg', 0.6).split(',')[1];

            setIsAiAnalysing(true);
            try {
                const result = await sendFrame(frameB64, sessionId, userId);
                if (result.confidence >= 0.45 && result.text && result.gesture_label !== 'unknown') {
                    setLastGesture(result.gesture_label);
                    setConfidence(result.confidence);
                    onGestureDetectedRef.current?.(result.gesture_label);
                    onGestureResultRef.current?.(result);
                }
            } catch { /* ignore */ } finally {
                setIsAiAnalysing(false);
            }
        }, AI_FALLBACK_INTERVAL_MS);

        return () => clearInterval(interval);
    }, [state, useAiFallback, isAiAnalysing, sessionId, userId]);

    useEffect(() => () => stopCamera(), [stopCamera]);

    const isActive = state === 'active';
    const isError = state === 'error';

    return (
        <div className="glass-card flex flex-col gap-2 p-3 w-full">
            <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm font-semibold">
                    <Hand size={16} className="text-primary" />
                    Gesture Camera
                    {isActive && modelStatus === 'loading' && (
                        <span className="flex items-center gap-1 text-[10px] text-yellow-400">
                            <Loader size={10} className="animate-spin" /> Loading AI...
                        </span>
                    )}
                    {isActive && modelStatus === 'ready' && handCount > 0 && (
                        <span className="text-[10px] text-green-400 animate-pulse">
                            ● {handCount} hand{handCount > 1 ? 's' : ''}
                        </span>
                    )}
                    <span
                        className="flex items-center gap-0.5 text-[9px] text-green-400/80 font-normal"
                        title="Landmarks are processed locally in your browser via MediaPipe. Only gesture vectors (not video frames) are sent to the server."
                        aria-label="Processado localmente no navegador"
                    >
                        🔒 Processado localmente
                    </span>
                </span>
                <button
                    type="button"
                    onClick={isActive ? stopCamera : startCamera}
                    disabled={disabled || isError}
                    title={isActive ? t('gesture.stopCamera') : t('gesture.startCamera')}
                    className={`p-2 rounded-lg border transition-all duration-200 ${isActive
                        ? 'bg-red-500/30 border-red-500/60 text-red-400'
                        : isError
                            ? 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400'
                            : 'bg-white/10 border-white/10 text-text-muted hover:bg-white/20 hover:text-white'
                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                    {isActive ? <CameraOff size={16} /> : <Camera size={16} />}
                </button>
            </div>

            <div
                className={`relative rounded-xl overflow-hidden bg-black/40 border border-white/10 ${isActive ? 'block' : 'hidden'}`}
                style={{ aspectRatio: '4/3' }}
            >
                <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
                <span
                    aria-live="assertive"
                    aria-atomic="true"
                    className="sr-only"
                >
                    {lastGesture
                        ? `${t('gesture.detected')}${lastGesture.replace(/_/g, ' ')} — ${Math.round(confidence * 100)}%`
                        : ''}
                </span>

                {lastGesture && (
                    <div className="absolute bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-primary/80 text-white text-xs font-medium backdrop-blur-sm">
                        {lastGesture.replace(/_/g, ' ')}
                        {confidence > 0 && <span className="ml-1 opacity-70">({Math.round(confidence * 100)}%)</span>}
                    </div>
                )}

                {isActive && (
                    <div className={`absolute top-2 left-2 flex items-center gap-1 px-2 py-0.5 rounded-full bg-black/60 text-[10px] backdrop-blur-sm ${modelStatus === 'ready' ? 'text-green-400' : 'text-yellow-400'
                        }`}>
                        {modelStatus === 'ready'
                            ? <span>&#9679; Live</span>
                            : <><Loader size={8} className="animate-spin" /> {t('gesture.loading')}</>}
                    </div>
                )}

                {isAiAnalysing && (
                    <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 rounded-full bg-black/60 text-white text-[10px] backdrop-blur-sm">
                        <Loader size={8} className="animate-spin" /> AI
                    </div>
                )}
            </div>

            {isActive && (
                <label className="flex items-center gap-2 text-[11px] text-text-muted cursor-pointer select-none">
                    <input
                        type="checkbox"
                        checked={useAiFallback}
                        onChange={(e) => setUseAiFallback(e.target.checked)}
                        className="w-3 h-3 accent-primary"
                    />
                    <Brain size={11} />
                    {t('gesture.useAI')}
                </label>
            )}

            {!isActive && (
                <p className="text-xs text-text-muted text-center">
                    {isError ? t('gesture.accessDenied') : t('gesture.cameraOff')}
                </p>
            )}
        </div>
    );
};

class GestureCameraErrorBoundary extends React.Component<
    { children: React.ReactNode },
    { hasError: boolean; errorMessage: string }
> {
    constructor(props: { children: React.ReactNode }) {
        super(props);
        this.state = { hasError: false, errorMessage: '' };
    }

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, errorMessage: error.message };
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="glass-card flex flex-col items-center gap-2 p-4 w-full text-center">
                    <p className="text-sm text-yellow-400">{translate('gesture.unavailable')}</p>
                    <p className="text-[10px] text-text-muted">{this.state.errorMessage}</p>
                    <button
                        type="button"
                        className="text-xs text-primary underline"
                        onClick={() => this.setState({ hasError: false, errorMessage: '' })}
                    >
                        {translate('gesture.retry')}
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}

const GestureCameraWithBoundary: React.FC<GestureCameraProps> = (props) => (
    <GestureCameraErrorBoundary>
        <GestureCamera {...props} />
    </GestureCameraErrorBoundary>
);

export default GestureCameraWithBoundary;