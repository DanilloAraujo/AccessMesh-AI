"""FastAPI-based MCP server exposing registered tools to agents."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from mcp.schemas.tool_schema import ToolDefinition, ToolResult
from mcp.tool_executor import executor
from mcp.tool_registry import registry

logger = logging.getLogger(__name__)

mcp_app = FastAPI(
    title="AccessMesh-AI MCP Server",
    description="Model Context Protocol server exposing agent tools.",
    version="1.0.0",
)


# MCP API Key auth dependency

def _verify_api_key(
    x_mcp_api_key: str = Header(default="", alias="X-MCP-API-Key"),
) -> None:
    """
    Validate the X-MCP-API-Key header when MCP_API_KEY is configured.

    When MCP_API_KEY is empty the server runs in open mode (local dev).
    """
    from shared.config import settings as _settings  # noqa: PLC0415

    if not _settings.mcp_api_key:
        return  # open mode — no auth required
    if x_mcp_api_key != _settings.mcp_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-MCP-API-Key header.",
        )


class ToolCallRequest(BaseModel):
    """Body for POST /tools/call — mirrors the MCP `tools/call` message."""

    name: str = Field(..., description="Name of the tool to invoke.")
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Keyword arguments forwarded to the tool's execute() method.",
    )


@mcp_app.get("/health", tags=["meta"])
def health() -> Dict[str, str]:
    """Liveness probe — returns 200 OK when the server is running."""
    return {"status": "ok", "tools_registered": str(len(registry.list_names()))}


@mcp_app.get(
    "/tools/list",
    response_model=list[ToolDefinition],
    tags=["mcp"],
    summary="List available tools",
)
def tools_list() -> list[ToolDefinition]:
    """
    MCP `tools/list` call.

    Returns the full definition of every tool registered in the ToolRegistry,
    including input schema, so agents can discover what tools are available.
    """
    return registry.list_definitions()


@mcp_app.post(
    "/tools/call",
    response_model=ToolResult,
    tags=["mcp"],
    summary="Call a tool",
    dependencies=[Depends(_verify_api_key)],
)
async def tools_call(request: ToolCallRequest) -> ToolResult:
    """
    MCP `tools/call` call.

    Executes the named tool with the provided arguments and returns a
    ToolResult envelope.  Returns HTTP 404 when the tool is unknown.
    Requires X-MCP-API-Key header when MCP_API_KEY is configured.

    The executor is run in a thread pool so blocking I/O (e.g. httpx.Client)
    does not stall the event loop.
    """
    if request.name not in registry.list_names():
        raise HTTPException(status_code=404, detail=f"Tool '{request.name}' not found.")

    result = await asyncio.to_thread(executor.run, request.name, **request.arguments)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(mcp_app, host="0.0.0.0", port=8001, log_level="info")
