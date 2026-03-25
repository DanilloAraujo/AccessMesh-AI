"""
mcp/__init__.py
────────────────
Model Context Protocol package for AccessMesh-AI.

Structure
─────────
mcp/
├ mcp_server.py      — FastAPI MCP server (tools/list, tools/call endpoints)
├ tool_registry.py   — Central registry of all available tools
├ tool_executor.py   — Decoupled executor: run(tool_name, **kwargs) → ToolResult
├ tools/             — Individual tool implementations
│   speech_to_text_tool.py
│   gesture_recognition_tool.py
│   text_to_speech_tool.py
│   text_translation_tool.py
│   meeting_summary_tool.py
│   llm_classify_tool.py
└ schemas/
    tool_schema.py   — Pydantic schemas: ToolDefinition, ToolInputSchema, ToolResult
"""

from mcp.tool_executor import executor
from mcp.tool_registry import registry
from mcp.tools import (
    GestureRecognitionTool,
    LLMClassifyTool,
    MeetingSummaryTool,
    SpeechToTextTool,
    TextToSpeechTool,
    SignToTextTool,
)

__all__ = [
    "registry",
    "executor",
    "SpeechToTextTool",
    "GestureRecognitionTool",
    "TextToSpeechTool",
    "SignToTextTool",
    "MeetingSummaryTool",
    "LLMClassifyTool",
]
