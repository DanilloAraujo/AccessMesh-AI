import {
    createContext,
    useContext,
    useEffect,
    useState,
    type ReactNode,
} from 'react';
import { useSpeechRecognition, type RecognitionState } from '../hooks/useSpeechRecognition';
import { notifyLanguageChange } from '../hooks/useTranslation';
import { useWebSocket, type UseWebSocketReturn } from '../hooks/useWebSocket';
import { type ChatMessage, type ConnectionStatus, type WebSocketService } from '../services/websocketService';
import { useAuth, type CommunicationMode } from './AuthContext';
import { useParams } from 'react-router-dom';

export interface GlossItem {
    gloss: string;
    duration_ms: number;
}

export interface MeetingContextValue {
    userId: string;
    sessionId: string;
    displayName: string;
    communicationMode: CommunicationMode;
    connectionStatus: ConnectionStatus;
    messages: ChatMessage[];
    glossSequence: GlossItem[];
    sendMessage: UseWebSocketReturn['sendMessage'];
    sendChatMessage: UseWebSocketReturn['sendChatMessage'];
    processSpeech: UseWebSocketReturn['processSpeech'];
    sendGesture: UseWebSocketReturn['sendGesture'];
    addMessage: UseWebSocketReturn['addMessage'];
    replaceMessage: UseWebSocketReturn['replaceMessage'];
    updateGloss: (items: GlossItem[]) => void;
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

    const { status, messages, userId, sessionId, sendMessage, sendChatMessage, processSpeech, sendGesture, addMessage, replaceMessage, wsClient } =
        useWebSocket(activeSessionId, user?.userId, user?.displayName);

    const [glossSequence, setGlossSequence] = useState<GlossItem[]>([]);

    const [targetLanguage, _setTargetLanguage] = useState<string>(
        () => user?.preferredLanguage ?? localStorage.getItem('preferredLanguage') ?? 'en-US',
    );
    const setTargetLanguage = (lang: string) => {
        localStorage.setItem('preferredLanguage', lang);
        sessionStorage.setItem('targetLanguage', lang);
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
        processSpeech,
    });

    useEffect(() => {
        onTranscript((msg) => {
            addMessage(msg);
            const gloss = (msg as unknown as Record<string, unknown>).sign_gloss;
            if (Array.isArray(gloss) && gloss.length > 0) {
                setGlossSequence(gloss as GlossItem[]);
            }
        });
    }, [onTranscript, addMessage]);

    useEffect(() => {
        const unsub = wsClient.onMessage((msg) => {
            if (msg.type === 'message' && msg.data?.sign_gloss) {
                const raw = msg.data.sign_gloss as GlossItem[];
                const senderIsMe = msg.data.from === (user?.displayName ?? wsClient.displayName)
                    || msg.data.from === wsClient.userId;
                const myMode = user?.communicationMode ?? 'text';
                if (Array.isArray(raw) && raw.length > 0 && !senderIsMe && myMode === 'sign_language') {
                    setGlossSequence(raw);
                }
            }
        });
        return unsub;
    }, [user?.userId, user?.communicationMode, user?.displayName, wsClient]);

    return (
        <MeetingContext.Provider
            value={{
                userId: user?.userId ?? userId,
                sessionId,
                displayName: user?.displayName ?? userId,
                communicationMode: user?.communicationMode ?? 'text',
                connectionStatus: status,
                messages,
                glossSequence,
                sendMessage,
                sendChatMessage,
                processSpeech,
                sendGesture,
                addMessage,
                replaceMessage,
                updateGloss: setGlossSequence,
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
