/**
 * pages/RegisterPage.tsx
 * ───────────────────────
 * New account registration form.
 * Lets the user choose their preferred communication mode right at sign-up.
 */

import { Eye, EyeOff, FileText, Hand, KeyRound, Mail, Mic, UserPlus } from 'lucide-react';
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth, type CommunicationMode } from '../context/AuthContext';
import { useTranslation } from '../hooks/useTranslation';

interface ModeCard {
    mode: CommunicationMode;
    icon: React.ReactNode;
    label: string;
    description: string;
}

const LANGUAGES = [
    { value: 'pt-BR', label: 'Português (BR)' },
    { value: 'en-US', label: 'English (US)' },
];

const RegisterPage: React.FC = () => {
    const { register } = useAuth();
    const navigate = useNavigate();
    const { t } = useTranslation();

    const MODE_CARDS: ModeCard[] = [
        { mode: 'text', icon: <FileText size={20} />, label: t('mode.text'), description: t('mode.text.description') },
        { mode: 'sign_language', icon: <Hand size={20} />, label: t('mode.libras'), description: t('mode.libras.description') },
        { mode: 'voice', icon: <Mic size={20} />, label: t('mode.voice'), description: t('mode.voice.description') },
    ];

    const [displayName, setDisplayName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPw, setShowPw] = useState(false);
    const [mode, setMode] = useState<CommunicationMode>('text');
    const [lang, setLang] = useState('en-US');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        if (password.length < 8) {
            setError(t('register.passwordTooShort'));
            return;
        }
        setLoading(true);
        try {
            await register(displayName.trim(), email.trim(), password, mode, lang);
            navigate('/', { replace: true });
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : t('register.errorFallback'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-[#0f172a] text-white px-4 py-8">
            <div className="glass-card w-full max-w-md p-8 flex flex-col gap-6 border border-white/10">
                {/* Header */}
                <div className="text-center">
                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-primary/20 border border-primary/30 mb-4">
                        <UserPlus size={22} className="text-primary" />
                    </div>
                    <h1 className="text-2xl font-bold">{t('register.title')}</h1>
                    <p className="text-sm text-text-muted mt-1">{t('register.subtitle')}</p>
                </div>

                <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
                    {/* Display name */}
                    <div className="flex flex-col gap-1">
                        <label htmlFor="name" className="text-xs text-text-muted">{t('register.nameLabel')}</label>
                        <input
                            id="name"
                            type="text"
                            autoComplete="name"
                            required
                            value={displayName}
                            onChange={(e) => setDisplayName(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-text-muted text-sm focus:outline-none focus:border-primary/60 transition-colors"
                            placeholder={t('register.namePlaceholderFull')}
                        />
                    </div>

                    {/* Email */}
                    <div className="flex flex-col gap-1">
                        <label htmlFor="email" className="text-xs text-text-muted flex items-center gap-1">
                            <Mail size={12} className="text-primary/70" /> {t('register.email')}
                        </label>
                        <input
                            id="email"
                            type="email"
                            autoComplete="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-text-muted text-sm focus:outline-none focus:border-primary/60 transition-colors"
                            placeholder={t('register.emailPlaceholder')}
                        />
                    </div>

                    {/* Password */}
                    <div className="flex flex-col gap-1">
                        <label htmlFor="password" className="text-xs text-text-muted flex items-center gap-1">
                            <KeyRound size={12} className="text-primary/70" /> {t('register.password')} <span className="text-text-muted/50">{t('register.passwordHint')}</span>
                        </label>
                        <div className="relative">
                            <input
                                id="password"
                                type={showPw ? 'text' : 'password'}
                                autoComplete="new-password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full pl-3 pr-10 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-text-muted text-sm focus:outline-none focus:border-primary/60 transition-colors"
                                placeholder="••••••••"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPw((v) => !v)}
                                aria-label={showPw ? t('login.hidePassword') : t('login.showPassword')}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-white transition-colors"
                            >
                                {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                            </button>
                        </div>
                    </div>

                    {/* Language */}
                    <div className="flex flex-col gap-2">
                        <span className="text-xs text-text-muted">{t('register.language')}</span>
                        <div className="flex gap-2">
                            {LANGUAGES.map(({ value, label }) => (
                                <button
                                    key={value}
                                    type="button"
                                    onClick={() => setLang(value)}
                                    className={`flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${lang === value
                                        ? 'bg-primary/30 border-primary/60 text-primary'
                                        : 'bg-white/5 border-white/10 text-text-muted hover:bg-white/10 hover:text-white'
                                        }`}
                                >
                                    {label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Communication mode */}
                    <div className="flex flex-col gap-2">
                        <span className="text-xs text-text-muted">
                            {t('register.modeQuestion')}{' '}
                            <span className="text-text-muted/50">{t('register.modeHint')}</span>
                        </span>
                        <div className="grid grid-cols-3 gap-2">
                            {MODE_CARDS.map(({ mode: m, icon, label, description }) => (
                                <button
                                    key={m}
                                    type="button"
                                    onClick={() => setMode(m)}
                                    aria-pressed={mode === m}
                                    className={`flex flex-col items-center gap-2 p-3 rounded-xl border text-center transition-all ${mode === m
                                        ? 'bg-primary/20 border-primary/60 text-primary'
                                        : 'bg-white/5 border-white/10 text-text-muted hover:bg-white/10 hover:text-white hover:border-white/20'
                                        }`}
                                >
                                    <div className={mode === m ? 'text-primary' : 'text-text-muted'}>
                                        {icon}
                                    </div>
                                    <span className="text-xs font-semibold">{label}</span>
                                    <span className="text-[10px] leading-tight opacity-70">{description}</span>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Error */}
                    {error && (
                        <p role="alert" className="text-sm text-red-400 rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2">
                            {error}
                        </p>
                    )}

                    {/* Submit */}
                    <button
                        type="submit"
                        disabled={loading}
                        className="flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-primary hover:bg-primary/80 text-white font-semibold text-sm transition-colors disabled:opacity-60"
                    >
                        {loading ? (
                            <span className="animate-pulse">{t('register.submitting')}</span>
                        ) : (
                            <>
                                <UserPlus size={15} /> {t('register.submitLabel')}
                            </>
                        )}
                    </button>
                </form>

                {/* Login link */}
                <p className="text-center text-xs text-text-muted">
                    {t('register.hasAccount')}{' '}
                    <Link to="/login" className="text-primary hover:underline">
                        {t('register.login')}
                    </Link>
                </p>
            </div>
        </div>
    );
};

export default RegisterPage;
