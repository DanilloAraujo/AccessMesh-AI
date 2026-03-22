const BASE_URL: string =
    import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

function _getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('accessmesh_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
}

export interface GlyphResult {
    gloss: string;
    duration_ms: number;
}

export interface GestureProcessResult {
    message_id: string;
    text: string;
    source: string;
    gloss_sequence: GlyphResult[];
    features_applied: string[];
}

export interface GestureFrameResult {
    message_id: string;
    text: string;
    gesture_label: string;
    confidence: number;
    source: string;
    features_applied: string[];
    gloss_sequence: GlyphResult[];
}

export async function processGesture(
    label: string,
    sessionId: string,
    userId: string,
): Promise<GestureProcessResult> {
    const response = await fetch(`${BASE_URL}/gesture/process`, {
        method: 'POST',
        headers: _getAuthHeaders(),
        body: JSON.stringify({ gesture_label: label, session_id: sessionId, user_id: userId }),
    });
    if (!response.ok) {
        throw new Error(`[gestureService] Pipeline error: HTTP ${response.status}`);
    }
    return response.json();
}

export interface LandmarkPoint {
    x: number;
    y: number;
    z: number;
}

export async function sendLandmarks(
    landmarks: LandmarkPoint[],
    sessionId: string,
    userId: string,
): Promise<GestureProcessResult> {
    const response = await fetch(`${BASE_URL}/gesture/landmarks`, {
        method: 'POST',
        headers: _getAuthHeaders(),
        body: JSON.stringify({ landmarks, session_id: sessionId, user_id: userId }),
    });
    if (!response.ok) {
        throw new Error(`[gestureService] Landmarks error: HTTP ${response.status}`);
    }
    return response.json();
}

export async function sendFrame(
    frameB64: string,
    sessionId: string,
    userId: string,
): Promise<GestureFrameResult> {
    const response = await fetch(`${BASE_URL}/gesture/frame`, {
        method: 'POST',
        headers: _getAuthHeaders(),
        body: JSON.stringify({ frame_b64: frameB64, session_id: sessionId, user_id: userId }),
    });
    if (!response.ok) {
        throw new Error(`[gestureService] Frame error: HTTP ${response.status}`);
    }
    return response.json();
}
