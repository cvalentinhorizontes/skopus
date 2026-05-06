"""Tests for skopus.evolve."""

import json

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
    # v0.2.0: vault merged into skopus_dir, no separate vault_dir
    result = default_result(name="EvolveTest")
    materialize(result, skopus_dir, commit=False)

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
    # v0.2.0: vault merged into skopus_dir, no separate vault_dir
    materialize(default_result(name="WinTest"), skopus_dir, commit=False)

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
    # v0.2.0: vault merged into skopus_dir, no separate vault_dir
    materialize(default_result(name="Noop"), skopus_dir, commit=False)

    result = run_evolve(skopus_dir, entries=[], commit=False)
    assert result.entries == []
    assert result.feedback_files_written == []
    assert result.committed is False
    assert "No entries" in result.message


def test_run_evolve_with_explicit_entries(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    # v0.2.0: vault merged into skopus_dir, no separate vault_dir
    materialize(default_result(name="Explicit"), skopus_dir, commit=False)

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
    # v0.2.0: vault merged into skopus_dir, no separate vault_dir
    materialize(default_result(name="Commit"), skopus_dir, commit=True)

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


def _seed_queue_entry(skopus_dir, **overrides):
    """Helper: write a drift-queue JSON entry as record_drift would."""
    queue_dir = skopus_dir / "queue" / "drift"
    queue_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": "queue1",
        "summary": "Agent skipped reading project memory before refactor",
        "source": "explicit-correction",
        "confidence": "confirmed",
        "scope": "project",
        "captured_at": "2026-05-05T13:00:00+00:00",
    }
    payload.update(overrides)
    out = queue_dir / f"{payload['captured_at'][:10]}-{payload['id']}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def test_run_evolve_drains_approved_queue_entries(tmp_path):
    """Approved queue entries land in feedback files just like interactive entries."""
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "memory" / "feedback").mkdir(parents=True)
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "charter" / "workflow_partnership.md").write_text("# Charter\n")

    queue_path = _seed_queue_entry(skopus_dir)

    queue_decisions = iter([("approve", "Read project memory before any refactor.")])
    run_evolve(
        skopus_dir,
        entries=[],
        queue_decisions_iter=queue_decisions,
        commit=False,
    )

    fb_files = list((skopus_dir / "memory" / "feedback").glob("*.md"))
    assert len(fb_files) == 1
    text = fb_files[0].read_text()
    assert "skipped reading project memory" in text.lower()
    assert "Read project memory before any refactor." in text

    assert not queue_path.exists()


def test_run_evolve_keeps_deferred_queue_entries(tmp_path):
    """Deferred entries remain in the queue for next session."""
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "memory" / "feedback").mkdir(parents=True)
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "charter" / "workflow_partnership.md").write_text("# Charter\n")

    queue_path = _seed_queue_entry(skopus_dir, id="defer-me")

    queue_decisions = iter([("defer", None)])
    run_evolve(
        skopus_dir,
        entries=[],
        queue_decisions_iter=queue_decisions,
        commit=False,
    )

    assert queue_path.exists()
    fb_files = list((skopus_dir / "memory" / "feedback").glob("*.md"))
    assert fb_files == []


def test_run_evolve_deletes_rejected_queue_entries_without_writing_feedback(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "memory" / "feedback").mkdir(parents=True)
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "charter" / "workflow_partnership.md").write_text("# Charter\n")

    queue_path = _seed_queue_entry(skopus_dir, id="reject-me")

    queue_decisions = iter([("reject", None)])
    run_evolve(
        skopus_dir,
        entries=[],
        queue_decisions_iter=queue_decisions,
        commit=False,
    )

    assert not queue_path.exists()
    fb_files = list((skopus_dir / "memory" / "feedback").glob("*.md"))
    assert fb_files == []


def test_run_evolve_works_with_no_queue(tmp_path):
    """Backward compat: existing callers that don't pass queue_decisions_iter
    continue to work with interactive-only flow."""
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "memory" / "feedback").mkdir(parents=True)
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "charter" / "workflow_partnership.md").write_text("# Charter\n")

    run_evolve(
        skopus_dir,
        entries=[EvolveEntry(kind="rule", title="t", why="w", how_to_apply="h")],
        commit=False,
    )
    fb_files = list((skopus_dir / "memory" / "feedback").glob("*.md"))
    assert len(fb_files) == 1


def test_run_evolve_uses_interactive_decisions_when_iter_is_none(tmp_path, monkeypatch):
    """Wires the cascade end-to-end: run_evolve with a non-empty queue and
    queue_decisions_iter=None lazy-imports interactive_decisions, which gets
    its questionary calls mocked. Closes the Task 49 reviewer's gap that
    would have shipped a ModuleNotFoundError to a real user."""
    from unittest.mock import MagicMock, patch

    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "memory" / "feedback").mkdir(parents=True)
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "charter" / "workflow_partnership.md").write_text("# Charter\n")

    queue_path = _seed_queue_entry(skopus_dir, id="cascade-test")

    # Mock questionary inside the bridge module
    with patch("skopus.evolve_queue_prompt_interactive.questionary") as mock_q:
        mock_select = MagicMock()
        mock_select.ask.return_value = "reject"
        mock_q.select.return_value = mock_select

        run_evolve(skopus_dir, entries=[], commit=False)
        # Note: queue_decisions_iter is intentionally omitted — that's what
        # triggers the lazy import of interactive_decisions.

    # Reject means: queue file gone, no feedback file written.
    assert not queue_path.exists()
    fb_files = list((skopus_dir / "memory" / "feedback").glob("*.md"))
    assert fb_files == []
