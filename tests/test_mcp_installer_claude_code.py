"""Tests for the Claude Code MCP installer.

Writes (or merges into) Claude Code's mcp config so it discovers
the Skopus stdio MCP server on next launch."""

import json

from skopus.mcp.installers.claude_code import (
    install_claude_code_mcp,
    uninstall_claude_code_mcp,
)


def test_install_creates_config_when_missing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = install_claude_code_mcp(home=home)
    assert result["written"] is True
    config_file = home / ".claude" / "settings.json"
    assert config_file.exists()
    cfg = json.loads(config_file.read_text())
    assert cfg["mcpServers"]["skopus"]["command"] == "skopus"
    assert cfg["mcpServers"]["skopus"]["args"] == ["mcp", "serve"]


def test_install_merges_into_existing_config(tmp_path):
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    existing = {"theme": "dark", "mcpServers": {"other": {"command": "other"}}}
    (claude_dir / "settings.json").write_text(json.dumps(existing))

    install_claude_code_mcp(home=home)

    cfg = json.loads((claude_dir / "settings.json").read_text())
    assert cfg["theme"] == "dark"  # other top-level keys preserved
    assert "other" in cfg["mcpServers"]  # other servers preserved
    assert "skopus" in cfg["mcpServers"]


def test_install_is_idempotent(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    install_claude_code_mcp(home=home)
    install_claude_code_mcp(home=home)
    cfg = json.loads((home / ".claude" / "settings.json").read_text())
    # Only one skopus entry — second install replaced the first
    assert list(cfg["mcpServers"].keys()).count("skopus") == 1


def test_install_reports_action_created_then_updated(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    first = install_claude_code_mcp(home=home)
    second = install_claude_code_mcp(home=home)
    assert first["action"] == "created"
    assert second["action"] == "updated"


def test_uninstall_removes_only_skopus_entry(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    install_claude_code_mcp(home=home)
    # Add another server alongside
    cfg_path = home / ".claude" / "settings.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["mcpServers"]["other"] = {"command": "other"}
    cfg_path.write_text(json.dumps(cfg))

    uninstall_claude_code_mcp(home=home)

    cfg = json.loads(cfg_path.read_text())
    assert "skopus" not in cfg["mcpServers"]
    assert "other" in cfg["mcpServers"]


def test_uninstall_when_not_installed_is_noop(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = uninstall_claude_code_mcp(home=home)
    assert result["removed"] is False
    assert "reason" in result


def test_install_handles_corrupt_existing_config(tmp_path):
    """If settings.json exists but is invalid JSON, install must not crash —
    it should back the corrupt file up and write a fresh one with skopus."""
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text("this is not { valid json")

    result = install_claude_code_mcp(home=home)
    assert result["written"] is True
    cfg = json.loads((claude_dir / "settings.json").read_text())
    assert "skopus" in cfg["mcpServers"]
    # Corrupt original was preserved as a sibling backup, not destroyed.
    backups = list(claude_dir.glob("settings.json.bak-*"))
    assert len(backups) == 1


def test_install_backs_up_corrupt_config_before_overwrite(tmp_path):
    """When existing settings.json is invalid JSON, install must back it up
    to a .bak-<timestamp> sibling before writing the fresh file."""
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    cfg_path = claude_dir / "settings.json"
    original_content = "this is not { valid json"
    cfg_path.write_text(original_content)

    install_claude_code_mcp(home=home)

    # Original is gone (renamed)
    assert cfg_path.exists()
    new_content = cfg_path.read_text()
    assert new_content != original_content
    # A backup file was created
    backups = list(claude_dir.glob("settings.json.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == original_content
