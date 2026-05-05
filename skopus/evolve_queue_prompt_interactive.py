"""Interactive (questionary-backed) decision generator for queue review.

Imported lazily by `run_evolve` only when no `decisions_iter` was passed.
Tests inject their own iterators and never hit this module."""

from __future__ import annotations

from collections.abc import Iterator

import questionary

from skopus.evolve_queue import QueueEntry


def _format_summary(qe: QueueEntry) -> str:
    """Pretty-print one queue entry for the prompt header."""
    return f"\n[{qe.captured_at}] {qe.source} / {qe.confidence} / scope={qe.scope}\n  {qe.summary}"


def interactive_decisions(
    entries: list[QueueEntry],
) -> Iterator[tuple[str, object]]:
    """Yield (decision, payload) for each queue entry by prompting the user.

    Uses questionary.select for the choice and questionary.text for the
    follow-up payloads (how_to_apply on approve, full edit dict on edit).

    Defer is the safe default — chosen when the user hits Esc/Ctrl-C or
    just hits enter without selecting. Nothing destructive on accidental
    input.
    """
    for qe in entries:
        print(_format_summary(qe))
        decision = questionary.select(
            "  Decision:",
            choices=["approve", "edit", "reject", "defer"],
            default="defer",
        ).ask()

        # User aborted (Esc/Ctrl-C) or returned nothing — treat as defer
        if decision is None:
            yield ("defer", None)
            continue

        if decision == "approve":
            how = (
                questionary.text(
                    "  How to apply (one short sentence):",
                    default="",
                ).ask()
                or ""
            )
            yield ("approve", how)
        elif decision == "edit":
            title = (
                questionary.text(
                    "  Title:",
                    default=qe.summary,
                ).ask()
                or qe.summary
            )
            why = (
                questionary.text(
                    "  Why (one short sentence):",
                    default="",
                ).ask()
                or ""
            )
            how = (
                questionary.text(
                    "  How to apply (one short sentence):",
                    default="",
                ).ask()
                or ""
            )
            yield ("edit", {"title": title, "why": why, "how_to_apply": how})
        elif decision == "reject":
            yield ("reject", None)
        else:  # defer (or any unexpected value — safe fallback)
            yield ("defer", None)
