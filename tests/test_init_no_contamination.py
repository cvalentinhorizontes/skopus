"""Tests that `skopus init` does not silently re-wire a project that's
already linked to a different ~/.skopus/.

Surfaced 2026-05-05 by the Phase 1+2 manual smoke run: I ran
`HOME=/tmp/throwaway skopus init --non-interactive` from inside my real
project (cwd had `.git/`). Init silently auto-linked cwd, replacing the
real project's CLAUDE.md Skopus block (pointing at `~/.skopus/`) with a
new one pointing at `/tmp/throwaway/.skopus/`. No warning, no opt-out.

Two safeguards locked here:
1. `--no-autolink` flag opts out of the cwd auto-link entirely.
2. Without `--force`, init refuses to re-wire a project whose existing
   Skopus block points at a different skopus_dir.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from skopus.cli import app


def _make_git_project(path: Path) -> None:
    """Make `path` look like a git project (init's auto-link checks for .git)."""
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").mkdir(exist_ok=True)


def _fake_claude_code_install(home: Path) -> None:
    """Create the `~/.claude/` dir so ClaudeCodeAdapter.detect() returns True.
    Without this, init's auto-link silently skips the adapter and the test
    can't exercise the contamination path that we're trying to lock against.
    """
    (home / ".claude").mkdir(parents=True, exist_ok=True)


def test_init_no_autolink_flag_skips_project_wiring(tmp_path, monkeypatch):
    """--no-autolink must not write any context file in cwd."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _fake_claude_code_install(tmp_path / "home")
    project = tmp_path / "project"
    _make_git_project(project)
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["init", "--non-interactive", "--name", "T", "--no-autolink"],
    )
    assert result.exit_code == 0, result.output

    # ~/.skopus/ should be created (global init still runs)
    assert (tmp_path / "home" / ".skopus" / "charter" / "CLAUDE.md").exists()

    # but project's CLAUDE.md / AGENTS.md / .cursor/ should NOT be touched
    assert not (project / "CLAUDE.md").exists()
    assert not (project / ".claude" / "CLAUDE.md").exists()
    assert not (project / "AGENTS.md").exists()
    assert not (project / ".cursor" / "rules" / "skopus.mdc").exists()


def test_init_refuses_to_overwrite_different_skopus_dir(tmp_path, monkeypatch):
    """If cwd already has a Skopus block pointing at a DIFFERENT skopus_dir,
    init must NOT silently overwrite it."""
    project = tmp_path / "project"
    _make_git_project(project)
    (project / "CLAUDE.md").write_text(
        "<!-- skopus:begin -->\n"
        "## Skopus Context\n\n"
        "- Charter: `/tmp/old-home/.skopus/charter/CLAUDE.md`\n"
        "<!-- skopus:end -->\n"
    )

    monkeypatch.setenv("HOME", str(tmp_path / "new-home"))
    _fake_claude_code_install(tmp_path / "new-home")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(app, ["init", "--non-interactive", "--name", "T"])

    project_md = (project / "CLAUDE.md").read_text()
    # The existing wiring must not be silently overwritten.
    assert "/tmp/old-home/.skopus" in project_md, (
        f"init silently re-wired the project to a different skopus_dir. "
        f"This is the cross-contamination bug. CLAUDE.md now contains:\n{project_md}"
    )
    # And init's stdout must mention the conflict
    out = result.output.lower()
    assert "already linked" in out or "already wired" in out or "conflict" in out, (
        f"init must surface the conflict explicitly. Output:\n{result.output}"
    )


def test_init_force_overrides_the_refusal(tmp_path, monkeypatch):
    """With --force, init may overwrite an existing different-skopus_dir wiring."""
    project = tmp_path / "project"
    _make_git_project(project)
    (project / "CLAUDE.md").write_text(
        "<!-- skopus:begin -->\n## Skopus Context\n\n"
        "- Charter: `/tmp/old-home/.skopus/charter/CLAUDE.md`\n"
        "<!-- skopus:end -->\n"
    )

    monkeypatch.setenv("HOME", str(tmp_path / "new-home"))
    _fake_claude_code_install(tmp_path / "new-home")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(app, ["init", "--non-interactive", "--name", "T", "--force"])

    assert result.exit_code == 0, result.output
    project_md = (project / "CLAUDE.md").read_text()
    # With --force, the new HOME's path replaces the old one.
    assert "/tmp/old-home/.skopus" not in project_md
    assert str(tmp_path / "new-home" / ".skopus") in project_md


def test_init_idempotent_when_pointing_at_same_skopus_dir(tmp_path, monkeypatch):
    """If cwd is already linked to the SAME skopus_dir we're initializing,
    re-init is a no-op refresh, not a refusal."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _fake_claude_code_install(tmp_path / "home")
    project = tmp_path / "project"
    _make_git_project(project)
    monkeypatch.chdir(project)

    runner = CliRunner()
    first = runner.invoke(app, ["init", "--non-interactive", "--name", "T"])
    assert first.exit_code == 0, first.output
    assert (project / "CLAUDE.md").exists()

    second = runner.invoke(app, ["init", "--non-interactive", "--name", "T"])
    assert second.exit_code == 0, second.output
