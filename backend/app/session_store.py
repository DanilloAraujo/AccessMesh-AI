"""Shared in-memory session message store for AccessMesh-AI."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Dict, List

# Shared across all route modules that import this.
history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
history_lock = asyncio.Lock()
MAX_HISTORY = 200


async def append_message(session_id: str, payload: Dict[str, Any]) -> None:
    """Thread-safe append of *payload* to the in-memory history for *session_id*."""
    async with history_lock:
        history[session_id].append(payload)
        if len(history[session_id]) > MAX_HISTORY:
            history[session_id] = history[session_id][-MAX_HISTORY:]


def get_messages(session_id: str) -> List[Dict[str, Any]]:
    """Return current in-memory messages for *session_id* (snapshot, no lock needed for read)."""
    return list(history.get(session_id, []))
