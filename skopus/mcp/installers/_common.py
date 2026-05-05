"""Shared helpers for per-agent MCP installers.

Each agent (Claude Code, Cline, Cursor, ...) writes the same
``{"mcpServers": {"skopus": {...}}}`` shape into its own config file.
The only thing that differs per agent is the path. This module owns the
common pieces — server identity, config load with corrupt-JSON fallback,
and a backup helper that preserves invalid existing configs before
overwrite.

Module is underscore-prefixed to signal "internal to ``skopus.mcp.installers``"
without truly hiding the symbols.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SERVER_NAME = "skopus"
SERVER_ENTRY = {"command": "skopus", "args": ["mcp", "serve"]}


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
