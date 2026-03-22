import { AnimatePresence, motion } from 'framer-motion';
import { PersonStanding, Video } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from '../hooks/useReducedMotion';
import { useTranslation } from '../hooks/useTranslation';


interface SignGlyph { gloss: string; duration_ms: number; }

export type AvatarProvider = 'video' | 'svg';

interface AvatarSignViewProps {
    glossSequence?: SignGlyph[];
    idleText?: string;
    provider?: AvatarProvider;
    videoClipsPath?: string;
}



// LIBRAS / ASL sign → SVG pose index (0–5).
// Each index maps to a distinct arm configuration in AvatarFigure:
//   0 = arms resting     1 = arms spread wide    2 = arms raised high
//   3 = right arm out    4 = left arm out         5 = hands diagonal
const GLOSS_TO_POSE: Record<string, number> = {
    // Greetings
    'OLÁ': 1, 'OLA': 1, 'HELLO': 1, 'HI': 1, 'WELCOME': 1, 'BEM-VINDO': 1,
    'TCHAU': 3, 'BYE': 3, 'GOODBYE': 3,
    // Affirmation
    'SIM': 3, 'YES': 3, 'CERTO': 3, 'OK': 3, 'OKAY': 3, 'CONFIRM': 3,
    'CORRETO': 3, 'VERDADE': 3, 'TRUE': 3,
    // Negation
    'NÃO': 2, 'NAO': 2, 'NO': 2, 'NUNCA': 2, 'NEGATIVE': 2, 'ERRADO': 2,
    // Positive sentiment
    'BOM': 4, 'GOOD': 4, 'ÓTIMO': 4, 'OTIMO': 4, 'EXCELLENT': 4, 'GREAT': 4,
    'OBRIGADO': 4, 'OBRIGADA': 4, 'THANK': 4, 'THANKS': 4, 'PLEASE': 4,
    'PARABÉNS': 4, 'CONGRATULATIONS': 4,
    // Questions
    'QUE': 2, 'WHAT': 2, 'ONDE': 2, 'WHERE': 2, 'QUANDO': 2, 'WHEN': 2,
    'COMO': 5, 'HOW': 5, 'POR QUE': 5, 'WHY': 5, 'QUEM': 5, 'WHO': 5,
    // Time
    'DIA': 5, 'DAY': 5, 'MORNING': 5, 'MANHÃ': 5, 'MANHÂ': 5,
    'HOJE': 5, 'TODAY': 5, 'NOW': 5, 'AGORA': 5,
    'NIGHT': 0, 'NOITE': 0, 'TARDE': 0, 'AFTERNOON': 0, 'EVENING': 0,
    // People
    'EU': 3, 'ME': 3, 'I': 3, 'MY': 3, 'MEU': 3, 'MINHA': 3,
    'VOCÊ': 4, 'VOCE': 4, 'YOU': 4, 'YOUR': 4, 'SEU': 4, 'SUA': 4,
    'NÓS': 2, 'NOS': 2, 'WE': 2, 'US': 2, 'OUR': 2,
    'ELE': 5, 'ELA': 5, 'HE': 5, 'SHE': 5, 'THEY': 5,
    // Meeting
    'MEETING': 1, 'REUNIÃO': 1, 'REUNIAO': 1,
    'START': 3, 'BEGIN': 3, 'INICIAR': 3, 'COMEÇAR': 3,
    'STOP': 0, 'END': 0, 'FIM': 0, 'PAUSE': 0, 'ENCERRAR': 0,
    'SPEAK': 4, 'FALAR': 4, 'TALK': 4,
    'LISTEN': 3, 'OUVIR': 3, 'HEAR': 3,
    'HELP': 2, 'AJUDA': 2, 'AJUDAR': 2,
    'UNDERSTAND': 5, 'ENTENDER': 5, 'ENTENDO': 5,
    'REPEAT': 2, 'REPETIR': 2, 'AGAIN': 2,
};

function glossToPose(gloss: string): number {
    const key = gloss.toUpperCase().trim();
    if (key in GLOSS_TO_POSE) return GLOSS_TO_POSE[key];
    // Deterministic fallback for unknown glosses — sum of char codes is stable (no bit-shift overflow)
    const sum = [...key].reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    return sum % 6;
}

function glossToColor(gloss: string): string {
    const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#06b6d4', '#10b981', '#f59e0b'];
    let h = 0;
    for (let i = 0; i < gloss.length; i++) h = (h * 31 + gloss.charCodeAt(i)) >>> 0;
    return colors[h % colors.length];
}


const AvatarFigure: React.FC<{ pose: number; color: string; isAnimating: boolean }> = ({
    pose, color, isAnimating,
}) => {
    const leftArmAngles = [30, 90, 150, 45, 120, 60];
    const rightArmAngles = [30, 90, 150, 120, 45, 150];
    const handOpen = [0.8, 1, 0.3, 0.6, 1, 0.4];
    const la = leftArmAngles[pose] ?? 30;
    const ra = rightArmAngles[pose] ?? 30;
    const ho = handOpen[pose] ?? 0.8;
    const toRad = (d: number) => (d * Math.PI) / 180;
    const armLen = 28; const fLen = 20;
    const lx = Math.sin(toRad(la)) * armLen;
    const ly = Math.cos(toRad(la)) * armLen;
    const rx = Math.sin(toRad(ra)) * armLen;
    const ry = Math.cos(toRad(ra)) * armLen;
    const lx2 = lx + Math.sin(toRad(la + 20)) * fLen;
    const ly2 = ly + Math.cos(toRad(la + 20)) * fLen;
    const rx2 = rx + Math.sin(toRad(ra + 20)) * fLen;
    const ry2 = ry + Math.cos(toRad(ra + 20)) * fLen;
    const hr = ho * 5 + 2;
    return (
        <svg viewBox="0 0 120 160" xmlns="http://www.w3.org/2000/svg" style={{ width: '100%', height: '100%' }} aria-hidden="true">
            {isAnimating && <circle cx="60" cy="80" r="55" fill={color} opacity="0.08" />}
            <line x1="60" y1="50" x2="60" y2="105" stroke={color} strokeWidth="5" strokeLinecap="round" />
            <circle cx="60" cy="35" r="18" fill="none" stroke={color} strokeWidth="4" />
            <circle cx="53" cy="32" r="2.5" fill={color} opacity="0.8" />
            <circle cx="67" cy="32" r="2.5" fill={color} opacity="0.8" />
            {isAnimating
                ? <path d="M 53 41 Q 60 47 67 41" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
                : <line x1="53" y1="42" x2="67" y2="42" stroke={color} strokeWidth="2" strokeLinecap="round" />}
            <line x1="60" y1="60" x2={60 - lx} y2={60 + ly} stroke={color} strokeWidth="4" strokeLinecap="round" />
            <line x1={60 - lx} y1={60 + ly} x2={60 - lx2} y2={60 + ly2} stroke={color} strokeWidth="3.5" strokeLinecap="round" />
            <circle cx={60 - lx2} cy={60 + ly2} r={hr} fill={color} opacity="0.9" />
            <line x1="60" y1="60" x2={60 + rx} y2={60 + ry} stroke={color} strokeWidth="4" strokeLinecap="round" />
            <line x1={60 + rx} y1={60 + ry} x2={60 + rx2} y2={60 + ry2} stroke={color} strokeWidth="3.5" strokeLinecap="round" />
            <circle cx={60 + rx2} cy={60 + ry2} r={hr} fill={color} opacity="0.9" />
            <line x1="60" y1="105" x2="45" y2="140" stroke={color} strokeWidth="4" strokeLinecap="round" />
            <line x1="60" y1="105" x2="75" y2="140" stroke={color} strokeWidth="4" strokeLinecap="round" />
        </svg>
    );
};


const SvgProvider: React.FC<{ glossSequence: SignGlyph[] }> = ({ glossSequence }) => {
    const prefersReduced = useReducedMotion();
    const [currentIndex, setCurrentIndex] = useState<number>(-1);
    const [isAnimating, setIsAnimating] = useState(false);
    const runIdRef = useRef(0);

    useEffect(() => {
        if (!glossSequence.length) { setCurrentIndex(-1); setIsAnimating(false); return; }
        const runId = ++runIdRef.current;
        let idx = 0;
        const playNext = () => {
            if (runId !== runIdRef.current) return;
            if (idx >= glossSequence.length) {
                setCurrentIndex(-1);
                setIsAnimating(false);
                return;
            }
            setCurrentIndex(idx);
            setIsAnimating(true);
            const dur = glossSequence[idx].duration_ms || 800;
            idx++;
            setTimeout(playNext, dur);
        };
        playNext();
        return () => { runIdRef.current++; };
    }, [glossSequence]);

    const currentGloss = currentIndex >= 0 ? glossSequence[currentIndex]?.gloss ?? null : null;
    const pose = currentGloss ? glossToPose(currentGloss) : 0;
    const color = currentGloss ? glossToColor(currentGloss) : '#6366f1';

    return (
        <div className="flex flex-col items-center gap-2 w-full">
            <div className="relative flex items-center justify-center rounded-2xl bg-gradient-to-br from-primary/10 to-accent/10 border border-white/10 overflow-hidden"
                style={{ width: '100%', aspectRatio: '1/1', maxWidth: 200 }}>
                <AnimatePresence mode="wait">
                    <motion.div key={currentGloss ?? 'idle'}
                        initial={prefersReduced ? {} : { opacity: 0, scale: 0.92 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={prefersReduced ? {} : { opacity: 0, scale: 1.05 }}
                        transition={prefersReduced ? { duration: 0 } : { duration: 0.25 }}
                        style={{ width: '75%', height: '75%' }}>
                        <AvatarFigure pose={pose} color={color} isAnimating={isAnimating} />
                    </motion.div>
                </AnimatePresence>
                <AnimatePresence mode="wait">
                    {currentGloss && (
                        <motion.div key={currentGloss + currentIndex}
                            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
                            className="absolute bottom-3 px-3 py-1 rounded-full text-white text-xs font-bold backdrop-blur-sm"
                            style={{ background: color + 'cc' }}>
                            {currentGloss}
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};

const VideoProvider: React.FC<{ glossSequence: SignGlyph[]; videoClipsPath: string }> = ({ glossSequence, videoClipsPath }) => {
    const [clipIndex, setClipIndex] = useState(0);
    const [svgFallbackIndices, setSvgFallbackIndices] = useState<Set<number>>(new Set());

    useEffect(() => {
        setClipIndex(0);
        setSvgFallbackIndices(new Set());
    }, [glossSequence]);

    const advance = () => setClipIndex((i) => i + 1);

    if (!glossSequence.length || clipIndex >= glossSequence.length) {
        return (
            <div className="flex flex-col items-center gap-2 p-3">
                <p className="text-xs text-text-muted text-center">No ASL clips loaded</p>
                <p className="text-[10px] text-text-muted text-center">Add .webm files to {videoClipsPath}</p>
            </div>
        );
    }

    const currentGloss = glossSequence[clipIndex].gloss.toLowerCase();
    const src = `${videoClipsPath}${currentGloss}.webm`;
    const isFallback = svgFallbackIndices.has(clipIndex);
    const color = glossToColor(glossSequence[clipIndex].gloss);

    const handleError = () => {
        setSvgFallbackIndices((prev) => new Set([...prev, clipIndex]));
        // Advance after fallback duration
        setTimeout(advance, glossSequence[clipIndex].duration_ms);
    };

    return (
        <div className="flex flex-col items-center gap-2 w-full">
            <div className="relative rounded-xl overflow-hidden bg-black/40 border border-white/10" style={{ width: '100%', aspectRatio: '4/3' }}>
                {isFallback ? (
                    <div className="w-full h-full flex items-center justify-center" style={{ background: color + '22' }}>
                        <AvatarFigure pose={glossToPose(glossSequence[clipIndex].gloss)} color={color} isAnimating />
                    </div>
                ) : (
                    <video
                        key={`${clipIndex}-${currentGloss}`}
                        src={src}
                        autoPlay
                        muted
                        playsInline
                        onEnded={advance}
                        onError={handleError}
                        className="w-full h-full object-contain"
                    />
                )}
                <div className="absolute bottom-2 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-full bg-black/60 text-white text-[10px] backdrop-blur-sm">
                    {glossSequence[clipIndex].gloss}
                    <span className="ml-1 text-text-muted">{clipIndex + 1}/{glossSequence.length}</span>
                </div>
            </div>
        </div>
    );
};


const GlossTimeline: React.FC<{ glossSequence: SignGlyph[] }> = ({ glossSequence }) => (
    glossSequence.length > 0 ? (
        <div className="flex flex-wrap gap-1 justify-center w-full">
            {glossSequence.map((g, i) => {
                const c = glossToColor(g.gloss);
                return (
                    <span key={`${g.gloss}_${i}`}
                        className="text-[10px] px-2 py-0.5 rounded-full font-semibold border"
                        style={{ borderColor: c + '60', background: c + '15', color: c }}>
                        {g.gloss}
                    </span>
                );
            })}
        </div>
    ) : null
);


const PROVIDER_LABELS: Record<AvatarProvider, string> = {
    video: 'ASL',
    svg: 'SVG',
};

const AvatarSignView: React.FC<AvatarSignViewProps> = ({
    glossSequence = [],
    idleText,
    provider = 'svg',
    videoClipsPath = '/signs/asl/',
}) => {
    const { t } = useTranslation();
    const resolvedIdleText = idleText ?? t('avatar.idle');
    const [currentProvider, setCurrentProvider] = useState<AvatarProvider>(provider);

    useEffect(() => { setCurrentProvider(provider); }, [provider]);

    return (
        <div className="glass-card flex flex-col items-center gap-3 p-4 w-full select-none">
            <div className="flex items-center justify-between w-full">
                <span className="flex items-center gap-2 text-sm font-semibold">
                    <PersonStanding size={16} className="text-primary" />
                    {t('avatar.title')}
                </span>

                <div className="flex items-center gap-1">
                    {(['svg', 'video'] as AvatarProvider[]).map((p) => (
                        <button
                            key={p}
                            type="button"
                            onClick={() => setCurrentProvider(p)}
                            title={p === 'video' ? t('avatar.provider.videoTitle') : t('avatar.provider.svgTitle')}
                            className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border transition-colors ${currentProvider === p
                                ? 'bg-primary/20 border-primary/40 text-primary'
                                : 'bg-white/5 border-white/10 text-text-muted hover:bg-white/10'
                                }`}
                        >
                            {p === 'video' && <Video size={10} />}
                            {p === 'svg' && <PersonStanding size={10} />}
                            {PROVIDER_LABELS[p]}
                        </button>
                    ))}
                </div>
            </div>

            {currentProvider === 'video' && (
                <VideoProvider glossSequence={glossSequence} videoClipsPath={videoClipsPath} />
            )}
            {currentProvider === 'svg' && (
                <SvgProvider glossSequence={glossSequence} />
            )}

            <GlossTimeline glossSequence={glossSequence} />

            <p className="text-xs text-text-muted text-center">
                {glossSequence.length > 0
                    ? `${t('avatar.signing')}${glossSequence.map((g) => g.gloss).join(' ')}`
                    : resolvedIdleText}
            </p>
        </div>
    );
};

export default AvatarSignView;
