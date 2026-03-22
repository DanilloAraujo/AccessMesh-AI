/**
 * pages/Home.tsx
 * --------------
 * Lobby page — greets the logged-in user, lets them change communication mode
 * and language, then enter the meeting room.
 */

import { Accessibility, ArrowRight, FileText, Hand, Languages, LogOut, Mic } from 'lucide-react';
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, type CommunicationMode } from '../context/AuthContext';
import { useTranslation } from '../hooks/useTranslation';

/** Generate a short, URL-safe room code (8 hex chars). */
function generateRoomId(): string {
    return crypto.randomUUID().replace(/-/g, '').slice(0, 8);
}

const LANGUAGES = [
    { value: 'pt-BR', label: 'Português (BR)' },
    { value: 'en-US', label: 'English (US)' },
];

interface ModeCard {
    mode: CommunicationMode;
    icon: React.ReactNode;
    label: string;
    send: string;
    receive: string;
}

const Home: React.FC = () => {
    const navigate = useNavigate();
    const { user, logout, updateMode, updateLanguage } = useAuth();
    const { t } = useTranslation();

    const MODE_CARDS: ModeCard[] = [
        { mode: 'text', icon: <FileText size={22} />, label: t('mode.text'), send: t('mode.text.sendFull'), receive: t('mode.text.receiveFull') },
        { mode: 'sign_language', icon: <Hand size={22} />, label: t('mode.libras'), send: t('mode.libras.sendFull'), receive: t('mode.libras.receiveFull') },
        { mode: 'voice', icon: <Mic size={22} />, label: t('mode.voice'), send: t('mode.voice.sendFull'), receive: t('mode.voice.receiveFull') },
    ];

    const [selectedMode, setSelectedMode] = useState<CommunicationMode>(
        user?.communicationMode ?? 'text',
    );
    const [selectedLang, setSelectedLang] = useState<string>(
        user?.preferredLanguage ?? 'en-US',
    );
    const [savingMode, setSavingMode] = useState(false);
    const [joinCode, setJoinCode] = useState('');

    const handleCreateRoom = () => {
        navigate(`/meeting/${generateRoomId()}`);
    };

    const handleJoinRoom = (e: React.FormEvent) => {
        e.preventDefault();
        const code = joinCode.trim();
        if (code) navigate(`/meeting/${encodeURIComponent(code)}`);
    };

    const handleModeChange = async (m: CommunicationMode) => {
        setSelectedMode(m);
        setSavingMode(true);
        try {
            await updateMode(m);
        } finally {
            setSavingMode(false);
        }
    };

    const handleLangChange = async (value: string) => {
        setSelectedLang(value);
        await updateLanguage(value);
        // notifyLanguageChange is already called inside updateLanguage (AuthContext)
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center gap-8 bg-[#0f172a] text-white px-4">

            {/* Header */}
            <div className="text-center">
                <div className="flex items-center justify-center gap-3 mb-4">
                    <Accessibility size={40} className="text-primary" />
                    <h1 className="text-4xl font-bold tracking-tight">AccessMesh AI</h1>
                </div>
                {user && (
                    <p className="text-lg text-text-muted">
                        {t('home.greeting')}, <span className="text-white font-semibold">{user.displayName}</span>!
                    </p>
                )}
                <p className="text-text-muted text-sm max-w-md mx-auto mt-1">
                    {t('home.fullSubtitle')}
                </p>
            </div>

            {/* Language selector */}
            <div className="flex flex-col items-center gap-2">
                <label className="flex items-center gap-2 text-sm text-text-muted">
                    <Languages size={16} className="text-primary/70" />
                    {t('home.language')}
                </label>
                <div className="flex gap-2">
                    {LANGUAGES.map(({ value, label }) => (
                        <button
                            key={value}
                            type="button"
                            onClick={() => handleLangChange(value)}
                            className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${selectedLang === value
                                ? 'bg-primary/30 border-primary/60 text-primary'
                                : 'bg-white/5 border-white/10 text-text-muted hover:bg-white/10 hover:text-white'
                                }`}
                        >
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Communication mode cards */}
            <div className="flex flex-col items-center gap-3 w-full max-w-lg">
                <p className="text-sm text-text-muted">
                    {t('home.modeQuestion')}
                    {savingMode && <span className="ml-2 text-primary/70 animate-pulse">{t('home.savingMode')}</span>}
                </p>
                <div className="grid grid-cols-3 gap-3 w-full">
                    {MODE_CARDS.map(({ mode, icon, label, send, receive }) => (
                        <button
                            key={mode}
                            type="button"
                            onClick={() => handleModeChange(mode)}
                            aria-pressed={selectedMode === mode}
                            className={`flex flex-col items-center gap-3 p-4 rounded-2xl border text-center transition-all ${selectedMode === mode
                                ? 'bg-primary/20 border-primary/60 shadow-lg shadow-primary/10'
                                : 'bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20'
                                }`}
                        >
                            <div className={`p-2 rounded-full ${selectedMode === mode ? 'bg-primary/20 text-primary' : 'bg-white/10 text-text-muted'}`}>
                                {icon}
                            </div>
                            <span className={`text-sm font-semibold ${selectedMode === mode ? 'text-primary' : 'text-white'}`}>
                                {label}
                            </span>
                            <div className="flex flex-col gap-1 w-full">
                                <span className="text-[11px] text-text-muted leading-tight">
                                    <span className="text-white/50">{t('home.modeSend')}</span>{send}
                                </span>
                                <span className="text-[11px] text-text-muted leading-tight">
                                    <span className="text-white/50">{t('home.modeReceive')}</span>{receive}
                                </span>
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* CTA — create a new room or join an existing one */}
            <div className="flex flex-col items-center gap-3 w-full max-w-sm">
                <button
                    type="button"
                    onClick={handleCreateRoom}
                    className="w-full px-8 py-4 rounded-2xl bg-primary hover:bg-primary/90 text-white font-semibold text-lg transition-colors duration-200 shadow-lg shadow-primary/30"
                >
                    {t('home.newRoom')}
                </button>

                <div className="flex items-center gap-3 w-full">
                    <div className="flex-1 h-px bg-white/10" />
                    <span className="text-xs text-text-muted">{t('home.orJoin')}</span>
                    <div className="flex-1 h-px bg-white/10" />
                </div>

                <form onSubmit={handleJoinRoom} className="flex w-full gap-2">
                    <input
                        type="text"
                        value={joinCode}
                        onChange={(e) => setJoinCode(e.target.value)}
                        placeholder={t('home.roomCode')}
                        aria-label={t('home.roomCode')}
                        className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-text-muted focus:outline-none focus:border-primary/50 transition-colors"
                    />
                    <button
                        type="submit"
                        disabled={!joinCode.trim()}
                        aria-label={t('home.joinButton')}
                        className="px-4 py-3 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 text-white transition-colors disabled:opacity-40"
                    >
                        <ArrowRight size={18} />
                    </button>
                </form>
            </div>

            {/* Logout */}
            <button
                type="button"
                onClick={logout}
                className="flex items-center gap-2 text-xs text-text-muted hover:text-white transition-colors"
            >
                <LogOut size={13} /> {t('home.logout')}
            </button>
        </div>
    );
};

export default Home;
