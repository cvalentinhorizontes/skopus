"""Smoke tests for ADVERTISED adapters — the file-side contract.

These tests assert the contract Skopus owns:
  * install() writes the expected file at the expected path
  * the file contains valid Skopus markers
  * the file is well-formed for its target format (markdown, MDC frontmatter, etc.)
  * status() agrees with the file state
  * uninstall() restores cleanly
  * idempotent install — two installs == one block

These do NOT assert that the agent platform actually loads the file at
session start. That's a separate manual smoke list at
docs/proposals/skopus-v1/phase1-manual-smoke.md, out of scope for pytest
because it requires the platform installed and a live session."""

import re

import pytest

from skopus.adapters import (
    ADAPTERS,
    AdapterStatus,
    AdapterTier,
    AgentsMdAdapter,
    ClaudeCodeAdapter,
    CursorAdapter,
)
from skopus.adapters.base import SKOPUS_SECTION_END, SKOPUS_SECTION_START

# Single source of truth for what's advertised + what file we expect.
ADVERTISED_ADAPTERS = [
    pytest.param(ClaudeCodeAdapter, "CLAUDE.md", "claude-code", id="claude-code"),
    pytest.param(CursorAdapter, ".cursor/rules/skopus.mdc", "cursor", id="cursor"),
    pytest.param(AgentsMdAdapter, "AGENTS.md", "agents-md", id="agents-md"),
]


@pytest.mark.parametrize("adapter_cls,relative_path,name", ADVERTISED_ADAPTERS)
def test_advertised_adapter_is_in_registry(adapter_cls, relative_path, name):
    """Every adapter we claim to advertise must be in ADAPTERS by its canonical name."""
    assert name in ADAPTERS
    assert ADAPTERS[name] is adapter_cls


@pytest.mark.parametrize("adapter_cls,relative_path,name", ADVERTISED_ADAPTERS)
def test_advertised_adapter_has_advertised_tier(adapter_cls, relative_path, name):
    """Tier honesty: advertised list and tier attribute must agree."""
    assert adapter_cls.tier is AdapterTier.ADVERTISED


@pytest.mark.parametrize("adapter_cls,relative_path,name", ADVERTISED_ADAPTERS)
def test_install_writes_expected_file(tmp_path, adapter_cls, relative_path, name):
    project = tmp_path / "project"
    project.mkdir()
    adapter = adapter_cls()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    expected = project / relative_path
    assert expected.exists(), f"{adapter_cls.__name__} did not write {relative_path}"
    content = expected.read_text(encoding="utf-8")
    assert SKOPUS_SECTION_START in content
    assert SKOPUS_SECTION_END in content


@pytest.mark.parametrize("adapter_cls,relative_path,name", ADVERTISED_ADAPTERS)
def test_status_matches_file_state(tmp_path, adapter_cls, relative_path, name):
    project = tmp_path / "project"
    project.mkdir()
    adapter = adapter_cls()
    assert adapter.status(project_path=project) is AdapterStatus.NOT_INSTALLED
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert adapter.status(project_path=project) is AdapterStatus.INSTALLED
    adapter.uninstall(project_path=project)
    assert adapter.status(project_path=project) is AdapterStatus.NOT_INSTALLED


@pytest.mark.parametrize("adapter_cls,relative_path,name", ADVERTISED_ADAPTERS)
def test_install_is_idempotent(tmp_path, adapter_cls, relative_path, name):
    project = tmp_path / "project"
    project.mkdir()
    adapter = adapter_cls()
    for _ in range(3):
        adapter.install(
            charter_path=tmp_path / ".skopus" / "charter",
            vault_path=tmp_path / "Vault",
            project_path=project,
        )
    expected = project / relative_path
    content = expected.read_text(encoding="utf-8")
    assert content.count(SKOPUS_SECTION_START) == 1
    assert content.count(SKOPUS_SECTION_END) == 1


def test_cursor_adapter_writes_valid_mdc_frontmatter(tmp_path):
    """Cursor's .mdc requires YAML frontmatter with `alwaysApply` to be loaded.

    Uses regex (not PyYAML) to keep the test dependency-free — this is a
    smoke check that the contract is met, not a full YAML compliance check."""
    project = tmp_path / "project"
    project.mkdir()
    CursorAdapter().install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    content = (project / ".cursor" / "rules" / "skopus.mdc").read_text(encoding="utf-8")

    # MDC frontmatter is delimited by --- ... --- at the top of the file.
    assert content.startswith("---\n"), "Cursor MDC must open with frontmatter delimiter '---'"
    # alwaysApply: true must appear (any whitespace, anywhere in the frontmatter)
    assert re.search(r"^alwaysApply:\s*true\s*$", content, re.MULTILINE), (
        "Cursor MDC must declare 'alwaysApply: true' in frontmatter"
    )


def test_agents_md_adapter_does_not_use_dotdir_even_when_present(tmp_path):
    """AGENTS.md is universal — must never write to .claude/AGENTS.md
    or other dotdir variants, even when those dotdirs exist."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".claude").mkdir()
    (project / ".cursor").mkdir()
    AgentsMdAdapter().install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert (project / "AGENTS.md").exists()
    assert not (project / ".claude" / "AGENTS.md").exists()
    assert not (project / ".cursor" / "AGENTS.md").exists()
