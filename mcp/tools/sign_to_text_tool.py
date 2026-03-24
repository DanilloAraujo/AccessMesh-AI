"""
MCP Tool: sign_to_text_tool

Adapts spoken-language text into sign-language grammatical structure
(LIBRAS / ASL) using Azure OpenAI GPT-4o, enabling bidirectional
translation between spoken language and signed representations.

Supported actions
-----------------
adapt_for_sign
    Rewrites input text to match sign-language grammatical structure
    (topic-comment order, content-words only) using Azure OpenAI GPT-4o.
    Required params: text, sign_language ("libras" | "asl")
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

_SIGN_LANG_NAMES = {
    "libras": "Libras (Brazilian Sign Language)",
    "asl": "ASL (American Sign Language)",
}


class SignToTextTool:
    """
    MCP tool that adapts spoken-language text for sign-language delivery
    using Azure OpenAI GPT-4o.

    name        : sign_to_text_tool
    description : Adapts text into sign-language grammatical structure (LIBRAS/ASL)
                  via Azure OpenAI GPT-4o.
    """

    name: str = "sign_to_text_tool"
    description: str = (
        "Adapts spoken-language text into sign-language grammatical structure "
        "(LIBRAS / ASL) using Azure OpenAI GPT-4o. Rewrites text with "
        "topic-comment order and content-words only."
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
                "description": "'adapt_for_sign'.",
            },
            "sign_language": {
                "type": "string",
                "description": "Sign language for adaptation: 'libras' or 'asl'.",
                "default": "asl",
            },
        },
    }

    def __init__(self) -> None:
        self._openai = OpenAIService()

    # ── Internal helpers ──────────────────────────────────────────────

    def _adapt_for_sign(self, text: str, sign_language: str) -> str:
        if not self._openai.is_enabled:
            raise RuntimeError(
                "SignToTextTool: Azure OpenAI not configured — "
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
            "SignToTextTool: Azure OpenAI returned empty response for sign-language adaptation."
        )

    # ── MCP entry point ───────────────────────────────────────────────

    def execute(
        self,
        text: str,
        action: str,
        sign_language: str = "asl",
    ) -> Dict[str, Any]:
        """
        Execute the sign-language adaptation.

        Returns
        -------
        For action='adapt_for_sign':
            {"adapted_text": str, "sign_language": str}
        """
        if action == "adapt_for_sign":
            adapted = self._adapt_for_sign(text, sign_language)
            return {"adapted_text": adapted, "sign_language": sign_language}

        raise ValueError(
            f"SignToTextTool: unknown action '{action}'. Expected 'adapt_for_sign'."
        )
