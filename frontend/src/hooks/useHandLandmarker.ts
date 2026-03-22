/**
 * hooks/useHandLandmarker.ts
 * --------------------------
 * Loads the MediaPipe HandLandmarker (WASM float16) once per page and exposes
 * a stable `detect(video)` function for real-time hand landmark extraction.
 *
 * The WASM runtime (~5 MB) and model (~10 MB) are streamed from CDN at first
 * call. Nothing is bundled into the React app.
 */

import { FilesetResolver, HandLandmarker, type HandLandmarkerResult } from '@mediapipe/tasks-vision';
import { useEffect, useRef, useState } from 'react';

export type HandLandmarkerStatus = 'loading' | 'ready' | 'error';

export interface UseHandLandmarkerReturn {
    status: HandLandmarkerStatus;
    /** Run hand landmark detection on the given video element. Returns null if not ready. */
    detect: (video: HTMLVideoElement) => HandLandmarkerResult | null;
}

// Module-level singleton — one loaded instance shared across all component instances.
let _handLandmarker: HandLandmarker | null = null;
let _loadingPromise: Promise<HandLandmarker> | null = null;

const WASM_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm';
const MODEL_URL =
    'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

async function loadHandLandmarker(): Promise<HandLandmarker> {
    if (_handLandmarker) return _handLandmarker;
    if (_loadingPromise) return _loadingPromise;

    _loadingPromise = (async () => {
        const vision = await FilesetResolver.forVisionTasks(WASM_CDN);

        const options = {
            baseOptions: { modelAssetPath: MODEL_URL },
            runningMode: 'VIDEO' as const,
            numHands: 2,
            minHandDetectionConfidence: 0.5,
            minHandPresenceConfidence: 0.5,
            minTrackingConfidence: 0.5,
        };

        // Prefer GPU delegate; fall back to CPU if unavailable.
        try {
            _handLandmarker = await HandLandmarker.createFromOptions(vision, {
                ...options,
                baseOptions: { ...options.baseOptions, delegate: 'GPU' },
            });
        } catch {
            _handLandmarker = await HandLandmarker.createFromOptions(vision, {
                ...options,
                baseOptions: { ...options.baseOptions, delegate: 'CPU' },
            });
        }

        return _handLandmarker;
    })();

    return _loadingPromise;
}

export function useHandLandmarker(): UseHandLandmarkerReturn {
    const [status, setStatus] = useState<HandLandmarkerStatus>('loading');
    // Strictly-increasing timestamp guard required by MediaPipe VIDEO mode.
    const lastTimestampRef = useRef<number>(-1);

    useEffect(() => {
        let cancelled = false;
        loadHandLandmarker()
            .then(() => { if (!cancelled) setStatus('ready'); })
            .catch((err) => {
                console.error('[useHandLandmarker] Failed to load model:', err);
                if (!cancelled) setStatus('error');
            });
        return () => { cancelled = true; };
    }, []);

    const detect = (video: HTMLVideoElement): HandLandmarkerResult | null => {
        if (!_handLandmarker || status !== 'ready') return null;
        if (video.readyState < 2 || !video.videoWidth) return null;

        const now = performance.now();
        if (now <= lastTimestampRef.current) return null;
        lastTimestampRef.current = now;

        try {
            return _handLandmarker.detectForVideo(video, now);
        } catch {
            return null;
        }
    };

    return { status, detect };
}
