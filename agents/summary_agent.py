"""Summary Agent — generates structured meeting summaries from transcripts."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Sequence, Union

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

logger = logging.getLogger(__name__)

TranscriptEntry = Union[TranscriptionMessage, GestureMessage]


class SummaryAgent(BaseAgent):
    """Produces a MeetingSummaryMessage from session transcript entries."""

    # Agent Mesh: passively accumulate every terminal AVATAR_READY event
    subscribes_to: ClassVar[List[MessageType]] = [MessageType.AVATAR_READY]

    def __init__(
        self,
        mcp_client: Optional[MCPClient] = None,
    ) -> None:
        self._mcp_client = mcp_client or _default_mcp_client
        # Passive in-memory accumulator: session_id -> list of utterance texts
        self._session_transcripts: Dict[str, List[str]] = {}

    async def process_session(
        self,
        entries: Sequence[TranscriptEntry],
        *,
        session_id: str,
        host_user_id: str = "system",
    ) -> MeetingSummaryMessage:
        """
        Summarise all transcript entries and return a MeetingSummaryMessage.
        Delegates to the MCP tool ``meeting_summary_tool`` via MCPClient.
        """
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

        logger.info(
            "SummaryAgent: session=%s participants=%d messages=%d stub=%s",
            session_id,
            len(participant_ids),
            len(transcript_texts),
            result.data.get("stub", False),
        )
        return MeetingSummaryMessage(
            session_id=session_id,
            sender_id=host_user_id,
            message_type=MessageType.SUMMARY,
            summary_text=result.data["summary_text"],
            key_points=result.data.get("key_points", []),
            participant_ids=result.data.get("participant_ids", participant_ids),
            total_messages=result.data.get("total_messages", len(transcript_texts)),
        )

    # ── Agent Mesh handler (passive accumulator) ───────────────────────────

    async def handle(self, event: "BaseMessage", bus: "AsyncAgentBus") -> None:
        """
        Passively record the original text of each fully-processed utterance.
        Does NOT publish anything — accumulation is a side-effect only.
        Call ``generate_meeting_minutes()`` to produce the summary on demand.
        """
        try:
            text = (event.metadata or {}).get("original_text", "")
            if text:
                self._session_transcripts.setdefault(event.session_id, []).append(text)
                logger.debug(
                    "SummaryAgent: accumulated session=%s total=%d",
                    event.session_id,
                    len(self._session_transcripts[event.session_id]),
                )
        except Exception as exc:
            logger.error("SummaryAgent.handle error: %s", exc, exc_info=True)

    def get_accumulated_texts(self, session_id: str) -> List[str]:
        """Return accumulated utterances for *session_id* (used by API routes)."""
        return list(self._session_transcripts.get(session_id, []))

    def clear_session(self, session_id: str) -> None:
        """Discard accumulated texts for a session after a summary is generated."""
        self._session_transcripts.pop(session_id, None)

    async def generate_meeting_minutes(
        self,
        session_id: str,
        host_user_id: str = "system",
    ) -> MeetingSummaryMessage:
        """
        Generate a MeetingSummaryMessage from bus-accumulated events.
        Delegates directly to the MCP tool ``meeting_summary_tool`` via MCPClient.
        API routes should call this instead of ``process_session()`` directly.
        """
        texts = self.get_accumulated_texts(session_id)
        if not texts:
            return MeetingSummaryMessage(
                session_id=session_id,
                sender_id=host_user_id,
                message_type=MessageType.SUMMARY,
                summary_text="No speech recorded in this session.",
                key_points=[],
                participant_ids=[],
                total_messages=0,
            )

        result = await self._mcp_client.call_tool(
            "meeting_summary_tool",
            transcript_texts=texts,
            session_id=session_id,
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
            participant_ids=result.data.get("participant_ids", []),
            total_messages=result.data.get("total_messages", len(texts)),
        )
