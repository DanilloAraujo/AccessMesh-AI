import { Brain, Camera, Copy, FileText, Hand, Info, Languages, Maximize2, MessageSquare, Mic, MicOff, Minimize2, Send, Settings, Shield } from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import AvatarSignView from '../components/AvatarSignView';
import GestureCamera from '../components/GestureCamera';
import MeetingControls from '../components/MeetingControls';
import SummaryModal from '../components/SummaryModal';
import TranscriptPanel from '../components/TranscriptPanel';
import { useMeeting } from '../context/MeetingContext';
import { useTranslation } from '../hooks/useTranslation';
import type { GestureFrameResult } from '../services/gestureService';

const MeetingRoom: React.FC = () => {
  const {
    glossSequence, updateGloss, sessionId, userId, displayName,
    sendGesture, addMessage, replaceMessage, sendChatMessage,
    setMicEnabled, startListening, stopListening, recognitionState,
    targetLanguage, setTargetLanguage, communicationMode, connectionStatus,
  } = useMeeting();
  const { t } = useTranslation();

  const isText = communicationMode === 'text';
  const isSign = communicationMode === 'sign_language';
  const isVoice = communicationMode === 'voice';

  const [consentGiven, setConsentGiven] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopyLink = useCallback(() => {
    const url = `${window.location.origin}/meeting/${sessionId}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [sessionId]);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [inputText, setInputText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [cameraOn, setCameraOn] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const micOn = recognitionState === 'listening';
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const mainCardRef = useRef<HTMLDivElement>(null);

  // Text mode needs no media permissions — grant consent immediately
  useEffect(() => {
    if (isText) setConsentGiven(true);
  }, [isText]);

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCameraOn(true);
    } catch (err) {
      console.error('[MeetingRoom] Camera access denied:', err);
    }
  }, []);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraOn(false);
  }, []);

  const handleCameraToggle = useCallback(() => {
    if (cameraOn) stopCamera(); else startCamera();
  }, [cameraOn, startCamera, stopCamera]);

  const handleFullscreenToggle = useCallback(() => {
    const el = mainCardRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => { });
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => { });
    }
  }, []);

  useEffect(() => {
    const onFsChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  useEffect(() => {
    if (!consentGiven) return;
    // The user explicitly requested autonomy over the microphone.
    // The mic will no longer auto-start. Users must manually click "Start Recording" 
    // even after giving privacy consent.
  }, [consentGiven]);

  useEffect(() => {
    if (cameraOn && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [cameraOn]);

  const handleGestureDetected = (gestureLabel: string) => {
    // Update local avatar immediately
    updateGloss([{ gloss: gestureLabel.replace(/_/g, ' ').toUpperCase(), duration_ms: 1200 }]);
    // Optimistic local entry so the sender sees their own gesture in chat/transcript
    const tempId = `gesture_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    addMessage({
      id: tempId,
      type: 'message',
      from: displayName || userId,
      content: gestureLabel.replace(/_/g, ' '),
      timestamp: new Date().toISOString(),
      source: 'gesture',
    });
    // Route through pipeline → broadcasts text + gloss + TTS to all participants
    sendGesture(gestureLabel, targetLanguage)
      .then((msg) => { if (msg) replaceMessage(tempId, msg); })
      .catch(() => { });
  };

  const handleGestureResult = (result: GestureFrameResult) => {
    if (result.gloss_sequence?.length > 0) {
      updateGloss(result.gloss_sequence);
    }
  };

  const handleTextSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = inputText.trim();
    if (!text || isSending) return;
    setIsSending(true);
    setInputText('');
    const tempId = `temp_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    addMessage({ id: tempId, type: 'message', from: displayName || userId, content: text, timestamp: new Date().toISOString(), source: 'text' });
    try {
      const sentMsg = await sendChatMessage(text, targetLanguage);
      if (sentMsg) replaceMessage(tempId, sentMsg);
    } finally {
      setIsSending(false);
    }
  };

  
  const consentContent = isSign
    ? {
      title: t('consent.camera.title'),
      desc: t('consent.camera.desc'),
      items: [
        t('consent.camera.item1'),
        t('consent.camera.item2'),
      ],
      btnLabel: t('consent.camera.btn'),
      btnIcon: <Camera size={16} />,
      btnAriaLabel: t('consent.camera.btnAria'),
    }
    : {
      title: t('consent.mic.title'),
      desc: t('consent.mic.desc'),
      items: [
        t('consent.mic.item1'),
        t('consent.mic.item2'),
      ],
      btnLabel: t('consent.mic.btn'),
      btnIcon: <Mic size={16} />,
      btnAriaLabel: t('consent.mic.btnAria'),
    };

  return (
    <div className="flex flex-col h-screen p-4 gap-4 bg-[#0f172a] text-white overflow-hidden">
      
      {!consentGiven && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="consent-title"
          aria-describedby="consent-desc"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
        >
          <div className="glass-card max-w-md w-full p-8 flex flex-col gap-6 border border-primary/30">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-full bg-primary/20 border border-primary/30">
                <Shield size={28} className="text-primary" />
              </div>
              <h2 id="consent-title" className="text-xl font-bold">
                {consentContent.title}
              </h2>
            </div>

            <p id="consent-desc" className="text-sm text-text-muted leading-relaxed">
              {consentContent.desc}
            </p>
            <ul className="text-sm text-text-muted space-y-2 ml-4 list-disc">
              {consentContent.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <p className="text-xs text-text-muted border border-white/10 rounded-lg px-4 py-3 bg-white/5">
              {t('consent.privacy')}
            </p>
            <p className="text-xs text-yellow-400/80 border border-yellow-500/20 rounded-lg px-4 py-3 bg-yellow-500/5">
              <strong>{t('consent.aiWarning.prefix')}</strong>{t('consent.aiWarning.text')}
            </p>

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => setConsentGiven(true)}
                aria-label={consentContent.btnAriaLabel}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-primary hover:bg-primary/80 text-white font-semibold transition-colors"
              >
                {consentContent.btnIcon}
                {consentContent.btnLabel}
              </button>
              <button
                type="button"
                onClick={() => window.history.back()}
                aria-label={t('consent.declineAria')}
                className="px-4 py-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-text-muted text-sm transition-colors"
              >
                {t('consent.decline')}
              </button>
            </div>
          </div>
        </div>
      )}

      
      {consentGiven && (
        <div
          role="note"
          aria-label={t('aiBanner.ariaLabel')}
          className="w-full shrink-0 flex items-center gap-2 px-4 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/25 text-yellow-300 text-xs"
        >
          <Brain size={13} className="shrink-0" />
          <span>
            <strong>{t('aiBanner.title')}</strong> — {t('aiBanner.text')}
          </span>
          <a
            href="/docs/responsible-ai"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto flex items-center gap-1 underline hover:text-yellow-200 whitespace-nowrap"
            aria-label={t('aiBanner.learnMoreAria')}
          >
            <Info size={11} /> {t('aiBanner.learnMore')}
          </a>
        </div>
      )}

      
      <div className="flex-1 flex flex-col md:flex-row gap-4 min-h-0 overflow-hidden">
        
        <div className="flex-1 flex flex-col gap-4 min-w-0 min-h-0 overflow-hidden">
          {/* Main video/interaction card */}
          <div ref={mainCardRef} className="flex-1 glass-card relative flex items-center justify-center overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-accent/5" />

            {/* Sign-language mode: full-screen placeholder — camera is in the sidebar GestureCamera */}
            {isSign && (
              <div className="z-10 text-center">
                <div className="w-24 h-24 rounded-full bg-accent/20 flex items-center justify-center mx-auto mb-4 border border-accent/30">
                  <Hand size={40} className="text-accent" />
                </div>
                <h1 className="text-xl font-bold">{t('meeting.librasModeTitle')}</h1>
                <p className="text-text-muted text-sm">{t('meeting.librasModeDesc')}</p>
              </div>
            )}

            {/* Text mode placeholder */}
            {isText && (
              <div className="z-10 text-center">
                <div className="w-24 h-24 rounded-full bg-primary/20 flex items-center justify-center mx-auto mb-4 border border-primary/30">
                  <MessageSquare size={40} className="text-primary" />
                </div>
                <h1 className="text-xl font-bold">{t('meeting.textModeTitle')}</h1>
                <p className="text-text-muted text-sm">{t('meeting.textModeDesc')}</p>
              </div>
            )}

            {/* Voice mode: mic recording area */}
            {isVoice && (
              <div className="z-10 text-center flex flex-col items-center gap-6">
                {/* Big pulsing mic ring */}
                <div className={`w-32 h-32 rounded-full flex items-center justify-center border-2 transition-all duration-300 shadow-lg ${micOn
                  ? 'bg-red-500/20 border-red-400/70 animate-pulse shadow-red-500/20'
                  : 'bg-primary/10 border-primary/40'
                  }`}>
                  {micOn
                    ? <Mic size={52} className="text-red-400" />
                    : <MicOff size={52} className="text-primary/60" />}
                </div>

                {/* Status label */}
                <div>
                  <h1 className="text-2xl font-bold tracking-tight">
                    {micOn ? t('meeting.voiceActive') : t('meeting.voiceInactive')}
                  </h1>
                  <p className="text-text-muted text-sm mt-1">
                    {micOn
                      ? t('meeting.voiceActiveDesc')
                      : t('meeting.voiceInactiveDesc')}
                  </p>
                </div>

                {/* Inline start/stop button */}
                <button
                  type="button"
                  onClick={() => {
                    if (recognitionState === 'listening') {
                      stopListening();
                      setMicEnabled(false);
                    } else {
                      startListening();
                      setMicEnabled(true);
                    }
                  }}
                  aria-label={micOn ? t('meeting.voiceStopBtn') : t('meeting.voiceStartBtn')}
                  className={`flex items-center gap-2 px-6 py-3 rounded-full font-semibold text-sm transition-all duration-200 border ${micOn
                    ? 'bg-red-500/30 border-red-500/60 text-red-300 hover:bg-red-500/40'
                    : 'bg-primary/20 border-primary/40 text-primary hover:bg-primary/30'
                    }`}
                >
                  {micOn ? <MicOff size={16} /> : <Mic size={16} />}
                  {micOn ? t('meeting.voiceStopBtn') : t('meeting.voiceStartBtn')}
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={handleFullscreenToggle}
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              className="absolute top-4 right-4 z-20 p-1.5 rounded-lg bg-black/40 hover:bg-black/60 text-white/70 hover:text-white border border-white/10 transition-colors"
            >
              {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>

            <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20">
              <MeetingControls
                cameraOn={cameraOn}
                micOn={micOn}
                isListening={recognitionState === 'listening'}
                onCameraToggle={handleCameraToggle}
                onMicToggle={() => {
                  if (recognitionState === 'listening') {
                    stopListening();
                    setMicEnabled(false);
                  } else {
                    startListening();
                    setMicEnabled(true);
                  }
                }}
                showCamera={false}
                showMic={isVoice}
              />
            </div>
          </div>

          {/* Session info bar */}
          <div className="h-20 shrink-0 glass-card px-6 flex items-center justify-between">
            <div>
              <h3 className="font-semibold">Session: AccessMesh-AI</h3>
              <p className="text-xs text-text-muted flex items-center gap-1.5">
                ID: <span className="font-mono select-all">{sessionId}</span>
                <button
                  type="button"
                  onClick={handleCopyLink}
                  title={t('meeting.copyLink')}
                  aria-label={t('meeting.copyLink')}
                  className="p-0.5 rounded hover:text-white transition-colors"
                >
                  <Copy size={11} />
                </button>
                {copied && <span className="text-green-400 text-[10px]">{t('meeting.copied')}</span>}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-xs text-text-muted">
                <Languages size={14} className="text-primary/70" />
                <select
                  value={targetLanguage}
                  onChange={(e) => setTargetLanguage(e.target.value)}
                  aria-label="Speech recognition language"
                  title="Select the language you are speaking"
                  className="bg-white/5 border border-white/10 rounded-md px-2 py-1 text-xs text-white focus:outline-none focus:border-primary/50 cursor-pointer"
                >
                  <option value="pt-BR">Português (BR)</option>
                  <option value="en-US">English (US)</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => setSummaryOpen(true)}
                title={t('meeting.genSummaryLabel')}
                aria-label={t('meeting.genSummaryLabel')}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/20 hover:bg-primary/30 border border-primary/30 text-primary text-sm font-medium transition-colors"
              >
                <FileText size={16} />
                {t('meeting.genSummary')}
              </button>
              <button
                type="button"
                aria-label="Open meeting settings"
                className="p-2 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
              >
                <Settings size={20} className="text-text-muted" />
              </button>
            </div>
          </div>

          {/* Transcript: fixed bar at the bottom of the main column for all modes */}
          <div className="h-40 md:h-48 shrink-0">
            <TranscriptPanel />
          </div>

          {/* Text mode: minimal send form */}
          {isText && (
            <form onSubmit={handleTextSend} className="glass-card flex gap-2 p-4">
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={t('meeting.messagePlaceholder')}
                aria-label={t('meeting.messageLabel')}
                className="flex-1 bg-white/10 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-primary/50 transition-colors"
              />
              <button
                type="submit"
                disabled={isSending || connectionStatus !== 'connected'}
                aria-label={t('meeting.sendBtnLabel')}
                className="btn-primary p-2 disabled:opacity-50"
              >
                <Send size={18} />
              </button>
            </form>
          )}
        </div>

        
        {isSign && <div className="flex flex-row gap-4 shrink-0">
          <div className="flex flex-col w-72 shrink-0">
            <GestureCamera
              onGestureDetected={handleGestureDetected}
              onGestureResult={handleGestureResult}
              autoStart={consentGiven}
            />
          </div>
          <div className="flex flex-col w-72 shrink-0">
            <AvatarSignView glossSequence={glossSequence} idleText={t('avatar.idle')} />
          </div>
        </div>}
      </div>{/* end column content wrapper */}

      {/* Summary Modal — always accessible from all modes */}
      <SummaryModal open={summaryOpen} onClose={() => setSummaryOpen(false)} sessionId={sessionId} />
    </div>
  );
};

export default MeetingRoom;
