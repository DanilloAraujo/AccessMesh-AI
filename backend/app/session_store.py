"""Shared session message store for AccessMesh-AI.

In production (Cosmos enabled) this module is a thin compatibility shim —
all reads and writes go through CosmosService which is the single source of
truth across multiple instances.  In local development (no Cosmos), an
in-memory fallback is used so the app still works without Azure credentials.

IMPORTANT: The in-memory fallback breaks under multi-instance deployments
because each instance holds its own isolated dict.  Always configure
COSMOS_ENDPOINT + COSMOS_KEY in production / staging.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── In-memory fallback (dev / no Cosmos) ──────────────────────────────────
# WARNING: NOT safe for multi-instance deployments.
history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
history_lock = asyncio.Lock()
MAX_HISTORY = 200


def _get_cosmos() -> Optional[Any]:
    """Return the CosmosService singleton from app state, if available."""
    try:
        # Import here to avoid circular imports; app state is set at startup.
        from backend.app.factory import _cosmos_service_instance  # noqa: PLC0415
        return _cosmos_service_instance
    except (ImportError, AttributeError):
        return None


async def append_message(session_id: str, payload: Dict[str, Any]) -> None:
    """
    Persist *payload* for *session_id*.

    Priority:
      1. CosmosService (durable, shared across instances)
      2. In-memory dict (local-dev fallback only — NOT multi-instance safe)
    """
    cosmos = _get_cosmos()
    if cosmos and getattr(cosmos, "is_enabled", False):
        try:
            await cosmos.append_message(session_id, payload)
            return
        except Exception as exc:
            logger.warning(
                "[session_store] Cosmos write failed — falling back to memory: %s", exc
            )
    # Fallback: in-memory (single-instance / local dev only)
    logger.debug("[session_store] Using in-memory store for session=%s", session_id)
    async with history_lock:
        history[session_id].append(payload)
        if len(history[session_id]) > MAX_HISTORY:
            history[session_id] = history[session_id][-MAX_HISTORY:]


async def get_messages_async(session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Read messages for *session_id* — async, Cosmos-first.

    Priority:
      1. CosmosService (durable, shared across instances)
      2. In-memory dict (local-dev fallback)
    """
    cosmos = _get_cosmos()
    if cosmos and getattr(cosmos, "is_enabled", False):
        try:
            return await cosmos.get_messages(session_id, limit=limit)
        except Exception as exc:
            logger.warning(
                "[session_store] Cosmos read failed — falling back to memory: %s", exc
            )
    return list(history.get(session_id, []))


def get_messages(session_id: str) -> List[Dict[str, Any]]:
    """Synchronous snapshot from the in-memory fallback only.

    Prefer ``get_messages_async`` in async route handlers so Cosmos is
    queried.  This sync version exists only for backwards-compatibility.
    """
    return list(history.get(session_id, []))
