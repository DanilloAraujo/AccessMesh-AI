"""AsyncAgentBus — Pub/sub backbone for the Agent Mesh."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    DefaultDict,
    Dict,
    List,
    Optional,
    Tuple,
)
import time

from shared.message_schema import BaseMessage, MessageType, message_from_dict

if TYPE_CHECKING:
    from services.servicebus_service import ServiceBusService

logger = logging.getLogger(__name__)

# Handler function type for async subscribers
HandlerFn = Callable[["BaseMessage", "AsyncAgentBus"], Awaitable[None]]

# Correlation key used by watchers: (MessageType, correlation_id)
_WatchKey = Tuple[MessageType, str]

# ──────────────────────────────────────────────────────────────────
# SERVICE BUS SUBSCRIPTION AUDIT
# ──────────────────────────────────────────────────────────────────
# Forward types: events copied to the Azure SB topic for external
# consumers AND for triggering cross-instance workers.
#
# Required Azure SB subscriptions:
#   1. sub-transcription     → filter: message_type = 'TRANSCRIPTION'
#   2. sub-accessible        → filter: message_type = 'ACCESSIBLE'
#   3. sub-summary           → filter: message_type = 'SUMMARY'
#   4. sub-error             → filter: message_type = 'ERROR'
#   5. sub-summary-request   → filter: message_type = 'SUMMARY_REQUEST'
#                              consumed by SummaryAgent._receive_loop
#
# Internal pipeline steps (ROUTED, AUDIO_CHUNK, GESTURE) are dispatched
# entirely in-process and are NOT forwarded to SB.
# ──────────────────────────────────────────────────────────────────
_SB_FORWARD_TYPES: frozenset[str] = frozenset({
    MessageType.TRANSCRIPTION,   # raw speech — analytics / audit
    MessageType.ACCESSIBLE,      # terminal pipeline result (text ready)
    MessageType.SUMMARY,         # meeting summary — external consumers
    MessageType.SUMMARY_REQUEST, # on-demand trigger — consumed by SummaryAgent worker
    MessageType.ERROR,           # errors
})

# SB subscriptions that have a _receive_loop receiver in this process.
# Only SUMMARY_REQUEST needs a receive loop — it triggers real work in
# SummaryAgent.  All other SB subscriptions are for external consumers only.
_SB_RECEIVE_SUBSCRIPTIONS: dict[str, str] = {
    "sub-summary-request": MessageType.SUMMARY_REQUEST,
}


class AsyncAgentBus:
    """Async pub/sub bus for the Agent Mesh with Azure Service Bus."""

    def __init__(self) -> None:
        # event_type → list of handlers
        self._subscribers: DefaultDict[MessageType, List[HandlerFn]] = defaultdict(list)

        # correlation_id → {MessageType: BaseMessage}
        # Stores every event published under a correlation_id so that
        # wait_for_correlated can serve events that already arrived.
        self._event_store: DefaultDict[str, Dict[MessageType, BaseMessage]] = defaultdict(dict)

        # correlation_id → timestamp of last update (for TTL eviction)
        self._event_store_ts: Dict[str, float] = {}

        # (MessageType, correlation_id) → asyncio.Future
        # Resolved when the matching event is published.
        self._watchers: Dict[_WatchKey, asyncio.Future] = {}

        # Service Bus transport (None → in-process mode)
        self._sb_service: Optional["ServiceBusService"] = None
        self._receiver_tasks: List[asyncio.Task] = []

        # Cleanup task for stale event store entries
        self._cleanup_task: Optional[asyncio.Task] = None

        # Maximum entries in event store before forced eviction
        self._max_store_size: int = 10_000
        # How long (seconds) before a stale entry is evicted
        self._store_ttl: float = 120.0

    # ──────────────────────────────────────────────────────────────────
    # Lifecycle (Service Bus)
    # ──────────────────────────────────────────────────────────────────

    async def start(
        self,
        sb_service: Optional["ServiceBusService"] = None,
    ) -> None:
        """
        Start Service Bus receive loops for every subscribed MessageType.

        Call after all agents have registered via ``subscribe()``.
        If ``sb_service`` is None, a ServiceBusService is auto-created from
        settings.  No receivers are started when the service is in stub mode
        (no connection string configured).
        """
        if sb_service is None:
            from services.servicebus_service import ServiceBusService  # noqa: PLC0415

            sb_service = ServiceBusService()

        self._sb_service = sb_service

        if not self._sb_service.is_enabled:
            logger.info(
                "[AgentBus] Service Bus not configured — running in in-process mode."
            )
        else:
            logger.info(
                "[AgentBus] Service Bus configured — dispatching in-process, "
                "forwarding terminal events to SB topic, and starting receive "
                "loops for worker subscriptions (SUMMARY_REQUEST)."
            )

            # Pre-warm the AMQP sender so the first real message send doesn't
            # run into a cold TCP+TLS+AMQP handshake inside the 0.8 s timeout.
            await self._sb_service.initialize()

            # Start receive loops only for subscriptions that have registered
            # handlers in this process.  Currently only SUMMARY_REQUEST is
            # consumed here; other subscriptions (TRANSCRIPTION, ACCESSIBLE,
            # SUMMARY, ERROR) are for external consumers only.
            for sub_name, event_type_value in _SB_RECEIVE_SUBSCRIPTIONS.items():
                event_type = MessageType(event_type_value)
                if self._subscribers.get(event_type):
                    task = asyncio.create_task(
                        self._receive_loop(sub_name, event_type),
                        name=f"agent-bus:sb-recv:{sub_name}",
                    )
                    self._receiver_tasks.append(task)
                    logger.info(
                        "[AgentBus] Started SB receive loop: subscription=%s event_type=%s",
                        sub_name, event_type,
                    )
                else:
                    logger.debug(
                        "[AgentBus] No handlers for %s — skipping SB receive loop for %s",
                        event_type, sub_name,
                    )

        # Start periodic cleanup of stale event store entries
        self._cleanup_task = asyncio.create_task(
            self._event_store_cleanup_loop(),
            name="agent-bus:event-store-cleanup",
        )

    async def stop(self) -> None:
        """Cancel all receiver tasks and close the Service Bus client."""
        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        for task in self._receiver_tasks:
            if not task.done():
                task.cancel()
        if self._receiver_tasks:
            await asyncio.gather(*self._receiver_tasks, return_exceptions=True)
        self._receiver_tasks.clear()

        if self._sb_service:
            await self._sb_service.close()
            self._sb_service = None

        logger.info("[AgentBus] stopped.")

    # ──────────────────────────────────────────────────────────────────
    # Subscription
    # ──────────────────────────────────────────────────────────────────

    def subscribe(self, event_type: MessageType, handler: HandlerFn) -> None:
        """Register *handler* to be called whenever *event_type* is published."""
        self._subscribers[event_type].append(handler)
        logger.info(
            "[AgentBus] Subscribed handler '%s' to %s",
            getattr(handler, "__qualname__", repr(handler)),
            event_type,
        )

    # ──────────────────────────────────────────────────────────────────
    # Publishing
    # ──────────────────────────────────────────────────────────────────

    async def publish(self, event: BaseMessage) -> None:
        """
        Publish *event* to all registered subscribers.

        Always dispatches locally via ``_dispatch_local`` so the in-process
        pipeline resolves immediately with no network round-trip.  When a
        Service Bus service is configured, the event is also forwarded to the
        SB topic asynchronously (fire-and-forget) for external consumers or
        future multi-instance scenarios.  Receive loops are not used in
        single-instance mode to prevent double-dispatch.
        """
        logger.debug(
            "[AgentBus] publish %s corr=%s session=%s",
            event.message_type,
            event.metadata.get("correlation_id", event.message_id),
            event.session_id,
        )

        # In-process dispatch — always, regardless of SB mode.
        await self._dispatch_local(event)

        # Forward only terminal/observable event types to SB topic.
        # Intermediate pipeline events (ROUTED, ACCESSIBLE, TRANSLATED) are
        # dispatched in-process and have no external consumers.
        if (
            self._sb_service
            and self._sb_service.is_enabled
            and event.message_type in _SB_FORWARD_TYPES
        ):
            body = event.model_dump_json().encode("utf-8")
            asyncio.create_task(
                self._sb_forward(body, event.message_type),
                name=f"agent-bus:sb-fwd:{event.message_type}",
            )

    async def _sb_forward(self, body: bytes, message_type: str) -> None:
        """Fire-and-forget SB send with a hard timeout to protect the event loop.

        Azure SB SDK retries on AMQP errors can block the event loop for 1-2 s.
        The 0.8 s timeout ensures pipeline tasks are never starved by SB retries.
        """
        try:
            await asyncio.wait_for(
                self._sb_service.send_message(body, message_type),
                timeout=1.5,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "[AgentBus] SB forward timed out after 0.8 s for %s — "
                "AMQP connection may be slow or unavailable", message_type,
            )
        except Exception as exc:
            logger.warning("[AgentBus] SB forward failed (non-fatal) for %s: %s", message_type, exc)

    async def _dispatch_local(self, event: BaseMessage) -> None:
        """
        Update _event_store, resolve watchers, and fan-out to local handlers.

        This is the core dispatch logic shared by both operating modes:
        - In-process: called directly from ``publish``
        - Service Bus: called from ``_receive_loop`` after deserialisation
        """
        correlation_id: str = event.metadata.get("correlation_id", event.message_id)
        event_type = MessageType(event.message_type)

        logger.debug(
            "[AgentBus] dispatch_local %s corr=%s session=%s",
            event_type, correlation_id, event.session_id,
        )

        # Store for potential late wait_for_correlated calls
        self._event_store[correlation_id][event_type] = event
        self._event_store_ts[correlation_id] = time.monotonic()

        # Guard: if the store exceeds max size, evict oldest entries
        if len(self._event_store) > self._max_store_size:
            self._evict_oldest(self._max_store_size // 2)

        # Resolve any watcher waiting for this (event_type, correlation_id)
        watch_key: _WatchKey = (event_type, correlation_id)
        if watch_key in self._watchers:
            fut = self._watchers.pop(watch_key)
            if not fut.done():
                fut.set_result(event)

        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            logger.debug("[AgentBus] No subscribers for %s", event_type)
            return

        for handler in handlers:
            asyncio.create_task(
                self._safe_call(handler, event),
                name=f"agent-bus:{event_type}:{getattr(handler, '__qualname__', '?')}",
            )

    async def publish_and_collect(
        self,
        seed_event: BaseMessage,
        *,
        collect_type: MessageType,
        timeout: float = 30.0,
    ) -> Optional[BaseMessage]:
        """
        Publish *seed_event* and wait for an event of *collect_type* that
        shares the same ``correlation_id`` (== seed_event.message_id).

        Returns the collected event, or None on timeout.

        The watcher Future is registered BEFORE publishing to avoid a race
        condition where the entire pipeline completes before the Future exists.
        """
        correlation_id = seed_event.message_id

        # Propagate correlation_id in seed event metadata
        seed_event.metadata.setdefault("correlation_id", correlation_id)

        # Check if already in store (e.g. ultra-fast pipeline)
        existing = self._event_store.get(correlation_id, {}).get(collect_type)
        if existing:
            await self.publish(seed_event)
            return existing

        # Register watcher before publishing to avoid race condition
        loop = asyncio.get_running_loop()
        watch_key: _WatchKey = (collect_type, correlation_id)
        fut: asyncio.Future = loop.create_future()
        self._watchers[watch_key] = fut

        await self.publish(seed_event)

        t_publish = time.perf_counter()
        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            wait_ms = (time.perf_counter() - t_publish) * 1000
            if wait_ms > 200:
                logger.warning(
                    "[AgentBus] publish_and_collect slow wake-up: %.0f ms after publish "
                    "(collect_type=%s corr=%s) — event loop may be overloaded",
                    wait_ms, collect_type, correlation_id,
                )
            else:
                logger.debug(
                    "[AgentBus] publish_and_collect resolved in %.0f ms (collect_type=%s)",
                    wait_ms, collect_type,
                )
            return result
        except asyncio.TimeoutError:
            logger.warning(
                "[AgentBus] publish_and_collect timeout after %.1fs — "
                "collect_type=%s corr=%s",
                timeout, collect_type, correlation_id,
            )
            self._watchers.pop(watch_key, None)
            return None
        finally:
            # Clean up event store for this correlation chain
            self._event_store.pop(correlation_id, None)
            self._event_store_ts.pop(correlation_id, None)

    # ──────────────────────────────────────────────────────────────────
    # Fan-in helper
    # ──────────────────────────────────────────────────────────────────

    async def wait_for_correlated(
        self,
        correlation_id: str,
        event_type: MessageType,
        *,
        timeout: float = 8.0,
    ) -> Optional[BaseMessage]:
        """
        Wait for an event of *event_type* that carries *correlation_id*.

        Used by AccessibilityAgent to signal the terminal ACCESSIBLE event.
        AccessibilityAgent in parallel with the TRANSLATED event.

        If the event already arrived (fan-out beat fan-in), it is returned
        immediately from _event_store without creating a Future.
        """
        # Fast path: already stored
        stored = self._event_store.get(correlation_id, {}).get(event_type)
        if stored:
            return stored

        loop = asyncio.get_running_loop()
        watch_key: _WatchKey = (event_type, correlation_id)

        # Another wait_for_correlated may have already registered a Future
        fut = self._watchers.get(watch_key)
        if fut is None:
            fut = loop.create_future()
            self._watchers[watch_key] = fut

        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "[AgentBus] wait_for_correlated timeout %.1fs — "
                "event_type=%s corr=%s",
                timeout, event_type, correlation_id,
            )
            return None

    # ──────────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────────

    async def _receive_loop(self, subscription_name: str, event_type: MessageType) -> None:
        """
        Long-running task that reads messages from a Service Bus subscription
        and dispatches them to local handlers via ``_dispatch_local``.

        Automatically reconnects after transient errors with a 5-second delay.
        Stops cleanly when the task is cancelled (e.g. on shutdown).
        """
        assert self._sb_service is not None

        while True:
            try:
                receiver = self._sb_service.create_receiver(subscription_name)
                async with receiver:
                    async for msg in receiver:
                        try:
                            raw = b"".join(msg.body)
                            data = json.loads(raw.decode("utf-8"))
                            event = message_from_dict(data)
                            await self._dispatch_local(event)
                            await receiver.complete_message(msg)
                        except Exception as exc:
                            logger.warning(
                                "[AgentBus] Error processing SB message for %s: %s",
                                event_type, exc, exc_info=True,
                            )
                            try:
                                await receiver.abandon_message(msg)
                            except Exception:
                                pass
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    "[AgentBus] SB receive_loop for %s crashed: %s — retrying in 5s",
                    event_type, exc,
                )
                await asyncio.sleep(5)

    async def _safe_call(self, handler: HandlerFn, event: BaseMessage) -> None:
        """Run *handler* and swallow/log any exception so the bus never crashes."""
        try:
            await handler(event, self)
        except Exception as exc:
            logger.warning(
                "[AgentBus] Handler '%s' raised for event %s: %s",
                getattr(handler, "__qualname__", repr(handler)),
                event.message_type,
                exc,
                exc_info=True,
            )

    def reset(self) -> None:
        """Clear all state — useful in tests. Does not close SB resources."""
        self._subscribers.clear()
        self._event_store.clear()
        self._event_store_ts.clear()
        for fut in self._watchers.values():
            if not fut.done():
                fut.cancel()
        self._watchers.clear()

    # ──────────────────────────────────────────────────────────────────
    # Event store maintenance
    # ──────────────────────────────────────────────────────────────────

    async def _event_store_cleanup_loop(self) -> None:
        """
        Periodically evict stale entries from _event_store to prevent
        unbounded memory growth in long-running sessions.
        """
        try:
            while True:
                await asyncio.sleep(60)  # cleanup interval
                self._evict_stale()
        except asyncio.CancelledError:
            pass

    def _evict_stale(self) -> None:
        """Remove entries older than _store_ttl seconds."""
        now = time.monotonic()
        stale = [
            cid for cid, ts in self._event_store_ts.items()
            if now - ts > self._store_ttl
        ]
        for cid in stale:
            self._event_store.pop(cid, None)
            self._event_store_ts.pop(cid, None)
        if stale:
            logger.debug("[AgentBus] evicted %d stale event store entries.", len(stale))

    def _evict_oldest(self, keep: int) -> None:
        """Keep only the *keep* most recent entries by timestamp."""
        sorted_ids = sorted(self._event_store_ts, key=self._event_store_ts.get)  # type: ignore[arg-type]
        to_remove = sorted_ids[: len(sorted_ids) - keep]
        for cid in to_remove:
            self._event_store.pop(cid, None)
            self._event_store_ts.pop(cid, None)
        if to_remove:
            logger.debug("[AgentBus] evicted %d oldest event store entries (max size guard).", len(to_remove))


# ── Module-level singleton ────────────────────────────────────────────
# Import anywhere:  from agents.agent_bus import agent_bus
agent_bus = AsyncAgentBus()
