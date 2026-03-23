"""AgentMeshPipeline — orchestration wrapper over AsyncAgentBus for the Agent Mesh."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from agents.agent_bus import AsyncAgentBus, agent_bus as _default_bus
from shared.message_schema import (
    AccessibilityFeature,
    AccessibleMessage,
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
        pubsub_service=None,
        telemetry=None,
    ) -> None:
        self._bus = bus or _default_bus
        self._pubsub = pubsub_service
        self._telemetry = telemetry

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
        terminal AccessibleMessage produced by AccessibilityAgent (fan-in).

        Pipeline: Router → (AccessibilityAgent ‖ TranslationAgent) → fan-in ACCESSIBLE

        All participants receive text — no TTS, no sign gloss.
        Falls back to a minimal AccessibleMessage on timeout.
        """
        logger.info(
            "Pipeline.run — session=%s user=%s lang=%s→%s text=%s",
            session_id, user_id, language, target_language, text[:80],
        )

        t0 = time.perf_counter()
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
            collect_type=MessageType.ACCESSIBLE,
            timeout=_settings.pipeline_timeout_seconds,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        if terminal is None:
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

        accessible: AccessibleMessage = terminal  # type: ignore[assignment]

        logger.info(
            "Pipeline done — session=%s elapsed_ms=%.0f features=%s translated=%s",
            session_id,
            elapsed_ms,
            [f.value if hasattr(f, "value") else f for f in accessible.features_applied],
            "yes" if accessible.metadata.get("translated_text") else "no",
        )
        return accessible
