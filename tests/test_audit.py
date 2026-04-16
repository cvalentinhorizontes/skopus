"""Tests for skopus.audit — memory health checks."""

from pathlib import Path

import pytest

from skopus.audit import check_scope_tags, run_audit, sync_index


def _scaffold(tmp_path: Path) -> Path:
    """Create a minimal skopus directory with memory/feedback structure."""
    skopus_dir = tmp_path / ".skopus"
    feedback_dir = skopus_dir / "memory" / "feedback"
    feedback_dir.mkdir(parents=True)
    return skopus_dir


def _write_feedback(feedback_dir: Path, name: str, *, scope: str | None = None) -> None:
    """Write a minimal feedback file with optional scope tag."""
    lines = [
        "---",
        f"name: {name}",
        f"description: Test feedback {name}",
        "type: feedback",
        "captured: 2026-04-16",
    ]
    if scope is not None:
        lines.append(f"scope: {scope}")
    lines.extend([
        "---",
        "",
        f"# {name}",
        "",
        "**Why:** Testing.",
        "",
        "**How to apply:** Test only.",
    ])
    (feedback_dir / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")


def _write_memory_md(skopus_dir: Path, feedback_entries: list[str]) -> None:
    """Write a MEMORY.md with the given feedback basenames."""
    lines = [
        "# Memory Index",
        "",
        "## Feedback Memory",
        "",
    ]
    for entry in feedback_entries:
        lines.append(f"- [feedback/{entry}](feedback/{entry}) — hook for {entry}")
    lines.extend([
        "",
        "## Project Memory",
        "",
        "*(empty)*",
        "",
        "---",
    ])
    (skopus_dir / "memory" / "MEMORY.md").write_text("\n".join(lines), encoding="utf-8")


# ── sync_index ──────────────────────────────────────────────────────


class TestSyncIndex:
    def test_clean_state(self, tmp_path: Path) -> None:
        """No issues when disk and index match."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha", scope="permanent")
        _write_feedback(feedback_dir, "beta", scope="skopus")
        _write_memory_md(skopus_dir, ["alpha.md", "beta.md"])

        result = sync_index(skopus_dir)
        assert result["missing_from_index"] == []
        assert result["dangling_entries"] == []

    def test_missing_from_index(self, tmp_path: Path) -> None:
        """Files on disk not in MEMORY.md."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha", scope="permanent")
        _write_feedback(feedback_dir, "beta", scope="skopus")
        # Only alpha in index
        _write_memory_md(skopus_dir, ["alpha.md"])

        result = sync_index(skopus_dir)
        assert result["missing_from_index"] == ["beta.md"]
        assert result["dangling_entries"] == []

    def test_dangling_entries(self, tmp_path: Path) -> None:
        """Index entries pointing to files that don't exist on disk."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha", scope="permanent")
        # Index references alpha + ghost
        _write_memory_md(skopus_dir, ["alpha.md", "ghost.md"])

        result = sync_index(skopus_dir)
        assert result["missing_from_index"] == []
        assert result["dangling_entries"] == ["ghost.md"]

    def test_both_issues(self, tmp_path: Path) -> None:
        """Both missing and dangling at the same time."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha", scope="permanent")
        _write_feedback(feedback_dir, "beta", scope="skopus")
        # Index has alpha + ghost (missing beta, ghost is dangling)
        _write_memory_md(skopus_dir, ["alpha.md", "ghost.md"])

        result = sync_index(skopus_dir)
        assert result["missing_from_index"] == ["beta.md"]
        assert result["dangling_entries"] == ["ghost.md"]

    def test_fix_adds_missing(self, tmp_path: Path) -> None:
        """fix=True adds missing entries to MEMORY.md."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha", scope="permanent")
        _write_feedback(feedback_dir, "new-rule", scope="skopus")
        _write_memory_md(skopus_dir, ["alpha.md"])

        sync_index(skopus_dir, fix=True)

        text = (skopus_dir / "memory" / "MEMORY.md").read_text()
        assert "feedback/new-rule.md" in text

    def test_fix_removes_dangling(self, tmp_path: Path) -> None:
        """fix=True removes dangling entries from MEMORY.md."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha", scope="permanent")
        _write_memory_md(skopus_dir, ["alpha.md", "ghost.md"])

        sync_index(skopus_dir, fix=True)

        text = (skopus_dir / "memory" / "MEMORY.md").read_text()
        assert "ghost.md" not in text
        assert "feedback/alpha.md" in text

    def test_fix_both(self, tmp_path: Path) -> None:
        """fix=True handles both missing and dangling in one pass."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha", scope="permanent")
        _write_feedback(feedback_dir, "new-one", scope="skopus")
        _write_memory_md(skopus_dir, ["alpha.md", "ghost.md"])

        result = sync_index(skopus_dir, fix=True)

        text = (skopus_dir / "memory" / "MEMORY.md").read_text()
        assert "feedback/new-one.md" in text
        assert "ghost.md" not in text
        assert result["missing_from_index"] == ["new-one.md"]
        assert result["dangling_entries"] == ["ghost.md"]

    def test_no_feedback_dir(self, tmp_path: Path) -> None:
        """Graceful when feedback dir doesn't exist."""
        skopus_dir = tmp_path / ".skopus"
        (skopus_dir / "memory").mkdir(parents=True)
        _write_memory_md(skopus_dir, [])

        result = sync_index(skopus_dir)
        assert result["missing_from_index"] == []
        assert result["dangling_entries"] == []

    def test_no_memory_md(self, tmp_path: Path) -> None:
        """Graceful when MEMORY.md doesn't exist."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "orphan", scope="permanent")

        result = sync_index(skopus_dir)
        assert result["missing_from_index"] == ["orphan.md"]
        assert result["dangling_entries"] == []


# ── check_scope_tags ────────────────────────────────────────────────


class TestCheckScopeTags:
    def test_all_have_scope(self, tmp_path: Path) -> None:
        """No issues when all files have scope."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "a", scope="permanent")
        _write_feedback(feedback_dir, "b", scope="skopus")

        result = check_scope_tags(skopus_dir)
        assert result == []

    def test_missing_scope(self, tmp_path: Path) -> None:
        """Detects files without scope tag."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "has-scope", scope="permanent")
        _write_feedback(feedback_dir, "no-scope")  # no scope

        result = check_scope_tags(skopus_dir)
        assert result == ["no-scope.md"]

    def test_empty_feedback_dir(self, tmp_path: Path) -> None:
        """Empty feedback dir returns empty list."""
        skopus_dir = _scaffold(tmp_path)
        result = check_scope_tags(skopus_dir)
        assert result == []

    def test_no_feedback_dir(self, tmp_path: Path) -> None:
        """Missing feedback dir returns empty list."""
        skopus_dir = tmp_path / ".skopus"
        skopus_dir.mkdir(parents=True)
        result = check_scope_tags(skopus_dir)
        assert result == []


# ── run_audit ───────────────────────────────────────────────────────


class TestRunAudit:
    def test_clean_report(self, tmp_path: Path) -> None:
        """Clean state reports clean=True."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha", scope="permanent")
        _write_memory_md(skopus_dir, ["alpha.md"])

        report = run_audit(skopus_dir)
        assert report["clean"] is True
        assert report["sync"]["missing_from_index"] == []
        assert report["sync"]["dangling_entries"] == []
        assert report["scope"] == []

    def test_dirty_report(self, tmp_path: Path) -> None:
        """Issues detected reports clean=False."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha")  # no scope
        _write_memory_md(skopus_dir, ["ghost.md"])  # dangling

        report = run_audit(skopus_dir)
        assert report["clean"] is False
        assert report["sync"]["missing_from_index"] == ["alpha.md"]
        assert report["sync"]["dangling_entries"] == ["ghost.md"]
        assert report["scope"] == ["alpha.md"]

    def test_fix_mode(self, tmp_path: Path) -> None:
        """fix=True fixes index issues but scope stays reported."""
        skopus_dir = _scaffold(tmp_path)
        feedback_dir = skopus_dir / "memory" / "feedback"
        _write_feedback(feedback_dir, "alpha")  # no scope
        _write_memory_md(skopus_dir, ["ghost.md"])

        report = run_audit(skopus_dir, fix=True)

        # Index was fixed
        text = (skopus_dir / "memory" / "MEMORY.md").read_text()
        assert "feedback/alpha.md" in text
        assert "ghost.md" not in text

        # Scope is still reported (not auto-fixed)
        assert report["scope"] == ["alpha.md"]


# ── CLI integration ─────────────────────────────────────────────────


class TestAuditCLI:
    def test_audit_not_initialized(self, tmp_path: Path, monkeypatch) -> None:
        """audit fails with exit 1 when skopus is not initialized."""
        from typer.testing import CliRunner

        from skopus.cli import app

        monkeypatch.setenv("HOME", str(tmp_path))

        runner = CliRunner()
        result = runner.invoke(app, ["audit"])
        assert result.exit_code == 1

    def test_audit_report_clean(self, tmp_path: Path, monkeypatch) -> None:
        """audit reports clean when everything is in order."""
        from typer.testing import CliRunner

        from skopus.cli import app

        monkeypatch.setenv("HOME", str(tmp_path))

        skopus_dir = tmp_path / ".skopus"
        feedback_dir = skopus_dir / "memory" / "feedback"
        feedback_dir.mkdir(parents=True)
        _write_feedback(feedback_dir, "alpha", scope="permanent")
        _write_memory_md(skopus_dir, ["alpha.md"])

        runner = CliRunner()
        result = runner.invoke(app, ["audit"])
        assert result.exit_code == 0
        assert "All checks passed" in result.stdout

    def test_audit_report_issues(self, tmp_path: Path, monkeypatch) -> None:
        """audit reports issues when there are problems."""
        from typer.testing import CliRunner

        from skopus.cli import app

        monkeypatch.setenv("HOME", str(tmp_path))

        skopus_dir = tmp_path / ".skopus"
        feedback_dir = skopus_dir / "memory" / "feedback"
        feedback_dir.mkdir(parents=True)
        _write_feedback(feedback_dir, "orphan")  # no scope, not in index
        _write_memory_md(skopus_dir, ["ghost.md"])

        runner = CliRunner()
        result = runner.invoke(app, ["audit"])
        assert result.exit_code == 0
        assert "missing from index" in result.stdout or "dangling" in result.stdout

    def test_audit_fix(self, tmp_path: Path, monkeypatch) -> None:
        """audit --fix fixes index issues."""
        from typer.testing import CliRunner

        from skopus.cli import app

        monkeypatch.setenv("HOME", str(tmp_path))

        skopus_dir = tmp_path / ".skopus"
        feedback_dir = skopus_dir / "memory" / "feedback"
        feedback_dir.mkdir(parents=True)
        _write_feedback(feedback_dir, "orphan", scope="permanent")
        _write_memory_md(skopus_dir, ["ghost.md"])

        runner = CliRunner()
        result = runner.invoke(app, ["audit", "--fix"])
        assert result.exit_code == 0
        assert "Fixed" in result.stdout or "added" in result.stdout

        # Verify the fix
        text = (skopus_dir / "memory" / "MEMORY.md").read_text()
        assert "orphan.md" in text
        assert "ghost.md" not in text
