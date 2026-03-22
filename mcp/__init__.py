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
│   text_to_sign_tool.py
│   text_to_speech_tool.py
│   meeting_summary_tool.py
└ schemas/
    tool_schema.py   — Pydantic schemas: ToolDefinition, ToolInputSchema, ToolResult
"""

from mcp.tool_executor import executor
from mcp.tool_registry import registry
from mcp.tools import (
    GestureRecognitionTool,
    MeetingSummaryTool,
    SpeechToTextTool,
    TextToSignTool,
    TextToSpeechTool,
)

__all__ = [
    "registry",
    "executor",
    "SpeechToTextTool",
    "GestureRecognitionTool",
    "TextToSignTool",
    "TextToSpeechTool",
    "MeetingSummaryTool",
]
