"""Shared helpers for per-agent MCP installers.

Each agent (Claude Code, Cline, Cursor, ...) writes the same
``{"mcpServers": {"skopus": {...}}}`` shape into its own config file.
The only thing that differs per agent is the path. This module owns the
common pieces — server identity, config load with corrupt-JSON fallback,
a backup helper that preserves invalid existing configs before
overwrite, and the SERVER_ENTRY builder that resolves ``skopus`` to its
absolute path at install time.

Module is underscore-prefixed to signal "internal to ``skopus.mcp.installers``"
without truly hiding the symbols.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SERVER_NAME = "skopus"


class SkopusBinaryNotFoundError(RuntimeError):
    """Raised when the `skopus` binary cannot be located on PATH at install
    time. Without an absolute path in the MCP config, desktop agents
    (Cursor, Claude Code, etc.) spawn the server with a minimal PATH that
    typically does NOT include ~/.local/bin or other pipx/venv dirs, so
    the spawn fails silently and the agent reports zero Skopus tools.

    Surfaced 2026-05-05 by the Phase 2 manual smoke run: Carlos wired
    Cursor with `skopus link --mcp cursor`. Cursor's mcp.json correctly
    contained `{"command": "skopus", ...}` but Cursor couldn't find
    `skopus` in its spawn env. Tools never registered. Zero error
    surfaced to the user.
    """


def build_server_entry() -> dict[str, object]:
    """Return the MCP `mcpServers.skopus` entry with an ABSOLUTE path to
    the `skopus` binary.

    Resolves at install time via shutil.which. If `skopus` is not on the
    install-time PATH, raises SkopusBinaryNotFoundError with remediation
    guidance — DO NOT fall back to the bare string ``skopus``: that's
    the bug pattern this exists to prevent.
    """
    binary = shutil.which("skopus")
    if binary is None:
        raise SkopusBinaryNotFoundError(
            "Could not find `skopus` on PATH at install time. The MCP "
            "config needs an absolute path so agent runtimes (Cursor, "
            "Claude Code Desktop, etc.) can spawn it from their own "
            "minimal environment. Install skopus globally or via pipx "
            "and ensure the install dir is on your shell PATH, then "
            "re-run `skopus link --mcp <agent>`."
        )
    return {"command": binary, "args": ["mcp", "serve"]}


# Back-compat: callers that imported SERVER_ENTRY directly still work, but
# they get a SNAPSHOT taken at module-import time. Prefer build_server_entry()
# for new code so the resolution happens at install time, not import time.
def _import_time_entry() -> dict[str, object]:
    """Import-time fallback. If skopus isn't on PATH at import time (e.g.
    during a fresh test environment), don't crash — defer to install-time
    resolution. Tests pass an explicit `command` override anyway."""
    try:
        return build_server_entry()
    except SkopusBinaryNotFoundError:
        return {"command": "skopus", "args": ["mcp", "serve"]}


SERVER_ENTRY = _import_time_entry()


def load_mcp_config(config_path: Path) -> dict:
    """Load an MCP config file. Returns {} on missing file or invalid JSON.

    Side-effect-free: callers that want to preserve a corrupt file
    must back it up via ``backup_corrupt_config`` BEFORE calling this.
    """
    if not config_path.is_file():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "skopus.mcp.installers: cannot read %s: %s",
            config_path,
            exc,
        )
        return {}
    return data if isinstance(data, dict) else {}


def backup_corrupt_config(config_path: Path) -> Path | None:
    """If ``config_path`` exists but is invalid JSON, rename it to a
    ``<name>.bak-<unix-ts>`` sibling so the user can recover.

    Returns the backup path, or ``None`` if no backup was needed
    (file missing, valid JSON, or unreadable).
    """
    if not config_path.is_file():
        return None
    try:
        json.loads(config_path.read_text(encoding="utf-8"))
        return None  # valid JSON, no backup needed
    except json.JSONDecodeError:
        ts = int(time.time())
        # Preserve the full original filename (including its real suffix)
        # and append .bak-<ts>. Using ``with_suffix`` would clobber a
        # multi-part name like ``cline_mcp_settings.json``.
        backup = config_path.with_name(f"{config_path.name}.bak-{ts}")
        config_path.rename(backup)
        logger.warning(
            "skopus.mcp.installers: corrupt JSON in %s; moved to %s before overwrite",
            config_path,
            backup,
        )
        return backup
    except OSError:
        return None  # leave untouched if unreadable
