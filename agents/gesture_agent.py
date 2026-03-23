"""
Gesture Agent — converts sign-language signals into text messages.

Role (Agent Mesh): gesture_agent

Accepts gesture labels (from Azure OpenAI Vision frame analysis) and
landmark data (MediaPipe), returning a GestureMessage for pipeline dispatch.
Broadcasting is handled by realtime_dispatcher (Agent Mesh rule).

Input : gesture_label str + optional landmarks dict
Output: GestureMessage | None
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, cast

from agents.base_agent import BaseAgent
from shared.message_schema import GestureMessage, MessageType, TranscriptionMessage

if TYPE_CHECKING:
    from agents.agent_bus import AsyncAgentBus
    from shared.message_schema import BaseMessage

logger = logging.getLogger(__name__)


class GestureAgent(BaseAgent):
    """
    Converts a gesture label or landmark data into a GestureMessage.
    Broadcasting is the realtime_dispatcher’s responsibility (Agent Mesh rule).

    Agent Mesh role: subscribes to GESTURE events, translates the gesture
    label to natural text, and re-publishes a TranscriptionMessage so the
    full pipeline (RouterAgent → Accessibility → Translation → Avatar) runs.
    """

    # Agent Mesh: consume GESTURE events and re-inject as TRANSCRIPTION
    subscribes_to: ClassVar[List[MessageType]] = [MessageType.GESTURE]

    def __init__(self) -> None:
        pass

    def recognize(
        self,
        gesture_label: str,
        landmarks: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, float]:
        """Map a gesture label to natural-language text. Returns (text, confidence)."""
        text = gesture_label.replace("_", " ").capitalize()
        logger.debug("GestureAgent.recognize: '%s' → '%s'", gesture_label, text)
        return text, 1.0

    def process_gesture(
        self,
        gesture_label: str,
        *,
        session_id: str,
        user_id: str,
        landmarks: Optional[Dict[str, Any]] = None,
    ) -> Optional[GestureMessage]:
        """Recognise a gesture and return a GestureMessage, or None if empty."""
        text, confidence = self.recognize(gesture_label, landmarks=landmarks)

        if not text:
            logger.debug(
                "process_gesture: no text produced for gesture '%s', skipping.",
                gesture_label,
            )
            return None

        return GestureMessage(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            sender_id=user_id,
            message_type=MessageType.GESTURE,
            text=text,
            gesture_label=gesture_label,
            confidence=confidence,
        )

    # ── Agent Mesh handler ────────────────────────────────────────────

    async def handle(self, event: "BaseMessage", bus: "AsyncAgentBus") -> None:
        """
        Receive a GestureMessage, map the gesture label to natural-language
        text, and re-publish a TranscriptionMessage so the full Agent Mesh
        pipeline processes it (RouterAgent → AccessibilityAgent →
        TranslationAgent → AccessibilityAgent fan-in).

        This makes gesture input a first-class citizen: it flows through
        exactly the same enrichment pipeline as speech input.
        """
        try:
            gesture_msg = cast(GestureMessage, event)
            landmarks = gesture_msg.metadata.get("landmarks") if gesture_msg.metadata else None
            text, confidence = self.recognize(
                gesture_msg.gesture_label or "",
                landmarks=landmarks,
            )
            if not text:
                logger.debug("GestureAgent.handle: no text extracted, skipping.")
                return

            transcription = TranscriptionMessage(
                session_id=gesture_msg.session_id,
                sender_id=gesture_msg.sender_id,
                message_type=MessageType.TRANSCRIPTION,
                text=text,
                confidence=confidence,
                metadata={
                    **gesture_msg.metadata,
                    # correlation_id == gesture message id so the whole chain
                    # is traceable back to this specific gesture event
                    "correlation_id": gesture_msg.message_id,
                    "source": "gesture",
                },
            )
            await bus.publish(transcription)
        except Exception as exc:
            logger.error("GestureAgent.handle error: %s", exc, exc_info=True)
