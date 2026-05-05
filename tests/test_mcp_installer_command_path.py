"""Tests that pin the absolute-path requirement for the MCP server command.

Surfaced 2026-05-05 by the Phase 2 manual smoke run: Carlos wired
Cursor with `skopus link --mcp cursor`. The config wrote
`{"command": "skopus", ...}` (bare name). Cursor's spawn environment
doesn't include ~/.local/bin on PATH, so the spawn failed silently
and Cursor reported zero Skopus tools.

Fix: build_server_entry() resolves `skopus` to its absolute path via
shutil.which at install time, raising SkopusBinaryNotFoundError if
not found. These tests lock that contract.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from skopus.mcp.installers._common import (
    SkopusBinaryNotFoundError,
    build_server_entry,
)


def test_build_server_entry_returns_absolute_command_path():
    """The command field must be an absolute path. Bare names like
    ``"skopus"`` fail in desktop-agent spawn environments that don't
    inherit the user's shell PATH."""
    entry = build_server_entry()
    cmd = entry["command"]
    assert isinstance(cmd, str)
    assert Path(cmd).is_absolute(), (
        f"build_server_entry returned non-absolute command {cmd!r}. "
        "MCP installers must always emit absolute paths."
    )
    assert Path(cmd).name == "skopus", f"command must end in `skopus`, got {cmd!r}"


def test_build_server_entry_resolves_to_real_skopus_binary():
    """Sanity: the resolved path matches `which skopus` from the test env."""
    entry = build_server_entry()
    assert entry["command"] == shutil.which("skopus")


def test_build_server_entry_args_unchanged():
    """The args list stays `["mcp", "serve"]` regardless of which binary
    path is chosen."""
    entry = build_server_entry()
    assert entry["args"] == ["mcp", "serve"]


def test_build_server_entry_raises_when_skopus_not_on_path(monkeypatch, tmp_path):
    """When `skopus` cannot be located, build_server_entry must raise
    SkopusBinaryNotFoundError with remediation guidance — never silently
    fall back to the bare string `"skopus"` (which is the bug pattern
    this test exists to prevent)."""
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(SkopusBinaryNotFoundError) as exc_info:
        build_server_entry()

    msg = str(exc_info.value)
    assert "PATH" in msg or "path" in msg
    assert "skopus link --mcp" in msg, (
        "Error must tell the user how to recover (re-run skopus link --mcp)"
    )
