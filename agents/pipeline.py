"""AgentMeshPipeline — orchestration wrapper over AsyncAgentBus for the Agent Mesh."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from agents.agent_bus import AsyncAgentBus, agent_bus as _default_bus
from services.webpubsub_service import WebPubSubService
from shared.message_schema import (
    AccessibilityFeature,
    AccessibleMessage,
    AvatarReadyMessage,
    Language,
    MessageType,
    TranscriptionMessage,
)

logger = logging.getLogger(__name__)

_LANGUAGE_MAP: dict[str, Language] = {
    "en-US": Language.EN_US,
    "pt-BR": Language.PT_BR,
    "es": Language.ES,
    "fr": Language.FR,
    "de": Language.DE,
}


class AgentMeshPipeline:
    """Orchestrates the message processing flow through the Agent Mesh bus."""

    def __init__(
        self,
        bus: Optional[AsyncAgentBus] = None,
        pubsub_service: Optional[WebPubSubService] = None,
        telemetry=None,
    ) -> None:
        self._bus = bus or _default_bus
        self._pubsub = pubsub_service
        self._telemetry = telemetry

    async def _publish(self, group: str, payload: dict) -> None:
        """Non-blocking publish to WebPubSub via thread pool."""
        if not self._pubsub:
            return
        try:
            await asyncio.to_thread(self._pubsub.send_to_group, group=group, message=payload)
        except Exception as exc:
            logger.warning("Failed to publish to WebPubSub: %s", exc)

    async def run(
        self,
        text: str,
        *,
        session_id: str,
        user_id: str,
        language: str = "en-US",
        target_language: str = "en-US",
    ) -> AccessibleMessage:
        """
        Publish a TranscriptionMessage onto the AsyncAgentBus and collect the
        terminal AvatarReadyMessage produced by the agent chain.

        The entire pipeline (Router → Accessibility ‖ Translation → Avatar →
        SummaryAccumulator) executes via the bus without any direct agent
        references here.  This method only knows about the seed event type
        (TRANSCRIPTION) and the terminal event type (AVATAR_READY).

        Falls back to a minimal AccessibleMessage if the bus times out.
        """
        logger.info(
            "Pipeline.run (bus) — session=%s user=%s lang=%s text=%s",
            session_id, user_id, language, text[:80],
        )

        transcription = TranscriptionMessage(
            session_id=session_id,
            sender_id=user_id,
            message_type=MessageType.TRANSCRIPTION,
            text=text,
            confidence=1.0,
            detected_language=_LANGUAGE_MAP.get(language),
            metadata={
                "language": language,
                "target_language": target_language,
            },
        )

        from shared.config import settings as _settings

        terminal = await self._bus.publish_and_collect(
            transcription,
            collect_type=MessageType.AVATAR_READY,
            timeout=_settings.pipeline_timeout_seconds,
        )

        if terminal is None:
            # Timeout — return a minimal subtitle-only result so the caller
            # always gets a usable AccessibleMessage
            logger.warning(
                "Pipeline.run timeout (%.0fs) — returning minimal result for session=%s",
                _settings.pipeline_timeout_seconds, session_id,
            )
            return AccessibleMessage(
                session_id=session_id,
                sender_id=user_id,
                text=text,
                features_applied=[AccessibilityFeature.SUBTITLES],
                aria_labels={
                    "role": "log",
                    "aria-live": "polite",
                    "aria-label": f"Caption from {user_id}: {text}",
                },
                metadata={},
            )

        # Convert AvatarReadyMessage into an AccessibleMessage-compatible
        # object so MessageRouter._build_payload() works unchanged.
        avatar_ready: AvatarReadyMessage = terminal  # type: ignore[assignment]
        meta: dict = dict(avatar_ready.metadata or {})
        gloss = (avatar_ready.animation_data or {}).get("gloss_sequence") or meta.get("gloss_sequence")
        if gloss:
            meta["gloss_sequence"] = gloss

        features = [AccessibilityFeature.SUBTITLES, AccessibilityFeature.SIGN_LANGUAGE]
        if meta.get("audio_b64"):
            features.append(AccessibilityFeature.AUDIO_DESCRIPTION)

        result = AccessibleMessage(
            message_id=avatar_ready.message_id,
            session_id=avatar_ready.session_id,
            sender_id=avatar_ready.sender_id,
            text=meta.get("original_text", text),
            features_applied=features,
            aria_labels={
                "role": "log",
                "aria-live": "polite",
                "aria-label": f"Caption from {avatar_ready.sender_id}: {meta.get('original_text', text)}",
            },
            metadata=meta,
        )

        logger.info(
            "Pipeline done — session=%s features=%s gloss_count=%d audio=%s",
            session_id,
            [f.value if hasattr(f, "value") else f for f in result.features_applied],
            len(meta.get("gloss_sequence") or []),
            "yes" if meta.get("audio_b64") else "no",
        )
        return result
