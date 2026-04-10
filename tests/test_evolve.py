"""Tests for skopus.evolve."""

from pathlib import Path

from skopus.evolve import (
    EvolveEntry,
    _append_to_charter,
    _slugify,
    _write_feedback_file,
    run_evolve,
)
from skopus.renderer import materialize
from skopus.wizard import default_result


def test_slugify_basic():
    assert _slugify("Hello World") == "hello-world"
    assert _slugify("Root cause over symptom") == "root-cause-over-symptom"
    assert _slugify("") == "entry"
    assert _slugify("!!!---!!!") == "entry"


def test_slugify_length_capped():
    long_title = "a" * 100
    assert len(_slugify(long_title)) <= 40


def test_write_feedback_file(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "memory" / "feedback").mkdir(parents=True)

    entry = EvolveEntry(
        kind="validated",
        title="Use TeamCreate for investigate",
        why="Structured coordination beats fire-and-forget",
        how_to_apply="Always use TeamCreate + SendMessage for multi-agent research",
    )
    path = _write_feedback_file(skopus_dir, entry)

    assert path.exists()
    content = path.read_text()
    assert "Use TeamCreate for investigate" in content
    assert "Structured coordination" in content
    assert "SendMessage" in content
    assert path.parent == skopus_dir / "memory" / "feedback"


def test_append_to_charter_adds_drift_entry(tmp_path):
    """Drift entries should be appended to §7 of the full charter."""
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    result = default_result(name="EvolveTest")
    materialize(result, skopus_dir, vault_dir, commit=False)

    drift = EvolveEntry(
        kind="drift",
        title="Pushed without CI running",
        why="Broke PR reviewer's time",
        how_to_apply="Always run make ci-backend before git push",
    )
    updated = _append_to_charter(skopus_dir, [drift])

    assert "§7 (drift log)" in updated
    charter_content = (skopus_dir / "charter" / "workflow_partnership.md").read_text()
    assert "Pushed without CI running" in charter_content
    assert "make ci-backend" in charter_content


def test_append_to_charter_adds_win_entry(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    materialize(default_result(name="WinTest"), skopus_dir, vault_dir, commit=False)

    win = EvolveEntry(
        kind="validated",
        title="Non-destructive init is the default",
        why="Preserves user edits on re-run",
        how_to_apply="Only overwrite with --force",
    )
    updated = _append_to_charter(skopus_dir, [win])

    assert "§8 (what has worked)" in updated
    charter = (skopus_dir / "charter" / "workflow_partnership.md").read_text()
    assert "Non-destructive init is the default" in charter


def test_run_evolve_with_no_entries_is_noop(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    materialize(default_result(name="Noop"), skopus_dir, vault_dir, commit=False)

    result = run_evolve(skopus_dir, entries=[], commit=False)
    assert result.entries == []
    assert result.feedback_files_written == []
    assert result.committed is False
    assert "No entries" in result.message


def test_run_evolve_with_explicit_entries(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    materialize(default_result(name="Explicit"), skopus_dir, vault_dir, commit=False)

    entries = [
        EvolveEntry(
            kind="drift",
            title="Used root CLAUDE.md instead of .claude/CLAUDE.md",
            why="Adapter didn't check for .claude/ subdir",
            how_to_apply="Always check for .claude/ before falling back to root",
        ),
        EvolveEntry(
            kind="validated",
            title="Non-destructive merge pattern",
            why="Preserves user edits on skopus init re-run",
            how_to_apply="Default skip, --force to overwrite",
        ),
    ]

    result = run_evolve(skopus_dir, entries=entries, commit=False)

    assert len(result.entries) == 2
    assert len(result.feedback_files_written) == 2
    for path in result.feedback_files_written:
        assert path.exists()
        assert path.parent == skopus_dir / "memory" / "feedback"

    assert len(result.charter_sections_updated) == 2  # one drift, one win
    charter = (skopus_dir / "charter" / "workflow_partnership.md").read_text()
    assert "Used root CLAUDE.md" in charter
    assert "Non-destructive merge pattern" in charter


def test_run_evolve_commits_when_enabled(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    materialize(default_result(name="Commit"), skopus_dir, vault_dir, commit=True)

    entries = [
        EvolveEntry(
            kind="rule",
            title="CI before push",
            why="Broken pushes waste reviewer time",
            how_to_apply="make ci-backend → green → push",
        )
    ]
    result = run_evolve(skopus_dir, entries=entries, commit=True)
    assert result.committed is True

    # Verify the commit landed
    import subprocess

    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=skopus_dir,
        capture_output=True,
        text=True,
    )
    assert "charter-evolve" in log.stdout
