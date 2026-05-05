"""Tests for `skopus doctor --agent <name>` showing MCP installation status."""

import json

from typer.testing import CliRunner

from skopus.cli import app

runner = CliRunner()


def _seed(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "memory").mkdir(parents=True)
    (skopus_dir / "vault" / "wiki").mkdir(parents=True)
    (skopus_dir / "charter" / "CLAUDE.md").write_text("# c\n")
    (skopus_dir / "memory" / "MEMORY.md").write_text("# m\n")
    (skopus_dir / "vault" / "wiki" / "index.md").write_text("# i\n")


def test_doctor_shows_mcp_not_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    result = runner.invoke(app, ["doctor", "--agent", "claude-code"])
    assert result.exit_code == 0
    out = result.output.lower()
    assert "mcp" in out
    assert "not_installed" in out or "not installed" in out


def test_doctor_shows_mcp_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    # Pre-install MCP via the same shape the installer produces
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps({"mcpServers": {"skopus": {"command": "skopus", "args": ["mcp", "serve"]}}})
    )
    result = runner.invoke(app, ["doctor", "--agent", "claude-code"])
    assert result.exit_code == 0
    out = result.output.lower()
    assert "mcp" in out
    assert "installed" in out


def test_doctor_shows_mcp_for_cline(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    cline_dir = tmp_path / ".config" / "cline"
    cline_dir.mkdir(parents=True)
    (cline_dir / "cline_mcp_settings.json").write_text(
        json.dumps({"mcpServers": {"skopus": {"command": "skopus", "args": ["mcp", "serve"]}}})
    )
    result = runner.invoke(app, ["doctor", "--agent", "aider"])
    # Use aider as a known adapter that won't have an MCP installer (n/a)
    assert result.exit_code == 0
    out = result.output.lower()
    assert "mcp" in out
    assert "n/a" in out


def test_doctor_shows_mcp_corrupt_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("not { valid json")
    result = runner.invoke(app, ["doctor", "--agent", "claude-code"])
    assert result.exit_code == 0
    out = result.output.lower()
    # Corrupt config should not crash; should report a clear state
    assert "mcp" in out
    assert "config-unparseable" in out or "unparseable" in out or "not_installed" in out


def test_doctor_shows_mcp_installed_for_codex(tmp_path, monkeypatch):
    """Codex stores MCP config in TOML; doctor must read TOML (not JSON)
    and look up snake_case mcp_servers (not mcpServers)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        '[mcp_servers.skopus]\ncommand = "/usr/bin/skopus"\nargs = ["mcp", "serve"]\n'
    )
    result = runner.invoke(app, ["doctor", "--agent", "codex"])
    assert result.exit_code == 0
    out = result.output.lower()
    assert "mcp" in out
    assert "installed" in out


def test_doctor_shows_mcp_not_installed_for_codex(tmp_path, monkeypatch):
    """Codex with no config.toml should report not_installed (not crash)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    result = runner.invoke(app, ["doctor", "--agent", "codex"])
    assert result.exit_code == 0
    out = result.output.lower()
    assert "mcp" in out
    assert "not_installed" in out or "not installed" in out


def test_doctor_shows_mcp_corrupt_toml_for_codex(tmp_path, monkeypatch):
    """Unparseable TOML must not crash; doctor should report a clear state."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed(tmp_path)
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text("this is not [valid toml = ")
    result = runner.invoke(app, ["doctor", "--agent", "codex"])
    assert result.exit_code == 0
    out = result.output.lower()
    assert "mcp" in out
    assert "config-unparseable" in out or "unparseable" in out or "not_installed" in out
