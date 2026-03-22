import { Mic, MicOff } from 'lucide-react';
import React, { useEffect } from 'react';
import { useMeeting } from '../context/MeetingContext';
import { useTranslation } from '../hooks/useTranslation';

interface MicrophoneInputProps {
    disabled?: boolean;
    language?: string;
    targetLanguage?: string;
}

const MicrophoneInput: React.FC<MicrophoneInputProps> = ({
    disabled = false,
    language = localStorage.getItem('preferredLanguage') ?? 'en-US',
    targetLanguage = localStorage.getItem('preferredLanguage') ?? 'en-US',
}) => {
    const { recognitionState, startListening, stopListening } = useMeeting();
    const { t } = useTranslation();

    useEffect(() => {
        sessionStorage.setItem('language', language);
    }, [language]);

    useEffect(() => {
        sessionStorage.setItem('targetLanguage', targetLanguage);
    }, [targetLanguage]);

    const handleClick = () => {
        if (disabled) return;
        if (recognitionState === 'listening') {
            stopListening();
        } else if (recognitionState === 'idle') {
            startListening();
        }
    };

    const isListening = recognitionState === 'listening';
    const isError = recognitionState === 'error';

    return (
        <button
            type="button"
            onClick={handleClick}
            disabled={disabled}
            title={
                isListening ? t('mic.stopRecording') :
                    isError ? t('mic.error') :
                        t('mic.startVoice')
            }
            className={`p-2 rounded-lg border transition-all duration-200 ${isListening
                ? 'bg-red-500/30 border-red-500/60 text-red-400 animate-pulse'
                : isError
                    ? 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400'
                    : 'bg-white/10 border-white/10 text-text-muted hover:bg-white/20 hover:text-white'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
            {isListening ? <MicOff size={18} /> : <Mic size={18} />}
        </button>
    );
};

export default MicrophoneInput;
