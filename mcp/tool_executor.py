"""Invokes tools by name with validated parameters."""

from __future__ import annotations

import logging
from typing import Any, Dict

from mcp.schemas.tool_schema import ToolResult
from mcp.tool_registry import ToolRegistry, registry as _default_registry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes MCP tools looked up from a ToolRegistry."""

    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        self._registry = tool_registry or _default_registry

    def run(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """
        Execute the named tool and return a ToolResult.

        Returns success=True with the tool output dict in ``data``,
        or success=False with an error message in ``error``.
        """
        tool = self._registry.get(tool_name)
        if tool is None:
            logger.warning("ToolExecutor: tool '%s' not found in registry. Available: %s", tool_name, self._registry.list_names())
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' is not registered.",
            )

        logger.info("ToolExecutor: executing '%s' with args=%s", tool_name, list(kwargs.keys()))
        try:
            result: Dict[str, Any] = tool.execute(**kwargs)
            logger.info("ToolExecutor: '%s' executed successfully. result_keys=%s", tool_name, list(result.keys()) if isinstance(result, dict) else '?')
            return ToolResult(tool_name=tool_name, success=True, data=result)
        except Exception as exc:
            logger.error("ToolExecutor: '%s' raised an exception — %s", tool_name, exc)
            return ToolResult(tool_name=tool_name, success=False, error=str(exc))


# Module-level singleton for convenience.
executor = ToolExecutor()
