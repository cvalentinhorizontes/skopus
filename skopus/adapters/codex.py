"""Codex (OpenAI Codex CLI) adapter — writes to AGENTS.md and ``$CODEX_HOME/skills/``."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from skopus.adapters.base import AdapterTier, MarkdownAdapter
from skopus.commands import load_command_templates, write_skill_md


class CodexAdapter(MarkdownAdapter):
    """OpenAI Codex CLI — reads AGENTS.md for project-scoped context.

    User-defined skills live at ``$CODEX_HOME/skills/<name>/SKILL.md`` (the
    ``init_skill.py`` convention shipped with codex-rs). Default
    ``CODEX_HOME`` is ``~/.codex``.
    """

    name = "codex"
    display_name = "Codex"
    tier = AdapterTier.EXPERIMENTAL
    context_file_name = "AGENTS.md"
    prefer_dotdir_name = None  # Codex uses root AGENTS.md
    detect_config_dirs: ClassVar[list[str]] = ["~/.codex"]
    detect_binaries: ClassVar[list[str]] = ["codex"]

    def install_commands(self, skopus_dir: Path) -> list[Path]:
        codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        skills_dir = codex_home / "skills"
        return [write_skill_md(skills_dir, t) for t in load_command_templates()]
