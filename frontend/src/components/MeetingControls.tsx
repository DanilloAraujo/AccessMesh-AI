import {
    Camera,
    CameraOff,
    Captions,
    CaptionsOff,
    Mic,
    MicOff,
    Monitor,
    MonitorOff,
    PhoneOff,
} from 'lucide-react';
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../hooks/useTranslation';

interface MeetingControlsProps {
    cameraOn?: boolean;
    micOn?: boolean;
    isListening?: boolean;
    onCameraToggle?: () => void;
    onMicToggle?: () => void;
    onLeave?: () => void;
    showCamera?: boolean;
    showMic?: boolean;
}

const MeetingControls: React.FC<MeetingControlsProps> = ({
    cameraOn: cameraOnProp,
    micOn: micOnProp,
    isListening = false,
    onCameraToggle,
    onMicToggle,
    onLeave,
    showCamera = true,
    showMic = true,
}) => {
    const [micOnLocal, setMicOnLocal] = useState(true);
    const [cameraOnLocal, setCameraOnLocal] = useState(true);
    const [screenOn, setScreenOn] = useState(false);
    const [captionsOn, setCaptionsOn] = useState(true);
    const navigate = useNavigate();
    const { t } = useTranslation();

    const micOn = micOnProp !== undefined ? micOnProp : micOnLocal;
    const cameraOn = cameraOnProp !== undefined ? cameraOnProp : cameraOnLocal;

    const handleMicToggle = () => { onMicToggle?.(); if (micOnProp === undefined) setMicOnLocal((v) => !v); };
    const handleCameraToggle = () => { onCameraToggle?.(); if (cameraOnProp === undefined) setCameraOnLocal((v) => !v); };

    const handleLeave = () => {
        if (onLeave) { onLeave(); } else { navigate('/'); }
    };

    const controlBtn = (
        active: boolean,
        onClick: () => void,
        ActiveIcon: React.ElementType,
        InactiveIcon: React.ElementType,
        title: string,
        danger = false,
        recording = false,
    ) => (
        <button
            type="button"
            onClick={onClick}
            title={title}
            aria-label={title}
            aria-pressed={!danger ? active : undefined}
            className={`p-3 rounded-full transition-colors duration-200 ${danger
                ? 'bg-red-500/80 hover:bg-red-500 text-white'
                : recording
                    ? 'bg-red-500/30 border border-red-500/50 text-red-400 animate-pulse'
                    : active
                        ? 'bg-white/10 hover:bg-white/20 text-white'
                        : 'bg-white/5 hover:bg-white/10 text-text-muted'
                }`}
        >
            {active ? <ActiveIcon size={20} /> : <InactiveIcon size={20} />}
        </button>
    );

    return (
        <div className="flex items-center gap-3 px-6 py-3 glass-card rounded-full">
            {showMic && controlBtn(micOn, handleMicToggle, Mic, MicOff, isListening ? t('controls.stopRecording') : micOn ? t('controls.mute') : t('controls.unmute'), false, isListening)}
            {showCamera && controlBtn(cameraOn, handleCameraToggle, Camera, CameraOff, cameraOn ? t('controls.stopCamera') : t('controls.startCamera'))}
            {controlBtn(
                screenOn,
                () => setScreenOn((v) => !v),
                Monitor,
                MonitorOff,
                screenOn ? t('controls.stopScreen') : t('controls.shareScreen'),
            )}
            {controlBtn(
                captionsOn,
                () => setCaptionsOn((v) => !v),
                Captions,
                CaptionsOff,
                captionsOn ? t('controls.hideCaptions') : t('controls.showCaptions'),
            )}

            <div className="w-px h-6 bg-white/10 mx-1" />

            <button
                type="button"
                onClick={handleLeave}
                title={t('controls.leaveMeeting')}
                aria-label={t('controls.leaveMeeting')}
                className="p-3 rounded-full bg-red-500/80 hover:bg-red-500 text-white transition-colors duration-200"
            >
                <PhoneOff size={20} />
            </button>
        </div>
    );
};

export default MeetingControls;
