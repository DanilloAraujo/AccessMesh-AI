from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

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

    api_key: str = ""
    api_endpoint: str = ""
    provider: str = "stub"      # "stub" | "azure"
    speech_region: str = ""
    default_language: str = "en-US"
    timeout_seconds: float = 30.0

class AvatarService:
    """
    Service for avatar-related operations, including text-to-speech (TTS) synthesis with viseme data and (future) sign language synthesis.

    This class provides methods to synthesize speech audio and viseme events using Azure Cognitive Services, based on the provided configuration.
    It supports dynamic configuration via the AvatarConfig dataclass and can auto-upgrade to Azure provider if credentials are available.

    Methods:
        - synthesise_tts_with_visemes: Generates TTS audio and viseme events for a given text.
        - synthesise_sign: Placeholder for sign language avatar synthesis (not implemented).

    Usage:
        Instantiate with an AvatarConfig or allow auto-configuration from shared settings.
        Use is_enabled to check if Azure TTS is available.
    """
   
    def __init__(self, config: Optional[AvatarConfig] = None) -> None:
        """
        Initialize the AvatarService with the given configuration or from shared settings.

        Args:
            config (Optional[AvatarConfig]): Optional configuration for the avatar service. If not provided, uses shared settings.
        """
        if config is None:
            from shared.config import settings  # noqa: PLC0415

            resolved_provider = settings.avatar_provider or "stub"

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
        """
        Indicates whether the Azure TTS provider is enabled and properly configured.

        Returns:
            bool: True if Azure TTS is available, False otherwise.
        """
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
        Synthesize text-to-speech (TTS) audio with viseme data using Azure Cognitive Services.

        Args:
            text (str): The text to synthesize.
            language (Optional[str]): The language code for synthesis (e.g., 'en-US'). If not provided, uses default.
            voice_name (Optional[str]): The specific voice to use. If not provided, uses default for the language.

        Returns:
            Dict[str, Any]: A dictionary containing base64-encoded audio, viseme events, duration, language, and voice info.

        Raises:
            RuntimeError: If the service is not enabled or credentials are missing.
            ImportError: If the Azure Speech SDK is not installed.
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
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
        )
        speech_config.speech_synthesis_voice_name = effective_voice

        viseme_events: List[Dict[str, Any]] = []

        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=None,
        )

        synthesizer.viseme_received.connect(
            lambda evt: viseme_events.append(
                {
                    "offset_ms": round(evt.audio_offset / 10_000, 2),
                    "viseme_id": evt.viseme_id,
                }
            )
        )

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
        Placeholder for 3D sign-language avatar synthesis.

        Args:
            gloss_sequence (List[str]): The sequence of glosses (sign language tokens) to synthesize.
            language (str, optional): The sign language code. Defaults to "libras".

        Raises:
            NotImplementedError: Always, as this feature is not yet implemented.
        """
        raise NotImplementedError(
            "AvatarService: 3D sign-language avatar synthesis is not yet implemented. "
            "The SVG-based AvatarSignView component handles runtime gloss rendering client-side."
        )
