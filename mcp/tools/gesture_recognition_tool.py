"""
mcp/tools/gesture_recognition_tool.py

MCP Tool: gesture_recognition_tool

Converts a sign-language gesture label (or raw landmark data) into natural
text by delegating to GestureService — the correct service layer, keeping
tools independent of agents (dependency direction: tools → services).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.gesture_service import GestureService

logger = logging.getLogger(__name__)


class GestureRecognitionTool:
    """MCP tool that maps a gesture label or hand-landmark payload to natural-language text."""

    name: str = "gesture_recognition_tool"
    description: str = (
        "Converts a sign-language gesture label or hand-landmark data into "
        "natural-language text. Intended for Libras / ASL input captured by "
        "the GestureCamera frontend component."
    )
    input_schema: Dict[str, Any] = {
        "type": "object",
        "required": ["gesture_label", "session_id", "user_id"],
        "properties": {
            "gesture_label": {
                "type": "string",
                "description": "Raw gesture/sign identifier detected by the pose model.",
            },
            "session_id": {
                "type": "string",
                "description": "Active meeting session ID.",
            },
            "user_id": {
                "type": "string",
                "description": "ID of the participant performing the gesture.",
            },
            "landmarks": {
                "type": "object",
                "description": "Optional hand/body landmark dictionary for advanced models.",
            },
        },
    }

    def __init__(self, service: Optional[GestureService] = None) -> None:
        self._service = service or GestureService()

    def execute(
        self,
        gesture_label: str,
        session_id: str,
        user_id: str,
        landmarks: Optional[List[Dict[str, float]]] = None,
    ) -> Dict[str, Any]:
        """Run the tool and return a result dict compatible with the MCP protocol."""
        if landmarks and len(landmarks) >= 21:
            result = GestureService._classify_landmarks_rule_based(landmarks)
        else:
            result = self._service.recognise_from_label(gesture_label)

        text: str = result.get("text", "") or gesture_label.replace("_", " ").capitalize()
        confidence: float = result.get("confidence", 0.0)

        if not text:
            return {
                "text": "",
                "gesture_label": gesture_label,
                "confidence": 0.0,
                "session_id": session_id,
                "user_id": user_id,
            }

        return {
            "text": text,
            "gesture_label": gesture_label,
            "confidence": confidence,
            "session_id": session_id,
            "user_id": user_id,
        }
