"""Tests for skopus.adapters.claude_code."""

from pathlib import Path

from skopus.adapters import get_adapter
from skopus.adapters.base import AdapterStatus
from skopus.adapters.claude_code import (
    SKOPUS_SECTION_END,
    SKOPUS_SECTION_START,
    ClaudeCodeAdapter,
)


def test_get_adapter_returns_claude_code():
    adapter = get_adapter("claude-code")
    assert isinstance(adapter, ClaudeCodeAdapter)
    assert adapter.name == "claude-code"


def test_get_adapter_normalizes_name():
    adapter = get_adapter("Claude Code")
    assert isinstance(adapter, ClaudeCodeAdapter)


def test_get_adapter_raises_on_unknown():
    import pytest

    with pytest.raises(KeyError):
        get_adapter("nonexistent")


def test_install_creates_new_claude_md(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    charter = tmp_path / ".skopus" / "charter"
    vault = tmp_path / "Vault"

    adapter = ClaudeCodeAdapter()
    result = adapter.install(charter_path=charter, vault_path=vault, project_path=project)

    assert result.status == AdapterStatus.INSTALLED
    claude_md = project / "CLAUDE.md"
    assert claude_md.exists()
    content = claude_md.read_text()
    assert SKOPUS_SECTION_START in content
    assert SKOPUS_SECTION_END in content
    assert str(charter) in content
    assert str(vault) in content


def test_install_backs_up_existing_claude_md(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    existing_content = "# My Project\n\nSome existing rules.\n"
    (project / "CLAUDE.md").write_text(existing_content)

    adapter = ClaudeCodeAdapter()
    result = adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )

    assert len(result.backed_up) == 1
    backup = result.backed_up[0]
    assert backup.exists()
    assert backup.read_text() == existing_content

    merged = (project / "CLAUDE.md").read_text()
    assert "# My Project" in merged  # existing preserved
    assert SKOPUS_SECTION_START in merged  # skopus added


def test_install_is_idempotent(tmp_path):
    """Installing twice should update the block in place, not duplicate it."""
    project = tmp_path / "project"
    project.mkdir()
    adapter = ClaudeCodeAdapter()

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

    content = (project / "CLAUDE.md").read_text()
    # Only one skopus block
    assert content.count(SKOPUS_SECTION_START) == 1
    assert content.count(SKOPUS_SECTION_END) == 1


def test_uninstall_removes_skopus_block(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    existing = "# My Project\n\nSome rules.\n"
    (project / "CLAUDE.md").write_text(existing)

    adapter = ClaudeCodeAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    adapter.uninstall(project_path=project)

    content = (project / "CLAUDE.md").read_text()
    assert SKOPUS_SECTION_START not in content
    assert "# My Project" in content  # original preserved


def test_uninstall_on_empty_restores_backup(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    existing = "original content\n"
    (project / "CLAUDE.md").write_text(existing)

    adapter = ClaudeCodeAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    adapter.uninstall(project_path=project)

    # Backup should have been used to restore original
    restored = (project / "CLAUDE.md").read_text()
    assert "original content" in restored


def test_status_reports_installed_state(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    adapter = ClaudeCodeAdapter()

    assert adapter.status(project_path=project) == AdapterStatus.NOT_INSTALLED

    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert adapter.status(project_path=project) == AdapterStatus.INSTALLED


def test_detect_returns_bool():
    """detect() should return a bool without raising."""
    adapter = ClaudeCodeAdapter()
    result = adapter.detect()
    assert isinstance(result, bool)
