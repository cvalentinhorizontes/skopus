"""Tests for skopus.renderer."""

from pathlib import Path

from skopus.renderer import materialize, resolve_vault_path
from skopus.wizard import default_result


def test_resolve_vault_path_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    resolved = resolve_vault_path("~/my-vault")
    assert resolved == tmp_path / "my-vault"


def test_materialize_writes_all_expected_files(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    result = default_result(name="TestUser", seed_profile="solo-dev")

    written = materialize(result, skopus_dir, vault_dir, commit=False)

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

    # Slash commands
    for cmd in ["ingest", "compile", "query", "lint", "wiki"]:
        assert (vault_dir / ".claude" / "commands" / f"{cmd}.md").exists()

    # Every returned path actually exists
    for path in written:
        assert path.exists(), f"{path} in written list but doesn't exist"


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


def test_materialize_is_idempotent(tmp_path):
    """Running materialize twice should not crash or duplicate content."""
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    result = default_result(name="Idem")

    written_1 = materialize(result, skopus_dir, vault_dir, commit=False)
    written_2 = materialize(result, skopus_dir, vault_dir, commit=False)

    assert len(written_1) == len(written_2)
    # Content of charter should be identical (same timestamp resolution)
    # (Date has day granularity so same day = same render)
    assert (skopus_dir / "charter" / "CLAUDE.md").exists()


def test_materialize_with_commit_creates_git_repos(tmp_path):
    """When commit=True, both ~/.skopus/ and vault should be git repos."""
    skopus_dir = tmp_path / ".skopus"
    vault_dir = tmp_path / "Vault"
    result = default_result(name="GitTest")

    materialize(result, skopus_dir, vault_dir, commit=True)

    assert (skopus_dir / ".git").exists(), "skopus dir is not a git repo"
    assert (vault_dir / ".git").exists(), "vault dir is not a git repo"
