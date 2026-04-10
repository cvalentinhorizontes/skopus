"""Tests for the v0.0.3 platform adapters.

Covers the shared MarkdownAdapter pattern across Codex, Aider, Gemini CLI,
and Copilot CLI, plus the custom Cursor adapter.
"""

from pathlib import Path

import pytest

from skopus.adapters import (
    ADAPTERS,
    AiderAdapter,
    CodexAdapter,
    CopilotCliAdapter,
    CursorAdapter,
    GeminiCliAdapter,
    get_adapter,
)
from skopus.adapters.base import (
    SKOPUS_SECTION_END,
    SKOPUS_SECTION_START,
    AdapterStatus,
    MarkdownAdapter,
)


# --- Registry tests ---


def test_registry_has_all_expected_adapters():
    """v0.0.3 registry must include all 6 adapters + aliases."""
    assert "claude-code" in ADAPTERS
    assert "cursor" in ADAPTERS
    assert "codex" in ADAPTERS
    assert "aider" in ADAPTERS
    assert "gemini-cli" in ADAPTERS
    assert "copilot-cli" in ADAPTERS


def test_registry_aliases_resolve():
    """Common aliases (gemini, copilot) should resolve to the full adapter."""
    gemini = get_adapter("gemini")
    assert isinstance(gemini, GeminiCliAdapter)
    copilot = get_adapter("copilot")
    assert isinstance(copilot, CopilotCliAdapter)


def test_get_adapter_normalizes_spaces():
    """'Gemini CLI' should resolve the same as 'gemini-cli'."""
    assert isinstance(get_adapter("Gemini CLI"), GeminiCliAdapter)
    assert isinstance(get_adapter("Copilot CLI"), CopilotCliAdapter)


# --- Codex adapter (MarkdownAdapter pattern) ---


def test_codex_writes_agents_md(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    adapter = CodexAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    agents_md = project / "AGENTS.md"
    assert agents_md.exists()
    content = agents_md.read_text()
    assert SKOPUS_SECTION_START in content
    assert SKOPUS_SECTION_END in content


def test_codex_idempotent(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    adapter = CodexAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    content = (project / "AGENTS.md").read_text()
    assert content.count(SKOPUS_SECTION_START) == 1


def test_codex_status_and_uninstall(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    adapter = CodexAdapter()
    assert adapter.status(project_path=project) == AdapterStatus.NOT_INSTALLED
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert adapter.status(project_path=project) == AdapterStatus.INSTALLED
    adapter.uninstall(project_path=project)
    assert adapter.status(project_path=project) == AdapterStatus.NOT_INSTALLED


def test_codex_backs_up_existing_agents_md(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    existing = "# Codex rules\n\nMy rules here.\n"
    (project / "AGENTS.md").write_text(existing)

    adapter = CodexAdapter()
    result = adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert len(result.backed_up) == 1
    assert result.backed_up[0].read_text() == existing
    merged = (project / "AGENTS.md").read_text()
    assert "# Codex rules" in merged
    assert SKOPUS_SECTION_START in merged


# --- Aider, Gemini, Copilot (share the same base path) ---


@pytest.mark.parametrize(
    "adapter_cls,file_name",
    [
        (AiderAdapter, "AGENTS.md"),
        (GeminiCliAdapter, "GEMINI.md"),
        (CopilotCliAdapter, "AGENTS.md"),
    ],
)
def test_markdown_adapter_writes_correct_file(tmp_path, adapter_cls, file_name):
    project = tmp_path / "project"
    project.mkdir()
    adapter = adapter_cls()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert (project / file_name).exists()
    content = (project / file_name).read_text()
    assert SKOPUS_SECTION_START in content


@pytest.mark.parametrize(
    "adapter_cls",
    [AiderAdapter, CodexAdapter, GeminiCliAdapter, CopilotCliAdapter],
)
def test_detect_returns_bool(adapter_cls):
    """All adapters must implement detect() and return a bool."""
    adapter = adapter_cls()
    result = adapter.detect()
    assert isinstance(result, bool)


# --- Cursor adapter (custom — MDC format) ---


def test_cursor_writes_mdc_rule(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    adapter = CursorAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    rule = project / ".cursor" / "rules" / "skopus.mdc"
    assert rule.exists()
    content = rule.read_text()
    # MDC frontmatter with alwaysApply
    assert "alwaysApply: true" in content
    assert "---" in content
    assert SKOPUS_SECTION_START in content


def test_cursor_status_and_uninstall(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    adapter = CursorAdapter()
    assert adapter.status(project_path=project) == AdapterStatus.NOT_INSTALLED
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert adapter.status(project_path=project) == AdapterStatus.INSTALLED
    adapter.uninstall(project_path=project)
    assert adapter.status(project_path=project) == AdapterStatus.NOT_INSTALLED
    assert not (project / ".cursor" / "rules" / "skopus.mdc").exists()


def test_cursor_detect_returns_bool():
    adapter = CursorAdapter()
    assert isinstance(adapter.detect(), bool)


# --- MarkdownAdapter.prefer_dotdir_name ---


class _DotDirAdapter(MarkdownAdapter):
    """Test adapter that prefers a dotdir."""

    name = "test-dotdir"
    context_file_name = "CONFIG.md"
    prefer_dotdir_name = ".testagent"


def test_markdown_adapter_prefers_dotdir_when_present(tmp_path):
    project = tmp_path / "project"
    (project / ".testagent").mkdir(parents=True)

    adapter = _DotDirAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert (project / ".testagent" / "CONFIG.md").exists()
    assert not (project / "CONFIG.md").exists()


def test_markdown_adapter_falls_back_to_root_without_dotdir(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    adapter = _DotDirAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert (project / "CONFIG.md").exists()
    assert not (project / ".testagent" / "CONFIG.md").exists()
