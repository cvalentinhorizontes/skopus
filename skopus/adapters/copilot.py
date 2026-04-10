"""GitHub Copilot CLI adapter — writes to AGENTS.md.

The GitHub Copilot CLI (``gh copilot`` or the standalone ``copilot`` binary)
reads AGENTS.md as a project-scoped context convention. A global skill file
can also be copied to ``~/.copilot/skills/`` if that directory exists.
"""

from __future__ import annotations

from skopus.adapters.base import MarkdownAdapter


class CopilotCliAdapter(MarkdownAdapter):
    """GitHub Copilot CLI — AGENTS.md context."""

    name = "copilot-cli"
    display_name = "GitHub Copilot CLI"
    context_file_name = "AGENTS.md"
    prefer_dotdir_name = None
    detect_config_dirs = ["~/.copilot", "~/.config/gh/copilot"]
    detect_binaries = ["copilot", "gh"]
