"""Manages Web PubSub hub groups that map to meeting sessions.

Scale-out note
--------------
``_sessions`` is an in-process cache for the current instance.  Cosmos DB
is the authoritative store:

  * Writes  : every mutation (create/join/end) is written to Cosmos
              synchronously (non-blocking fire-and-forget).
  * Reads   : ``get_session_async`` and ``list_active_sessions_async`` query
              Cosmos first so cross-instance data is always visible.
              The in-process cache is used only when Cosmos is unavailable
              (local dev without credentials).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from backend.app.models.meeting_model import Meeting, MeetingStatus, Participant
from services.webpubsub_service import WebPubSubService

logger = logging.getLogger(__name__)


def _cosmos_fire_and_forget(coro) -> None:
    """Schedule an async cosmos coroutine without blocking the caller."""
    try:
        task = asyncio.get_running_loop().create_task(coro)
        def _on_done(t: "asyncio.Task") -> None:
            exc = t.exception() if not t.cancelled() else None
            if exc:
                logger.warning("[HubManager] Cosmos fire-and-forget failed: %s", exc)
        task.add_done_callback(_on_done)
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
        # In-process cache — single-instance fast path only.
        # Do NOT rely on this dict for correctness in multi-instance deployments.
        self._sessions: Dict[str, Meeting] = {}

    # ── Session lifecycle ─────────────────────────────────────────────

    def create_session(
        self,
        session_id: str,
        title: str = "AccessMesh Meeting",
        language: str = "en-US",
    ) -> Meeting:
        """Create a new meeting session (idempotent).  Persists to Cosmos."""
        if session_id not in self._sessions:
            meeting = Meeting(session_id=session_id, title=title, language=language)
            self._sessions[session_id] = meeting
            if self._cosmos and self._cosmos.is_enabled:
                _cosmos_fire_and_forget(self._cosmos.upsert_session(session_id, {
                    "title": title,
                    "language": language,
                    "status": meeting.status,
                    "created_at": meeting.created_at.isoformat(),
                }))
            logger.info("[HubManager] Session created: %s", session_id)
        return self._sessions[session_id]

    def end_session(self, session_id: str) -> None:
        """Mark a session as ended in cache and Cosmos."""
        meeting = self._sessions.get(session_id)
        if meeting:
            meeting.status = MeetingStatus.ENDED
            if self._cosmos and self._cosmos.is_enabled:
                _cosmos_fire_and_forget(self._cosmos.upsert_session(session_id, {"status": "ended"}))
            logger.info("[HubManager] Session ended: %s", session_id)

    # ── Reads: Cosmos-first for multi-instance correctness ───────────

    def get_session(self, session_id: str) -> Optional[Meeting]:
        """Return cached session (fast path).  Falls back to None if not cached.

        For cross-instance visibility use ``get_session_async``.
        """
        return self._sessions.get(session_id)

    async def get_session_async(self, session_id: str) -> Optional[Meeting]:
        """Return session, querying Cosmos when not in local cache.

        This ensures that sessions created by another instance are visible.
        The result is NOT stored in the local cache to avoid stale state.
        """
        cached = self._sessions.get(session_id)
        if cached:
            return cached

        if self._cosmos and self._cosmos.is_enabled:
            try:
                doc = await self._cosmos.get_session(session_id)
                if doc:
                    meeting = Meeting(
                        session_id=session_id,
                        title=doc.get("title", "AccessMesh Meeting"),
                        language=doc.get("language", "en-US"),
                    )
                    if doc.get("status") == "ended":
                        meeting.status = MeetingStatus.ENDED
                    logger.debug("[HubManager] Session %s loaded from Cosmos", session_id)
                    return meeting
            except Exception as exc:
                logger.warning("[HubManager] Cosmos get_session failed: %s", exc)
        return None

    def list_active_sessions(self) -> List[Meeting]:
        """In-process cache snapshot.  Use ``list_active_sessions_async`` in production."""
        return [m for m in self._sessions.values() if m.status == MeetingStatus.ACTIVE]

    async def list_active_sessions_async(self) -> List[Dict[str, Any]]:
        """Query Cosmos for all active sessions (cross-instance aware)."""
        if self._cosmos and self._cosmos.is_enabled:
            try:
                return await self._cosmos.list_active_sessions()
            except Exception as exc:
                logger.warning("[HubManager] Cosmos list_active_sessions failed: %s", exc)
        # Fallback to in-process cache
        return [
            {"session_id": m.session_id, "title": m.title, "status": m.status}
            for m in self._sessions.values()
            if m.status == MeetingStatus.ACTIVE
        ]

    # ── Participant management ────────────────────────────────────────

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
        if self._cosmos and self._cosmos.is_enabled:
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

    # ── Token + health ────────────────────────────────────────────────

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
            if self._cosmos and self._cosmos.is_enabled:
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
            if self._cosmos and self._cosmos.is_enabled:
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
        if self._cosmos and self._cosmos.is_enabled:
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

