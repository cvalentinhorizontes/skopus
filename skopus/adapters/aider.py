"""Aider adapter — writes to AGENTS.md.

Aider (https://aider.chat) doesn't have native per-project context auto-loading
in the same way Claude Code does, but it reads AGENTS.md as a convention when
available. Aider has ``.aider.conf.yml`` for configuration.
"""

from __future__ import annotations

from pathlib import Path

from skopus.adapters.base import MarkdownAdapter


class AiderAdapter(MarkdownAdapter):
    """Aider (paulgauthier/aider) — AGENTS.md context."""

    name = "aider"
    display_name = "Aider"
    context_file_name = "AGENTS.md"
    prefer_dotdir_name = None
    detect_config_dirs = ["~/.aider.conf.yml", "~/.aider"]
    detect_binaries = ["aider"]

    def detect(self) -> bool:
        """Aider's config file is a file, not a dir — handle it specially."""
        import shutil as _shutil

        for dir_path in self.detect_config_dirs:
            expanded = Path(dir_path).expanduser()
            if expanded.exists():  # works for both file and dir
                return True
        for binary in self.detect_binaries:
            if _shutil.which(binary):
                return True
        return False
