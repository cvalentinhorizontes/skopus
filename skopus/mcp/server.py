"""Skopus MCP server — stdio transport via FastMCP.

Builds a FastMCP server with all Skopus tools registered. The actual
server loop is launched by `skopus mcp serve` (CLI command added in Task 28).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from skopus.mcp.tools.charter import skopus_get_charter_section
from skopus.mcp.tools.drift import skopus_record_drift
from skopus.mcp.tools.memory import skopus_search_memory
from skopus.mcp.tools.status import skopus_status
from skopus.mcp.tools.vault import skopus_query_vault


def build_server() -> FastMCP:
    """Construct the Skopus MCP server with all registered tools."""
    server = FastMCP("skopus")
    server.tool()(skopus_status)
    server.tool()(skopus_search_memory)
    server.tool()(skopus_query_vault)
    server.tool()(skopus_get_charter_section)
    server.tool()(skopus_record_drift)
    return server
