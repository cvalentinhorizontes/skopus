"""Claude Code MCP installer.

Writes (or merges into) ~/.claude/settings.json's `mcpServers` block so
Claude Code discovers the Skopus stdio MCP server on next launch.

Behavior:
  * Preserves all other top-level settings.json keys (theme, etc.).
  * Preserves other entries in the mcpServers block.
  * Idempotent: re-running install() updates Skopus's entry in place.
  * Uninstall removes only the skopus entry; other servers untouched.
  * Corrupt JSON in existing settings.json is renamed to a
    ``settings.json.bak-<unix-timestamp>`` sibling before a fresh file
    is written, so the user can recover their original content.
"""

from __future__ import annotations

import json
from pathlib import Path

from skopus.mcp.installers._common import (
    SERVER_NAME,
    backup_corrupt_config,
    build_server_entry,
    load_mcp_config,
)


def _config_path(home: Path) -> Path:
    return home / ".claude" / "settings.json"


def install_claude_code_mcp(home: Path | None = None) -> dict:
    """Add (or refresh) the Skopus entry in Claude Code's mcpServers block.

    Args:
        home: Override for testing. Defaults to ``Path.home()``.

    Returns:
        {"written": True, "config_path": str, "action": "created"|"updated"}
    """
    home = home or Path.home()
    config_path = _config_path(home)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # If the existing file is corrupt JSON, preserve it as .bak-<ts> before
    # load_mcp_config returns {} and we overwrite. This guards against
    # silently destroying a user's settings on a single typo.
    backup_corrupt_config(config_path)

    cfg = load_mcp_config(config_path)
    if "mcpServers" not in cfg or not isinstance(cfg.get("mcpServers"), dict):
        cfg["mcpServers"] = {}

    action = "updated" if SERVER_NAME in cfg["mcpServers"] else "created"
    cfg["mcpServers"][SERVER_NAME] = build_server_entry()

    config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return {"written": True, "config_path": str(config_path), "action": action}


def uninstall_claude_code_mcp(home: Path | None = None) -> dict:
    """Remove the Skopus entry from Claude Code's mcpServers block.

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
