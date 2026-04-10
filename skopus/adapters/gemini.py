"""Gemini CLI adapter — writes to GEMINI.md."""

from __future__ import annotations

from skopus.adapters.base import MarkdownAdapter


class GeminiCliAdapter(MarkdownAdapter):
    """Google Gemini CLI — reads GEMINI.md for project context."""

    name = "gemini-cli"
    display_name = "Gemini CLI"
    context_file_name = "GEMINI.md"
    prefer_dotdir_name = None
    detect_config_dirs = ["~/.gemini"]
    detect_binaries = ["gemini"]
