"""AGENTS.md adapter — the universal-fallback writer.

AGENTS.md is the cross-agent standard backed by the Linux Foundation
(Anthropic, OpenAI, Block, etc.). This adapter writes a single
AGENTS.md at the project root with the slim Skopus context block,
serving as the Tier C/D fallback for any agent that consumes AGENTS.md
but does not have a dedicated Skopus adapter.

Unlike the agent-specific MarkdownAdapter subclasses (aider, codex,
copilot, gemini), this adapter:
  * has no `prefer_dotdir_name` (always project root)
  * has no platform detection (universal — detect() always True)
  * is the canonical writer for the AGENTS.md surface
"""

from __future__ import annotations

from skopus.adapters.base import AdapterTier, MarkdownAdapter


class AgentsMdAdapter(MarkdownAdapter):
    """Universal-fallback writer for AGENTS.md."""

    name = "agents-md"
    display_name = "AGENTS.md (universal)"
    tier = AdapterTier.ADVERTISED
    context_file_name = "AGENTS.md"
    prefer_dotdir_name = None

    def detect(self) -> bool:
        """Universal fallback — always installable, no platform to detect."""
        return True
