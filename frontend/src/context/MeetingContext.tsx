import {
    createContext,
    useContext,
    useEffect,
    useState,
    type ReactNode,
} from 'react';
import { useParams } from 'react-router-dom';
import { useSpeechRecognition, type RecognitionState } from '../hooks/useSpeechRecognition';
import { notifyLanguageChange } from '../hooks/useTranslation';
import { useWebSocket, type UseWebSocketReturn } from '../hooks/useWebSocket';
import { type ChatMessage, type ConnectionStatus, type WebSocketService } from '../services/websocketService';
import { useAuth, type CommunicationMode } from './AuthContext';

export interface MeetingContextValue {
    userId: string;
    sessionId: string;
    displayName: string;
    communicationMode: CommunicationMode;
    connectionStatus: ConnectionStatus;
    messages: ChatMessage[];
    sendChatMessage: UseWebSocketReturn['sendChatMessage'];
    processSpeech: UseWebSocketReturn['processSpeech'];
    sendGesture: UseWebSocketReturn['sendGesture'];
    addMessage: UseWebSocketReturn['addMessage'];
    replaceMessage: UseWebSocketReturn['replaceMessage'];
    targetLanguage: string;
    setTargetLanguage: (lang: string) => void;
    micEnabled: boolean;
    setMicEnabled: (enabled: boolean) => void;
    startListening: () => void;
    stopListening: () => void;
    recognitionState: RecognitionState;
    wsClient: WebSocketService;
}

const MeetingContext = createContext<MeetingContextValue | null>(null);

export function MeetingProvider({ children }: { children: ReactNode }) {
    const { user } = useAuth();
    const { roomId } = useParams<{ roomId?: string }>();
    const activeSessionId = roomId || 'default-room';

    const { status, messages, userId, sessionId, sendChatMessage, processSpeech, sendGesture, addMessage, replaceMessage, wsClient } =
        useWebSocket(activeSessionId, user?.userId, user?.displayName);

    const [targetLanguage, _setTargetLanguage] = useState<string>(
        () => user?.preferredLanguage ?? localStorage.getItem('preferredLanguage') ?? 'en-US',
    );
    const setTargetLanguage = (lang: string) => {
        localStorage.setItem('preferredLanguage', lang);
        sessionStorage.setItem('targetLanguage', lang);
        // Also sync 'language' key so useSpeechRecognition picks up the change
        // immediately on the next MediaRecorder chunk and when native recognition restarts.
        sessionStorage.setItem('language', lang);
        _setTargetLanguage(lang);
        notifyLanguageChange();
    };

    useEffect(() => {
        if (user?.preferredLanguage) {
            sessionStorage.setItem('language', user.preferredLanguage);
            sessionStorage.setItem('targetLanguage', user.preferredLanguage);
            _setTargetLanguage(user.preferredLanguage);
            notifyLanguageChange();
        }
    }, [user?.preferredLanguage]);

    const [micEnabled, setMicEnabled] = useState<boolean>(false);
    const { startListening, stopListening, recognitionState, onTranscript } = useSpeechRecognition({
        sessionId,
        userId: user?.userId ?? userId,
        targetLanguage,
        processSpeech,
    });

    useEffect(() => {
        onTranscript((msg) => {
            addMessage(msg);
        });
    }, [onTranscript, addMessage]);

    return (
        <MeetingContext.Provider
            value={{
                userId: user?.userId ?? userId,
                sessionId,
                displayName: user?.displayName ?? userId,
                communicationMode: user?.communicationMode ?? 'text',
                connectionStatus: status,
                messages,
                sendChatMessage,
                processSpeech,
                sendGesture,
                addMessage,
                replaceMessage,
                targetLanguage,
                setTargetLanguage,
                micEnabled,
                setMicEnabled,
                startListening,
                stopListening,
                recognitionState,
                wsClient,
            }}
        >
            {children}
        </MeetingContext.Provider>
    );
}

export function useMeeting(): MeetingContextValue {
    const ctx = useContext(MeetingContext);
    if (!ctx) {
        throw new Error('useMeeting must be used inside <MeetingProvider>');
    }
    return ctx;
}
