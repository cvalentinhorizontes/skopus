"""Platform adapters — one file per AI coding assistant."""

from skopus.adapters.base import Adapter, AdapterStatus
from skopus.adapters.claude_code import ClaudeCodeAdapter

# Registry of known adapters. New adapters register themselves here.
ADAPTERS: dict[str, type[Adapter]] = {
    "claude-code": ClaudeCodeAdapter,
    # v0.0.2: cursor, codex, aider, gemini, copilot, opencode
}


def get_adapter(name: str) -> Adapter:
    """Look up an adapter by normalized name."""
    key = name.lower().replace(" ", "-").replace("_", "-")
    if key not in ADAPTERS:
        raise KeyError(f"unknown adapter: {name} (known: {sorted(ADAPTERS)})")
    return ADAPTERS[key]()


__all__ = ["Adapter", "AdapterStatus", "get_adapter", "ADAPTERS"]
