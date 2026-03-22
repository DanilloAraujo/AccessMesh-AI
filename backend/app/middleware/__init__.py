"""
backend/app/middleware/request_tracing.py

ASGI middleware that injects a correlation ID (X-Request-ID) into every
request and propagates it through response headers and log records.

The correlation ID is sourced from:
  1. Incoming X-Request-ID header (if provided by the client or upstream)
  2. A freshly generated UUID4

This enables distributed request tracing across the backend → agent bus →
MCP tool chain when combined with Application Insights.
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context variable accessible from any async frame within the request scope.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Injects X-Request-ID into every request/response cycle.

    Usage in factory.py:
        from backend.app.middleware.request_tracing import RequestTracingMiddleware
        application.add_middleware(RequestTracingMiddleware)
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Prefer client-supplied ID for end-to-end tracing, else generate one.
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_var.set(request_id)

        # Attach to request state so route handlers can access it.
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
