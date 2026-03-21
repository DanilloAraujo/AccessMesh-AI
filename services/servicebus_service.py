"""
services/servicebus_service.py
──────────────────────────────
Azure Service Bus service wrapper for the Agent Mesh.

Provides a thin async infrastructure layer over the Azure Service Bus SDK:
  - Persistent topic sender (reused across sends for efficiency)
  - Subscription receiver factory (one per MessageType)
  - Raises RuntimeError when connection string is not configured

The AgentBus (agents/agent_bus.py) owns all fan-out / correlation logic.
This service is pure transport infrastructure.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ServiceBusConfig(BaseModel):
    """Service Bus connection configuration."""

    connection_string: str
    topic_name: str = "accessmesh-events"


class ServiceBusService:
    """
    Async wrapper around the Azure Service Bus SDK (azure-servicebus>=7.12.0).

    Typical usage in factory.py:
        svc = ServiceBusService()
        await agent_bus.start(sb_service=svc)
        ...
        await svc.close()

    When no connection string is provided, is_enabled returns False and
    send_message / create_receiver raise RuntimeError.
    Ensure SERVICEBUS_CONNECTION_STRING is set before instantiating.
    """

    def __init__(self, config: Optional[ServiceBusConfig] = None) -> None:
        if config is None:
            from shared.config import settings  # noqa: PLC0415

            config = ServiceBusConfig(
                connection_string=settings.servicebus_connection_string or "",
                topic_name=settings.servicebus_topic_name,
            )

        self._config = config
        self._client = None

        if config.connection_string:
            try:
                from azure.servicebus.aio import ServiceBusClient  # noqa: PLC0415

                self._client = ServiceBusClient.from_connection_string(
                    conn_str=config.connection_string,
                    logging_enable=False,
                )
                logger.info(
                    "ServiceBusService initialised — topic: %s", config.topic_name
                )
            except Exception as exc:
                logger.warning("Failed to create ServiceBusClient: %s", exc)
                self._client = None
        else:
            logger.warning(
                "ServiceBusService: no connection string — running in stub mode. "
                "Set SERVICEBUS_CONNECTION_STRING to enable."
            )

    @property
    def is_enabled(self) -> bool:
        """True when a live Service Bus client is available."""
        return self._client is not None

    async def send_message(self, body: bytes, message_type: str) -> None:
        """
        Send a raw bytes payload to the configured topic.

        ``message_type`` is stored both as the message ``subject`` and in
        ``application_properties`` so SQL filters on subscriptions can route by type.
        """
        if not self._client:
            raise RuntimeError(
                "ServiceBusService is not configured — set SERVICEBUS_CONNECTION_STRING to enable message publishing."
            )

        from azure.servicebus import ServiceBusMessage  # noqa: PLC0415

        msg = ServiceBusMessage(
            body=body,
            subject=message_type,
            application_properties={"message_type": message_type},
        )
        try:
            async with self._client.get_topic_sender(
                topic_name=self._config.topic_name
            ) as sender:
                await sender.send_messages(msg)
        except Exception as exc:
            logger.warning(
                "ServiceBusService.send_message failed for type '%s': %s",
                message_type, exc,
            )
            raise

    def create_receiver(self, subscription_name: str):
        """
        Return an async ServiceBusReceiver for *subscription_name*.

        The caller is responsible for entering the context manager::

            async with svc.create_receiver("sub-transcription") as receiver:
                async for msg in receiver:
                    ...
        """
        if not self._client:
            raise RuntimeError(
                "ServiceBusService is in stub mode — no client available. "
                "Set SERVICEBUS_CONNECTION_STRING to enable."
            )
        return self._client.get_subscription_receiver(
            topic_name=self._config.topic_name,
            subscription_name=subscription_name,
        )

    async def close(self) -> None:
        """Close the underlying Service Bus client."""
        if self._client:
            try:
                await self._client.close()
                logger.info("ServiceBusService closed.")
            except Exception as exc:
                logger.warning("ServiceBusService — client close error: %s", exc)
            finally:
                self._client = None
