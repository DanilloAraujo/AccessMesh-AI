/**
 * hooks/useGestureCamera.ts
 * -------------------------
 * React hook that encapsulates webcam access and gesture detection.
 * Provides start/stop controls, a video ref for preview, and fires
 * onGestureDetected whenever a sign is recognised above the confidence threshold.
 *
 * Frames are captured every 2.5 s and sent to the backend /gesture/frame
 * endpoint, which invokes Azure OpenAI GPT-4o Vision via the agent pipeline.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { sendFrame } from '../services/gestureService';


export type CameraState = 'idle' | 'active' | 'error';

export interface UseGestureCameraReturn {
    cameraState: CameraState;
    lastGesture: string | null;
    videoRef: React.RefObject<HTMLVideoElement | null>;
    startCamera: () => Promise<void>;
    stopCamera: () => void;
}

const FRAME_INTERVAL_MS = 2500;
const CONFIDENCE_THRESHOLD = 0.45;

export interface GestureCameraOptions {
    sessionId: string;
    userId: string;
    onGestureDetected?: (label: string) => void;
    disabled?: boolean;
}

export function useGestureCamera({
    sessionId,
    userId,
    onGestureDetected,
    disabled = false,
}: GestureCameraOptions): UseGestureCameraReturn {
    const [cameraState, setCameraState] = useState<CameraState>('idle');
    const [lastGesture, setLastGesture] = useState<string | null>(null);
    const videoRef = useRef<HTMLVideoElement | null>(null);
    const streamRef = useRef<MediaStream | null>(null);

    const stopCamera = useCallback(() => {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        if (videoRef.current) videoRef.current.srcObject = null;
        setCameraState('idle');
        setLastGesture(null);
    }, []);

    const startCamera = useCallback(async () => {
        if (cameraState !== 'idle' || disabled) return;
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            streamRef.current = stream;
            if (videoRef.current) videoRef.current.srcObject = stream;
            setCameraState('active');
        } catch (err) {
            console.error('[useGestureCamera] Camera access failed:', err);
            setCameraState('error');
            setTimeout(() => setCameraState('idle'), 3000);
        }
    }, [cameraState, disabled]);

    // Real gesture detection via Azure OpenAI Vision through /gesture/frame.
    useEffect(() => {
        if (cameraState !== 'active') return;

        let active = true;
        const canvas = document.createElement('canvas');

        const capture = async () => {
            const video = videoRef.current;
            if (!active || !video || video.readyState < 2) return;

            canvas.width = Math.min(video.videoWidth, 640);
            canvas.height = Math.round(canvas.width * (video.videoHeight / video.videoWidth));
            const ctx = canvas.getContext('2d');
            if (!ctx) return;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const frameB64 = canvas.toDataURL('image/jpeg', 0.7).split(',')[1];

            try {
                const result = await sendFrame(frameB64, sessionId, userId);
                if (active && result.confidence >= CONFIDENCE_THRESHOLD && result.gesture_label !== 'unknown') {
                    setLastGesture(result.gesture_label);
                    onGestureDetected?.(result.gesture_label);
                }
            } catch (err) {
                console.warn('[useGestureCamera] Frame detection failed:', err);
            }
        };

        const intervalId = setInterval(capture, FRAME_INTERVAL_MS);
        return () => {
            active = false;
            clearInterval(intervalId);
        };
    }, [cameraState, onGestureDetected, sessionId, userId]);

    // Cleanup on unmount
    useEffect(() => () => stopCamera(), [stopCamera]);

    return { cameraState, lastGesture, videoRef, startCamera, stopCamera };
}
