"""
Router Agent — decides which downstream agents process each transcription.

Role (Agent Mesh): router_agent

Routing policy:
  1. If text is non-empty, always activate: accessibility_agent, translation_agent, avatar_agent
  2. If AZURE_OPENAI credentials are provided, GPT-4o classifies the intent
     to optionally skip agents (e.g. skip TTS for pure command messages).
  3. Falls back to activating all agents when LLM is unavailable.

Input : TranscriptionMessage
Output: RoutedMessage
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, List, Optional, cast

from agents.base_agent import BaseAgent
from mcp.mcp_client import MCPClient, mcp_client as _default_mcp_client
from shared.message_schema import MessageType, RoutedMessage, TranscriptionMessage

if TYPE_CHECKING:
    from agents.agent_bus import AsyncAgentBus
    from shared.message_schema import BaseMessage

logger = logging.getLogger(__name__)

_DEFAULT_AGENTS: List[str] = ["accessibility_agent", "translation_agent", "avatar_agent"]


class RouterAgent(BaseAgent):
    """
    Analyses a TranscriptionMessage and returns a RoutedMessage containing
    the ordered list of agents to invoke.

    When Azure OpenAI credentials are available, GPT-4o classifies the
    message intent to make intelligent routing decisions. Falls back to
    activating all agents for any non-empty text.
    """

    # Agent Mesh: consume TRANSCRIPTION events from the bus
    subscribes_to: ClassVar[List[MessageType]] = [MessageType.TRANSCRIPTION]

    def __init__(self, mcp_client: Optional[MCPClient] = None) -> None:
        # Routing decisions are delegated to llm_classify_tool via MCP — no direct
        # OpenAI credentials needed here; the tool encapsulates that dependency.
        self._mcp_client = mcp_client or _default_mcp_client

    async def route(self, msg: TranscriptionMessage) -> RoutedMessage:
        target_agents: List[str] = _DEFAULT_AGENTS
        stub = True

        if msg.text.strip():
            # Delegate routing classification to the MCP llm_classify_tool.
            # This keeps the agent layer free of direct LLM/HTTP coupling.
            result = await self._mcp_client.call_tool("llm_classify_tool", text=msg.text)
            if result.success and result.data:
                agents = result.data.get("agents")
                stub = result.data.get("stub", True)
                if isinstance(agents, list) and agents:
                    target_agents = agents

        routed = RoutedMessage(
            session_id=msg.session_id,
            sender_id=msg.sender_id,
            text=msg.text,
            target_agents=target_agents,
            metadata={**msg.metadata, "source_message_id": msg.message_id},
        )

        logger.info(
            "RouterAgent: session=%s text_len=%d → agents=%s (llm_stub=%s)",
            msg.session_id, len(msg.text), target_agents, stub,
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
            transcription = cast(TranscriptionMessage, event)
            # route() is fully async — await directly, no thread pool needed.
            routed = await self.route(transcription)
            routed.metadata["correlation_id"] = correlation_id
            await bus.publish(routed)
        except Exception as exc:
            logger.error("RouterAgent.handle error: %s", exc, exc_info=True)

