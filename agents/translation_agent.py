"""Translation Agent — adapts text for sign-language and translates across languages."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, List, Optional, cast

from agents.base_agent import BaseAgent
from mcp.mcp_client import MCPClient, mcp_client as _default_mcp_client
from shared.message_schema import (
    AccessibleMessage,
    Language,
    MessageType,
    RoutedMessage,
    TranslatedMessage,
)

if TYPE_CHECKING:
    from agents.agent_bus import AsyncAgentBus
    from shared.message_schema import BaseMessage

logger = logging.getLogger(__name__)

_LANGUAGE_MAP = {
    "en-US": Language.EN_US,
    "pt-BR": Language.PT_BR,
    "es": Language.ES,
    "fr": Language.FR,
    "de": Language.DE,
}


class TranslationAgent(BaseAgent):
    """Adapts messages for sign-language delivery and translates across languages."""

    # Agent Mesh: consume ROUTED events from the bus (fan-out parallel path)
    # NOTE: TranslationAgent subscribes to ROUTED (not ACCESSIBLE) so it runs
    # in parallel with AccessibilityAgent — neither waits for the other.
    subscribes_to: ClassVar[List[MessageType]] = [MessageType.ROUTED]

    def __init__(
        self,
        target_language: str = "en-US",
        mcp_client: Optional[MCPClient] = None,
    ) -> None:
        self._target_lang = _LANGUAGE_MAP.get(target_language, Language.EN_US)
        self._mcp_client = mcp_client or _default_mcp_client

    async def process(
        self,
        msg: AccessibleMessage,
        source_language: str = "en-US",
        target_language_code: Optional[str] = None,
    ) -> TranslatedMessage:
        """
        Translate the message into the target language.
        Only runs when source and target languages differ (base language codes).
        Sign-language adaptation has been removed — all output is plain text.
        """
        source_lang = _LANGUAGE_MAP.get(source_language, Language.EN_US)
        effective_target = target_language_code or source_language

        translated_text = msg.text
        source_base = source_language.split("-")[0]
        target_base = effective_target.split("-")[0]

        if source_base != target_base:
            logger.info(
                "TranslationAgent.process — session=%s lang=%s→%s text=%s",
                msg.session_id, source_language, effective_target, msg.text[:80],
            )
            translate_result = await self._mcp_client.call_tool(
                "text_translation_tool",
                text=msg.text,
                action="translate",
                source_language=source_language,
                target_language=effective_target,
            )
            if translate_result.success and translate_result.data:
                translated_text = translate_result.data.get("translated_text") or msg.text
                provider = translate_result.data.get("provider", "unknown")
                logger.debug(
                    "TranslationAgent: translated via %s → '%s'", provider, translated_text[:60]
                )
            else:
                logger.warning(
                    "TranslationAgent: text_translation_tool failed — %s",
                    translate_result.error if translate_result else "no result",
                )

        target_lang_enum = _LANGUAGE_MAP.get(effective_target, source_lang)
        metadata = dict(msg.metadata)
        if translated_text and translated_text != msg.text:
            metadata["translated_text"] = translated_text

        return TranslatedMessage(
            session_id=msg.session_id,
            sender_id=msg.sender_id,
            original_text=msg.text,
            translated_text=translated_text,
            source_language=source_lang,
            target_language=target_lang_enum,
            metadata=metadata,
        )

    # ── Agent Mesh handler ────────────────────────────────────────────

    async def handle(self, event: "BaseMessage", bus: "AsyncAgentBus") -> None:
        """
        Receive a RoutedMessage directly from the bus (fan-out parallel with
        AccessibilityAgent), adapt for sign language, translate, and publish
        TranslatedMessage for AccessibilityAgent fan-in.

        Key architectural decision: subscribing to ROUTED instead of
        ACCESSIBLE means TranslationAgent runs concurrently with
        AccessibilityAgent — true parallel fan-out.
        """
        correlation_id = event.metadata.get("correlation_id", event.message_id)
        try:
            routed = cast(RoutedMessage, event)
            if "translation_agent" not in routed.target_agents:
                logger.debug("TranslationAgent: skipped (not in target_agents)")
                return

            target_language = routed.metadata.get("target_language", "en-US")
            source_language = routed.metadata.get("language", "en-US")

            # Build minimal AccessibleMessage for process() — same pattern as
            # the old pipeline’s minimal_for_translation
            minimal = AccessibleMessage(
                session_id=routed.session_id,
                sender_id=routed.sender_id,
                message_type=MessageType.ACCESSIBLE,
                text=routed.text,
                features_applied=[],
                metadata={**routed.metadata, "correlation_id": correlation_id},
            )

            # process() is fully async — await directly, no thread pool needed.
            translated = await self.process(minimal, source_language, target_language)
            translated.metadata["correlation_id"] = correlation_id
            await bus.publish(translated)
        except Exception as exc:
            logger.error("TranslationAgent.handle error: %s", exc, exc_info=True)

