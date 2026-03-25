"""
agents/base_agent.py
────────────────────
BaseAgent — classe base ABC para todos os agentes do Agent Mesh.

Cada agente concreto:
  1. Declara ``subscribes_to: ClassVar[list[MessageType]]`` com os tipos de
     eventos que consome.
  2. Implementa ``async handle(event, bus)`` com a lógica de processamento.
  3. Chama ``agent.register(bus)`` no startup para se inscrever no bus —
     produzido automaticamente por ``BaseAgent.register()``.

Essa abstração garante que:
  * Nenhum agente conhece diretamente outro agente.
  * Adicionar um novo agente ao mesh é feito declarando ``subscribes_to``
    e implementando ``handle`` — sem tocar em pipeline.py.
  * O wiring completo fica em factory.py, que itera os agentes e chama
    ``agent.register(bus)``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import ClassVar, List

from agents.agent_bus import AsyncAgentBus
from shared.message_schema import BaseMessage, MessageType

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base for all Agent Mesh participants.

    Subclasses must define:
      ``subscribes_to``  — class-level list of MessageType values this agent
                           handles.  Can be empty for on-demand-only agents.
      ``handle``         — async method called by the bus on every matching
                           event.
    """

    # Override in each concrete agent
    subscribes_to: ClassVar[List[MessageType]] = []

    @property
    def name(self) -> str:
        """Human-readable agent name — used in logs and telemetry."""
        return type(self).__name__

    def register(self, bus: AsyncAgentBus) -> None:
        """
        Subscribe this agent to all event types declared in ``subscribes_to``.

        Called once at application startup (factory.py).
        """
        if not self.subscribes_to:
            logger.info("[AgentMesh] %s has no bus subscriptions (on-demand only)", self.name)
            return

        for event_type in self.subscribes_to:
            bus.subscribe(event_type, self.handle)
            logger.info(
                "[AgentMesh] %s subscribed to %s",
                self.name,
                event_type,
            )

    @abstractmethod
    async def handle(self, event: BaseMessage, bus: AsyncAgentBus) -> None:
        """
        Process *event* and publish result(s) back onto *bus*.

        Contract:
          * Always propagate ``metadata["correlation_id"]`` to published
            events — the fan-in (AccessibilityAgent) and collect callers rely on it.
          * Never raise — catch all exceptions internally and log them.
            The bus's _safe_call already provides a last-resort guard.
          * Do NOT call other agents directly — only publish to bus.
        """
