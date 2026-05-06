"""Tests for `skopus doctor --agent <name>` per-adapter introspection."""

from typer.testing import CliRunner

from skopus.cli import app

runner = CliRunner()


def _seed_minimal_skopus(tmp_path):
    """Create the minimal ~/.skopus/ tree doctor expects to exist."""
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "memory").mkdir(parents=True)
    (skopus_dir / "vault" / "wiki").mkdir(parents=True)
    (skopus_dir / "charter" / "CLAUDE.md").write_text("# charter\n")
    (skopus_dir / "memory" / "MEMORY.md").write_text("# memory\n")
    (skopus_dir / "vault" / "wiki" / "index.md").write_text("# index\n")


def test_doctor_agent_unknown_returns_clear_error(tmp_path, monkeypatch):
    """Asking about a nonexistent adapter must fail loudly with the known list."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_minimal_skopus(tmp_path)

    result = runner.invoke(app, ["doctor", "--agent", "no-such-thing"])
    assert result.exit_code != 0, f"expected non-zero exit, got output: {result.output}"
    # Error message must list the unknown name AND at least one known adapter
    assert "no-such-thing" in result.output
    assert "claude-code" in result.output


def test_doctor_agent_lists_tier_for_advertised(tmp_path, monkeypatch):
    """For an advertised adapter, doctor --agent prints tier + status."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_minimal_skopus(tmp_path)

    result = runner.invoke(app, ["doctor", "--agent", "claude-code"])
    assert result.exit_code == 0, f"expected exit 0, got: {result.output}"
    assert "claude-code" in result.output.lower()
    assert "advertised" in result.output.lower()
    # Status keyword must appear: installed | not_installed | not installed
    output_lower = result.output.lower()
    assert any(s in output_lower for s in ("installed", "not_installed", "not installed"))


def test_doctor_agent_lists_tier_for_experimental(tmp_path, monkeypatch):
    """For an experimental adapter, doctor --agent prints the disclaimer."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_minimal_skopus(tmp_path)

    result = runner.invoke(app, ["doctor", "--agent", "codex"])
    assert result.exit_code == 0
    out_lower = result.output.lower()
    assert "codex" in out_lower
    assert "experimental" in out_lower
    # The disclaimer should warn about smoke-test requirement for marketing
    assert "smoke" in out_lower


def test_doctor_no_agent_flag_runs_legacy_check(tmp_path, monkeypatch):
    """Calling doctor without --agent preserves the existing system-wide check."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_minimal_skopus(tmp_path)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    # Existing system-wide check shows charter/memory/vault rows
    assert "Charter" in result.output
    assert "Memory" in result.output
