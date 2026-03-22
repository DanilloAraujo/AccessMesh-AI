import { AnimatePresence, motion } from 'framer-motion';
import { Captions } from 'lucide-react';
import React, { useEffect, useRef } from 'react';
import { useMeeting } from '../context/MeetingContext';
import { useTranslation } from '../hooks/useTranslation';
import type { ChatMessage } from '../services/websocketService';

interface TranscriptPanelProps {
    /** When provided, only messages with this source are shown. */
    sourceFilter?: ChatMessage['source'];
    /** Override the panel header title. */
    title?: string;
}

const TranscriptPanel: React.FC<TranscriptPanelProps> = ({ sourceFilter, title }) => {
    const { t } = useTranslation();
    const panelTitle = title ?? t('transcript.title');
    // Use the shared messages from context — already includes own sends + remote broadcasts.
    const { messages, userId, displayName } = useMeeting();
    const entries = messages.filter(
        (m) =>
            (m.source === 'voice' || m.source === 'gesture' || m.source === 'text') &&
            !!m.content?.trim() &&
            (sourceFilter ? m.source === sourceFilter : true),
    );
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [entries]);

    return (
        <div className="glass-card flex flex-col h-full overflow-hidden">
            <div className="p-3 border-b border-white/10 flex items-center gap-2 bg-white/5">
                <Captions size={16} className="text-primary" />
                <h3 className="text-sm font-semibold">{panelTitle}</h3>
                {entries.length > 0 && (
                    <span className="ml-auto text-[10px] text-text-muted">
                        {entries.length} {entries.length !== 1 ? t('transcript.lines') : t('transcript.line')}
                    </span>
                )}
            </div>

            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-3 scroll-thin space-y-2"
                aria-live="polite"
                aria-label={t('transcript.ariaLabel')}
                role="log"
            >
                <AnimatePresence initial={false}>
                    {entries.length === 0 && (
                        <p className="text-xs text-text-muted text-center mt-4">
                            {t('transcript.empty')}
                        </p>
                    )}
                    {entries.map((entry) => (
                        <motion.div
                            key={entry.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            className="flex gap-2 items-start text-sm"
                        >
                            <span
                                className={`shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full ${entry.source === 'voice' ? 'bg-primary' : entry.source === 'gesture' ? 'bg-accent' : 'bg-gray-400'
                                    }`}
                            />
                            <div className="flex-1 min-w-0">
                                <span className="text-[10px] text-text-muted mr-1">
                                    {(entry.from === displayName || entry.from === userId) ? t('transcript.you') : entry.from}
                                </span>
                                <span className="break-words">{entry.content}</span>
                                {entry.source === 'voice' && entry.confidence !== undefined && (
                                    <span
                                        className={`ml-1.5 inline-block text-[9px] px-1 py-0.5 rounded font-mono leading-none ${entry.confidence >= 0.9
                                            ? 'bg-green-500/20 text-green-400'
                                            : entry.confidence >= 0.7
                                                ? 'bg-yellow-500/20 text-yellow-400'
                                                : 'bg-red-500/20 text-red-400'
                                            }`}
                                        title={t('transcript.confidenceTitle').replace('{pct}', String(Math.round(entry.confidence * 100)))}
                                        aria-label={t('transcript.confidenceAria').replace('{pct}', String(Math.round(entry.confidence * 100)))}
                                    >
                                        {Math.round(entry.confidence * 100)}%
                                    </span>
                                )}
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>
            </div>
        </div>
    );
};

export default TranscriptPanel;
