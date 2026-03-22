/** Manages the connection with Azure Web PubSub. */

const BASE_URL: string =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** Delays (ms) between successive reconnect attempts — exponential-ish backoff. */
const RECONNECT_DELAYS_MS = [1_000, 2_000, 5_000, 10_000];

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface ChatMessage {
  id: string;
  type: string;
  from: string;
  content: string;
  timestamp: string;
  /** 'voice' when the message was produced by the speech pipeline, 'gesture' for gesture input */
  source?: 'text' | 'voice' | 'gesture';
  /** Accessibility features applied by the accessibility_agent */
  features_applied?: string[];
  /** Sign-language gloss sequence (from text_to_sign_tool via pipeline) */
  sign_gloss?: Array<{ gloss: string; duration_ms: number }>;
  /** Translated text when target language differs from source */
  translated_content?: string;
  /** Base64-encoded MP3 from text_to_speech_tool — TTS playback for other participants (RB01) */
  audio_b64?: string;
  /** True while the pipeline is still processing — renders as a typing indicator */
  pending?: boolean;
  /** STT transcription confidence score (0–1) — displayed next to voice messages */
  confidence?: number;
  /** Azure Neural TTS viseme timing events for avatar lip-sync */
  viseme_events?: Array<{ offset_ms: number; viseme_id: number }>;
}

export interface PubSubMessage {
  type: string;
  data?: ChatMessage;
  [key: string]: any;
}

class WebSocketService {
  private socket: WebSocket | null = null;
  private messageListeners: Set<(data: PubSubMessage) => void> = new Set();
  private statusListeners: Set<(status: ConnectionStatus) => void> = new Set();
  public userId: string;
  public displayName: string = "";
  public sessionId: string;
  private isConnecting: boolean = false;
  private intentionalDisconnect: boolean = false;
  private reconnectAttempt: number = 0;
  private _beforeUnloadHandler = () => this.disconnect();

  constructor() {
    // Use sessionStorage so each browser tab gets its own unique userId.
    // localStorage would make every tab in the same browser share the same id,
    // causing all messages to appear as "You" for every participant.
    const storedId = sessionStorage.getItem('accessmesh_user_id');
    this.userId = storedId ?? `user_${Math.random().toString(36).substring(2, 11)}`;
    if (!storedId) sessionStorage.setItem('accessmesh_user_id', this.userId);
    this.sessionId = 'default-room';
    window.addEventListener('beforeunload', this._beforeUnloadHandler);
  }

  /** Returns headers including Authorization when a JWT is present in localStorage. */
  private _getAuthHeaders(extra: Record<string, string> = {}): Record<string, string> {
    const token = localStorage.getItem('accessmesh_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json', ...extra };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
  }

  /**
   * Gets token from backend and connects to WebSocket.
   */
  async connect(): Promise<void> {
    if (this.socket || this.isConnecting) return;

    try {
      this.intentionalDisconnect = false;
      this.isConnecting = true;
      this.updateStatus('connecting');

      const response = await fetch(`${BASE_URL}/pubsub/token`, {
        method: 'POST',
        headers: this._getAuthHeaders(),
        body: JSON.stringify({
          user_id: this.userId,
          session_id: this.sessionId
        })
      });

      if (!response.ok) throw new Error('Failed to obtain token');

      const { url } = await response.json();

      // If disconnected during fetch, don't open socket
      if (!this.isConnecting) return;

      const ws = new WebSocket(url, 'json.webpubsub.azure.v1');
      this.socket = ws;

      ws.onopen = () => {
        this.isConnecting = false;
        this.reconnectAttempt = 0;
        // Do NOT send here — with json.webpubsub.azure.v1 the service first
        // sends {"type":"system","event":"connected"} before the client may
        // send anything. joinGroup is sent in onmessage on that event.
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data: PubSubMessage = JSON.parse(event.data);
          // Azure sends a system "connected" event when the session is ready.
          // Only after that can we send joinGroup and mark ourselves connected.
          if ((data as any).type === 'system' && (data as any).event === 'connected') {
            ws.send(JSON.stringify({
              type: 'joinGroup',
              group: this.sessionId,
              ackId: 1,
            }));
            this.updateStatus('connected');
            // Load existing session history so late joiners see prior messages.
            this._loadHistory();
            return;
          }
          this.messageListeners.forEach(cb => cb(data));
        } catch (e) {
          console.error('[WebSocket] Error processing JSON message:', e);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        this.updateStatus('error');
      };

      ws.onclose = () => {
        this.socket = null;
        this.updateStatus('disconnected');
        if (!this.intentionalDisconnect) {
          this._scheduleReconnect();
        }
      };

    } catch (error) {
      console.error('❌ Error connecting:', error);
      this.updateStatus('error');
      this.isConnecting = false;
    }
  }

  /**
   * Schedules a reconnect attempt with exponential backoff.
   */
  private _scheduleReconnect(): void {
    const delay = RECONNECT_DELAYS_MS[Math.min(this.reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)];
    this.reconnectAttempt++;
    setTimeout(() => {
      if (!this.intentionalDisconnect) {
        this.connect().then(() => {
          this.reconnectAttempt = 0;
        }).catch(() => {/* onclose will trigger next attempt */ });
      }
    }, delay);
  }

  /**
   * Fetches message history for the current session and dispatches each
   * message to registered listeners — called once after joining the group
   * so late joiners see messages sent before they connected.
   */
  private async _loadHistory(): Promise<void> {
    try {
      const response = await fetch(
        `${BASE_URL}/chat/history/${encodeURIComponent(this.sessionId)}`,
        { headers: this._getAuthHeaders({ 'Content-Type': '' }) },
      );
      if (!response.ok) return;
      const body = await response.json();
      const msgs: ChatMessage[] = (body.messages ?? []).map((m: Record<string, any>) => ({
        id: m.id ?? `hist_${Math.random().toString(36).substring(2, 11)}`,
        type: 'message',
        from: m.from ?? m.sender_id ?? 'unknown',
        content: m.content ?? '',
        timestamp: m.stored_at ?? m.timestamp ?? new Date().toISOString(),
        source: (m.source as ChatMessage['source']) ?? 'text',
        features_applied: m.features_applied,
        sign_gloss: m.sign_gloss,
        translated_content: m.translated_content,
        audio_b64: m.audio_b64,
      }));
      for (const msg of msgs) {
        this.messageListeners.forEach(cb => cb({ type: 'message', data: msg }));
      }
    } catch (e) {
      console.warn('[WebSocket] Failed to load history:', e);
    }
  }

  /**
   * Sends a message to the group (raw WebSocket — for internal use only).
   * External callers should use sendChatMessage() so text goes through the pipeline.
   */
  sendMessage(text: string): ChatMessage | null {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const message: ChatMessage = {
        id: `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
        type: 'message',
        from: this.displayName || this.userId,
        content: text,
        timestamp: new Date().toISOString()
      };

      this.socket.send(JSON.stringify({
        type: 'sendToGroup',
        group: this.sessionId,
        data: message
      }));

      return message;
    }
    return null;
  }

  /**
   * Sends an enriched ChatMessage to all group members via the WebSocket
   * sendToGroup client message.  noEcho prevents the sender from receiving
   * their own broadcast (the sender already has it via addMessage).
   */
  private _broadcastToGroup(msg: ChatMessage): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'sendToGroup',
        group: this.sessionId,
        noEcho: true,
        dataType: 'json',
        data: msg,
      }));
    }
  }

  /**
   * Posts plain-text chat to the backend chat pipeline.
   * The pipeline runs router → accessibility → translation → avatar and
   * broadcasts the enriched result (with sign_gloss) to all participants.
   */
  async sendChatMessage(text: string, targetLanguage = 'en-US'): Promise<ChatMessage | null> {
    console.log('[websocketService] sendChatMessage → POST /chat/send — text=%s target=%s', text.substring(0, 80), targetLanguage);
    try {
      const response = await fetch(`${BASE_URL}/chat/send`, {
        method: 'POST',
        headers: this._getAuthHeaders(),
        body: JSON.stringify({
          text,
          session_id: this.sessionId,
          user_id: this.userId,
          display_name: this.displayName,
          language: targetLanguage,
          target_language: targetLanguage,
        }),
      });

      if (!response.ok) {
        console.error('[sendChatMessage] Pipeline returned HTTP', response.status);
        return null;
      }

      const result = await response.json();
      console.log('[websocketService] sendChatMessage response — id=%s features=%o audio=%s', result.message_id, result.features_applied, result.audio_b64 ? 'yes' : 'no');
      const enriched: ChatMessage = {
        id: result.message_id ?? `local_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
        type: 'message',
        from: this.displayName || this.userId,
        content: result.text ?? text,
        timestamp: new Date().toISOString(),
        source: 'text',
        features_applied: result.features_applied ?? [],
        sign_gloss: result.sign_gloss ?? undefined,
        translated_content: result.translated_content ?? undefined,
        audio_b64: result.audio_b64 ?? undefined,
        confidence: result.confidence ?? undefined,
        viseme_events: result.viseme_events ?? undefined,
      };
      // Broadcast the enriched message to all other group members via WebSocket.
      // This is more reliable than the server-side REST send_to_group.
      this._broadcastToGroup(enriched);
      return enriched;
    } catch (err) {
      console.error('[sendChatMessage] Network error:', err);
      return null;
    }
  }

  /**
   * Posts transcribed text to the backend speech pipeline.
   * The pipeline runs router → accessibility → translation → avatar
   * and broadcasts the result to ALL session participants via Web PubSub.
   *
   * Returns a local ChatMessage for optimistic UI update (the sender
   * is excluded from the WebPubSub broadcast echo).
   */
  async processSpeech(text: string, language = 'en-US', targetLanguage = 'en-US'): Promise<ChatMessage | null> {
    console.log('[websocketService] processSpeech → POST /speech/voice — text=%s lang=%s target=%s', text.substring(0, 80), language, targetLanguage);
    try {
      const response = await fetch(`${BASE_URL}/speech/voice`, {
        method: 'POST',
        headers: this._getAuthHeaders(),
        body: JSON.stringify({
          text,
          session_id: this.sessionId,
          user_id: this.userId,
          display_name: this.displayName,
          language,
          target_language: targetLanguage,
        }),
      });

      if (!response.ok) {
        console.error('[processSpeech] Pipeline returned HTTP', response.status);
        return null;
      }

      const result = await response.json();
      console.log('[websocketService] processSpeech response — id=%s features=%o audio=%s', result.message_id, result.features_applied, result.audio_b64 ? 'yes' : 'no');

      // Build a local ChatMessage so the sender sees it immediately.
      const localMsg: ChatMessage = {
        id: result.message_id,
        type: 'message',
        from: this.displayName || this.userId,
        content: result.text,
        timestamp: new Date().toISOString(),
        source: 'voice',
        features_applied: result.features_applied ?? [],
        sign_gloss: result.sign_gloss ?? undefined,
        translated_content: result.translated_content ?? undefined,
        audio_b64: result.audio_b64 ?? undefined,
        confidence: result.confidence ?? undefined,
        viseme_events: result.viseme_events ?? undefined,
      };
      // Broadcast the enriched voice message to all other group members.
      this._broadcastToGroup(localMsg);
      return localMsg;
    } catch (err) {
      console.error('[processSpeech] Network error:', err);
      return null;
    }
  }

  /**
   * Posts any modality through the unified hub endpoint (RB04 / RB05).
   * All channels (web, mobile, Teams, Slack…) share the same API contract.
   */
  async sendHubMessage(
    inputType: 'speech' | 'gesture' | 'text',
    content: string,
    channel = 'web',
    language = 'en-US',
    targetLanguage = 'en-US',
  ): Promise<ChatMessage | null> {
    console.log('[websocketService] sendHubMessage → POST /hub/message — type=%s channel=%s lang=%s target=%s content=%s', inputType, channel, language, targetLanguage, content.substring(0, 60));
    try {
      const response = await fetch(`${BASE_URL}/hub/message`, {
        method: 'POST',
        headers: this._getAuthHeaders(),
        body: JSON.stringify({
          channel,
          input_type: inputType,
          content,
          session_id: this.sessionId,
          user_id: this.userId,
          display_name: this.displayName,
          language,
          target_language: targetLanguage,
        }),
      });
      if (!response.ok) {
        console.error('[sendHubMessage] HTTP', response.status);
        return null;
      }
      const result = await response.json();
      console.log('[websocketService] sendHubMessage response — id=%s features=%o audio=%s', result.message_id, result.features_applied, result.audio_b64 ? 'yes' : 'no');
      const sourceMap: Record<string, ChatMessage['source']> = {
        speech: 'voice',
        gesture: 'gesture',
        text: 'text',
      };
      const localMsg: ChatMessage = {
        id: result.message_id,
        type: 'message',
        from: this.displayName || this.userId,
        content: result.text,
        timestamp: new Date().toISOString(),
        source: sourceMap[inputType] ?? 'text',
        features_applied: result.features_applied ?? [],
        sign_gloss: result.sign_gloss ?? undefined,
        translated_content: result.translated_content ?? undefined,
        audio_b64: result.audio_b64 ?? undefined,
        confidence: result.confidence ?? undefined,
        viseme_events: result.viseme_events ?? undefined,
      };
      this._broadcastToGroup(localMsg);
      return localMsg;
    } catch (err) {
      console.error('[sendHubMessage] Network error:', err);
      return null;
    }
  }

  /**
   * Registers a message listener. Returns an unsubscribe function.
   */
  onMessage(callback: (data: PubSubMessage) => void): () => void {
    this.messageListeners.add(callback);
    return () => this.messageListeners.delete(callback);
  }

  /**
   * Fetches a meeting summary (Ata) for the given session.
   */
  async fetchSummary(sessionId: string): Promise<Record<string, unknown>> {
    const response = await fetch(
      `${BASE_URL}/chat/summary/${encodeURIComponent(sessionId)}`,
      { headers: this._getAuthHeaders({ 'Content-Type': '' }) },
    );
    if (!response.ok) throw new Error(`Summary request failed: ${response.status}`);
    return response.json();
  }

  /**
   * Registers a status change listener. Returns an unsubscribe function.
   */
  onStatusChange(callback: (status: ConnectionStatus) => void): () => void {
    this.statusListeners.add(callback);
    return () => this.statusListeners.delete(callback);
  }

  private updateStatus(status: ConnectionStatus): void {
    this.statusListeners.forEach(cb => cb(status));
  }

  disconnect(): void {
    this.intentionalDisconnect = true;
    this.isConnecting = false;
    window.removeEventListener('beforeunload', this._beforeUnloadHandler);
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}

export { WebSocketService };
