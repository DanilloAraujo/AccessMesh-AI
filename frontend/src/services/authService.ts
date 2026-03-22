/**
 * frontend/src/services/authService.ts
 * ─────────────────────────────────────
 * REST client for the AccessMesh-AI auth endpoints.
 *
 * Omnichannel note: this service talks to the same /auth/* endpoints used by
 * every channel (web, mobile, Teams adapter). Adding a new client channel
 * means pointing it at the same endpoints — no backend changes required.
 */

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export type CommunicationMode = 'text' | 'sign_language' | 'voice';

export interface UserProfile {
    userId: string;
    displayName: string;
    email?: string;
    communicationMode: CommunicationMode;
    preferredLanguage: string;
    token: string;
}

export interface PreferencesPayload {
    communication_mode?: CommunicationMode;
    preferred_language?: string;
    target_language?: string;
    sign_language?: boolean;
    subtitles?: boolean;
    audio_description?: boolean;
    high_contrast?: boolean;
    large_text?: boolean;
    translation_enabled?: boolean;
}

// ── API calls ────────────────────────────────────────────────────────────────

async function _post<T>(path: string, body: unknown, token?: string): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? 'Request failed');
    }
    return res.json();
}

async function _put<T>(path: string, body: unknown, token: string): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(body),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? 'Request failed');
    }
    return res.json();
}

async function _get<T>(path: string, token: string): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? 'Request failed');
    }
    return res.json();
}

// ── Public API ───────────────────────────────────────────────────────────────

interface _AuthResponse {
    access_token: string;
    token_type: string;
    user_id: string;
    display_name: string;
    communication_mode: string;
    preferred_language: string;
}

/**
 * Register a new account. Returns a UserProfile (including JWT) on success.
 */
export async function register(
    displayName: string,
    email: string,
    password: string,
    communicationMode: CommunicationMode = 'text',
    preferredLanguage = 'en-US',
): Promise<UserProfile> {
    const data = await _post<_AuthResponse>('/auth/register', {
        display_name: displayName,
        email,
        password,
        communication_mode: communicationMode,
        preferred_language: preferredLanguage,
    });
    return _mapAuthResponse(data);
}

/**
 * Login with email + password. Returns UserProfile (including JWT).
 */
export async function login(email: string, password: string): Promise<UserProfile> {
    const data = await _post<_AuthResponse>('/auth/login', { email, password });
    return _mapAuthResponse(data);
}

/**
 * Fetch current user claims from the server (validates stored token).
 */
export async function getMe(token: string): Promise<{ user_id: string; claims: Record<string, unknown> }> {
    return _get('/auth/me', token);
}

/**
 * Update communication mode and accessibility preferences.
 * Persisted to Cosmos DB so any channel the user logs into next will reflect the change.
 */
export async function updatePreferences(
    payload: PreferencesPayload,
    token: string,
): Promise<{ status: string; user_id: string; communication_mode: string; preferred_language: string }> {
    return _put('/auth/me/preferences', payload, token);
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _mapAuthResponse(data: _AuthResponse): UserProfile {
    return {
        userId: data.user_id,
        displayName: data.display_name,
        communicationMode: (data.communication_mode ?? 'text') as CommunicationMode,
        preferredLanguage: data.preferred_language ?? 'en-US',
        token: data.access_token,
    };
}
