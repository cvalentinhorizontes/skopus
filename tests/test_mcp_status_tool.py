"""Tests for the skopus_status MCP tool — the always-on health check.

Tests use plain sync def + asyncio.run() rather than pytest-asyncio
to keep the dev-dep surface minimal."""

import asyncio

from skopus.mcp import build_server
from skopus.mcp.tools.status import skopus_status


def test_skopus_status_returns_alive_payload(tmp_path, monkeypatch):
    """skopus_status returns a dict with at least: alive, version, skopus_dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".skopus").mkdir()

    result = asyncio.run(skopus_status())

    assert isinstance(result, dict)
    assert result["alive"] is True
    assert "version" in result
    assert result["skopus_dir"] == str(tmp_path / ".skopus")
    assert result["skopus_initialized"] is True


def test_skopus_status_reports_skopus_uninitialized(tmp_path, monkeypatch):
    """If ~/.skopus does not exist, status reports alive but skopus_initialized=False."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Deliberately do NOT create ~/.skopus

    result = asyncio.run(skopus_status())

    assert result["alive"] is True
    assert result["skopus_initialized"] is False


def test_skopus_status_is_registered_in_server():
    """build_server() must register skopus_status — protects against
    decorator wiring regressions."""
    server = build_server()
    tools = asyncio.run(server.list_tools())
    tool_names = [t.name for t in tools]
    assert "skopus_status" in tool_names
