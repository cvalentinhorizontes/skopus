"""Skopus Guard — installs PreToolUse hooks for agents that support them.

The guard hook injects relevant corrections from feedback memory right before
risky actions (git push, deploy, rm -rf, etc.). This keeps corrections fresh
in the agent's most recent context instead of buried in the system prompt.

Supported agents:
  - Claude Code: hooks via .claude/settings.json (project-level)
  - Cursor: hooks via .cursor/settings.json (project-level)
"""

from __future__ import annotations

import json
import shutil
from importlib.resources import files
from pathlib import Path


# Agents that support PreToolUse hooks
HOOK_CAPABLE_AGENTS = {"claude-code", "cursor"}

# Settings file per agent
SETTINGS_FILES = {
    "claude-code": ".claude/settings.json",
    "cursor": ".cursor/settings.json",
}


def _load_guard_script() -> str:
    """Load the bundled guard hook script."""
    return (files("skopus") / "templates" / "hooks" / "skopus-guard.sh").read_text(
        encoding="utf-8"
    )


def _guard_hook_entry() -> dict:
    """Build the PreToolUse hook entry for settings.json."""
    return {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "command": "$HOME/.skopus/hooks/skopus-guard.sh",
                "timeout": 5,
            }
        ],
    }


def install_guard(project_path: Path, agent: str) -> bool:
    """Install the Skopus guard hook for a project.

    1. Copies the guard script to ~/.skopus/hooks/ (shared across projects)
    2. Adds a PreToolUse hook entry to the project's settings.json

    Returns True if installed, False if the agent doesn't support hooks.
    """
    agent_key = agent.lower().replace(" ", "-")
    if agent_key not in HOOK_CAPABLE_AGENTS:
        return False

    # Step 1: Install the guard script to ~/.skopus/hooks/
    hooks_dir = Path.home() / ".skopus" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    guard_path = hooks_dir / "skopus-guard.sh"
    guard_path.write_text(_load_guard_script(), encoding="utf-8")
    guard_path.chmod(0o755)

    # Step 2: Add hook entry to project settings.json
    settings_rel = SETTINGS_FILES[agent_key]
    settings_path = project_path / settings_rel
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("PreToolUse", [])

    # Check if guard is already installed (idempotent)
    guard_command = "$HOME/.skopus/hooks/skopus-guard.sh"
    already_installed = any(
        any(
            h.get("command", "") == guard_command
            for h in entry.get("hooks", [])
        )
        for entry in pre_tool_use
    )

    if not already_installed:
        pre_tool_use.append(_guard_hook_entry())
        settings_path.write_text(
            json.dumps(settings, indent=2) + "\n", encoding="utf-8"
        )

    return True


def uninstall_guard(project_path: Path, agent: str) -> bool:
    """Remove the Skopus guard hook from a project's settings.json.

    Does NOT delete the guard script from ~/.skopus/hooks/ (other projects
    may still use it).
    """
    agent_key = agent.lower().replace(" ", "-")
    if agent_key not in HOOK_CAPABLE_AGENTS:
        return False

    settings_rel = SETTINGS_FILES[agent_key]
    settings_path = project_path / settings_rel
    if not settings_path.exists():
        return False

    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False

    pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
    guard_command = "$HOME/.skopus/hooks/skopus-guard.sh"

    # Filter out the guard entry
    filtered = [
        entry
        for entry in pre_tool_use
        if not any(
            h.get("command", "") == guard_command
            for h in entry.get("hooks", [])
        )
    ]

    if len(filtered) < len(pre_tool_use):
        settings["hooks"]["PreToolUse"] = filtered
        settings_path.write_text(
            json.dumps(settings, indent=2) + "\n", encoding="utf-8"
        )
        return True

    return False
