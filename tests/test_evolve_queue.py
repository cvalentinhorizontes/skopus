"""Tests for the drift-queue reader that bridges Phase 2's record_drift
output into Phase 3's /charter-evolve approval flow."""

from __future__ import annotations

import json
from pathlib import Path

from skopus.evolve import EvolveEntry
from skopus.evolve_queue import (
    QueueEntry,
    delete_queue_entry,
    load_queue_entries,
    queue_entry_to_evolve_entry,
)


def _write_queue_entry(queue_dir: Path, **overrides) -> Path:
    """Helper: write a JSON entry matching skopus_record_drift's payload shape."""
    queue_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": "abc123def456",
        "summary": "Agent rounded currency to 2 decimals",
        "source": "explicit-correction",
        "confidence": "confirmed",
        "scope": "project",
        "captured_at": "2026-05-05T13:00:00+00:00",
    }
    payload.update(overrides)
    out = queue_dir / f"{payload['captured_at'][:10]}-{payload['id']}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def test_load_returns_empty_when_no_queue_dir(tmp_path):
    """Missing queue dir is the common case (fresh skopus init). Don't crash."""
    entries = load_queue_entries(tmp_path)
    assert entries == []


def test_load_returns_empty_when_queue_dir_empty(tmp_path):
    queue_dir = tmp_path / "queue" / "drift"
    queue_dir.mkdir(parents=True)
    entries = load_queue_entries(tmp_path)
    assert entries == []


def test_load_parses_one_entry(tmp_path):
    queue_dir = tmp_path / "queue" / "drift"
    _write_queue_entry(queue_dir)
    entries = load_queue_entries(tmp_path)
    assert len(entries) == 1
    e = entries[0]
    assert isinstance(e, QueueEntry)
    assert e.id == "abc123def456"
    assert e.summary == "Agent rounded currency to 2 decimals"
    assert e.source == "explicit-correction"
    assert e.confidence == "confirmed"
    assert e.scope == "project"
    assert e.captured_at == "2026-05-05T13:00:00+00:00"


def test_load_returns_entries_sorted_by_captured_at_oldest_first(tmp_path):
    """Oldest-first so the user sees corrections in the order they happened."""
    queue_dir = tmp_path / "queue" / "drift"
    _write_queue_entry(queue_dir, id="aaa", captured_at="2026-05-05T11:00:00+00:00")
    _write_queue_entry(queue_dir, id="bbb", captured_at="2026-05-05T13:00:00+00:00")
    _write_queue_entry(queue_dir, id="ccc", captured_at="2026-05-05T12:00:00+00:00")
    entries = load_queue_entries(tmp_path)
    assert [e.id for e in entries] == ["aaa", "ccc", "bbb"]


def test_load_skips_files_with_invalid_json(tmp_path):
    """One bad file must not poison the rest."""
    queue_dir = tmp_path / "queue" / "drift"
    queue_dir.mkdir(parents=True)
    (queue_dir / "good.json").write_text(
        json.dumps(
            {
                "id": "good",
                "summary": "fine",
                "source": "explicit-correction",
                "confidence": "weak",
                "scope": "user",
                "captured_at": "2026-05-05T10:00:00+00:00",
            }
        )
    )
    (queue_dir / "bad.json").write_text("not valid json {")

    entries = load_queue_entries(tmp_path)
    assert len(entries) == 1
    assert entries[0].id == "good"


def test_load_skips_files_missing_required_fields(tmp_path):
    """Defensive: a payload missing summary or id is unusable."""
    queue_dir = tmp_path / "queue" / "drift"
    queue_dir.mkdir(parents=True)
    (queue_dir / "incomplete.json").write_text(
        json.dumps({"id": "x", "captured_at": "2026-05-05T10:00:00+00:00"})
    )
    entries = load_queue_entries(tmp_path)
    assert entries == []


def test_load_remembers_path_for_each_entry(tmp_path):
    """Each entry must know its own source file so delete_queue_entry can remove it."""
    queue_dir = tmp_path / "queue" / "drift"
    written = _write_queue_entry(queue_dir, id="path-test")
    entries = load_queue_entries(tmp_path)
    assert entries[0].path == written


def test_delete_removes_the_file(tmp_path):
    queue_dir = tmp_path / "queue" / "drift"
    written = _write_queue_entry(queue_dir, id="delete-me")
    entries = load_queue_entries(tmp_path)
    assert written.exists()
    delete_queue_entry(entries[0])
    assert not written.exists()


def test_delete_is_idempotent(tmp_path):
    """Calling delete on an already-deleted entry must not crash."""
    queue_dir = tmp_path / "queue" / "drift"
    _write_queue_entry(queue_dir, id="gone")
    entries = load_queue_entries(tmp_path)
    delete_queue_entry(entries[0])
    delete_queue_entry(entries[0])  # should be a no-op
    # Still no exception


def test_queue_entry_maps_to_drift_evolve_entry():
    """An explicit-correction queue entry maps to kind=drift in the evolve flow.
    The summary becomes the title; source/confidence/scope land in why; the
    user fills in how_to_apply during interactive approval."""
    qe = QueueEntry(
        id="a1",
        summary="Agent rounded currency to 2 decimals",
        source="explicit-correction",
        confidence="confirmed",
        scope="project",
        captured_at="2026-05-05T13:00:00+00:00",
        path=Path("/tmp/dummy.json"),
    )
    ee = queue_entry_to_evolve_entry(qe)
    assert isinstance(ee, EvolveEntry)
    assert ee.kind == "drift"
    assert "rounded currency" in ee.title.lower()
    # The why field must surface confidence + scope so reviewers can judge promotion
    assert "confirmed" in ee.why.lower()
    assert "project" in ee.why.lower()
    # how_to_apply is left empty; it's filled during approval
    assert ee.how_to_apply == ""


def test_queue_entry_with_charter_evolve_source_maps_to_drift():
    """Source `charter-evolve` (re-queued from a prior session) is still drift kind."""
    qe = QueueEntry(
        id="a2",
        summary="x",
        source="charter-evolve",
        confidence="probable",
        scope="user",
        captured_at="2026-05-05T13:00:00+00:00",
        path=Path("/tmp/dummy.json"),
    )
    ee = queue_entry_to_evolve_entry(qe)
    assert ee.kind == "drift"
