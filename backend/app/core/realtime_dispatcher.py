"""Dispatches processed messages to session participants in real time."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.webpubsub_service import WebPubSubService

logger = logging.getLogger(__name__)


class RealtimeDispatcher:
    """Wraps WebPubSubService for outgoing message broadcast."""

    def __init__(self, pubsub: Optional[WebPubSubService] = None) -> None:
        self._pubsub = pubsub


    def dispatch(
        self,
        session_id: str,
        payload: Dict[str, Any],
        *,
        exclude_sender: Optional[str] = None,
    ) -> bool:
        """Broadcast *payload* to all participants in *session_id*."""
        if self._pubsub is None:
            logger.warning(
                "[Dispatcher] PubSub unavailable — message not sent to session %s",
                session_id,
            )
            return False

        try:
            self._pubsub.send_to_group(group=session_id, message=payload)
            logger.debug("[Dispatcher] Sent to group %s: %s", session_id, payload.get("type", "?"))
            return True
        except Exception as exc:
            logger.error("[Dispatcher] Failed to dispatch to %s: %s", session_id, exc)
            return False

    def dispatch_system(self, session_id: str, text: str) -> bool:
        """Convenience helper for system-level announcements."""
        return self.dispatch(
            session_id,
            {"type": "system", "content": text},
        )

    def dispatch_error(self, session_id: str, detail: str) -> bool:
        """Convenience helper for error notifications."""
        return self.dispatch(
            session_id,
            {"type": "error", "content": detail},
        )
