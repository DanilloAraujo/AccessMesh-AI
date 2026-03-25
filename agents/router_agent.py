"""
Router Agent — decides which downstream agents process each transcription.

Role (Agent Mesh): router_agent

Routing policy (deterministic, no LLM overhead):
  - All messages → accessibility_agent (subtitles, sign-language accessibilty)

Input : TranscriptionMessage
Output: RoutedMessage
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, List

from agents.base_agent import BaseAgent
from shared.message_schema import MessageType, RoutedMessage, TranscriptionMessage

if TYPE_CHECKING:
    from agents.agent_bus import AsyncAgentBus
    from shared.message_schema import BaseMessage

logger = logging.getLogger(__name__)

_ALL_AGENTS: List[str] = ["accessibility_agent", "speech_agent"]
_TEXT_ONLY_AGENTS: List[str] = ["accessibility_agent"]


class RouterAgent(BaseAgent):
    """
    Analyses a TranscriptionMessage and returns a RoutedMessage containing
    the ordered list of agents to invoke.

    Routing is purely rule-based (no LLM call) to keep per-message latency
    under 1 ms.  Full fan-out to both agents is the default for any natural-
    language text; empty/command-only messages skip the translation path.
    """

    # Agent Mesh: consume TRANSCRIPTION events from the bus
    subscribes_to: ClassVar[List[MessageType]] = [MessageType.TRANSCRIPTION]

    async def route(self, msg: TranscriptionMessage) -> RoutedMessage:
        # Route based on communication mode declared in the message metadata.
        # - voice/gesture messages: include speech_agent for TTS output (aids
        #   participants who prefer audio feedback).
        # - text-only messages: skip TTS to avoid echoing typed input as audio.
        communication_mode: str = msg.metadata.get("communication_mode", "voice")
        if communication_mode in ("voice", "gesture"):
            target_agents = _ALL_AGENTS
        else:
            target_agents = _TEXT_ONLY_AGENTS

        routed = RoutedMessage(
            session_id=msg.session_id,
            sender_id=msg.sender_id,
            text=msg.text,
            target_agents=target_agents,
            metadata={**msg.metadata, "source_message_id": msg.message_id},
        )

        logger.info(
            "RouterAgent: session=%s text_len=%d → %s",
            msg.session_id, len(msg.text), target_agents,
        )
        return routed

    # ── Agent Mesh handler ────────────────────────────────────────────

    async def handle(self, event: "BaseMessage", bus: "AsyncAgentBus") -> None:
        """
        Receive a TranscriptionMessage from the bus, run routing logic, and
        publish a RoutedMessage back onto the bus with ``correlation_id``
        propagated for the downstream fan-out.
        """
        correlation_id = event.metadata.get("correlation_id", event.message_id)
        try:
            transcription: TranscriptionMessage = event  # type: ignore[assignment]
            routed = await self.route(transcription)
            routed.metadata["correlation_id"] = correlation_id
            await bus.publish(routed)
        except Exception as exc:
            logger.error("RouterAgent.handle error: %s", exc, exc_info=True)

