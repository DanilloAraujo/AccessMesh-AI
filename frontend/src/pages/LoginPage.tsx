/**
 * pages/LoginPage.tsx
 * ────────────────────
 * Email + password login form.
 */

import { Eye, EyeOff, KeyRound, LogIn, Mail } from 'lucide-react';
import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../hooks/useTranslation';

const LoginPage: React.FC = () => {
    const { login } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const { t } = useTranslation();
    // If the user was redirected from a protected page, go back there after login.
    const from: string = (location.state as { from?: string } | null)?.from ?? '/';

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPw, setShowPw] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);
        try {
            await login(email.trim(), password);
            navigate(from, { replace: true });
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : t('login.errorFallback'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex flex-col items-center justify-center bg-[#0f172a] text-white px-4">
            <div className="glass-card w-full max-w-sm p-8 flex flex-col gap-6 border border-white/10">
                {/* Header */}
                <div className="text-center">
                    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-primary/20 border border-primary/30 mb-4">
                        <KeyRound size={22} className="text-primary" />
                    </div>
                    <h1 className="text-2xl font-bold">{t('login.submit')}</h1>
                    <p className="text-sm text-text-muted mt-1">{t('login.subtitle')}</p>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
                    {/* Email */}
                    <div className="flex flex-col gap-1">
                        <label htmlFor="email" className="text-xs text-text-muted flex items-center gap-1">
                            <Mail size={12} className="text-primary/70" /> {t('login.email')}
                        </label>
                        <input
                            id="email"
                            type="email"
                            autoComplete="email"
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-text-muted text-sm focus:outline-none focus:border-primary/60 focus:bg-white/8 transition-colors"
                            placeholder={t('login.emailPlaceholder')}
                        />
                    </div>

                    {/* Password */}
                    <div className="flex flex-col gap-1">
                        <label htmlFor="password" className="text-xs text-text-muted flex items-center gap-1">
                            <KeyRound size={12} className="text-primary/70" /> {t('login.password')}
                        </label>
                        <div className="relative">
                            <input
                                id="password"
                                type={showPw ? 'text' : 'password'}
                                autoComplete="current-password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full pl-3 pr-10 py-2 rounded-lg bg-white/5 border border-white/10 text-white placeholder-text-muted text-sm focus:outline-none focus:border-primary/60 focus:bg-white/8 transition-colors"
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
                            <span className="animate-pulse">{t('login.submitting')}</span>
                        ) : (
                            <>
                                <LogIn size={15} /> {t('login.submit')}
                            </>
                        )}
                    </button>
                </form>

                {/* Register link */}
                <p className="text-center text-xs text-text-muted">
                    {t('login.noAccount')}{' '}
                    <Link to="/register" className="text-primary hover:underline">
                        {t('login.register')}
                    </Link>
                </p>
            </div>
        </div>
    );
};

export default LoginPage;
