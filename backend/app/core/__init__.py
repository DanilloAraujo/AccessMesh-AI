"""
backend/app/core
────────────────
Core infrastructure: hub management and real-time dispatch.
"""

from .hub_manager import HubManager
from .realtime_dispatcher import RealtimeDispatcher

__all__ = ["HubManager", "RealtimeDispatcher"]
