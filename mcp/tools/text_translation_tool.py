"""
MCP Tool: text_translation_tool

Encapsulates all Azure OpenAI / Azure AI Translator calls that the
TranslationAgent previously made directly, restoring the clean separation
between the agent layer and the tool/model layer.

Supported actions
-----------------
adapt_for_sign
    Rewrites input text to match sign-language grammatical structure
    (topic-comment order, content-words only) using Azure OpenAI GPT-4o.
    Required params: text, sign_language ("libras" | "asl")

translate
    Translates text between spoken languages.
    Uses Azure AI Translator (fast, dedicated) as the primary path and
    falls back to Azure OpenAI GPT-4o when the Translator is not configured.
    Required params: text, source_language, target_language
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

_SIGN_LANG_NAMES = {
    "libras": "Libras (Brazilian Sign Language)",
    "asl": "ASL (American Sign Language)",
}


class TextTranslationTool:
    """
    MCP tool that provides sign-language structural adaptation and spoken-language
    translation via Azure OpenAI and Azure AI Translator.

    name        : text_translation_tool
    description : Sign-language adaptation (GPT-4o) and spoken-language
                  translation (Azure AI Translator + GPT-4o fallback).
    """

    name: str = "text_translation_tool"
    description: str = (
        "Adapts text for sign-language grammatical structure (LIBRAS/ASL) "
        "and translates between spoken languages using Azure AI Translator "
        "with Azure OpenAI GPT-4o as fallback."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "required": ["text", "action"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Input text to process.",
            },
            "action": {
                "type": "string",
                "description": "'adapt_for_sign' or 'translate'.",
            },
            "sign_language": {
                "type": "string",
                "description": "Sign language for adaptation: 'libras' or 'asl'. "
                               "Required when action='adapt_for_sign'.",
                "default": "libras",
            },
            "source_language": {
                "type": "string",
                "description": "BCP-47 source language tag (e.g. 'pt-BR'). "
                               "Required when action='translate'.",
                "default": "en-US",
            },
            "target_language": {
                "type": "string",
                "description": "BCP-47 target language tag (e.g. 'en-US'). "
                               "Required when action='translate'.",
                "default": "en-US",
            },
        },
    }

    def __init__(
        self,
        translator_service=None,
    ) -> None:
        self._openai = OpenAIService()

        if translator_service is None:
            try:
                from services.translator_service import TranslatorService  # noqa: PLC0415
                translator_service = TranslatorService()
            except Exception:
                translator_service = None
        self._translator = translator_service

    # ── Internal helpers ──────────────────────────────────────────────

    def _adapt_for_sign(self, text: str, sign_language: str) -> str:
        if not self._openai.is_enabled:
            raise RuntimeError(
                "TextTranslationTool: Azure OpenAI not configured — "
                "set AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT for sign-language adaptation."
            )
        lang_name = _SIGN_LANG_NAMES.get(sign_language, sign_language.upper())
        adapted = self._openai.chat_complete_sync(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a {lang_name} expert. "
                        "Adapt the input text to sign-language grammatical structure: "
                        "use topic-comment order, remove articles and auxiliary verbs, "
                        "keep only content words. Return ONLY the adapted text, no explanation."
                    ),
                },
                {"role": "user", "content": text},
            ],
            max_tokens=256,
        )
        if adapted:
            return adapted
        raise RuntimeError(
            "TextTranslationTool: Azure OpenAI returned empty response for sign-language adaptation."
        )

    def _translate_with_azure(self, text: str, source_language: str, target_language: str) -> Optional[str]:
        """Try Azure AI Translator. Returns None when not configured or on error."""
        if not self._translator:
            return None
        try:
            import asyncio  # noqa: PLC0415
            is_enabled = getattr(self._translator, "is_enabled", False)
            if not is_enabled:
                return None
            # TranslatorService.translate is async — run synchronously inside the tool executor thread.
            result = asyncio.run(
                self._translator.translate(text, target_language, source_language)
            )
            return result if result and result != text else None
        except Exception as exc:
            logger.warning("TextTranslationTool: Azure Translator failed: %s", exc)
            return None

    def _translate_with_gpt(self, text: str, source_language: str, target_language: str) -> str:
        translated = self._openai.chat_complete_sync(
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional translator. Reply with ONLY the translated text.",
                },
                {
                    "role": "user",
                    "content": f"Translate from {source_language} to {target_language}:\n\n{text}",
                },
            ],
            max_tokens=512,
        )
        if translated:
            return translated
        raise RuntimeError(
            f"TextTranslationTool: Azure OpenAI returned empty translation "
            f"for {source_language}→{target_language}."
        )

    # ── MCP entry point ───────────────────────────────────────────────

    def execute(
        self,
        text: str,
        action: str,
        sign_language: str = "libras",
        source_language: str = "en-US",
        target_language: str = "en-US",
    ) -> Dict[str, Any]:
        """
        Execute the requested translation action.

        Returns
        -------
        For action='adapt_for_sign':
            {"adapted_text": str, "sign_language": str}

        For action='translate':
            {"translated_text": str, "provider": "azure_translator" | "openai" | "passthrough"}
        """
        if action == "adapt_for_sign":
            adapted = self._adapt_for_sign(text, sign_language)
            return {"adapted_text": adapted, "sign_language": sign_language}

        if action == "translate":
            source_base = source_language.split("-")[0]
            target_base = target_language.split("-")[0]
            if source_base == target_base:
                return {"translated_text": text, "provider": "passthrough"}

            azure_result = self._translate_with_azure(text, source_language, target_language)
            if azure_result:
                logger.debug("TextTranslationTool: translated via Azure Translator")
                return {"translated_text": azure_result, "provider": "azure_translator"}

            gpt_result = self._translate_with_gpt(text, source_language, target_language)
            logger.debug("TextTranslationTool: translated via OpenAI GPT")
            return {"translated_text": gpt_result, "provider": "openai"}

        raise ValueError(
            f"TextTranslationTool: unknown action '{action}'. "
            "Expected 'adapt_for_sign' or 'translate'."
        )
