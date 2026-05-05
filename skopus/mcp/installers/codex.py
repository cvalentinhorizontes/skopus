"""Codex CLI MCP installer.

Writes (or merges into) ``~/.codex/config.toml``'s ``[mcp_servers.skopus]``
section so the OpenAI Codex CLI agent discovers the Skopus stdio MCP
server on next launch.

Codex CLI uses TOML (not JSON) and snake_case key naming
(``mcp_servers``, not ``mcpServers``). Schema reference:
https://developers.openai.com/codex/config-reference

Behavior mirrors the JSON installers (claude_code, cline, cursor): the
shared ``build_server_entry()`` resolves ``skopus`` to an absolute path at
install time so Codex's spawn environment can find it without depending
on shell PATH (the same class of bug as the Cursor fix in ``eeda5c2``).
Corrupt-TOML safety mirrors the JSON ``backup_corrupt_config`` pattern.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 CI matrix only
    import tomli as tomllib

from skopus.mcp.installers._common import SERVER_NAME, build_server_entry

logger = logging.getLogger(__name__)


def _config_path(home: Path) -> Path:
    return home / ".codex" / "config.toml"


def _load_codex_config(config_path: Path) -> dict[str, Any]:
    """Load a Codex TOML config. Returns {} on missing file or unparseable TOML.

    Side-effect-free: callers that want to preserve a corrupt file must
    back it up via ``_backup_corrupt_toml`` BEFORE calling this.
    """
    if not config_path.is_file():
        return {}
    try:
        loaded: dict[str, Any] = tomllib.loads(config_path.read_text(encoding="utf-8"))
        return loaded
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.warning("skopus.mcp.installers.codex: cannot read %s: %s", config_path, exc)
        return {}


def _backup_corrupt_toml(config_path: Path) -> Path | None:
    """If ``config_path`` exists but is invalid TOML, rename it to a
    ``<name>.bak-<unix-ts>`` sibling so the user can recover.

    Mirrors ``_common.backup_corrupt_config`` but for TOML instead of JSON
    (the JSON helper hard-codes ``json.JSONDecodeError`` so it can't be
    reused). Returns the backup path, or ``None`` if no backup was needed.
    """
    if not config_path.is_file():
        return None
    try:
        tomllib.loads(config_path.read_text(encoding="utf-8"))
        return None  # valid TOML, no backup needed
    except tomllib.TOMLDecodeError:
        ts = int(time.time())
        backup = config_path.with_name(f"{config_path.name}.bak-{ts}")
        config_path.rename(backup)
        logger.warning(
            "skopus.mcp.installers.codex: corrupt TOML in %s; moved to %s before overwrite",
            config_path,
            backup,
        )
        return backup
    except OSError:
        return None


def install_codex_mcp(home: Path | None = None) -> dict[str, Any]:
    """Add (or refresh) the Skopus entry in Codex's ``[mcp_servers]`` table.

    Args:
        home: Override for testing. Defaults to ``Path.home()``.

    Returns:
        ``{"written": True, "config_path": str, "action": "created"|"updated"}``
    """
    home = home or Path.home()
    config_path = _config_path(home)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    _backup_corrupt_toml(config_path)

    cfg = _load_codex_config(config_path)
    if "mcp_servers" not in cfg or not isinstance(cfg.get("mcp_servers"), dict):
        cfg["mcp_servers"] = {}

    action = "updated" if SERVER_NAME in cfg["mcp_servers"] else "created"
    cfg["mcp_servers"][SERVER_NAME] = build_server_entry()

    # tomli_w writes a clean TOML representation. Comments and original
    # whitespace from a hand-edited config will be lost — same tradeoff
    # the JSON installers make when they reformat to indent=2.
    config_path.write_bytes(tomli_w.dumps(cfg).encode("utf-8"))
    return {"written": True, "config_path": str(config_path), "action": action}


def uninstall_codex_mcp(home: Path | None = None) -> dict[str, Any]:
    """Remove the Skopus entry from Codex's ``[mcp_servers]`` table.

    Leaves any other ``mcp_servers.<name>`` entries and top-level Codex
    config keys untouched. If removing skopus empties the ``mcp_servers``
    table, the empty table is dropped so we don't leave a stale section.

    Args:
        home: Override for testing. Defaults to ``Path.home()``.

    Returns:
        ``{"removed": True, "config_path": str}`` or
        ``{"removed": False, "reason": str}`` when nothing to do.
    """
    home = home or Path.home()
    config_path = _config_path(home)
    if not config_path.is_file():
        return {"removed": False, "reason": "config not found"}

    cfg = _load_codex_config(config_path)
    if SERVER_NAME not in cfg.get("mcp_servers", {}):
        return {"removed": False, "reason": "skopus entry not present"}

    del cfg["mcp_servers"][SERVER_NAME]
    if not cfg["mcp_servers"]:
        del cfg["mcp_servers"]

    config_path.write_bytes(tomli_w.dumps(cfg).encode("utf-8"))
    return {"removed": True, "config_path": str(config_path)}
