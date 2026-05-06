"""Tests for the skopus_record_drift MCP tool."""

import asyncio
import json

from skopus.mcp.tools.drift import skopus_record_drift


def test_drift_writes_queue_entry(tmp_path, monkeypatch):
    """Recording a valid drift writes a JSON entry to ~/.skopus/queue/drift/."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".skopus").mkdir()

    result = asyncio.run(
        skopus_record_drift(
            summary="Agent rounded currency to 2 decimals",
            source="explicit-correction",
            confidence="confirmed",
            scope="project",
        )
    )

    assert result["recorded"] is True
    queue_dir = tmp_path / ".skopus" / "queue" / "drift"
    files = list(queue_dir.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["summary"] == "Agent rounded currency to 2 decimals"
    assert payload["source"] == "explicit-correction"
    assert payload["confidence"] == "confirmed"
    assert payload["scope"] == "project"
    assert "captured_at" in payload
    assert "id" in payload


def test_drift_rejects_invalid_confidence(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".skopus").mkdir()

    result = asyncio.run(
        skopus_record_drift(summary="x", source="explicit-correction", confidence="totally-sure")
    )
    assert result["recorded"] is False
    assert "valid_confidence" in result


def test_drift_rejects_invalid_source(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".skopus").mkdir()

    result = asyncio.run(skopus_record_drift(summary="x", source="dreamt-it-up", confidence="weak"))
    assert result["recorded"] is False
    assert "valid_source" in result


def test_drift_rejects_invalid_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".skopus").mkdir()

    result = asyncio.run(
        skopus_record_drift(
            summary="x",
            source="explicit-correction",
            confidence="weak",
            scope="planet",
        )
    )
    assert result["recorded"] is False
    assert "valid_scope" in result


def test_drift_default_scope_is_user(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".skopus").mkdir()

    result = asyncio.run(
        skopus_record_drift(
            summary="default scope check",
            source="explicit-correction",
            confidence="weak",
        )
    )
    assert result["recorded"] is True
    queue_dir = tmp_path / ".skopus" / "queue" / "drift"
    payload = json.loads(next(queue_dir.glob("*.json")).read_text())
    assert payload["scope"] == "user"


def test_drift_creates_queue_dir_when_missing(tmp_path, monkeypatch):
    """Queue directory should be created if it doesn't exist yet."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".skopus").mkdir()  # but no queue/ subtree

    result = asyncio.run(
        skopus_record_drift(
            summary="creates dir",
            source="explicit-correction",
            confidence="weak",
        )
    )
    assert result["recorded"] is True
    assert (tmp_path / ".skopus" / "queue" / "drift").is_dir()


def test_drift_registered_in_server():
    from skopus.mcp import build_server

    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = [t.name for t in tools]
    assert "skopus_record_drift" in names
