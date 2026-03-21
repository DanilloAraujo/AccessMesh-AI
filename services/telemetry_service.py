from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

logger = logging.getLogger(__name__)



class TelemetryService:
    """
    Service for tracking telemetry and events using Azure Application Insights and OpenTelemetry.

    This class provides methods to track agent execution spans and custom events, supporting both enabled and disabled telemetry modes.
    """

    def __init__(self, connection_string: Optional[str] = None) -> None:
        """
        Initialize the TelemetryService with the given Application Insights connection string or from shared settings.

        Args:
            connection_string (Optional[str]): The Application Insights connection string. If not provided, uses shared settings.
        """
        if connection_string is None:
            from shared.config import settings  # noqa: PLC0415
            connection_string = settings.appinsights_connection_string or None
        self._enabled = False

        if connection_string:
            try:
                from azure.monitor.opentelemetry import configure_azure_monitor  # type: ignore[import]
                from opentelemetry import trace  # type: ignore[import]

                configure_azure_monitor(
                    connection_string=connection_string,
                    disable_live_metrics=True,  # disables QuickPulse/LiveStream pings
                )
                self._tracer = trace.get_tracer("accessmesh.pipeline")
                self._enabled = True
                logger.info("TelemetryService: Azure Application Insights configured.")
            except Exception as exc:
                logger.warning(
                    "TelemetryService: failed to init App Insights — continuing without it. %s", exc
                )

    @contextmanager
    def track_agent(
        self, agent_name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Generator[None, None, None]:
        """
        Context manager to track the execution of an agent span for telemetry.

        Args:
            agent_name (str): The name of the agent or operation.
            attributes (Optional[Dict[str, Any]]): Optional attributes to attach to the span.

        Yields:
            None
        """
        start = time.perf_counter()
        if self._enabled:
            with self._tracer.start_as_current_span(f"agent.{agent_name}") as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, str(v))
                try:
                    yield
                finally:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    span.set_attribute("latency_ms", round(elapsed_ms, 2))
                    logger.debug("[telemetry] %s — %.1f ms", agent_name, elapsed_ms)
        else:
            try:
                yield
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.debug("[telemetry] %s — %.1f ms", agent_name, elapsed_ms)

    def track_event(self, name: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """
        Track a custom event in the current telemetry span.

        Args:
            name (str): The event name.
            properties (Optional[Dict[str, Any]]): Optional event properties as a dictionary.
        """
        logger.debug("[telemetry] event=%s props=%s", name, properties)
        if not self._enabled:
            return
        try:
            from opentelemetry import trace  # type: ignore[import]

            span = trace.get_current_span()
            if span and span.is_recording():
                span.add_event(name, attributes={k: str(v) for k, v in (properties or {}).items()})
        except Exception as exc:
            logger.debug("TelemetryService.track_event error: %s", exc)

    @property
    def is_enabled(self) -> bool:
        """
        Indicates whether telemetry is enabled and configured.

        Returns:
            bool: True if telemetry is enabled, False otherwise.
        """
        return self._enabled
