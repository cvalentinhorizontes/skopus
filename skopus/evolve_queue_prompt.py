"""Per-entry approval prompt for queued drift entries.

Kept separate from `skopus.evolve_queue` (pure I/O) so the prompt logic
can be tested by injecting a `decisions_iter` rather than mocking
`questionary`. The CLI wires the real interactive flow on top.

Contract: the human sees each queued entry one at a time and chooses
one of four actions:
  * approve — entry's summary becomes the EvolveEntry; user fills how_to_apply
  * edit    — user rewrites title/why/how_to_apply before approval
  * reject  — entry is discarded (deleted from queue)
  * defer   — entry stays in the queue for next /charter-evolve session

Nothing auto-promotes. Carlos's standing rule.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum

from skopus.evolve import EvolveEntry
from skopus.evolve_queue import QueueEntry, queue_entry_to_evolve_entry


class QueueDecision(str, Enum):
    """The four valid per-entry decisions."""

    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    DEFER = "defer"


@dataclass
class ApprovedQueueEntry:
    """Output of the prompt for entries the user approved (with or without edit)."""

    source_queue_entry: QueueEntry
    evolve_entry: EvolveEntry


@dataclass
class QueueReviewResult:
    """Partition of reviewed queue entries into outcome buckets."""

    approved: list[ApprovedQueueEntry] = field(default_factory=list)
    rejected: list[QueueEntry] = field(default_factory=list)
    deferred: list[QueueEntry] = field(default_factory=list)


def review_queue_entries(
    entries: list[QueueEntry],
    *,
    decisions_iter: Iterator[tuple[str, object]],
) -> QueueReviewResult:
    """Partition entries by user decision.

    Args:
        entries: Queue entries to review (oldest-first).
        decisions_iter: Iterator yielding `(decision, payload)` per entry, in
            the same order as `entries`. Designed for test injection; the
            CLI wraps a questionary-driven generator around this.

            decision is one of "approve" / "edit" / "reject" / "defer".
            payload is:
              * approve: str (the how_to_apply text)
              * edit:    dict with keys "title", "why", "how_to_apply"
              * reject:  None
              * defer:   None
    """
    result = QueueReviewResult()
    for entry in entries:
        decision, payload = next(decisions_iter)
        if decision == QueueDecision.APPROVE.value:
            ee = queue_entry_to_evolve_entry(entry)
            ee.how_to_apply = str(payload) if payload is not None else ""
            result.approved.append(ApprovedQueueEntry(source_queue_entry=entry, evolve_entry=ee))
        elif decision == QueueDecision.EDIT.value:
            if not isinstance(payload, dict):
                raise TypeError(
                    f"edit decision must carry a dict payload, got {type(payload).__name__}"
                )
            ee = EvolveEntry(
                kind="drift",
                title=str(payload.get("title", "")),
                why=str(payload.get("why", "")),
                how_to_apply=str(payload.get("how_to_apply", "")),
            )
            result.approved.append(ApprovedQueueEntry(source_queue_entry=entry, evolve_entry=ee))
        elif decision == QueueDecision.REJECT.value:
            result.rejected.append(entry)
        elif decision == QueueDecision.DEFER.value:
            result.deferred.append(entry)
        else:
            raise ValueError(f"unknown decision: {decision!r}")
    return result
