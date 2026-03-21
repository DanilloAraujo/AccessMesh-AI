from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TOKEN_URL_TEMPLATE = (
    "https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
)


@dataclass
class SpeechConfig:

    subscription_key: str
    region: str
    default_language: str = "en-US"



class SpeechService:
    """
    Service for Azure Speech operations, including token issuance and audio transcription.

    This class provides methods to obtain a speech token for client-side use and to transcribe audio bytes using Azure Cognitive Services.
    """

    def __init__(self, config: Optional[SpeechConfig] = None) -> None:
        """
        Initialize the SpeechService with the given configuration or from shared settings.

        Args:
            config (Optional[SpeechConfig]): Optional configuration for Azure Speech. If not provided, uses shared settings.
        """
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
        """
        Indicates whether the SpeechService is enabled and properly configured.

        Returns:
            bool: True if the service is enabled, False otherwise.
        """
        return bool(self._key and self._region)


    async def get_speech_token(self) -> dict[str, str]:
        """
        Asynchronously obtain a speech token for Azure Speech client-side use.

        Returns:
            dict[str, str]: A dictionary containing the token and region.

        Raises:
            RuntimeError: If the service is not properly configured.
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
        Transcribe audio bytes to text using Azure Cognitive Services.

        Args:
            audio_bytes (bytes): The audio data to transcribe.
            language (Optional[str]): The language code for transcription. If not provided, uses default.

        Returns:
            tuple[str, float]: The transcribed text and confidence score.

        Raises:
            RuntimeError: If the Azure Speech SDK is not installed or recognition fails.
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
