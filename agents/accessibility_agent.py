"""Accessibility Agent — terminal fan-in agent: enriches text with translation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, List, Optional, cast

from agents.base_agent import BaseAgent
from shared.message_schema import (
    AccessibilityFeature,
    AccessibleMessage,
    MessageType,
    RoutedMessage,
)

if TYPE_CHECKING:
    from agents.agent_bus import AsyncAgentBus
    from shared.message_schema import BaseMessage

logger = logging.getLogger(__name__)


class AccessibilityAgent(BaseAgent):
    """Enriches messages with multimodal accessibility features."""

    # Agent Mesh: consume ROUTED events from the bus
    subscribes_to: ClassVar[List[MessageType]] = [MessageType.ROUTED]

    async def process(
        self,
        msg: RoutedMessage,
        translated_text: Optional[str] = None,
    ) -> AccessibleMessage:
        features = [AccessibilityFeature.SUBTITLES]
        metadata = dict(msg.metadata)

        logger.info("AccessibilityAgent.process — session=%s text=%s", msg.session_id, msg.text[:80])

        if translated_text and translated_text != msg.text:
            metadata["translated_text"] = translated_text

        return AccessibleMessage(
            session_id=msg.session_id,
            sender_id=msg.sender_id,
            text=msg.text,
            features_applied=features,
            aria_labels={
                "role": "log",
                "aria-live": "polite",
                "aria-label": f"Caption from {msg.sender_id}: {msg.text}",
            },
            metadata=metadata,
        )

    # ── Agent Mesh handler (fan-in) ───────────────────────────────────

    async def handle(self, event: "BaseMessage", bus: "AsyncAgentBus") -> None:
        """
        Fan-in terminal handler:
        1. Receives RoutedMessage.
        2. If translation_agent is in the pipeline, waits for correlated TRANSLATED.
        3. Merges translated text and publishes ACCESSIBLE as the terminal event.
        """
        correlation_id = event.metadata.get("correlation_id", event.message_id)
        try:
            routed = cast(RoutedMessage, event)

            translated_text: Optional[str] = None
            if "translation_agent" in routed.target_agents:
                translated_event = await bus.wait_for_correlated(
                    correlation_id, MessageType.TRANSLATED, timeout=4.0
                )
                if translated_event is not None:
                    candidate = getattr(translated_event, "translated_text", None)
                    if candidate and candidate != routed.text:
                        translated_text = candidate
                else:
                    logger.warning(
                        "AccessibilityAgent: timeout waiting for TRANSLATED corr=%s — no translation",
                        correlation_id,
                    )

            accessible = await self.process(routed, translated_text=translated_text)
            accessible.metadata["correlation_id"] = correlation_id
            await bus.publish(accessible)

            logger.info(
                "AccessibilityAgent: session=%s translated=%s",
                routed.session_id, "yes" if translated_text else "no",
            )
        except Exception as exc:
            logger.error("AccessibilityAgent.handle error: %s", exc, exc_info=True)
