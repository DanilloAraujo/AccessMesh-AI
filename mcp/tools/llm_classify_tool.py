"""
MCP Tool: llm_classify_tool

Uses Azure OpenAI GPT-4o-mini to classify a text message and determine
which agents should process it in the AccessMesh-AI pipeline.

Returns a JSON array of agent names selected based on message intent,
enabling intelligent routing without bypassing the MCP protocol boundary.

This tool replaces the direct OpenAI HTTP call that was previously embedded
in RouterAgent._classify_with_llm, restoring the clean separation between
the agent layer (RouterAgent) and the tool/model layer (MCP tools).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

_DEFAULT_AGENTS: List[str] = ["accessibility_agent"]

_SYSTEM_PROMPT = (
    "You are a routing assistant for an accessible meeting platform for deaf and "
    "hearing-impaired users. The pipeline has one processing agent: accessibility_agent. "
    "For any natural-language input activate: ['accessibility_agent']. "
    "You may return an empty list ONLY for pure system commands such as "
    "digits-only ('123'), punctuation-only, or explicit commands like '/mute'. "
    "Return ONLY a JSON array of agent names, e.g. "
    '["accessibility_agent"]'
)


class LLMClassifyTool:
    """
    MCP tool that classifies a text message via Azure OpenAI GPT-4o-mini
    to determine which pipeline agents should handle it.

    name        : llm_classify_tool
    description : Classifies a text message to determine which AccessMesh-AI
                  pipeline agents should process it (routing decision).
                  Returns a list of agent names. Falls back to all agents when
                  the LLM is unavailable.
    """

    name: str = "llm_classify_tool"
    description: str = (
        "Classifies a text message using Azure OpenAI GPT-4o-mini to determine "
        "which pipeline agents should process it. Returns a JSON array of agent "
        "names. Falls back to activating all agents when LLM is unavailable."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": "Text message to classify (max 200 chars used).",
            },
        },
    }

    def __init__(self) -> None:
        self._openai = OpenAIService()

    def execute(self, text: str) -> Dict[str, Any]:
        """
        Classify the message intent and return the agent list.

        Returns
        -------
        {
            "agents" : list[str]  ordered list of agent names to activate
            "stub"   : bool       True when LLM is unavailable (default routing used)
        }
        """
        if not self._openai.is_enabled:
            logger.debug("LLMClassifyTool: credentials not configured — using default routing.")
            return {"agents": _DEFAULT_AGENTS, "stub": True}

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"Message: {text[:200]}"},
        ]
        try:
            content = self._openai.chat_complete_sync(
                messages, max_tokens=64, temperature=0.0
            )
            if content:
                agents = json.loads(content)
                if isinstance(agents, list) and agents:
                    logger.debug("LLMClassifyTool: classified agents=%s", agents)
                    return {"agents": agents, "stub": False}
        except Exception as exc:
            logger.debug("LLMClassifyTool: LLM call failed — using default routing: %s", exc)

        return {"agents": _DEFAULT_AGENTS, "stub": True}
