"""
MCP Tool: text_to_speech_tool

Converts text into synthesised speech using Azure Neural TTS.

Primary path:  Azure Speech SDK (azure-cognitiveservices-speech) — provides
               MP3 audio AND viseme timing events for avatar lip-sync.
Fallback path: Azure TTS REST API via httpx — audio only, no viseme events.
               Used automatically when the SDK is unavailable.

Returns base64-encoded MP3 audio for browser playback plus viseme events
for the AvatarSignView lip-sync animation.
Falls back to an empty payload when AZURE_SPEECH_KEY / AZURE_SPEECH_REGION
are not configured.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.speech_service import SpeechService

logger = logging.getLogger(__name__)


class TextToSpeechTool:
    """
    MCP tool that synthesises speech audio from text.

    name        : text_to_speech_tool
    description : Converts text into synthesised speech (Azure Neural TTS).
                  Returns base64-encoded MP3 audio + viseme events for avatar
                  lip-sync animation.
    """

    name: str = "text_to_speech_tool"
    description: str = (
        "Synthesises natural-language text into speech audio using Azure "
        "Neural TTS. Returns base64-encoded audio (MP3) ready for browser "
        "playback and viseme timing events for avatar lip-sync animation."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to synthesise.",
            },
            "language": {
                "type": "string",
                "default": "en-US",
                "description": "BCP-47 language tag (e.g. 'pt-BR', 'en-US').",
            },
            "voice_name": {
                "type": "string",
                "description": "Azure TTS voice name (e.g. 'en-US-JennyNeural').",
            },
        },
    }

    _DEFAULT_VOICES: Dict[str, str] = {
        "en-US": "en-US-JennyNeural",
        "en-us": "en-US-JennyNeural",
        "pt-BR": "pt-BR-FranciscaNeural",
        "pt-br": "pt-BR-FranciscaNeural",
        "es":    "es-ES-ElviraNeural",
        "fr":    "fr-FR-DeniseNeural",
        "de":    "de-DE-KatjaNeural",
    }

    def __init__(self) -> None:
        self._speech = SpeechService()
        # In-process TTS cache: avoids repeated Azure calls for identical
        # (text, language, voice) triples — common for repeated chat messages.
        self._cache: Dict[tuple, Dict[str, Any]] = {}

    def execute(
        self,
        text: str,
        language: str = "en-US",
        voice_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the tool and return a result dict compatible with the MCP protocol.

        Tries the Azure Speech SDK first (provides viseme events for lip-sync).
        Falls back to the REST API when the SDK is unavailable.

        Returns
        -------
        {
            "audio_b64"    : str,   base64-encoded MP3 audio bytes
            "content_type" : str,   "audio/mpeg"
            "viseme_events": list,  [{offset_ms: float, viseme_id: int}, ...]
            "language"     : str,
            "voice_name"   : str,
            "stub"         : bool   True when credentials are missing
        }
        """
        resolved_voice = voice_name or self._DEFAULT_VOICES.get(
            language, self._DEFAULT_VOICES.get(language.split("-")[0], "en-US-JennyNeural")
        )

        # ── Cache lookup ─────────────────────────────────────────────────────
        _cache_key = (text, language, resolved_voice)
        if _cache_key in self._cache:
            logger.debug(
                "text_to_speech_tool: cache hit — lang=%s chars=%d", language, len(text)
            )
            return self._cache[_cache_key]

        # ── Delegate to SpeechService (SDK + REST fallback) ──────────────────
        svc_result = self._speech.synthesize_sync(text, language, resolved_voice)
        result = {**svc_result, "stub": False}
        self._cache[_cache_key] = result
        return result
