import { AnimatePresence, motion } from 'framer-motion';
import { CheckCircle, FileText, Loader2, X } from 'lucide-react';
import React, { useCallback, useState } from 'react';
import { useTranslation } from '../hooks/useTranslation';
import { useMeeting } from '../context/MeetingContext';

interface SummaryResult {
    summary: string;
    key_points: string[];
    message_count: number;
    stub: boolean;
    session_id: string;
}

interface SummaryModalProps {
    open: boolean;
    onClose: () => void;
    sessionId: string;
}

const SummaryModal: React.FC<SummaryModalProps> = ({ open, onClose, sessionId }) => {
    const { t } = useTranslation();
    const { wsClient } = useMeeting();
    const [result, setResult] = useState<SummaryResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleGenerate = useCallback(async () => {
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const data = await wsClient.fetchSummary(sessionId);
            setResult(data as unknown as SummaryResult);
        } catch (e) {
            setError('Failed to generate summary. Please try again.');
        } finally {
            setLoading(false);
        }
    }, [sessionId, wsClient]);

    const handleClose = () => {
        setResult(null);
        setError(null);
        onClose();
    };

    return (
        <AnimatePresence>
            {open && (
                <motion.div
                    className="fixed inset-0 z-50 flex items-center justify-center"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                >
                    {/* Backdrop */}
                    <div
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                        onClick={handleClose}
                    />

                    {/* Panel */}
                    <motion.div
                        className="relative z-10 w-full max-w-lg mx-4 glass-card p-6 flex flex-col gap-4"
                        initial={{ scale: 0.9, y: 20 }}
                        animate={{ scale: 1, y: 0 }}
                        exit={{ scale: 0.9, y: 20 }}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between">
                            <h2 className="flex items-center gap-2 font-bold text-lg">
                                <FileText size={20} className="text-primary" />
                                {t('summary.genTitle')}
                            </h2>
                            <button
                                type="button"
                                onClick={handleClose}
                                className="p-1 rounded-lg hover:bg-white/10 transition-colors text-text-muted"
                                aria-label="Close"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* Body */}
                        {!result && !loading && !error && (
                            <div className="text-sm text-text-muted text-center py-4">
                                <p dangerouslySetInnerHTML={{ __html: t('summary.prompt') }} />
                            </div>
                        )}

                        {loading && (
                            <div className="flex flex-col items-center gap-3 py-6">
                                <Loader2 size={32} className="text-primary animate-spin" />
                                <p className="text-sm text-text-muted">{t('summary.analyzing')}</p>
                            </div>
                        )}

                        {error && (
                            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                                {error}
                            </div>
                        )}

                        {result && (
                            <div className="flex flex-col gap-3 overflow-y-auto max-h-[60vh] scroll-thin">
                                {result.stub && (
                                    <div className="text-[11px] text-yellow-400/80 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2">
                                        {t('summary.stub')}
                                    </div>
                                )}

                                <div>
                                    <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-1">{t('summary.section')}</h3>
                                    <p className="text-sm leading-relaxed">{result.summary}</p>
                                </div>

                                {result.key_points.length > 0 && (
                                    <div>
                                        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">{t('summary.keyPoints')}</h3>
                                        <ul className="flex flex-col gap-2">
                                            {result.key_points.map((pt, i) => (
                                                <li key={i} className="flex items-start gap-2 text-sm">
                                                    <CheckCircle size={14} className="text-primary shrink-0 mt-0.5" />
                                                    <span>{pt}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                <p className="text-[11px] text-text-muted mt-1">
                                    {t('summary.analyzed').replace('{count}', String(result.message_count)).replace('{id}', result.session_id)}
                                </p>
                            </div>
                        )}

                        {/* Footer */}
                        <div className="flex gap-2 pt-2 border-t border-white/10">
                            {!result && (
                                <button
                                    type="button"
                                    onClick={handleGenerate}
                                    disabled={loading}
                                    className="btn-primary flex-1 flex items-center justify-center gap-2 py-2 disabled:opacity-50"
                                >
                                    {loading ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
                                    {t('summary.generate')}
                                </button>
                            )}
                            {result && (
                                <button
                                    type="button"
                                    onClick={handleGenerate}
                                    disabled={loading}
                                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm transition-colors disabled:opacity-50"
                                >
                                    <Loader2 size={14} />
                                    {t('summary.regenerate')}
                                </button>
                            )}
                            <button
                                type="button"
                                onClick={handleClose}
                                className="flex-1 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm transition-colors"
                            >
                                {t('summary.close')}
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default SummaryModal;
