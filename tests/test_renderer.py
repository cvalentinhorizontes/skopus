"""Tests for skopus.renderer (v0.2.0 — unified ~/.skopus/ directory)."""

from pathlib import Path

from skopus.renderer import materialize
from skopus.wizard import default_result


def test_materialize_writes_all_expected_files(tmp_path, monkeypatch):
    skopus_dir = tmp_path / ".skopus"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = default_result(name="TestUser", seed_profile="solo-dev")

    report = materialize(result, skopus_dir, commit=False)

    # Charter
    assert (skopus_dir / "charter" / "CLAUDE.md").exists()
    assert (skopus_dir / "charter" / "workflow_partnership.md").exists()
    assert (skopus_dir / "charter" / "user_profile.md").exists()

    # Memory
    assert (skopus_dir / "memory" / "MEMORY.md").exists()
    assert (skopus_dir / "memory" / "feedback" / "solo-dev_seed.md").exists()

    # Vault (now inside ~/.skopus/vault/)
    assert (skopus_dir / "vault" / "CLAUDE.md").exists()
    assert (skopus_dir / "vault" / "wiki" / "index.md").exists()
    assert (skopus_dir / "vault" / "log.md").exists()
    assert (skopus_dir / "vault" / "raw" / "articles").is_dir()
    assert (skopus_dir / "vault" / "wiki" / "concepts").is_dir()
    assert (skopus_dir / "vault" / "output").is_dir()

    # Metadata
    assert (skopus_dir / "adapters.lock").exists()
    assert (skopus_dir / "projects.json").exists()

    # Slash commands (global)
    for cmd in ["ingest", "compile", "query", "lint", "wiki", "charter-evolve", "bench-contribute"]:
        assert (tmp_path / ".claude" / "commands" / f"{cmd}.md").exists()

    # First run — nothing skipped
    for path in report.written:
        assert path.exists()
    assert len(report.skipped) == 0
    assert report.total_files > 10


def test_materialize_renders_user_name(tmp_path, monkeypatch):
    skopus_dir = tmp_path / ".skopus"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = default_result(name="Alexandra", seed_profile="founder")

    materialize(result, skopus_dir, commit=False)

    assert "Alexandra" in (skopus_dir / "charter" / "CLAUDE.md").read_text()
    assert "Alexandra" in (skopus_dir / "charter" / "workflow_partnership.md").read_text()
    assert "Alexandra" in (skopus_dir / "charter" / "user_profile.md").read_text()
    assert "founder" in (skopus_dir / "charter" / "user_profile.md").read_text()


def test_materialize_seeds_feedback_by_profile(tmp_path, monkeypatch):
    skopus_dir = tmp_path / ".skopus"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = default_result(name="Dev", seed_profile="bug-hunter")

    materialize(result, skopus_dir, commit=False)

    seed_file = skopus_dir / "memory" / "feedback" / "bug-hunter_seed.md"
    assert seed_file.exists()
    content = seed_file.read_text()
    assert "root cause" in content.lower()


def test_materialize_is_non_destructive_by_default(tmp_path, monkeypatch):
    skopus_dir = tmp_path / ".skopus"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = default_result(name="Idem")

    report_1 = materialize(result, skopus_dir, commit=False)
    report_2 = materialize(result, skopus_dir, commit=False)

    assert len(report_1.written) > 10
    assert len(report_1.skipped) == 0
    # Second run skips most files (adapters.lock is always rewritten)
    assert len(report_2.skipped) >= len(report_1.written) - 2


def test_materialize_force_overwrites(tmp_path, monkeypatch):
    skopus_dir = tmp_path / ".skopus"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = default_result(name="Force")

    materialize(result, skopus_dir, commit=False)

    charter_md = skopus_dir / "charter" / "CLAUDE.md"
    charter_md.write_text("USER EDIT\n")

    report = materialize(result, skopus_dir, commit=False, force=True)
    assert charter_md in report.written
    assert "USER EDIT" not in charter_md.read_text()


def test_materialize_preserves_user_edits_without_force(tmp_path, monkeypatch):
    skopus_dir = tmp_path / ".skopus"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = default_result(name="Preserve")

    materialize(result, skopus_dir, commit=False)

    charter_md = skopus_dir / "charter" / "CLAUDE.md"
    user_content = "# My Custom Charter\n"
    charter_md.write_text(user_content)

    report = materialize(result, skopus_dir, commit=False)
    assert charter_md in report.skipped
    assert charter_md.read_text() == user_content


def test_materialize_with_commit_creates_git_repo(tmp_path, monkeypatch):
    import subprocess

    skopus_dir = tmp_path / ".skopus"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = default_result(name="GitTest")

    materialize(result, skopus_dir, commit=True)

    # ONE git repo for everything (charter + memory + vault)
    assert (skopus_dir / ".git").exists()
    log = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=skopus_dir, capture_output=True, text=True,
    )
    assert log.returncode == 0
    assert log.stdout.strip()
