"""Platform adapters — one file per AI coding assistant."""

from skopus.adapters.aider import AiderAdapter
from skopus.adapters.base import Adapter, AdapterStatus
from skopus.adapters.claude_code import ClaudeCodeAdapter
from skopus.adapters.codex import CodexAdapter
from skopus.adapters.copilot import CopilotCliAdapter
from skopus.adapters.cursor import CursorAdapter
from skopus.adapters.gemini import GeminiCliAdapter

# Registry of known adapters. New adapters register themselves here.
# Keys are normalized names (matched against user input via lower/replace).
ADAPTERS: dict[str, type[Adapter]] = {
    "claude-code": ClaudeCodeAdapter,
    "cursor": CursorAdapter,
    "codex": CodexAdapter,
    "aider": AiderAdapter,
    "gemini-cli": GeminiCliAdapter,
    "copilot-cli": CopilotCliAdapter,
    # Aliases for the common name used in the wizard
    "gemini": GeminiCliAdapter,
    "copilot": CopilotCliAdapter,
}


def get_adapter(name: str) -> Adapter:
    """Look up an adapter by normalized name."""
    key = name.lower().replace(" ", "-").replace("_", "-")
    if key not in ADAPTERS:
        raise KeyError(f"unknown adapter: {name} (known: {sorted(ADAPTERS)})")
    return ADAPTERS[key]()


__all__ = [
    "ADAPTERS",
    "Adapter",
    "AdapterStatus",
    "AiderAdapter",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "CopilotCliAdapter",
    "CursorAdapter",
    "GeminiCliAdapter",
    "get_adapter",
]
