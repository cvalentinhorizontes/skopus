"""skopus_status — always-on health check for MCP clients.

Returns whether the server is alive and whether ~/.skopus is initialized.
Used by `skopus doctor --agent <name>` and by agents to verify the
service before issuing other tool calls.
"""

from __future__ import annotations

from pathlib import Path

from skopus import __version__


async def skopus_status() -> dict:
    """Return liveness + initialization state for ~/.skopus."""
    skopus_dir = Path.home() / ".skopus"
    return {
        "alive": True,
        "version": __version__,
        "skopus_dir": str(skopus_dir),
        "skopus_initialized": skopus_dir.exists(),
    }
