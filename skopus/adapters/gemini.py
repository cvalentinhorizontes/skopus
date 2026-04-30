"""Gemini CLI adapter — writes to GEMINI.md and ``~/.gemini/commands/``."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from skopus.adapters.base import MarkdownAdapter
from skopus.commands import load_command_templates, write_gemini_toml


class GeminiCliAdapter(MarkdownAdapter):
    """Google Gemini CLI — reads GEMINI.md for project context.

    User-defined custom commands live at ``~/.gemini/commands/<name>.toml``;
    each TOML file declares a ``description`` and a ``prompt`` body that
    Gemini executes when the user types ``/<name>``.
    """

    name = "gemini-cli"
    display_name = "Gemini CLI"
    context_file_name = "GEMINI.md"
    prefer_dotdir_name = None
    detect_config_dirs: ClassVar[list[str]] = ["~/.gemini"]
    detect_binaries: ClassVar[list[str]] = ["gemini"]

    def install_commands(self, skopus_dir: Path) -> list[Path]:
        commands_dir = Path.home() / ".gemini" / "commands"
        return [write_gemini_toml(commands_dir, t) for t in load_command_templates()]
