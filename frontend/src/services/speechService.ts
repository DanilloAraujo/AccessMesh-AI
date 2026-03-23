/**
 * services/speechService.ts
 * -------------------------
 * Encapsulates all speech-related HTTP calls to the backend.
 *
 * The browser never touches Azure directly — audio is sent as a binary blob
 * to POST /speech/recognize, where the backend handles transcription via the
 * MCP speech_to_text_tool and then runs the full agent pipeline.
 */

const BASE_URL: string =
    import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

function _getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('accessmesh_token');
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
}

export interface VoiceResponse {
    message_id: string;
    text: string;
    source: string;
    features_applied: string[];
    translated_content?: string;
}

/**
 * Upload a raw audio blob (WebM/Opus from MediaRecorder) to the backend.
 * The backend transcribes it via the MCP speech_to_text_tool and runs the
 * full pipeline (RouterAgent → AccessibilityAgent ‖ TranslationAgent → ACCESSIBLE),
 * broadcasting the result to all session participants.
 */
export async function recognizeAudio(
    audioBlob: Blob,
    sessionId: string,
    userId: string,
    language = 'en-US',
    targetLanguage = 'en-US',
): Promise<VoiceResponse> {
    const form = new FormData();
    form.append('audio', audioBlob, 'recording.webm');
    form.append('session_id', sessionId);
    form.append('user_id', userId);
    form.append('language', language);
    form.append('target_language', targetLanguage);

    const response = await fetch(`${BASE_URL}/speech/recognize`, {
        method: 'POST',
        headers: _getAuthHeaders(),  // no Content-Type — browser sets multipart boundary automatically
        body: form,
    });
    if (!response.ok) {
        throw new Error(`[speechService] recognize failed: HTTP ${response.status}`);
    }
    return response.json();
}
