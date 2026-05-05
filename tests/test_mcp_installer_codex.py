"""Tests for the Codex CLI MCP installer.

Mirrors the Cursor/Cline tests but targets ~/.codex/config.toml. Codex CLI
stores MCP servers under the [mcp_servers.<name>] section with snake_case
keys (not the camelCase mcpServers used by Claude Code/Cline/Cursor).

Schema source: https://developers.openai.com/codex/config-reference
"""

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 CI matrix only
    import tomli as tomllib

from skopus.mcp.installers.codex import (
    install_codex_mcp,
    uninstall_codex_mcp,
)


def _read_toml(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_install_creates_config_when_missing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = install_codex_mcp(home=home)
    assert result["written"] is True
    config_file = home / ".codex" / "config.toml"
    assert config_file.exists()

    cfg = _read_toml(config_file)
    # Codex schema uses snake_case `mcp_servers`, NOT camelCase mcpServers.
    assert "mcp_servers" in cfg, (
        "Codex config must use [mcp_servers.<name>] table — see "
        "developers.openai.com/codex/config-reference"
    )
    assert "skopus" in cfg["mcp_servers"]

    cmd = cfg["mcp_servers"]["skopus"]["command"]
    assert Path(cmd).is_absolute(), (
        f"command must be absolute path, got {cmd!r}. "
        "Bare names fail in desktop-agent spawn environments."
    )
    assert Path(cmd).name == "skopus"
    assert cfg["mcp_servers"]["skopus"]["args"] == ["mcp", "serve"]


def test_install_merges_into_existing_config(tmp_path):
    """Existing entries (including a non-skopus mcp_servers entry and a top-level
    Codex config key) must survive install."""
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    existing = (
        'model = "gpt-4o"\n'
        "\n"
        "[mcp_servers.other]\n"
        'command = "/usr/bin/other-mcp"\n'
        'args = ["--flag"]\n'
    )
    (codex_dir / "config.toml").write_text(existing)

    install_codex_mcp(home=home)

    cfg = _read_toml(codex_dir / "config.toml")
    assert cfg.get("model") == "gpt-4o", "top-level Codex keys must survive merge"
    assert "other" in cfg["mcp_servers"], "existing mcp_servers entries must survive"
    assert "skopus" in cfg["mcp_servers"]


def test_install_is_idempotent(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    install_codex_mcp(home=home)
    install_codex_mcp(home=home)
    cfg = _read_toml(home / ".codex" / "config.toml")
    # mcp_servers is a TOML table (Python dict). One key per server.
    assert list(cfg["mcp_servers"].keys()).count("skopus") == 1


def test_install_reports_action_created_then_updated(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    first = install_codex_mcp(home=home)
    second = install_codex_mcp(home=home)
    assert first["action"] == "created"
    assert second["action"] == "updated"


def test_uninstall_removes_only_skopus_entry(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    install_codex_mcp(home=home)

    cfg_path = home / ".codex" / "config.toml"
    # Add an unrelated entry post-install to confirm uninstall preserves it.
    appended = cfg_path.read_text() + ('\n[mcp_servers.other]\ncommand = "/usr/bin/other"\n')
    cfg_path.write_text(appended)

    uninstall_codex_mcp(home=home)

    cfg = _read_toml(cfg_path)
    assert "skopus" not in cfg.get("mcp_servers", {})
    assert "other" in cfg["mcp_servers"]


def test_uninstall_when_not_installed_is_noop(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    result = uninstall_codex_mcp(home=home)
    assert result["removed"] is False


def test_install_backs_up_corrupt_config_before_overwrite(tmp_path):
    """Same safety contract as the JSON installers: if the existing TOML
    is unparseable, rename it to a .bak-<unix-ts> sibling before writing."""
    home = tmp_path / "home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True)
    cfg_path = codex_dir / "config.toml"
    original = "this is not [valid toml syntax = "
    cfg_path.write_text(original)

    install_codex_mcp(home=home)

    backups = list(codex_dir.glob("config.toml.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == original
    assert cfg_path.read_text() != original
    # And the new config IS parseable, with skopus wired
    cfg = _read_toml(cfg_path)
    assert "skopus" in cfg["mcp_servers"]


def test_install_uninstall_round_trip_leaves_clean_config(tmp_path):
    """Install then uninstall against an empty home: config either gets
    cleaned to no mcp_servers section, or gets removed entirely. Either is
    acceptable; what's NOT acceptable is leaving an empty `[mcp_servers]`
    table behind."""
    home = tmp_path / "home"
    home.mkdir()
    install_codex_mcp(home=home)
    uninstall_codex_mcp(home=home)

    cfg_path = home / ".codex" / "config.toml"
    if cfg_path.exists():
        cfg = _read_toml(cfg_path)
        assert "skopus" not in cfg.get("mcp_servers", {})
