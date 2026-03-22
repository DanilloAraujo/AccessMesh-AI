import { useCallback, useEffect, useMemo, useState } from 'react';
import {
    type ChatMessage,
    type ConnectionStatus,
    type PubSubMessage,
    WebSocketService,
} from '../services/websocketService';

export interface UseWebSocketReturn {
    status: ConnectionStatus;
    messages: ChatMessage[];
    userId: string;
    sessionId: string;
    sendMessage: (text: string) => ChatMessage | null;
    sendChatMessage: (text: string, targetLanguage?: string) => Promise<ChatMessage | null>;
    processSpeech: (text: string, language?: string, targetLanguage?: string) => Promise<ChatMessage | null>;
    sendGesture: (gestureLabel: string, targetLanguage?: string) => Promise<ChatMessage | null>;
    addMessage: (msg: ChatMessage) => void;
    replaceMessage: (id: string, msg: ChatMessage) => void;
    wsClient: WebSocketService;
}

export function useWebSocket(
    sessionId: string = 'default-room',
    userId?: string,
    displayName?: string
): UseWebSocketReturn {
    const ws = useMemo(() => new WebSocketService(), []);

    const [status, setStatus] = useState<ConnectionStatus>('disconnected');
    const [messages, setMessages] = useState<ChatMessage[]>([]);

    useEffect(() => {
        if (displayName) ws.displayName = displayName;
    }, [displayName, ws]);

    useEffect(() => {
        let shouldReconnect = false;
        if (userId && ws.userId !== userId) {
            ws.userId = userId;
            sessionStorage.setItem('accessmesh_user_id', userId);
            shouldReconnect = true;
        }
        if (sessionId && ws.sessionId !== sessionId) {
            ws.sessionId = sessionId;
            shouldReconnect = true;
        }
        if (shouldReconnect) {
            ws.disconnect();
            setTimeout(() => ws.connect(), 150);
        }
    }, [userId, sessionId, ws]);

    useEffect(() => {
        const unsubMsg = ws.onMessage((raw: PubSubMessage) => {
            const d = raw.data;
            if (raw.type === 'message' && d?.id && d?.from) {
                setMessages((prev) => {
                    if (prev.some((m) => m.id === d.id)) return prev;
                    return [...prev, d];
                });
            }
        });
        const unsubStatus = ws.onStatusChange(setStatus);

        ws.connect();

        return () => {
            unsubMsg();
            unsubStatus();
            ws.disconnect();
        };
    }, [ws]);

    const sendMessage = useCallback((text: string) => ws.sendMessage(text), [ws]);

    const sendChatMessage = useCallback(
        (text: string, targetLanguage = 'en-US') => ws.sendChatMessage(text, targetLanguage),
        [ws],
    );

    const processSpeech = useCallback(
        (text: string, language = 'en-US', targetLanguage = 'en-US') => ws.processSpeech(text, language, targetLanguage),
        [ws],
    );

    const sendGesture = useCallback(
        (gestureLabel: string, targetLanguage = 'en-US') =>
            ws.sendHubMessage('gesture', gestureLabel, 'web', targetLanguage, targetLanguage),
        [ws],
    );

    const addMessage = useCallback((msg: ChatMessage) => {
        setMessages((prev) => {
            if (prev.some((m) => m.id === msg.id)) return prev;
            return [...prev, msg];
        });
    }, []);

    const replaceMessage = useCallback((id: string, msg: ChatMessage) => {
        setMessages((prev) => prev.map((m) => (m.id === id ? msg : m)));
    }, []);

    return {
        status,
        messages,
        userId: ws.userId,
        sessionId: ws.sessionId,
        sendMessage,
        sendChatMessage,
        processSpeech,
        sendGesture,
        addMessage,
        replaceMessage,
        wsClient: ws,
    };
}
