"""Tests for AdapterTier — the honesty surface for which adapters are
smoke-test-verified vs experimental."""

from skopus.adapters import (
    AiderAdapter,
    ClaudeCodeAdapter,
    CodexAdapter,
    CopilotCliAdapter,
    CursorAdapter,
    GeminiCliAdapter,
)
from skopus.adapters.base import Adapter, AdapterTier


def test_adapter_tier_enum_has_three_values():
    """Tier system: ADVERTISED (smoke-tested), EXPERIMENTAL (file-write only),
    UNVERIFIED (placeholder)."""
    assert AdapterTier.ADVERTISED.value == "advertised"
    assert AdapterTier.EXPERIMENTAL.value == "experimental"
    assert AdapterTier.UNVERIFIED.value == "unverified"


def test_base_adapter_default_tier_is_unverified():
    """An adapter that does not set tier explicitly is UNVERIFIED — fail
    closed: claims of verification must be opt-in."""
    assert Adapter.tier is AdapterTier.UNVERIFIED


def test_advertised_adapters_for_v071():
    """v0.7.0 advertises two of the eventual three bridges in this task:
    Claude Code and Cursor. AGENTS.md is added in a separate task."""
    assert ClaudeCodeAdapter.tier is AdapterTier.ADVERTISED
    assert CursorAdapter.tier is AdapterTier.ADVERTISED
    # Aider/Codex/Gemini/Copilot remain experimental until smoke-tested
    assert AiderAdapter.tier is AdapterTier.EXPERIMENTAL
    assert CodexAdapter.tier is AdapterTier.EXPERIMENTAL
    assert GeminiCliAdapter.tier is AdapterTier.EXPERIMENTAL
    assert CopilotCliAdapter.tier is AdapterTier.EXPERIMENTAL
