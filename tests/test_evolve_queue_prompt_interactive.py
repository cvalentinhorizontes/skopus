"""Test the interactive prompt generator with mocked questionary calls."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from skopus.evolve_queue import QueueEntry


def _entry(id_: str) -> QueueEntry:
    return QueueEntry(
        id=id_,
        summary=f"summary-{id_}",
        source="explicit-correction",
        confidence="confirmed",
        scope="project",
        captured_at="2026-05-05T13:00:00+00:00",
        path=Path(f"/tmp/{id_}.json"),
    )


def test_interactive_decisions_emits_one_decision_per_entry():
    """Stub questionary to return 'reject' for every entry; confirm 3 entries
    produce 3 decisions in order."""
    from skopus.evolve_queue_prompt_interactive import interactive_decisions

    entries = [_entry("a"), _entry("b"), _entry("c")]

    with patch("skopus.evolve_queue_prompt_interactive.questionary") as mock_q:
        mock_select = MagicMock()
        mock_select.ask.return_value = "reject"
        mock_q.select.return_value = mock_select

        decisions = list(interactive_decisions(entries))

    assert len(decisions) == 3
    assert all(d[0] == "reject" for d in decisions)
    assert all(d[1] is None for d in decisions)


def test_interactive_decisions_approve_path_prompts_for_how_to_apply():
    from skopus.evolve_queue_prompt_interactive import interactive_decisions

    entries = [_entry("a")]

    with patch("skopus.evolve_queue_prompt_interactive.questionary") as mock_q:
        mock_select = MagicMock()
        mock_select.ask.return_value = "approve"
        mock_q.select.return_value = mock_select

        mock_text = MagicMock()
        mock_text.ask.return_value = "Use Decimal for billing."
        mock_q.text.return_value = mock_text

        decisions = list(interactive_decisions(entries))

    assert decisions == [("approve", "Use Decimal for billing.")]


def test_interactive_decisions_defer_is_default_on_none_select():
    """If questionary.select returns None (user hit Esc/Ctrl-C), the safest
    action is defer — entry stays in queue, nothing destructive happens."""
    from skopus.evolve_queue_prompt_interactive import interactive_decisions

    entries = [_entry("a")]

    with patch("skopus.evolve_queue_prompt_interactive.questionary") as mock_q:
        mock_select = MagicMock()
        mock_select.ask.return_value = None  # user aborted
        mock_q.select.return_value = mock_select

        decisions = list(interactive_decisions(entries))

    assert decisions == [("defer", None)]


def test_interactive_decisions_edit_path_collects_title_why_how():
    """Edit decision asks for all 3 fields and yields a dict payload."""
    from skopus.evolve_queue_prompt_interactive import interactive_decisions

    entries = [_entry("a")]

    with patch("skopus.evolve_queue_prompt_interactive.questionary") as mock_q:
        mock_select = MagicMock()
        mock_select.ask.return_value = "edit"
        mock_q.select.return_value = mock_select

        mock_text = MagicMock()
        # Three .text().ask() calls in order: title, why, how_to_apply
        mock_text.ask.side_effect = ["New title", "New why", "New how"]
        mock_q.text.return_value = mock_text

        decisions = list(interactive_decisions(entries))

    assert decisions == [
        ("edit", {"title": "New title", "why": "New why", "how_to_apply": "New how"}),
    ]
