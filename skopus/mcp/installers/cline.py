"""Cline MCP installer.

Writes (or merges into) ~/.config/cline/cline_mcp_settings.json's
``mcpServers`` block so Cline discovers the Skopus stdio MCP server on
next launch.

Behavior mirrors the Claude Code installer — see
``skopus.mcp.installers._common`` for shared helpers.
"""

from __future__ import annotations

import json
from pathlib import Path

from skopus.mcp.installers._common import (
    SERVER_ENTRY,
    SERVER_NAME,
    backup_corrupt_config,
    load_mcp_config,
)


def _config_path(home: Path) -> Path:
    return home / ".config" / "cline" / "cline_mcp_settings.json"


def install_cline_mcp(home: Path | None = None) -> dict:
    """Add (or refresh) the Skopus entry in Cline's mcpServers block.

    Args:
        home: Override for testing. Defaults to ``Path.home()``.

    Returns:
        {"written": True, "config_path": str, "action": "created"|"updated"}
    """
    home = home or Path.home()
    config_path = _config_path(home)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    backup_corrupt_config(config_path)

    cfg = load_mcp_config(config_path)
    if "mcpServers" not in cfg or not isinstance(cfg.get("mcpServers"), dict):
        cfg["mcpServers"] = {}

    action = "updated" if SERVER_NAME in cfg["mcpServers"] else "created"
    cfg["mcpServers"][SERVER_NAME] = SERVER_ENTRY

    config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return {"written": True, "config_path": str(config_path), "action": action}


def uninstall_cline_mcp(home: Path | None = None) -> dict:
    """Remove the Skopus entry from Cline's mcpServers block.

    Args:
        home: Override for testing. Defaults to ``Path.home()``.

    Returns:
        {"removed": True, "config_path": str}
        or {"removed": False, "reason": str} when nothing to do.
    """
    home = home or Path.home()
    config_path = _config_path(home)
    if not config_path.is_file():
        return {"removed": False, "reason": "config not found"}

    cfg = load_mcp_config(config_path)
    if SERVER_NAME not in cfg.get("mcpServers", {}):
        return {"removed": False, "reason": "skopus entry not present"}

    del cfg["mcpServers"][SERVER_NAME]
    config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return {"removed": True, "config_path": str(config_path)}
