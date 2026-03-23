"""
mcp/tools/__init__.py
──────────────────────
Exports all MCP tool classes so they can be imported from `mcp.tools`.
"""

from mcp.tools.gesture_recognition_tool import GestureRecognitionTool
from mcp.tools.llm_classify_tool import LLMClassifyTool
from mcp.tools.meeting_summary_tool import MeetingSummaryTool
from mcp.tools.speech_to_text_tool import SpeechToTextTool
from mcp.tools.text_to_speech_tool import TextToSpeechTool
from mcp.tools.text_translation_tool import TextTranslationTool

__all__ = [
    "SpeechToTextTool",
    "GestureRecognitionTool",
    "TextToSpeechTool",
    "MeetingSummaryTool",
    "LLMClassifyTool",
    "TextTranslationTool",
]
