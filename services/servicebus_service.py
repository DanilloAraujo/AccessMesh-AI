"""Azure Service Bus service wrapper for the Agent Mesh."""

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
    """Async wrapper around the Azure Service Bus SDK (azure-servicebus)."""

    def __init__(self, config: Optional[ServiceBusConfig] = None) -> None:
        if config is None:
            from shared.config import settings  # noqa: PLC0415

            config = ServiceBusConfig(
                connection_string=settings.servicebus_connection_string or "",
                topic_name=settings.servicebus_topic_name,
            )

        self._config = config
        self._client = None
        # Cached persistent sender — avoids opening a new AMQP connection per message.
        self._sender = None

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

    async def initialize(self) -> None:
        """Pre-warm the AMQP sender so the first send_message call is fast.

        Called once at startup (agent_bus.start).  A 1-3 s TCP+TLS+AMQP
        handshake is acceptable here; it never is inside the hot message path.
        """
        if not self._client or self._sender is not None:
            return
        try:
            self._sender = self._client.get_topic_sender(
                topic_name=self._config.topic_name
            )
            await self._sender.__aenter__()
            logger.info(
                "ServiceBusService: AMQP sender pre-warmed — topic=%s",
                self._config.topic_name,
            )
        except Exception as exc:
            if self._sender is not None:
                try:
                    await self._sender.__aexit__(None, None, None)
                except Exception:
                    pass
                self._sender = None
            logger.warning(
                "ServiceBusService: sender pre-warm failed (will retry on first message): %s", exc
            )

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
            # Reuse the cached sender to avoid a new TCP/AMQP handshake per message.
            if self._sender is None:
                self._sender = self._client.get_topic_sender(
                    topic_name=self._config.topic_name
                )
                await self._sender.__aenter__()
            await self._sender.send_messages(msg)
        except BaseException as exc:
            # Use BaseException (not just Exception) to also catch
            # asyncio.CancelledError (Python 3.8+: CancelledError is BaseException).
            # asyncio.wait_for cancels the coroutine via CancelledError when the
            # timeout fires, so without this the sender would be left in a
            # half-open, broken state and the next send attempt would also fail.
            if self._sender is not None:
                try:
                    await self._sender.__aexit__(None, None, None)
                except Exception:
                    pass
                self._sender = None
            if isinstance(exc, Exception):  # don't log CancelledError as a warning
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
        """Close the cached sender and the underlying Service Bus client."""
        if self._sender is not None:
            try:
                await self._sender.__aexit__(None, None, None)
            except Exception:
                pass
            self._sender = None
        if self._client:
            try:
                await self._client.close()
                logger.info("ServiceBusService closed.")
            except Exception as exc:
                logger.warning("ServiceBusService — client close error: %s", exc)
            finally:
                self._client = None
