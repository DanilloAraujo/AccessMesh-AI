"""Avatar Agent — converts sign-adapted text into a gloss sequence for rendering."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, List, Optional, cast

from agents.base_agent import BaseAgent
from mcp.mcp_client import MCPClient, mcp_client as _default_mcp_client
from shared.message_schema import (
    AccessibilityFeature,
    AccessibleMessage,
    AvatarReadyMessage,
    MessageType,
    TranslatedMessage,
)

if TYPE_CHECKING:
    from agents.agent_bus import AsyncAgentBus
    from shared.message_schema import BaseMessage

logger = logging.getLogger(__name__)


class AvatarAgent(BaseAgent):
    """Generates the final sign-language gloss sequence from sign-adapted text."""

    # Agent Mesh: consume TRANSLATED events; fan-in ACCESSIBLE via wait_for_correlated
    subscribes_to: ClassVar[List[MessageType]] = [MessageType.TRANSLATED]

    def __init__(self, mcp_client: Optional[MCPClient] = None) -> None:
        self._mcp_client = mcp_client or _default_mcp_client

    async def process(self, msg: AccessibleMessage) -> AvatarReadyMessage:
        metadata = msg.metadata or {}
        sign_adapted_text: str = metadata.get("sign_adapted_text") or ""

        # Use sign-adapted text when available; fall back to the original text.
        # Never skip: gloss generation always runs (AccessibilityAgent no longer calls
        # text_to_sign_tool, so AvatarAgent is the sole source of the gloss sequence).
        source_text = sign_adapted_text if (sign_adapted_text and sign_adapted_text != msg.text) else msg.text

        # Derive sign language from the message language (libras for pt-*, asl for en-*).
        _sign_lang_map = {"pt": "libras", "pt-br": "libras", "en": "asl", "en-us": "asl"}
        msg_language: str = metadata.get("language", "en-US").lower()
        sign_language = _sign_lang_map.get(msg_language, _sign_lang_map.get(msg_language.split("-")[0], "libras"))

        logger.info(
            "AvatarAgent.process — session=%s source='%s' sign_lang=%s adapted=%s",
            msg.session_id, source_text[:80], sign_language,
            "yes" if source_text != msg.text else "no",
        )
        sign_result = await self._mcp_client.call_tool(
            "text_to_sign_tool", text=source_text, sign_language=sign_language
        )
        if sign_result.success and sign_result.data:
            new_gloss = sign_result.data.get("gloss_sequence", [])
            if new_gloss:
                msg.metadata["gloss_sequence"] = new_gloss
        else:
            logger.warning(
                "AvatarAgent: text_to_sign_tool failed — gloss will be empty. %s",
                sign_result.error if sign_result else "no result",
            )

        gloss = msg.metadata.get("gloss_sequence")
        ready = AvatarReadyMessage(
            session_id=msg.session_id,
            sender_id=msg.sender_id,
            avatar_url=None,
            animation_data={"gloss_sequence": gloss} if gloss else None,
            metadata={**msg.metadata, "source_message_id": msg.message_id},
        )

        logger.info("AvatarAgent: session=%s gloss_count=%d", msg.session_id, len(gloss) if gloss else 0)
        return ready

    # ── Agent Mesh handler (fan-in) ────────────────────────────────────

    async def handle(self, event: "BaseMessage", bus: "AsyncAgentBus") -> None:
        """
        Fan-in: receives TranslatedMessage (sign_adapted_text) and waits for the
        correlated AccessibleMessage (audio_b64) produced by AccessibilityAgent
        running in parallel.  Merges both, generates final gloss, and publishes
        AvatarReadyMessage — the terminal event collected by pipeline.py.
        """
        correlation_id = event.metadata.get("correlation_id", event.message_id)
        try:
            translated = cast(TranslatedMessage, event)

            # Fan-in: wait for AccessibilityAgent’s output (may already be in store)
            accessible_event = await bus.wait_for_correlated(
                correlation_id, MessageType.ACCESSIBLE, timeout=20.0
            )

            # Merge: sign_adapted_text from TranslationAgent + audio_b64 from AccessibilityAgent
            merged_meta: dict = dict(translated.metadata)
            merged_meta["original_text"] = translated.original_text

            if accessible_event is not None:
                acc_meta = getattr(accessible_event, "metadata", {}) or {}
                for key in ("audio_b64", "audio_content_type", "gloss_sequence"):
                    if acc_meta.get(key):
                        merged_meta.setdefault(key, acc_meta[key])
            else:
                logger.warning(
                    "AvatarAgent.handle: timeout waiting for ACCESSIBLE corr=%s — continuing without TTS",
                    correlation_id,
                )

            merged_accessible = AccessibleMessage(
                session_id=translated.session_id,
                sender_id=translated.sender_id,
                message_type=MessageType.ACCESSIBLE,
                text=translated.original_text,
                features_applied=[AccessibilityFeature.SIGN_LANGUAGE],
                metadata=merged_meta,
            )

            avatar_ready = await self.process(merged_accessible)
            avatar_ready.metadata["correlation_id"] = correlation_id
            # Preserve original text for SummaryAgent passive accumulation
            avatar_ready.metadata["original_text"] = translated.original_text
            await bus.publish(avatar_ready)
        except Exception as exc:
            logger.error("AvatarAgent.handle error: %s", exc, exc_info=True)
