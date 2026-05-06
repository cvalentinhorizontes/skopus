"""Tests for AgentsMdAdapter — the universal-fallback writer.

AGENTS.md is the cross-agent standard (Linux Foundation, Anthropic, OpenAI,
Block backed). Skopus needs an explicit adapter that writes ONLY AGENTS.md,
with no agent-specific dotdir, so it can be the canonical Tier C/D fallback
target independent of any specific platform's installation."""

from skopus.adapters import AgentsMdAdapter
from skopus.adapters.base import (
    SKOPUS_SECTION_END,
    SKOPUS_SECTION_START,
    AdapterStatus,
    AdapterTier,
)


def test_agents_md_adapter_is_advertised():
    """AGENTS.md is one of the three v0.7.0 advertised bridges."""
    assert AgentsMdAdapter.tier is AdapterTier.ADVERTISED


def test_agents_md_adapter_name():
    assert AgentsMdAdapter.name == "agents-md"
    assert "AGENTS.md" in AgentsMdAdapter.display_name


def test_agents_md_adapter_writes_root_file_only(tmp_path):
    """Universal fallback: writes <project>/AGENTS.md with no dotdir
    preference and no platform-specific path resolution."""
    project = tmp_path / "project"
    project.mkdir()
    adapter = AgentsMdAdapter()

    # Even if a .claude/ exists, AgentsMdAdapter writes to project root.
    (project / ".claude").mkdir()
    (project / ".cursor").mkdir()

    result = adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )

    assert (project / "AGENTS.md").exists()
    assert not (project / ".claude" / "AGENTS.md").exists()
    content = (project / "AGENTS.md").read_text()
    assert SKOPUS_SECTION_START in content
    assert SKOPUS_SECTION_END in content
    assert result.status is AdapterStatus.INSTALLED


def test_agents_md_adapter_detect_always_true():
    """AGENTS.md is the universal fallback — there is no specific platform
    to detect. detect() returns True so the adapter is always installable."""
    assert AgentsMdAdapter().detect() is True


def test_agents_md_adapter_idempotent(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    adapter = AgentsMdAdapter()

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


def test_agents_md_adapter_preserves_existing_content(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    existing = "# Project AGENTS.md\n\nProject-specific rules here.\n"
    (project / "AGENTS.md").write_text(existing)

    adapter = AgentsMdAdapter()
    result = adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )

    assert len(result.backed_up) == 1
    merged = (project / "AGENTS.md").read_text()
    assert "Project-specific rules here." in merged
    assert SKOPUS_SECTION_START in merged


def test_agents_md_adapter_uninstall_removes_block_only(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    existing = "# Project AGENTS.md\n\nKeep me.\n"
    (project / "AGENTS.md").write_text(existing)

    adapter = AgentsMdAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    adapter.uninstall(project_path=project)

    remaining = (project / "AGENTS.md").read_text()
    assert "Keep me." in remaining
    assert SKOPUS_SECTION_START not in remaining
