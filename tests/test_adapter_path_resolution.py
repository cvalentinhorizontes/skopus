"""Tests for claude_md_path resolution.

The adapter should prefer <project>/.claude/CLAUDE.md when the .claude/
directory exists, and fall back to <project>/CLAUDE.md otherwise.
"""

from skopus.adapters.base import AdapterStatus
from skopus.adapters.claude_code import (
    SKOPUS_SECTION_START,
    ClaudeCodeAdapter,
    claude_md_path,
)


def test_path_resolution_prefers_claude_dir(tmp_path):
    """When .claude/ exists, install should target .claude/CLAUDE.md."""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    assert claude_md_path(project) == project / ".claude" / "CLAUDE.md"


def test_path_resolution_falls_back_to_root(tmp_path):
    """When .claude/ does not exist, install should target root CLAUDE.md."""
    project = tmp_path / "project"
    project.mkdir()
    assert claude_md_path(project) == project / "CLAUDE.md"


def test_install_wires_into_claude_dir_when_present(tmp_path):
    """If .claude/ exists (typical for a project with agent config),
    skopus should wire the block into .claude/CLAUDE.md, NOT root."""
    project = tmp_path / "project"
    claude_dir = project / ".claude"
    claude_dir.mkdir(parents=True)
    existing_charter = "# Existing Project Charter\n\nWritten manually.\n"
    (claude_dir / "CLAUDE.md").write_text(existing_charter)

    adapter = ClaudeCodeAdapter()
    result = adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )

    # The root file must NOT have been created
    assert not (project / "CLAUDE.md").exists()

    # The .claude/CLAUDE.md file IS wired
    target = claude_dir / "CLAUDE.md"
    assert target.exists()
    content = target.read_text()
    assert "# Existing Project Charter" in content  # original preserved
    assert SKOPUS_SECTION_START in content  # skopus appended

    # A backup of the original was made
    assert len(result.backed_up) == 1
    assert result.backed_up[0].read_text() == existing_charter


def test_install_wires_root_when_no_claude_dir(tmp_path):
    """If .claude/ does NOT exist, fall back to root CLAUDE.md."""
    project = tmp_path / "project"
    project.mkdir()
    # No .claude dir, no pre-existing CLAUDE.md

    adapter = ClaudeCodeAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )

    # Root file IS created
    assert (project / "CLAUDE.md").exists()
    # .claude/CLAUDE.md was NOT created
    assert not (project / ".claude" / "CLAUDE.md").exists()


def test_status_checks_claude_dir_first(tmp_path):
    """status() should look in .claude/CLAUDE.md when .claude/ exists."""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)

    adapter = ClaudeCodeAdapter()
    assert adapter.status(project_path=project) == AdapterStatus.NOT_INSTALLED

    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    assert adapter.status(project_path=project) == AdapterStatus.INSTALLED


def test_uninstall_targets_claude_dir_when_present(tmp_path):
    """uninstall() should remove from .claude/CLAUDE.md when .claude/ exists."""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    existing = "# My Charter\n"
    (project / ".claude" / "CLAUDE.md").write_text(existing)

    adapter = ClaudeCodeAdapter()
    adapter.install(
        charter_path=tmp_path / ".skopus" / "charter",
        vault_path=tmp_path / "Vault",
        project_path=project,
    )
    adapter.uninstall(project_path=project)

    content = (project / ".claude" / "CLAUDE.md").read_text()
    assert SKOPUS_SECTION_START not in content
    assert "# My Charter" in content
