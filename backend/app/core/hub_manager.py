"""Manages Web PubSub hub groups that map to meeting sessions."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Set

from backend.app.models.meeting_model import Meeting, MeetingStatus, Participant
from services.webpubsub_service import WebPubSubService

logger = logging.getLogger(__name__)


def _cosmos_fire_and_forget(coro) -> None:
    """Schedule an async cosmos coroutine without blocking the caller."""
    try:
        asyncio.get_running_loop().create_task(coro)
    except RuntimeError:
        pass  # No running event loop (e.g., test/startup sync context)


class HubManager:
    """Manages Web PubSub hub groups that map to meeting sessions."""

    def __init__(
        self,
        pubsub: Optional[WebPubSubService] = None,
        cosmos=None,
    ) -> None:
        self._pubsub = pubsub
        self._cosmos = cosmos
        self._sessions: Dict[str, Meeting] = {}


    def create_session(
        self,
        session_id: str,
        title: str = "AccessMesh Meeting",
        language: str = "en-US",
    ) -> Meeting:
        """Create a new meeting session (idempotent)."""
        if session_id not in self._sessions:
            meeting = Meeting(session_id=session_id, title=title, language=language)
            self._sessions[session_id] = meeting
            if self._cosmos:
                _cosmos_fire_and_forget(self._cosmos.upsert_session(session_id, {
                    "title": title,
                    "language": language,
                    "status": meeting.status,
                    "created_at": meeting.created_at.isoformat(),
                }))
            logger.info("[HubManager] Session created: %s", session_id)
        return self._sessions[session_id]

    def end_session(self, session_id: str) -> None:
        """Mark a session as ended."""
        meeting = self._sessions.get(session_id)
        if meeting:
            meeting.status = MeetingStatus.ENDED
            if self._cosmos:
                _cosmos_fire_and_forget(self._cosmos.upsert_session(session_id, {"status": "ended"}))
            logger.info("[HubManager] Session ended: %s", session_id)

    def get_session(self, session_id: str) -> Optional[Meeting]:
        return self._sessions.get(session_id)

    def list_active_sessions(self) -> List[Meeting]:
        return [m for m in self._sessions.values() if m.status == MeetingStatus.ACTIVE]


    def join(
        self,
        session_id: str,
        user_id: str,
        display_name: str = "",
        features: Optional[List[str]] = None,
    ) -> Meeting:
        """Register a participant in a session, creating it if needed."""
        meeting = self.create_session(session_id)
        participant = Participant(
            user_id=user_id,
            display_name=display_name or user_id,
            accessibility_features=features or [],
        )
        meeting.add_participant(participant)
        # Update session in Cosmos
        if self._cosmos:
            _cosmos_fire_and_forget(self._cosmos.upsert_session(session_id, {
                "title": meeting.title,
                "language": meeting.language,
                "status": meeting.status,
                "participant_count": meeting.active_participant_count,
            }))
        logger.info("[HubManager] %s joined session %s", user_id, session_id)
        return meeting

    def leave(self, session_id: str, user_id: str) -> None:
        """Mark a participant as inactive."""
        meeting = self._sessions.get(session_id)
        if meeting:
            meeting.remove_participant(user_id)
            logger.info("[HubManager] %s left session %s", user_id, session_id)

    def get_participants(self, session_id: str) -> List[Participant]:
        meeting = self._sessions.get(session_id)
        if not meeting:
            return []
        return [p for p in meeting.participants.values() if p.is_active]


    def get_client_token(
        self,
        user_id: str,
        session_id: str,
        roles: Optional[List[str]] = None,
        minutes_to_expire: int = 60,
    ) -> Dict[str, str]:
        """Delegate to WebPubSubService to issue a WebSocket access token."""
        if self._pubsub is None:
            raise RuntimeError("WebPubSub service is not configured.")
        return self._pubsub.get_client_access_token(
            user_id=user_id,
            groups=[session_id],
            roles=roles or ["webpubsub.joinLeaveGroup", "webpubsub.sendToGroup"],
            minutes_to_expire=minutes_to_expire,
        )


    def health(self) -> bool:
        """Return True if the underlying hub is reachable."""
        if self._pubsub is None:
            return False
        try:
            return self._pubsub.check_connection()
        except Exception:
            return False

