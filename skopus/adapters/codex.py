"""Codex (OpenAI Codex CLI) adapter — writes to AGENTS.md."""

from __future__ import annotations

from skopus.adapters.base import MarkdownAdapter


class CodexAdapter(MarkdownAdapter):
    """OpenAI Codex CLI — reads AGENTS.md for project-scoped context."""

    name = "codex"
    display_name = "Codex"
    context_file_name = "AGENTS.md"
    prefer_dotdir_name = None  # Codex uses root AGENTS.md
    detect_config_dirs = ["~/.codex"]
    detect_binaries = ["codex"]
