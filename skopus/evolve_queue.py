"""Drift-queue reader: bridges Phase 2's `record_drift` output into the
Phase 3 `/charter-evolve` approval flow.

Phase 2 left a one-way write surface (`skopus_record_drift` writes JSON to
`~/.skopus/queue/drift/`). This module consumes that queue: loads entries,
sorts them oldest-first so the human sees corrections in the order an
agent actually recorded them, deletes individual entries on approval/reject.

Defensive against:
  * missing queue dir (common case — fresh skopus init)
  * invalid JSON in any single file (skipped, others survive)
  * missing required payload fields (skipped, others survive)
  * concurrent deletes (delete_queue_entry is idempotent)
"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skopus.evolve import EvolveEntry

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("id", "summary", "source", "confidence", "scope", "captured_at")


@dataclass
class QueueEntry:
    """One drift entry queued by `skopus_record_drift` for /charter-evolve review.

    Mirrors the JSON payload written by skopus/mcp/tools/drift.py, plus the
    source file path so delete_queue_entry can remove it after promotion.
    """

    id: str
    summary: str
    source: str
    confidence: str
    scope: str
    captured_at: str
    path: Path


def _parse_entry(path: Path) -> QueueEntry | None:
    """Load and validate one queue file. Returns None on any defect."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("skopus.evolve_queue: cannot read %s: %s", path, exc)
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("skopus.evolve_queue: invalid JSON in %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        logger.warning("skopus.evolve_queue: %s is not a JSON object", path)
        return None
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        logger.warning("skopus.evolve_queue: %s missing required fields %s", path, missing)
        return None
    return QueueEntry(
        id=str(data["id"]),
        summary=str(data["summary"]),
        source=str(data["source"]),
        confidence=str(data["confidence"]),
        scope=str(data["scope"]),
        captured_at=str(data["captured_at"]),
        path=path,
    )


def load_queue_entries(skopus_dir: Path) -> list[QueueEntry]:
    """Load all drift queue entries under <skopus_dir>/queue/drift/.

    Returns oldest-first so the user reviews corrections in the order
    they were recorded during the session.
    """
    queue_dir = skopus_dir / "queue" / "drift"
    if not queue_dir.is_dir():
        return []
    entries: list[QueueEntry] = []
    for path in sorted(queue_dir.glob("*.json")):
        parsed = _parse_entry(path)
        if parsed is not None:
            entries.append(parsed)
    entries.sort(key=lambda e: e.captured_at)
    return entries


def delete_queue_entry(entry: QueueEntry) -> None:
    """Remove the queue file for `entry`. Idempotent (concurrent delete safe)."""
    with contextlib.suppress(FileNotFoundError):
        entry.path.unlink()


def queue_entry_to_evolve_entry(qe: QueueEntry) -> EvolveEntry:
    """Map a drift queue entry to the EvolveEntry shape the existing
    /charter-evolve flow understands.

    All queue entries become kind=drift (a correction observation worth
    capturing). The mapper preserves source/confidence/scope in the `why`
    field so the human reviewer can judge promotion to a feedback file.
    `how_to_apply` is intentionally left empty — the reviewer fills it
    during the interactive approval prompt.
    """
    # Local import to avoid circular import with skopus.evolve
    from skopus.evolve import EvolveEntry

    title = qe.summary if len(qe.summary) <= 100 else qe.summary[:97] + "..."
    why = (
        f"Recorded by agent at {qe.captured_at} "
        f"(source: {qe.source}, confidence: {qe.confidence}, scope: {qe.scope})."
    )
    return EvolveEntry(kind="drift", title=title, why=why, how_to_apply="")
