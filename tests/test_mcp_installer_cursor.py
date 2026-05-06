"""Tests for the Cursor MCP installer.

Mirrors Claude Code installer tests but targets ~/.cursor/mcp.json."""

import json
from pathlib import Path

from skopus.mcp.installers.cursor import (
    install_cursor_mcp,
    uninstall_cursor_mcp,
)


def test_install_creates_config_when_missing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = install_cursor_mcp(home=home)
    assert result["written"] is True
    config_file = home / ".cursor" / "mcp.json"
    assert config_file.exists()
    cfg = json.loads(config_file.read_text())
    cmd = cfg["mcpServers"]["skopus"]["command"]
    assert Path(cmd).is_absolute(), (
        f"command must be absolute path, got {cmd!r}. "
        "Bare names fail in desktop-agent spawn environments."
    )
    assert Path(cmd).name == "skopus"
    assert cfg["mcpServers"]["skopus"]["args"] == ["mcp", "serve"]


def test_install_merges_into_existing_config(tmp_path):
    home = tmp_path / "home"
    cursor_dir = home / ".cursor"
    cursor_dir.mkdir(parents=True)
    existing = {"mcpServers": {"other": {"command": "other"}}}
    (cursor_dir / "mcp.json").write_text(json.dumps(existing))

    install_cursor_mcp(home=home)

    cfg = json.loads((cursor_dir / "mcp.json").read_text())
    assert "other" in cfg["mcpServers"]
    assert "skopus" in cfg["mcpServers"]


def test_install_is_idempotent(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    install_cursor_mcp(home=home)
    install_cursor_mcp(home=home)
    cfg = json.loads((home / ".cursor" / "mcp.json").read_text())
    assert list(cfg["mcpServers"].keys()).count("skopus") == 1


def test_install_reports_action_created_then_updated(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    first = install_cursor_mcp(home=home)
    second = install_cursor_mcp(home=home)
    assert first["action"] == "created"
    assert second["action"] == "updated"


def test_uninstall_removes_only_skopus_entry(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    install_cursor_mcp(home=home)
    cfg_path = home / ".cursor" / "mcp.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["mcpServers"]["other"] = {"command": "other"}
    cfg_path.write_text(json.dumps(cfg))

    uninstall_cursor_mcp(home=home)

    cfg = json.loads(cfg_path.read_text())
    assert "skopus" not in cfg["mcpServers"]
    assert "other" in cfg["mcpServers"]


def test_uninstall_when_not_installed_is_noop(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = uninstall_cursor_mcp(home=home)
    assert result["removed"] is False


def test_install_backs_up_corrupt_config_before_overwrite(tmp_path):
    home = tmp_path / "home"
    cursor_dir = home / ".cursor"
    cursor_dir.mkdir(parents=True)
    cfg_path = cursor_dir / "mcp.json"
    original = "this is not { valid json"
    cfg_path.write_text(original)

    install_cursor_mcp(home=home)

    backups = list(cursor_dir.glob("mcp.json.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == original
    assert cfg_path.read_text() != original
