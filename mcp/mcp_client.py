"""Async MCP client used by agents to invoke tools."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from mcp.schemas.tool_schema import ToolResult

logger = logging.getLogger(__name__)

# Optional: point agents at a remote MCP HTTP server.
# When empty the client uses the in-process executor (no network round-trip).
_MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "")


class MCPClient:
    """Async client for invoking registered MCP tools."""

    def __init__(self, server_url: str = "") -> None:
        self._url = (server_url or _MCP_SERVER_URL).rstrip("/")

    async def call_tool(self, name: str, **kwargs: Any) -> ToolResult:
        """Invoke an MCP tool by name with the given keyword arguments."""
        transport = "http" if self._url else "local"
        logger.info("MCPClient.call_tool — name=%s transport=%s args=%s", name, transport, list(kwargs.keys()))
        if self._url:
            result = await self._call_http(name, kwargs)
        else:
            result = await self._call_local(name, kwargs)
        logger.info("MCPClient.call_tool done — name=%s success=%s error=%s", name, result.success, result.error or '-')
        return result

    async def _call_http(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """POST a ``tools/call`` request to the MCP HTTP server."""
        from shared.config import settings as _settings  # noqa: PLC0415

        payload = {"name": name, "arguments": arguments}
        headers: dict[str, str] = {}
        if _settings.mcp_api_key:
            headers["X-MCP-API-Key"] = _settings.mcp_api_key

        try:
            async with httpx.AsyncClient(timeout=_settings.mcp_http_timeout_seconds) as client:
                resp = await client.post(
                    f"{self._url}/tools/call",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                return ToolResult(**resp.json())
        except Exception as exc:
            logger.error("MCPClient: HTTP call to tool '%s' failed — %s", name, exc)
            return ToolResult(tool_name=name, success=False, error=str(exc))

    async def _call_local(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Run the in-process executor in a thread pool (non-blocking).

        The executor import is deferred to call time to avoid the circular
        import chain:
          mcp_client ← accessibility_agent ← factory ← backend.app.__init__
          ← SpeechToTextTool._build_agent_from_settings ← mcp.tool_executor
        """
        from mcp.tool_executor import executor as _executor  # noqa: PLC0415
        return await asyncio.to_thread(_executor.run, name, **arguments)


# Module-level singleton — import this everywhere instead of the raw executor.
mcp_client = MCPClient()
