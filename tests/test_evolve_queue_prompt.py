"""Tests for the per-queue-entry approval prompt logic.

Carlos's standing rule: nothing auto-promotes. Every queue entry gets
shown to the human with one of {approve, edit, reject, defer}. This
file tests the dispatch logic — the actual questionary calls are
injected so tests don't need a TTY."""

from __future__ import annotations

from pathlib import Path

import pytest

from skopus.evolve_queue import QueueEntry
from skopus.evolve_queue_prompt import (
    QueueDecision,
    QueueReviewResult,
    review_queue_entries,
)


def _entry(id_="x", summary="rounded currency", **overrides) -> QueueEntry:
    base = {
        "id": id_,
        "summary": summary,
        "source": "explicit-correction",
        "confidence": "confirmed",
        "scope": "project",
        "captured_at": "2026-05-05T13:00:00+00:00",
        "path": Path("/tmp/dummy.json"),
    }
    base.update(overrides)
    return QueueEntry(**base)


def test_review_returns_empty_result_when_no_entries():
    result = review_queue_entries([], decisions_iter=iter([]))
    assert isinstance(result, QueueReviewResult)
    assert result.approved == []
    assert result.rejected == []
    assert result.deferred == []


def test_approve_lands_entry_in_approved_with_filled_how_to_apply():
    """When the user approves, the prompt asks for how_to_apply and that
    text lands in the resulting EvolveEntry."""
    qe = _entry()
    decisions = iter(
        [
            ("approve", "Always use Decimal arithmetic in billing code."),
        ]
    )
    result = review_queue_entries([qe], decisions_iter=decisions)
    assert len(result.approved) == 1
    assert result.approved[0].evolve_entry.how_to_apply == (
        "Always use Decimal arithmetic in billing code."
    )
    assert result.approved[0].source_queue_entry.id == "x"


def test_reject_lands_entry_in_rejected_with_no_how_to_apply_prompt():
    """Reject doesn't ask for how_to_apply — the entry is going to be deleted."""
    qe = _entry()
    decisions = iter([("reject", None)])
    result = review_queue_entries([qe], decisions_iter=decisions)
    assert result.approved == []
    assert len(result.rejected) == 1
    assert result.rejected[0].id == "x"


def test_defer_lands_entry_in_deferred_neither_approved_nor_rejected():
    """Deferred = stays in the queue for the next /charter-evolve session."""
    qe = _entry()
    decisions = iter([("defer", None)])
    result = review_queue_entries([qe], decisions_iter=decisions)
    assert result.approved == []
    assert result.rejected == []
    assert len(result.deferred) == 1
    assert result.deferred[0].id == "x"


def test_edit_lets_user_rewrite_title_and_why_before_approving():
    """Edit asks for title, why, and how_to_apply, then treats as approved."""
    qe = _entry(summary="vague summary")
    decisions = iter(
        [
            (
                "edit",
                {
                    "title": "Currency rounding bug",
                    "why": "Float arithmetic loses cents in billing totals",
                    "how_to_apply": "Use Decimal everywhere in src/billing/",
                },
            ),
        ]
    )
    result = review_queue_entries([qe], decisions_iter=decisions)
    assert len(result.approved) == 1
    ee = result.approved[0].evolve_entry
    assert ee.title == "Currency rounding bug"
    assert ee.why == "Float arithmetic loses cents in billing totals"
    assert ee.how_to_apply == "Use Decimal everywhere in src/billing/"


def test_mixed_decisions_partition_correctly():
    """3 entries, 3 different decisions — all land in the right bucket."""
    a = _entry(id_="a")
    b = _entry(id_="b")
    c = _entry(id_="c")
    decisions = iter(
        [
            ("approve", "do A"),
            ("reject", None),
            ("defer", None),
        ]
    )
    result = review_queue_entries([a, b, c], decisions_iter=decisions)
    assert [x.source_queue_entry.id for x in result.approved] == ["a"]
    assert [x.id for x in result.rejected] == ["b"]
    assert [x.id for x in result.deferred] == ["c"]


def test_decision_must_be_one_of_four_known_values():
    """Defensive: an unknown decision string raises (should never happen
    with questionary's choices, but lock the contract)."""
    qe = _entry()
    decisions = iter([("nuke", None)])
    with pytest.raises(ValueError, match="unknown decision"):
        review_queue_entries([qe], decisions_iter=decisions)


def test_edit_decision_requires_dict_payload():
    """Edit's payload contract is a dict — None or a string raises TypeError
    (not AssertionError, which would be silent under python -O)."""
    qe = _entry()
    decisions = iter([("edit", "not a dict")])
    with pytest.raises(TypeError, match="dict payload"):
        review_queue_entries([qe], decisions_iter=decisions)


def test_queue_decision_enum_values():
    """The four decisions are stable strings (no aliases, no plurals)."""
    assert QueueDecision.APPROVE.value == "approve"
    assert QueueDecision.EDIT.value == "edit"
    assert QueueDecision.REJECT.value == "reject"
    assert QueueDecision.DEFER.value == "defer"
