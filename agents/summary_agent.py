"""Summary Agent — generates structured meeting summaries from transcripts.

Architecture note
-----------------
The SummaryAgent is STATELESS.  It no longer accumulates events in memory.

Trigger: SUMMARY_REQUEST event on the Agent Bus.
  • With Service Bus: published by POST /chat/summary/{session_id},
    forwarded to sub-summary-request, consumed here via _receive_loop.
  • Without Service Bus (local dev): dispatched in-process directly.

Data source: CosmosService.get_messages() — the single source of truth
  shared across all instances.  Falls back to the in-memory session_store
  when Cosmos is unavailable (local dev without credentials).

Output: SUMMARY event published on the bus.
  • Forwarded to Azure SB topic sub-summary for external consumers.
  • Delivered via WebPubSub to all frontend clients in the session.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Sequence, Union

from agents.base_agent import BaseAgent
from mcp.mcp_client import MCPClient, mcp_client as _default_mcp_client
from shared.message_schema import (
    GestureMessage,
    MeetingSummaryMessage,
    MessageType,
    TranscriptionMessage,
)

if TYPE_CHECKING:
    from agents.agent_bus import AsyncAgentBus
    from shared.message_schema import BaseMessage
    from services.cosmos_service import CosmosService

logger = logging.getLogger(__name__)

TranscriptEntry = Union[TranscriptionMessage, GestureMessage]


class SummaryAgent(BaseAgent):
    """Stateless agent: triggered by SUMMARY_REQUEST, reads Cosmos, publishes SUMMARY."""

    # Subscribes to SUMMARY_REQUEST — the on-demand trigger from the API.
    # When SB is configured, this event arrives via the _receive_loop from
    # sub-summary-request.  In-process mode: dispatched directly.
    subscribes_to: ClassVar[List[MessageType]] = [MessageType.SUMMARY_REQUEST]

    def __init__(
        self,
        mcp_client: Optional[MCPClient] = None,
        cosmos_service: Optional["CosmosService"] = None,
    ) -> None:
        self._mcp_client = mcp_client or _default_mcp_client
        # CosmosService injected at startup (factory.py). May be None in tests.
        self._cosmos = cosmos_service

    # ── Agent Mesh handler ───────────────────────────────────────────

    async def handle(self, event: "BaseMessage", bus: "AsyncAgentBus") -> None:
        """
        Receive a SUMMARY_REQUEST event, fetch the full session history from
        Cosmos (or memory fallback), call GPT-4o via MCP tool, and publish
        a SUMMARY event back onto the bus.

        The SUMMARY event is then:
          • forwarded to Azure SB sub-summary (external consumers)
          • delivered via WebPubSub to all frontend participants
        """
        session_id = event.session_id
        host_user_id = event.metadata.get("requested_by", event.sender_id)

        logger.info(
            "SummaryAgent.handle: SUMMARY_REQUEST received session=%s requested_by=%s",
            session_id, host_user_id,
        )

        try:
            summary_msg = await self._generate(session_id, host_user_id)
            await bus.publish(summary_msg)
            logger.info(
                "SummaryAgent: SUMMARY published session=%s messages=%d",
                session_id, summary_msg.total_messages,
            )
        except Exception as exc:
            logger.error("SummaryAgent.handle error: %s", exc, exc_info=True)

    # ── Core generation logic ───────────────────────────────────────────

    async def _generate(
        self,
        session_id: str,
        host_user_id: str = "system",
    ) -> MeetingSummaryMessage:
        """
        Fetch message history and generate a MeetingSummaryMessage.

        Data priority:
          1. CosmosService.get_messages() — durable, cross-instance
          2. session_store (in-memory fallback for local dev)
        """
        raw_messages: List[Dict[str, Any]] = []

        if self._cosmos and self._cosmos.is_enabled:
            try:
                raw_messages = await self._cosmos.get_messages(session_id)
                logger.info(
                    "SummaryAgent: loaded %d messages from Cosmos session=%s",
                    len(raw_messages), session_id,
                )
            except Exception as exc:
                logger.warning(
                    "SummaryAgent: Cosmos read failed — falling back to memory: %s", exc
                )

        if not raw_messages:
            # Local dev fallback
            from backend.app.session_store import get_messages  # noqa: PLC0415
            raw_messages = get_messages(session_id)
            logger.info(
                "SummaryAgent: loaded %d messages from memory session=%s",
                len(raw_messages), session_id,
            )

        texts = [m.get("content", "") for m in raw_messages if m.get("content", "").strip()]
        participant_ids = list({m["sender_id"] for m in raw_messages if m.get("sender_id")})

        if not texts:
            logger.warning("SummaryAgent: no content found for session=%s", session_id)
            return MeetingSummaryMessage(
                session_id=session_id,
                sender_id=host_user_id,
                message_type=MessageType.SUMMARY,
                summary_text="No messages recorded for this session yet.",
                key_points=[],
                participant_ids=participant_ids,
                total_messages=0,
            )

        result = await self._mcp_client.call_tool(
            "meeting_summary_tool",
            transcript_texts=texts,
            session_id=session_id,
            participant_ids=participant_ids,
        )
        if not result.success:
            raise RuntimeError(
                f"SummaryAgent: meeting_summary_tool failed — {result.error}"
            )
        assert result.data is not None

        logger.info(
            "SummaryAgent: generated summary session=%s participants=%d messages=%d stub=%s",
            session_id,
            len(participant_ids),
            len(texts),
            result.data.get("stub", False),
        )
        return MeetingSummaryMessage(
            session_id=session_id,
            sender_id=host_user_id,
            message_type=MessageType.SUMMARY,
            summary_text=result.data["summary_text"],
            key_points=result.data.get("key_points", []),
            participant_ids=result.data.get("participant_ids", participant_ids),
            total_messages=result.data.get("total_messages", len(texts)),
        )

    # ── Backwards-compatible helpers (kept for routes that call directly) ───

    async def process_session(
        self,
        entries: Sequence[TranscriptEntry],
        *,
        session_id: str,
        host_user_id: str = "system",
    ) -> MeetingSummaryMessage:
        """Kept for backwards compatibility.  Prefer the bus-driven SUMMARY_REQUEST path."""
        transcript_texts = [e.text for e in entries if e.text]
        participant_ids = list({e.sender_id for e in entries})
        result = await self._mcp_client.call_tool(
            "meeting_summary_tool",
            transcript_texts=transcript_texts,
            session_id=session_id,
            participant_ids=participant_ids,
        )
        if not result.success:
            raise RuntimeError(
                f"SummaryAgent: meeting_summary_tool failed — {result.error}"
            )
        assert result.data is not None
        return MeetingSummaryMessage(
            session_id=session_id,
            sender_id=host_user_id,
            message_type=MessageType.SUMMARY,
            summary_text=result.data["summary_text"],
            key_points=result.data.get("key_points", []),
            participant_ids=result.data.get("participant_ids", participant_ids),
            total_messages=result.data.get("total_messages", len(transcript_texts)),
        )

    async def generate_meeting_minutes(
        self,
        session_id: str,
        host_user_id: str = "system",
    ) -> MeetingSummaryMessage:
        """Kept for backwards compatibility.  Prefer the bus-driven SUMMARY_REQUEST path."""
        return await self._generate(session_id, host_user_id)

