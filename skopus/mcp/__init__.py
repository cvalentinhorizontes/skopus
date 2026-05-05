"""Skopus MCP server — exposes Skopus context via the Model Context Protocol
so any MCP-capable agent can query on demand instead of inlining everything
at session start.

Currently registers: skopus_status, skopus_search_memory, skopus_query_vault,
skopus_get_charter_section, skopus_record_drift."""

from skopus.mcp.server import build_server

__all__ = ["build_server"]
