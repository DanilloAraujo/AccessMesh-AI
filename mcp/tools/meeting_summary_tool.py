"""
mcp/tools/meeting_summary_tool.py

MCP Tool: meeting_summary_tool

Generates a concise meeting summary from a list of transcript entries
by delegating to SummarizationService — the correct service layer, keeping
tools independent of agents (dependency direction: tools → services).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.summarization_service import SummarizationService

logger = logging.getLogger(__name__)


class MeetingSummaryTool:
    """MCP tool that summarises meeting transcript entries into a brief summary and key points."""

    name: str = "meeting_summary_tool"
    description: str = (
        "Generates a concise meeting summary and key-point list from the "
        "accumulated transcript. Suitable for post-meeting recaps and "
        "accessibility records."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "required": ["transcript_texts", "session_id"],
        "properties": {
            "transcript_texts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of transcribed utterances from the session.",
            },
            "session_id": {
                "type": "string",
                "description": "Active meeting session ID.",
            },
            "participant_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of participant IDs present in the session.",
            },
        },
    }

    def __init__(self, service: Optional[SummarizationService] = None) -> None:
        self._service = service or SummarizationService()

    def execute(
        self,
        transcript_texts: List[str],
        session_id: str,
        participant_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run the tool and return a result dict compatible with the MCP protocol."""
        result: Dict[str, Any] = self._service.summarise_sync(transcript_texts)

        return {
            "summary_text": result.get("summary", ""),
            "key_points": result.get("key_points", []),
            "total_messages": len(transcript_texts),
            "participant_ids": participant_ids or [],
            "session_id": session_id,
            "stub": result.get("stub", False),
        }
