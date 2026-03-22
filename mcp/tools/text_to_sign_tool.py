"""
MCP Tool: text_to_sign_tool

Converts sign-language-adapted text into a gloss sequence with animation
metadata for driving the AvatarSignView component.

Uses Azure OpenAI (GPT-4o) to generate linguistically-correct LIBRAS/ASL
gloss tokens. Falls back to simple uppercase tokenisation when credentials
are absent.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

_LANG_DISPLAY = {
    "libras": "Libras (Brazilian Sign Language)",
    "asl": "ASL (American Sign Language)",
}

_SIGN_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can",
    "o", "a", "os", "as", "um", "uma",
}


class TextToSignTool:
    """
    MCP tool that converts sign-adapted text into a gloss sequence.

    Calls GPT-4o to produce linguistically-correct LIBRAS/ASL tokens with
    per-sign animation durations. Loads Azure OpenAI credentials from
    application settings at first use.
    """

    name: str = "text_to_sign_tool"
    description: str = (
        "Converts sign-language-adapted text into a LIBRAS/ASL gloss sequence "
        "with animation timing metadata for real-time avatar rendering."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Sign-adapted text to convert to gloss tokens.",
            },
            "sign_language": {
                "type": "string",
                "default": "libras",
                "description": "Target sign language: 'libras' (Brazilian) or 'asl' (American).",
            },
        },
    }

    def _gloss_with_gpt(self, text: str, sign_language: str) -> List[Dict[str, Any]]:
        """Call Azure OpenAI GPT-4o to generate gloss tokens. Raises on failure."""
        openai = OpenAIService()
        if not openai.is_enabled:
            raise RuntimeError(
                "TextToSignTool: Azure OpenAI not configured — "
                "set AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT."
            )

        lang_name = _LANG_DISPLAY.get(sign_language, sign_language.upper())
        content = openai.chat_complete_sync(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a {lang_name} expert. Convert the input text into a "
                        "sign-language gloss sequence. Return ONLY a JSON array where each "
                        "element has 'gloss' (UPPERCASE sign token) and 'duration_ms' "
                        "(400 for short signs, 600 for standard, 800 for compound signs). "
                        "No markdown, no explanation."
                    ),
                },
                {"role": "user", "content": text},
            ],
            max_tokens=512,
            temperature=0.1,
        )
        if content is None:
            raise RuntimeError(
                "TextToSignTool: Azure OpenAI returned no response for gloss generation."
            )
        if content.startswith("```"):
            content = "\n".join(content.split("\n")[1:-1])
        signs = json.loads(content)
        if isinstance(signs, list):
            return signs
        raise RuntimeError("TextToSignTool: Azure OpenAI returned unexpected response format.")

    def _fallback_gloss(self, text: str) -> List[Dict[str, Any]]:
        """Stopword-stripped uppercase tokenisation when GPT-4o is unavailable."""
        tokens = [
            w.upper() for w in text.split()
            if w.strip() and w.lower().rstrip(".,!?") not in _SIGN_STOPWORDS
        ]
        return [{"gloss": t, "duration_ms": 600} for t in tokens]

    def execute(self, text: str, sign_language: str = "libras") -> Dict[str, Any]:
        signs = self._gloss_with_gpt(text, sign_language)
        gloss_sequence = [s["gloss"] for s in signs if isinstance(s, dict) and "gloss" in s]

        logger.debug(
            "text_to_sign_tool: '%s' → %d gloss tokens (%s)",
            text[:80], len(gloss_sequence), sign_language,
        )

        return {
            "gloss_sequence": gloss_sequence,
            "sign_language": sign_language,
            "animation_hints": {"speed": "normal", "expressiveness": "medium", "signs": signs},
            "original_text": text,
        }
