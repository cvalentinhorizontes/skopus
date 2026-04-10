"""Tests for skopus.renderer."""

from pathlib import Path

from skopus.renderer import materialize, resolve_vault_path
from skopus.wizard import default_result


def test_resolve_vault_path_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    resolved = resolve_vault_path("~/my-vault")
    assert resolved == tmp_path / "my-vault"


def test_materialize_writes_all_expected_files(tmp_path, monkeypatch):
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    # Redirect Path.home() so global commands land in tmp_path, not real ~/.claude/
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = default_result(name="TestUser", seed_profile="solo-dev")

    report = materialize(result, skopus_dir, vault_dir, commit=False)

    # Charter files
    assert (skopus_dir / "charter" / "CLAUDE.md").exists()
    assert (skopus_dir / "charter" / "workflow_partnership.md").exists()
    assert (skopus_dir / "charter" / "user_profile.md").exists()

    # Memory files
    assert (skopus_dir / "memory" / "MEMORY.md").exists()
    assert (skopus_dir / "memory" / "feedback" / "solo-dev_seed.md").exists()

    # Metadata
    assert (skopus_dir / "adapters.lock").exists()
    assert (skopus_dir / "projects.json").exists()

    # Vault
    assert (vault_dir / "CLAUDE.md").exists()
    assert (vault_dir / "wiki" / "index.md").exists()
    assert (vault_dir / "log.md").exists()

    # Vault structure directories
    assert (vault_dir / "raw" / "articles").is_dir()
    assert (vault_dir / "wiki" / "concepts").is_dir()
    assert (vault_dir / "output").is_dir()

    # Slash commands (both in vault AND global)
    for cmd in ["ingest", "compile", "query", "lint", "wiki"]:
        assert (vault_dir / ".claude" / "commands" / f"{cmd}.md").exists()
        assert (tmp_path / ".claude" / "commands" / f"{cmd}.md").exists()

    # Every written path actually exists; first run, nothing skipped
    for path in report.written:
        assert path.exists(), f"{path} in written list but doesn't exist"
    assert len(report.skipped) == 0, "first materialize should not skip anything"
    assert report.total_files > 10


def test_materialize_renders_user_name_into_charter(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    result = default_result(name="Alexandra", seed_profile="founder")

    materialize(result, skopus_dir, vault_dir, commit=False)

    charter_content = (skopus_dir / "charter" / "CLAUDE.md").read_text()
    assert "Alexandra" in charter_content
    full_charter = (skopus_dir / "charter" / "workflow_partnership.md").read_text()
    assert "Alexandra" in full_charter

    user_profile = (skopus_dir / "charter" / "user_profile.md").read_text()
    assert "Alexandra" in user_profile
    assert "founder" in user_profile


def test_materialize_seeds_feedback_by_profile(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    result = default_result(name="Dev", seed_profile="bug-hunter")

    materialize(result, skopus_dir, vault_dir, commit=False)

    seed_file = skopus_dir / "memory" / "feedback" / "bug-hunter_seed.md"
    assert seed_file.exists()
    content = seed_file.read_text()
    assert "silent-bug" in content.lower() or "root cause" in content.lower()


def test_materialize_is_non_destructive_by_default(tmp_path, monkeypatch):
    """Running materialize twice should skip existing files on the 2nd run."""
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = default_result(name="Idem")

    report_1 = materialize(result, skopus_dir, vault_dir, commit=False)
    report_2 = materialize(result, skopus_dir, vault_dir, commit=False)

    # First run writes everything, skips nothing
    assert len(report_1.written) > 10
    assert len(report_1.skipped) == 0

    # Second run skips the files it already wrote (non-destructive default).
    # adapters.lock is always rewritten (it's managed state), so it's in written.
    assert len(report_2.skipped) >= len(report_1.written) - 2
    assert (skopus_dir / "charter" / "CLAUDE.md").exists()


def test_materialize_force_overwrites_existing(tmp_path):
    """With force=True, existing files should be overwritten."""
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    result = default_result(name="Force")

    materialize(result, skopus_dir, vault_dir, commit=False)

    # Corrupt the charter file to verify it gets overwritten
    charter_md = skopus_dir / "charter" / "CLAUDE.md"
    charter_md.write_text("USER EDIT — should be overwritten by force\n")

    report = materialize(result, skopus_dir, vault_dir, commit=False, force=True)
    # With force, the charter is rewritten
    assert charter_md in report.written
    # The user edit is gone
    assert "USER EDIT" not in charter_md.read_text()


def test_materialize_preserves_user_edits_without_force(tmp_path):
    """User-edited files must survive a non-forced re-run."""
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    result = default_result(name="Preserve")

    materialize(result, skopus_dir, vault_dir, commit=False)

    charter_md = skopus_dir / "charter" / "CLAUDE.md"
    user_content = "# My Custom Charter\n\nI edited this and skopus should not touch it.\n"
    charter_md.write_text(user_content)

    report = materialize(result, skopus_dir, vault_dir, commit=False)

    # File was NOT rewritten
    assert charter_md in report.skipped
    assert charter_md.read_text() == user_content


def test_materialize_with_commit_creates_git_repos(tmp_path):
    """When commit=True, both ~/.skopus/ and vault should be git repos with commits."""
    import subprocess

    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    result = default_result(name="GitTest")

    materialize(result, skopus_dir, vault_dir, commit=True)

    assert (skopus_dir / ".git").exists(), "skopus dir is not a git repo"
    assert (vault_dir / ".git").exists(), "vault dir is not a git repo"

    # Verify actual commits were made (not just empty repos)
    for repo in (skopus_dir, vault_dir):
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert log.returncode == 0, f"git log failed in {repo}: {log.stderr}"
        assert log.stdout.strip(), f"no commits in {repo}"
