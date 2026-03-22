"""Central registry connecting tool names to class instances."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from mcp.schemas.tool_schema import PropertySchema, ToolDefinition, ToolInputSchema
from mcp.tools.gesture_recognition_tool import GestureRecognitionTool
from mcp.tools.llm_classify_tool import LLMClassifyTool
from mcp.tools.meeting_summary_tool import MeetingSummaryTool
from mcp.tools.speech_to_text_tool import SpeechToTextTool
from mcp.tools.text_to_sign_tool import TextToSignTool
from mcp.tools.text_to_speech_tool import TextToSpeechTool
from mcp.tools.text_translation_tool import TextTranslationTool

logger = logging.getLogger(__name__)


def _build_definition(tool: Any) -> ToolDefinition:
    """Convert a tool's class-level metadata into a ToolDefinition."""
    raw_schema: Dict[str, Any] = getattr(tool, "input_schema", {})
    input_schema = ToolInputSchema(
        type=raw_schema.get("type", "object"),
        required=raw_schema.get("required", []),
        properties={
            k: PropertySchema(
                type=v.get("type", "string"),
                description=v.get("description"),
                default=v.get("default"),
            )
            for k, v in raw_schema.get("properties", {}).items()
        },
    )
    return ToolDefinition(
        name=tool.name,
        description=tool.description,
        input_schema=input_schema,
    )


class ToolRegistry:
    """Holds all registered MCP tools indexed by name."""

    def __init__(self) -> None:
        self._tools: Dict[str, Any] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            SpeechToTextTool(),
            GestureRecognitionTool(),
            TextToSignTool(),
            TextToSpeechTool(),
            MeetingSummaryTool(),
            LLMClassifyTool(),
            TextTranslationTool(),
        ]
        for tool in defaults:
            self.register(tool)

    def register(self, tool: Any) -> None:
        """Add a tool instance to the registry."""
        if not hasattr(tool, "name") or not hasattr(tool, "execute"):
            raise ValueError(f"Tool {tool!r} must have 'name' and 'execute' attributes.")
        self._tools[tool.name] = tool
        logger.debug("ToolRegistry: registered '%s'", tool.name)

    def get(self, name: str) -> Optional[Any]:
        """Return the tool instance for *name*, or None if not found."""
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("ToolRegistry: tool '%s' not found.", name)
        return tool

    def list_definitions(self) -> List[ToolDefinition]:
        """Return a ToolDefinition for every registered tool."""
        return [_build_definition(t) for t in self._tools.values()]

    def list_names(self) -> List[str]:
        """Return the names of all registered tools."""
        return list(self._tools.keys())


# Module-level singleton used by the MCP server and agents.
registry = ToolRegistry()
