"""Tests for `skopus link --mcp <agent>` MCP-installer dispatch."""

import json

from typer.testing import CliRunner

from skopus.cli import app

runner = CliRunner()


def _seed_skopus(tmp_path):
    """Minimal ~/.skopus tree so link doesn't bail at the precheck."""
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "vault").mkdir(parents=True)


def test_link_mcp_claude_code_writes_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_skopus(tmp_path)

    result = runner.invoke(app, ["link", "--mcp", "claude-code"])
    assert result.exit_code == 0, result.output
    cfg_path = tmp_path / ".claude" / "settings.json"
    assert cfg_path.exists()
    cfg = json.loads(cfg_path.read_text())
    assert "skopus" in cfg["mcpServers"]


def test_link_mcp_cline_writes_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_skopus(tmp_path)

    result = runner.invoke(app, ["link", "--mcp", "cline"])
    assert result.exit_code == 0, result.output
    cfg_path = tmp_path / ".config" / "cline" / "cline_mcp_settings.json"
    assert cfg_path.exists()


def test_link_mcp_cursor_writes_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_skopus(tmp_path)

    result = runner.invoke(app, ["link", "--mcp", "cursor"])
    assert result.exit_code == 0, result.output
    cfg_path = tmp_path / ".cursor" / "mcp.json"
    assert cfg_path.exists()


def test_link_mcp_unknown_agent_errors_clearly(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_skopus(tmp_path)

    result = runner.invoke(app, ["link", "--mcp", "no-such-agent"])
    assert result.exit_code != 0
    out = result.output.lower()
    assert "no-such-agent" in out
    # Error must list the three known MCP installers
    assert "claude-code" in out
    assert "cline" in out
    assert "cursor" in out


def test_link_mcp_with_explicit_non_default_agent_errors(tmp_path, monkeypatch):
    """--mcp and a non-default --agent together should error, not silently
    drop --agent. Catches the common footgun of `--mcp cline --agent cursor`."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_skopus(tmp_path)

    result = runner.invoke(app, ["link", "--mcp", "cline", "--agent", "cursor"])
    assert result.exit_code != 0
    out = result.output.lower()
    assert "mutually exclusive" in out or "--agent" in out
    # No config files were written
    assert not (tmp_path / ".config" / "cline" / "cline_mcp_settings.json").exists()
    assert not (tmp_path / ".cursor" / "mcp.json").exists()


def test_link_without_mcp_flag_runs_legacy_adapter(tmp_path, monkeypatch):
    """If --mcp is not provided, link runs the existing adapter wiring path
    (no MCP config touched)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_skopus(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    result = runner.invoke(app, ["link", str(project)])
    assert result.exit_code == 0, result.output
    # Legacy path writes CLAUDE.md (or .claude/CLAUDE.md), not the MCP config
    assert not (tmp_path / ".claude" / "settings.json").exists()
    # The adapter wrote SOMEWHERE in the project
    md_paths = list(project.glob("**/CLAUDE.md"))
    assert len(md_paths) >= 1
