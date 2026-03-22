import { AnimatePresence, motion } from 'framer-motion';
import { Hand, MessageSquare, Mic, Send, User } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useMeeting } from '../context/MeetingContext';
import { useTranslation } from '../hooks/useTranslation';
import type { ChatMessage } from '../services/websocketService';
import MicrophoneInput from './MicrophoneInput';

const ChatPanel: React.FC = () => {
  const { t } = useTranslation();
  const {
    messages, userId, displayName, communicationMode, sendChatMessage, connectionStatus: status,
    addMessage, replaceMessage, updateGloss, targetLanguage, micEnabled,
  } = useMeeting();
  const [inputText, setInputText] = useState<string>('');
  const [isSending, setIsSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    const last = messages.at(-1);
    const isMine = last?.from === displayName || last?.from === userId;
    if (last && !isMine && last.audio_b64 && communicationMode === 'voice') {
      const audio = new Audio(`data:audio/mpeg;base64,${last.audio_b64}`);
      audio.play().catch(() => { });
    }
  }, [messages, userId, displayName, communicationMode]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = inputText.trim();
    if (!text || isSending) return;

    setIsSending(true);
    setInputText('');

    const tempId = `temp_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    addMessage({ id: tempId, type: 'message', from: displayName || userId, content: text, timestamp: new Date().toISOString(), source: 'text' });

    try {
      const sentMsg = await sendChatMessage(text, targetLanguage);
      if (sentMsg) {
        replaceMessage(tempId, sentMsg);
        if (sentMsg.sign_gloss?.length) updateGloss(sentMsg.sign_gloss);
      }
    } finally {
      setIsSending(false);
    }
  };

  const sourceIcon = (msg: ChatMessage) => {
    if (msg.source === 'voice') return <Mic size={10} className="text-primary" />;
    if (msg.source === 'gesture') return <Hand size={10} className="text-accent" />;
    return <User size={10} />;
  };

  return (
    <div className="glass-card flex flex-col h-full w-80 md:w-96 overflow-hidden" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="p-3 border-b border-white/10 flex justify-between items-center bg-white/5 gap-2">
        <h2 className="flex items-center gap-2 font-semibold shrink-0">
          <MessageSquare size={18} className="text-primary" />
          {t('chat.title')}
        </h2>

        <div className="flex items-center gap-1 shrink-0 ml-auto">
          <span className="text-[10px] uppercase tracking-wider text-text-muted">{status}</span>
          <div className={`w-2 h-2 rounded-full ${status === 'connected' ? 'bg-green-500' : 'bg-red-500'} shadow-[0_0_8px_rgba(34,197,94,0.5)]`} />
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 scroll-thin"
        style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}
      >
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.12 } }}
              transition={{ duration: 0.2 }}
              className={`mb-4 flex flex-col ${(msg.from === displayName || msg.from === userId) ? 'items-end' : 'items-start'}`}
            >
              <div className="flex items-center gap-1 mb-1 text-[10px] text-text-muted">
                {sourceIcon(msg)}
                <span>{(msg.from === displayName || msg.from === userId) ? t('chat.you') : msg.from}</span>
                {msg.source && msg.source !== 'text' && (
                  <span className="ml-1 text-primary/60 text-[9px] uppercase tracking-wider">{msg.source}</span>
                )}
              </div>
              <div
                className={`px-3 py-2 rounded-2xl max-w-[85%] text-sm ${(msg.from === displayName || msg.from === userId)
                  ? 'bg-primary/20 border border-primary/30 text-primary-100'
                  : 'bg-white/10 border border-white/10'
                  }`}
              >
                {msg.content}
                {/* Audio player only for voice-mode users — others receive text/gloss */}
                {msg.audio_b64 && communicationMode === 'voice' && (
                  <div className="mt-1 pt-1 border-t border-white/10">
                    <span id={`audio-transcript-${msg.id}`} className="sr-only">
                      Audio version: {msg.content}
                    </span>
                    <audio
                      controls
                      src={`data:audio/mpeg;base64,${msg.audio_b64}`}
                      className="w-full"
                      style={{ height: '40px', minWidth: '200px' }}
                      aria-label="Audio version of this message"
                      aria-describedby={`audio-transcript-${msg.id}`}
                    />
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      <form onSubmit={handleSend} className="p-4 bg-white/5 border-t border-white/10 flex gap-2">
        <MicrophoneInput disabled={!micEnabled} language={targetLanguage} targetLanguage={targetLanguage} />
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={t('chat.placeholder')}
          className="flex-1 bg-white/10 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary/50 transition-colors"
          style={{ flex: 1, backgroundColor: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '0.5rem 0.75rem', color: 'white' }}
        />
        <button type="submit" disabled={isSending || status !== 'connected'} className="btn-primary p-2 disabled:opacity-50" aria-label={t('chat.send')}>
          <Send size={18} />
        </button>
      </form>
    </div >
  );
};

export default ChatPanel;
