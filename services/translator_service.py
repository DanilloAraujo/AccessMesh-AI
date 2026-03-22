"""Azure AI Translator (Cognitive Services) wrapper."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TRANSLATE_URL = "{endpoint}/translate"
_API_VERSION = "3.0"


@dataclass
class TranslatorConfig:
    key: str
    endpoint: str = "https://api.cognitive.microsofttranslator.com"
    region: str = ""


class TranslatorService:
    """Calls the Azure AI Translator REST API for text translation."""

    def __init__(self, config: Optional[TranslatorConfig] = None) -> None:
        if config is None:
            from shared.config import settings  # noqa: PLC0415
            if settings.translator_key:
                config = TranslatorConfig(
                    key=settings.translator_key,
                    endpoint=settings.translator_endpoint,
                    region=settings.translator_region,
                )
        self._enabled = False
        self._key = ""
        self._endpoint = "https://api.cognitive.microsofttranslator.com"
        self._region = ""

        if config and config.key:
            self._key = config.key
            self._endpoint = (config.endpoint or "https://api.cognitive.microsofttranslator.com").rstrip("/")
            self._region = config.region
            self._enabled = True
            logger.info("TranslatorService: ready (region=%s)", self._region or "global")

    async def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> str:
        """
        Translate `text` to `target_language` using Azure AI Translator.
        Raises RuntimeError when the service is not configured.
        """
        if not self._enabled:
            raise RuntimeError(
                "Azure Translator is not configured — set TRANSLATOR_KEY and TRANSLATOR_ENDPOINT."
            )
        if not text.strip():
            return text

        # Skip unnecessary round-trip when languages match
        if source_language and source_language.split("-")[0] == target_language.split("-")[0]:
            return text

        params = {"api-version": _API_VERSION, "to": target_language}
        if source_language:
            params["from"] = source_language

        headers = {
            "Ocp-Apim-Subscription-Key": self._key,
            "Content-Type": "application/json; charset=UTF-8",
        }
        if self._region:
            headers["Ocp-Apim-Subscription-Region"] = self._region

        url = f"{self._endpoint}/translate"
        body = [{"text": text}]

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, params=params, headers=headers, json=body)
            resp.raise_for_status()
        translations = resp.json()
        translated = translations[0]["translations"][0]["text"]
        logger.debug(
            "TranslatorService: %s→%s '%s' → '%s'",
            source_language or "auto", target_language, text[:40], translated[:40],
        )
        return translated

    @property
    def is_enabled(self) -> bool:
        return self._enabled
