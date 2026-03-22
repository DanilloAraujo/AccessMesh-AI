"""WebSocket connection manager."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """In-process registry of active WebSocket connections."""

    def __init__(self) -> None:
        # session_id → {user_id: WebSocket}
        self._connections: Dict[str, Dict[str, WebSocket]] = defaultdict(dict)


    async def connect(
        self, session_id: str, user_id: str, websocket: WebSocket
    ) -> None:
        await websocket.accept()
        self._connections[session_id][user_id] = websocket
        logger.info("[WS Manager] %s joined room %s", user_id, session_id)

    async def disconnect(self, session_id: str, user_id: str) -> None:
        room = self._connections.get(session_id, {})
        ws = room.pop(user_id, None)
        if ws:
            try:
                await ws.close()
            except Exception:
                pass
        if not room:
            self._connections.pop(session_id, None)
        logger.info("[WS Manager] %s left room %s", user_id, session_id)


    async def broadcast(
        self,
        session_id: str,
        payload: dict,
        *,
        exclude: Optional[str] = None,
    ) -> None:
        """Send *payload* to every connected user in *session_id*."""
        room = self._connections.get(session_id, {})
        dead: List[str] = []
        for uid, ws in room.items():
            if uid == exclude:
                continue
            try:
                await ws.send_json(payload)
            except Exception as exc:
                logger.warning("[WS Manager] Dead socket for %s: %s", uid, exc)
                dead.append(uid)
        for uid in dead:
            room.pop(uid, None)

    async def send_to(
        self, session_id: str, user_id: str, payload: dict
    ) -> bool:
        """Send *payload* to a specific user. Returns False if not connected."""
        ws = self._connections.get(session_id, {}).get(user_id)
        if ws is None:
            return False
        try:
            await ws.send_json(payload)
            return True
        except Exception as exc:
            logger.warning("[WS Manager] Error sending to %s: %s", user_id, exc)
            return False


    def active_users(self, session_id: str) -> Set[str]:
        return set(self._connections.get(session_id, {}).keys())

    def session_count(self) -> int:
        return len(self._connections)


# Application-wide singleton – import where needed
ws_manager = WebSocketManager()
