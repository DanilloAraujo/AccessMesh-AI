"""Azure Cognitive Services Speech Service wrapper."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_TOKEN_URL_TEMPLATE = (
    "https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
)


@dataclass
class SpeechConfig:
    """Configuration for the Azure Speech Service."""

    subscription_key: str
    region: str
    default_language: str = "en-US"


class SpeechService:
    """Wraps Azure Cognitive Services Speech for token issuance and transcription."""

    def __init__(self, config: Optional[SpeechConfig] = None) -> None:
        if config is None:
            from shared.config import settings  # noqa: PLC0415
            config = SpeechConfig(
                subscription_key=settings.azure_speech_key or "",
                region=settings.azure_speech_region or "",
                default_language=settings.speech_default_language,
            )
        self._key = config.subscription_key
        self._region = config.region
        self._language = config.default_language
        self._token_url = _TOKEN_URL_TEMPLATE.format(region=config.region) if config.region else ""

    @property
    def is_enabled(self) -> bool:
        return bool(self._key and self._region)


    async def get_speech_token(self) -> dict[str, str]:
        """
        Issue a short-lived Azure Speech auth token (valid for 10 minutes).
        Intended for the frontend to use with SpeechConfig.fromAuthorizationToken().
        """
        if not self.is_enabled:
            raise RuntimeError("Speech Service is not configured — set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.")
        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Content-Length": "0",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self._token_url, headers=headers)
            response.raise_for_status()

        logger.info("Speech token issued for region '%s'.", self._region)
        return {"token": response.text, "region": self._region}


    def transcribe_from_bytes(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
    ) -> tuple[str, float]:
        """
        Transcribe audio from raw bytes using the Azure Speech SDK.
        Expects PCM 16 kHz, 16-bit, mono WAV data.

        Returns a tuple of (recognised_text, confidence).
        Returns ("", 0.0) when no speech is detected.
        """
        try:
            import azure.cognitiveservices.speech as speechsdk  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "azure-cognitiveservices-speech is required for server-side "
                "transcription. Run: pip install azure-cognitiveservices-speech"
            ) from exc

        lang = language or self._language

        speech_cfg = speechsdk.SpeechConfig(
            subscription=self._key, region=self._region
        )
        speech_cfg.speech_recognition_language = lang

        push_stream = speechsdk.audio.PushAudioInputStream()
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_cfg, audio_config=audio_config
        )

        push_stream.write(audio_bytes)
        push_stream.close()

        result = recognizer.recognize_once()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            confidence = getattr(result, "confidence", 1.0) or 1.0
            logger.info("Transcribed (%s): %s", lang, result.text[:120])
            return result.text, float(confidence)

        if result.reason == speechsdk.ResultReason.NoMatch:
            logger.debug("No speech recognised in submitted audio.")
            return "", 0.0

        logger.error("Speech recognition error — reason: %s", result.reason)
        raise RuntimeError(f"Speech recognition failed: {result.reason}")


    # Default voice map

    _DEFAULT_VOICES: Dict[str, str] = {
        "en-US":  "en-US-JennyNeural",
        "en-us":  "en-US-JennyNeural",
        "pt-BR":  "pt-BR-FranciscaNeural",
        "pt-br":  "pt-BR-FranciscaNeural",
        "es":     "es-ES-ElviraNeural",
        "fr":     "fr-FR-DeniseNeural",
        "de":     "de-DE-KatjaNeural",
    }

    def synthesize_sync(
        self,
        text: str,
        language: str = "en-US",
        voice_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesise speech from text synchronously (blocking).

        Tries the Azure Speech SDK first; falls back to the TTS REST API
        when the SDK is unavailable.

        Parameters
        ----------
        text:
            Text to synthesise.
        language:
            BCP-47 language tag (e.g. ``"pt-BR"``, ``"en-US"``).
        voice_name:
            Azure Neural TTS voice name.  Resolved from ``_DEFAULT_VOICES``
            when omitted.

        Returns
        -------
        dict with keys:
            ``audio_b64``  — base64-encoded MP3 bytes
            ``content_type`` — ``"audio/mpeg"``
            ``duration_ms`` — playback duration
            ``language`` — resolved language tag
            ``voice_name`` — resolved voice name

        Raises
        ------
        RuntimeError
            When ``AZURE_SPEECH_KEY`` / ``AZURE_SPEECH_REGION`` are not set,
            or when synthesis fails on both the SDK and REST paths.
        """
        if not self.is_enabled:
            raise RuntimeError(
                "SpeechService: Azure Speech Service not configured — "
                "set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION."
            )

        resolved_voice = voice_name or self._DEFAULT_VOICES.get(
            language,
            self._DEFAULT_VOICES.get(language.split("-")[0], "en-US-JennyNeural"),
        )

        # Primary: Azure Speech SDK
        try:
            return self._synthesize_sdk(text, language, resolved_voice)
        except ImportError:
            logger.warning(
                "SpeechService.synthesize_sync: SDK unavailable — "
                "falling back to REST API."
            )
        except Exception as exc:
            logger.warning(
                "SpeechService.synthesize_sync: SDK synthesis failed (%s) — "
                "falling back to REST API.",
                exc,
            )

        # Fallback: TTS REST API
        return self._synthesize_rest(text, language, resolved_voice)

    def _synthesize_sdk(
        self,
        text: str,
        language: str,
        resolved_voice: str,
    ) -> Dict[str, Any]:
        """Primary TTS path using the azure-cognitiveservices-speech SDK."""
        import azure.cognitiveservices.speech as speechsdk  # type: ignore[import]

        speech_config = speechsdk.SpeechConfig(
            subscription=self._key,
            region=self._region,
        )
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
        )
        speech_config.speech_synthesis_voice_name = resolved_voice

        # audio_config=None → capture to result.audio_data (no speaker output).
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=None,
        )

        ssml = (
            f"<speak version='1.0' xml:lang='{language}' "
            f"xmlns:mstts='http://www.w3.org/2001/mstts'>"
            f"<voice name='{resolved_voice}'>"
            f"<mstts:express-as style='default'>{text}</mstts:express-as>"
            f"</voice></speak>"
        )
        result: speechsdk.SpeechSynthesisResult = synthesizer.speak_ssml_async(ssml).get()  # type: ignore[assignment]

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.info(
                "SpeechService._synthesize_sdk: %d bytes, %.0f ms",
                len(result.audio_data),
                result.audio_duration.total_seconds() * 1000,
            )
            return {
                "audio_b64": base64.b64encode(result.audio_data).decode("ascii"),
                "content_type": "audio/mpeg",
                "duration_ms": round(result.audio_duration.total_seconds() * 1000, 2),
                "language": language,
                "voice_name": resolved_voice,
            }

        cancellation = result.cancellation_details
        raise RuntimeError(
            f"SpeechService._synthesize_sdk: synthesis failed — "
            f"{cancellation.reason}: {cancellation.error_details}"
        )

    def _synthesize_rest(
        self,
        text: str,
        language: str,
        resolved_voice: str,
    ) -> Dict[str, Any]:
        """Fallback TTS path via the Azure TTS REST API."""
        logger.info(
            "SpeechService._synthesize_rest: synthesising %d chars — %s / %s",
            len(text),
            language,
            resolved_voice,
        )
        ssml = (
            f"<speak version='1.0' xml:lang='{language}'>"
            f"<voice name='{resolved_voice}'>{text}</voice></speak>"
        )
        tts_url = (
            f"https://{self._region}.tts.speech.microsoft.com/cognitiveservices/v1"
        )
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                tts_url,
                content=ssml.encode("utf-8"),
                headers={
                    "Ocp-Apim-Subscription-Key": self._key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
                    "User-Agent": "AccessMesh-AI/1.0",
                },
            )
            resp.raise_for_status()
            audio_bytes = resp.content
        return {
            "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
            "content_type": "audio/mpeg",
            "duration_ms": 0.0,
            "language": language,
            "voice_name": resolved_voice,
        }
