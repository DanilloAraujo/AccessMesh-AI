"""
agents/__init__.py
──────────────────
Agent Mesh registry and bus — central directory of all active agent instances.

Agents register themselves with ``agent_registry`` at application startup so
the pipeline can discover them by name.  They also register onto
``agent_bus`` (AsyncAgentBus) so the mesh routes events without any agent
knowing its neighbours directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agents.agent_bus import AsyncAgentBus, agent_bus  # noqa: F401 — re-exported

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Central registry of agent instances for Agent Mesh capability discovery."""

    def __init__(self) -> None:
        self._agents: Dict[str, Any] = {}

    def register(self, name: str, agent: Any) -> None:
        """Register an agent instance under the given name."""
        self._agents[name] = agent
        logger.debug("AgentRegistry: registered '%s' (%s)", name, type(agent).__name__)

    def get(self, name: str) -> Optional[Any]:
        """Return the agent instance, or None if not registered."""
        agent = self._agents.get(name)
        if agent is None:
            logger.warning("AgentRegistry: agent '%s' not found.", name)
        return agent

    def is_registered(self, name: str) -> bool:
        """Return True when an agent with this name has been registered."""
        return name in self._agents

    def list_names(self) -> List[str]:
        """Return the names of all registered agents."""
        return list(self._agents.keys())


# Module-level singletons — import and use throughout the application.
agent_registry = AgentRegistry()
