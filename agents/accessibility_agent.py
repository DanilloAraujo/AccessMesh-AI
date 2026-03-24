"""Accessibility Agent — terminal fan-in agent: enriches text with accessibility features."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, List, cast

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
    ) -> AccessibleMessage:
        # Base feature: always add subtitles
        features = [AccessibilityFeature.SUBTITLES]
        metadata = dict(msg.metadata)

        # Apply participant-requested accessibility features from metadata.
        # These are set by the frontend when the user configures their preferences
        # (high contrast, large text, sign language overlay).
        requested: list[str] = metadata.get("accessibility_features", [])
        for feat_value in requested:
            try:
                feat = AccessibilityFeature(feat_value)
                if feat not in features:
                    features.append(feat)
            except ValueError:
                pass  # ignore unknown feature values

        logger.info("AccessibilityAgent.process — session=%s features=%s text=%s", msg.session_id, [f.value for f in features], msg.text[:80])

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

    # ── Agent Mesh handler ───────────────────────────────────────────

    async def handle(self, event: "BaseMessage", bus: "AsyncAgentBus") -> None:
        """
        Receives RoutedMessage, enriches it with accessibility features
        (subtitles, ARIA labels), and publishes ACCESSIBLE as the terminal event.
        """
        correlation_id = event.metadata.get("correlation_id", event.message_id)
        try:
            routed = cast(RoutedMessage, event)
            accessible = await self.process(routed)
            accessible.metadata["correlation_id"] = correlation_id
            await bus.publish(accessible)

            logger.info(
                "AccessibilityAgent: session=%s features=%s",
                routed.session_id, accessible.features_applied,
            )
        except Exception as exc:
            logger.error("AccessibilityAgent.handle error: %s", exc, exc_info=True)
