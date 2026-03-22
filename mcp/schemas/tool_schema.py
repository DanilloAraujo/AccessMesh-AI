"""
mcp/schemas/tool_schema.py
───────────────────────────
Pydantic schemas that describe MCP tool definitions, their input contracts,
and the structure of execution results.

These schemas follow the Model Context Protocol specification so tools can
be served by any MCP-compatible server and consumed by any MCP-capable agent.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PropertySchema(BaseModel):
    """JSON-Schema-style definition of a single input property."""

    type: str = Field(..., description="JSON Schema type (string, number, array, object, boolean).")
    description: Optional[str] = Field(default=None, description="Human-readable description.")
    default: Optional[Any] = Field(default=None, description="Default value if not provided.")
    items: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Schema for array items (when type == 'array').",
    )


class ToolInputSchema(BaseModel):
    """
    JSON Schema object describing the inputs accepted by a tool.
    Maps directly to the `input_schema` attribute on each tool class.
    """

    type: str = Field(default="object", description="Always 'object' for MCP tools.")
    required: List[str] = Field(default_factory=list, description="Required property names.")
    properties: Dict[str, PropertySchema] = Field(
        default_factory=dict,
        description="Map of property name → PropertySchema.",
    )


class ToolDefinition(BaseModel):
    """
    Full definition of an MCP tool as advertised to agents via the tool registry.

    This is what an agent receives when it calls `tools/list` on the MCP server.
    """

    name: str = Field(..., description="Unique tool identifier (snake_case).")
    description: str = Field(..., description="Human-readable description of the tool's purpose.")
    version: str = Field(default="1.0.0", description="Semantic version of the tool contract.")
    input_schema: ToolInputSchema = Field(..., description="Schema for the tool's input parameters.")


class ToolResult(BaseModel):
    """
    Standardised response envelope returned after tool execution.

    Wraps the raw output dict from each tool's `execute()` method with
    metadata about success / failure.
    """

    tool_name: str = Field(..., description="Name of the tool that was executed.")
    success: bool = Field(..., description="Whether the execution completed without errors.")
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Execution result payload on success.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message when success is False.",
    )
