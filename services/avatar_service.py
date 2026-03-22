"""Avatar synthesis service — Azure Neural TTS with viseme timing events."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Azure Neural TTS — canonical voice per BCP-47 language tag.
_DEFAULT_VOICES: Dict[str, str] = {
    "en-US": "en-US-JennyNeural",
    "en-us": "en-US-JennyNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "pt-br": "pt-BR-FranciscaNeural",
    "es":    "es-ES-ElviraNeural",
    "fr":    "fr-FR-DeniseNeural",
    "de":    "de-DE-KatjaNeural",
}


@dataclass
class AvatarConfig:
    """Configuration for the avatar synthesis provider."""

    api_key: str = ""
    api_endpoint: str = ""
    provider: str = "stub"      # "stub" | "azure"
    speech_region: str = ""
    default_language: str = "en-US"
    timeout_seconds: float = 30.0


class AvatarService:
    """Synthesises speech audio and viseme events via Azure Neural TTS."""

    def __init__(self, config: Optional[AvatarConfig] = None) -> None:
        if config is None:
            from shared.config import settings  # noqa: PLC0415

            resolved_provider = settings.avatar_provider or "stub"

            # Auto-upgrade: if Speech credentials are present but provider is still
            # "stub" (the default), silently activate the Azure provider so avatar
            # synthesis works without explicit AVATAR_PROVIDER configuration.
            if (
                resolved_provider == "stub"
                and settings.azure_speech_key
                and settings.azure_speech_region
            ):
                resolved_provider = "azure"
                logger.info(
                    "AvatarService: AVATAR_PROVIDER upgraded to 'azure' "
                    "(AZURE_SPEECH_KEY + AZURE_SPEECH_REGION are configured)."
                )

            config = AvatarConfig(
                api_key=settings.azure_speech_key or "",
                api_endpoint=settings.avatar_api_endpoint or "",
                provider=resolved_provider,
                speech_region=settings.azure_speech_region or "",
                default_language=settings.speech_default_language or "en-US",
            )
        self._config = config

    @property
    def is_enabled(self) -> bool:
        """True when Azure Neural TTS credentials are present and provider is 'azure'."""
        return (
            self._config.provider == "azure"
            and bool(self._config.api_key)
            and bool(self._config.speech_region)
        )

    def synthesise_tts_with_visemes(
        self,
        text: str,
        language: Optional[str] = None,
        voice_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesise *text* via Azure Neural TTS and capture viseme timing events.

        Parameters
        ----------
        text        : Plain text or SSML snippet to synthesise.
        language    : BCP-47 language tag (e.g. 'pt-BR', 'en-US').
                      Falls back to ``AvatarConfig.default_language``.
        voice_name  : Override the default neural voice for *language*.

        Returns
        -------
        {
            "audio_b64"    : str,  # base64 MP3 audio bytes
            "content_type" : str,  # "audio/mpeg"
            "viseme_events": list, # [{offset_ms: float, viseme_id: int}, ...]
            "duration_ms"  : float,
            "language"     : str,
            "voice_name"   : str,
            "stub"         : bool  # always False on success
        }

        Raises
        ------
        RuntimeError  when credentials are missing or synthesis fails.
        ImportError   when azure-cognitiveservices-speech is not installed.
        """
        if not self.is_enabled:
            raise RuntimeError(
                f"AvatarService: provider is '{self._config.provider}' — "
                "Azure Speech credentials (AZURE_SPEECH_KEY + AZURE_SPEECH_REGION) "
                "are required for TTS avatar synthesis."
            )

        try:
            import azure.cognitiveservices.speech as speechsdk  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "AvatarService: azure-cognitiveservices-speech is not installed. "
                "Run: pip install azure-cognitiveservices-speech"
            ) from exc

        effective_lang = language or self._config.default_language
        effective_voice = voice_name or _DEFAULT_VOICES.get(
            effective_lang, _DEFAULT_VOICES.get(effective_lang.split("-")[0], "en-US-JennyNeural")
        )

        logger.info(
            "AvatarService.synthesise_tts_with_visemes — lang=%s voice=%s chars=%d",
            effective_lang,
            effective_voice,
            len(text),
        )

        speech_config = speechsdk.SpeechConfig(
            subscription=self._config.api_key,
            region=self._config.speech_region,
        )
        # Request 16 kHz 128 kbps mono MP3 — compact format suitable for WebSocket delivery.
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
        )
        speech_config.speech_synthesis_voice_name = effective_voice

        viseme_events: List[Dict[str, Any]] = []

        # audio_config=None → capture audio to result.audio_data (no speaker output).
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=None,
        )

        # Subscribe to viseme event — fired for each phoneme during synthesis.
        # SDK offset unit: 100-nanosecond ticks → convert to milliseconds.
        synthesizer.viseme_received.connect(
            lambda evt: viseme_events.append(
                {
                    "offset_ms": round(evt.audio_offset / 10_000, 2),
                    "viseme_id": evt.viseme_id,
                }
            )
        )

        # Use SSML with mstts:express-as for natural prosody in pt-BR and en-US.
        ssml = (
            f"<speak version='1.0' xml:lang='{effective_lang}' "
            f"xmlns:mstts='http://www.w3.org/2001/mstts'>"
            f"<voice name='{effective_voice}'>"
            f"<mstts:express-as style='default'>{text}</mstts:express-as>"
            f"</voice></speak>"
        )

        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio_bytes = result.audio_data
            duration_ms = round(result.audio_duration.total_seconds() * 1000, 2)

            logger.info(
                "AvatarService: synthesis complete — %d bytes, %d visemes, %.0f ms",
                len(audio_bytes),
                len(viseme_events),
                duration_ms,
            )
            return {
                "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
                "content_type": "audio/mpeg",
                "viseme_events": viseme_events,
                "duration_ms": duration_ms,
                "language": effective_lang,
                "voice_name": effective_voice,
                "stub": False,
            }

        # Synthesis failed — extract detailed error message from cancellation details.
        cancellation = speechsdk.SpeechSynthesisCancellationDetails.from_result(result)
        error_msg = f"reason={cancellation.reason}, details={cancellation.error_details}"
        logger.error("AvatarService: synthesis failed — %s", error_msg)
        raise RuntimeError(f"AvatarService: Azure Neural TTS synthesis failed — {error_msg}")

    def synthesise_sign(
        self,
        gloss_sequence: List[str],
        language: str = "libras",
    ) -> Dict[str, Any]:
        """
        3D sign-language avatar synthesis (reserved for future avatar API integration).
        The current implementation delegates to the client-side SVG avatar in
        AvatarSignView.tsx which renders gloss sequences without a server round-trip.
        """
        raise NotImplementedError(
            "AvatarService: 3D sign-language avatar synthesis is not yet implemented. "
            "The SVG-based AvatarSignView component handles runtime gloss rendering client-side."
        )
