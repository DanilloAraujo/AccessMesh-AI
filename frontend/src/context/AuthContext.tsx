/**
 * frontend/src/context/AuthContext.tsx
 * ──────────────────────────────────────
 * Provides identity, JWT, and user preferences to the whole app.
 *
 * ProtectedRoute pattern
 * ──────────────────────
 * Wrap any route element with <ProtectedRoute> to redirect unauthenticated
 * users to /login automatically.
 *
 * Omnichannel note
 * ────────────────
 * The JWT stored here is a standard Bearer token recognised by all
 * AccessMesh-AI backend endpoints. Channel adapters (Teams bot, mobile app)
 * use the same token format — they just obtain it via /auth/login on their
 * respective platforms.
 */

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
    type ReactNode,
} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { notifyLanguageChange, translate } from '../hooks/useTranslation';
import {
    login as apiLogin,
    register as apiRegister,
    getMe,
    updatePreferences,
    type CommunicationMode,
    type PreferencesPayload,
    type UserProfile,
} from '../services/authService';

// ── Types ────────────────────────────────────────────────────────────────────

export interface AuthContextValue {
    /** Authenticated user info, or null when not logged in. */
    user: UserProfile | null;
    /** True while the context is restoring a token from localStorage. */
    loading: boolean;
    isAuthenticated: boolean;

    // Actions
    login: (email: string, password: string) => Promise<void>;
    register: (
        displayName: string,
        email: string,
        password: string,
        mode?: CommunicationMode,
        lang?: string,
    ) => Promise<void>;
    logout: () => void;
    updateMode: (mode: CommunicationMode) => Promise<void>;
    updateLanguage: (lang: string) => Promise<void>;
    updateAccessibility: (prefs: PreferencesPayload) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = 'accessmesh_token';

// ── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<UserProfile | null>(null);
    const [loading, setLoading] = useState(true);

    // Restore session from localStorage on mount
    useEffect(() => {
        const tok = localStorage.getItem(TOKEN_KEY);
        if (!tok) {
            setLoading(false);
            return;
        }
        getMe(tok)
            .then(({ user_id, claims }) => {
                setUser({
                    userId: user_id,
                    displayName: (claims.display_name as string) ?? user_id,
                    email: (claims.email as string) ?? undefined,
                    communicationMode:
                        ((claims.communication_mode as string) ?? 'text') as CommunicationMode,
                    preferredLanguage: (claims.preferred_language as string) ?? 'en-US',
                    token: tok,
                });
            })
            .catch(() => {
                // Token expired or invalid — clear and redirect to login
                localStorage.removeItem(TOKEN_KEY);
            })
            .finally(() => setLoading(false));
    }, []);

    const _persist = (profile: UserProfile) => {
        localStorage.setItem(TOKEN_KEY, profile.token);
        setUser(profile);
    };

    const login = useCallback(async (email: string, password: string) => {
        const profile = await apiLogin(email, password);
        _persist(profile);
    }, []);

    const register = useCallback(
        async (
            displayName: string,
            email: string,
            password: string,
            mode: CommunicationMode = 'text',
            lang = 'en-US',
        ) => {
            const profile = await apiRegister(displayName, email, password, mode, lang);
            _persist(profile);
        },
        [],
    );

    const logout = useCallback(() => {
        localStorage.removeItem(TOKEN_KEY);
        setUser(null);
    }, []);

    const updateMode = useCallback(
        async (mode: CommunicationMode) => {
            if (!user) return;
            await updatePreferences({ communication_mode: mode }, user.token);
            setUser((prev) => prev ? { ...prev, communicationMode: mode } : prev);
        },
        [user],
    );

    const updateLanguage = useCallback(
        async (lang: string) => {
            if (!user) return;
            await updatePreferences({ preferred_language: lang, target_language: lang }, user.token);
            setUser((prev) => prev ? { ...prev, preferredLanguage: lang } : prev);
            notifyLanguageChange();
        },
        [user],
    );

    const updateAccessibility = useCallback(
        async (prefs: PreferencesPayload) => {
            if (!user) return;
            await updatePreferences(prefs, user.token);
        },
        [user],
    );

    return (
        <AuthContext.Provider
            value={{
                user,
                loading,
                isAuthenticated: !!user,
                login,
                register,
                logout,
                updateMode,
                updateLanguage,
                updateAccessibility,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
    return ctx;
}

// ── ProtectedRoute ───────────────────────────────────────────────────────────

export function ProtectedRoute({ children }: { children: ReactNode }) {
    const { isAuthenticated, loading } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        if (!loading && !isAuthenticated) {
            navigate('/login', { replace: true, state: { from: location.pathname + location.search } });
        }
    }, [loading, isAuthenticated, navigate, location]);

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#0f172a] text-white">
                <span className="animate-pulse text-text-muted">{translate('auth.loading')}</span>
            </div>
        );
    }

    return isAuthenticated ? <>{children}</> : null;
}

export type { CommunicationMode };

