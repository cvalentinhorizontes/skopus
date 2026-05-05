"""`/charter-evolve` — the session-end reflection loop.

Runs at the end of a working session to capture validated judgment calls,
corrections, and non-obvious empirical facts before they evaporate. This is
the mechanism that makes the charter compound over sessions without manual
editing.

Interactive design: the command prompts the user with 3 questions,
lightweight enough to answer in 60 seconds, and writes the answers into:
  1. ``~/.skopus/memory/feedback/YYYY-MM-DD-<slug>.md`` — new feedback files
  2. ``~/.skopus/charter/workflow_partnership.md`` — drift log / what-worked sections

The user sees a summary and confirms before anything is written. Git commits
happen only if the user approves.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import questionary

    HAS_QUESTIONARY = True
except ImportError:  # pragma: no cover
    HAS_QUESTIONARY = False


@dataclass
class EvolveEntry:
    """A single reflection captured during /charter-evolve."""

    kind: str  # "validated" | "drift" | "rule"
    title: str
    why: str
    how_to_apply: str


@dataclass
class EvolveResult:
    """Outcome of a /charter-evolve run."""

    entries: list[EvolveEntry] = field(default_factory=list)
    feedback_files_written: list[Path] = field(default_factory=list)
    charter_sections_updated: list[str] = field(default_factory=list)
    committed: bool = False
    message: str = ""


def _slugify(text: str, max_len: int = 40) -> str:
    """Turn a title into a filename-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len] if slug else "entry"


def _prompt_entries() -> list[EvolveEntry]:
    """Interactive prompt for evolve entries. Falls back to empty if no TTY."""
    import sys

    if not sys.stdin.isatty() or not HAS_QUESTIONARY:
        return []

    entries: list[EvolveEntry] = []

    # Section 1 — validated wins
    if questionary.confirm(
        "Did anything non-obvious work today that you'd want repeated?",
        default=False,
    ).ask():
        while True:
            title = questionary.text(
                "  → Rule or observation (short, imperative)",
            ).ask()
            if not title:
                break
            why = (
                questionary.text(
                    "  → Why it worked (one sentence)",
                ).ask()
                or ""
            )
            how = (
                questionary.text(
                    "  → How to apply next time (one sentence)",
                ).ask()
                or ""
            )
            entries.append(EvolveEntry(kind="validated", title=title, why=why, how_to_apply=how))
            if not questionary.confirm("  Add another validated call?", default=False).ask():
                break

    # Section 2 — corrections (drifts)
    if questionary.confirm(
        "Did I drift anywhere? Any correction to remember?",
        default=False,
    ).ask():
        while True:
            title = questionary.text(
                "  → What I got wrong",
            ).ask()
            if not title:
                break
            why = (
                questionary.text(
                    "  → Why it was wrong",
                ).ask()
                or ""
            )
            how = (
                questionary.text(
                    "  → The rule to follow next time",
                ).ask()
                or ""
            )
            entries.append(EvolveEntry(kind="drift", title=title, why=why, how_to_apply=how))
            if not questionary.confirm("  Add another correction?", default=False).ask():
                break

    # Section 3 — new non-negotiable rule
    if questionary.confirm(
        "Any new non-negotiable rule you want added to the charter?",
        default=False,
    ).ask():
        while True:
            title = questionary.text("  → Rule").ask()
            if not title:
                break
            why = questionary.text("  → Why it's non-negotiable").ask() or ""
            how = questionary.text("  → How it applies").ask() or ""
            entries.append(EvolveEntry(kind="rule", title=title, why=why, how_to_apply=how))
            if not questionary.confirm("  Add another rule?", default=False).ask():
                break

    return entries


def _write_feedback_file(skopus_dir: Path, entry: EvolveEntry) -> Path:
    """Write a new feedback file for an evolve entry."""
    date = datetime.now().strftime("%Y-%m-%d")
    slug = _slugify(entry.title)
    feedback_dir = skopus_dir / "memory" / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    path = feedback_dir / f"{date}-{slug}.md"

    content = f"""---
name: {entry.kind}-{slug}
description: {entry.title}
type: feedback
captured: {date}
---

# {entry.title}

**Why:** {entry.why}

**How to apply:** {entry.how_to_apply}
"""
    path.write_text(content, encoding="utf-8")
    return path


def _append_to_charter(skopus_dir: Path, entries: list[EvolveEntry]) -> list[str]:
    """Append drift/validated entries to the full charter's §7 and §8.

    Skips the append if the charter file doesn't contain the expected section
    headers (user may have restructured it).
    """
    charter = skopus_dir / "charter" / "workflow_partnership.md"
    if not charter.exists():
        return []

    content = charter.read_text(encoding="utf-8")
    sections_updated: list[str] = []
    date = datetime.now().strftime("%Y-%m-%d")

    drifts = [e for e in entries if e.kind == "drift"]
    wins = [e for e in entries if e.kind == "validated"]

    if drifts and "## 7. Where We've Drifted" in content:
        addition = "\n"
        for e in drifts:
            addition += f"\n> **{date} — {e.title}.** **Why:** {e.why} **Fix:** {e.how_to_apply}\n"
        content = content.replace(
            "## 7. Where We've Drifted (Evidence Log)",
            "## 7. Where We've Drifted (Evidence Log)" + addition,
            1,
        )
        sections_updated.append("§7 (drift log)")

    if wins and "## 8. What Has Worked" in content:
        addition = "\n"
        for e in wins:
            addition += f"\n- **{date} — {e.title}.** {e.why} *(How: {e.how_to_apply})*\n"
        content = content.replace(
            "## 8. What Has Worked (Patterns to Repeat)",
            "## 8. What Has Worked (Patterns to Repeat)" + addition,
            1,
        )
        sections_updated.append("§8 (what has worked)")

    charter.write_text(content, encoding="utf-8")
    return sections_updated


def _commit(skopus_dir: Path, message: str) -> bool:
    """Commit pending changes in ~/.skopus/ using inline identity."""
    if not (skopus_dir / ".git").exists():
        return False
    try:
        identity = [
            "-c",
            "user.email=skopus@localhost",
            "-c",
            "user.name=Skopus",
            "-c",
            "commit.gpgsign=false",
        ]
        subprocess.run(
            ["git", "add", "-A"],
            cwd=skopus_dir,
            check=True,
            capture_output=True,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=skopus_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        if not status.stdout.strip():
            return False
        subprocess.run(
            ["git", *identity, "commit", "-q", "-m", message],
            cwd=skopus_dir,
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def run_evolve(
    skopus_dir: Path,
    *,
    entries: list[EvolveEntry] | None = None,
    queue_decisions_iter=None,
    commit: bool = True,
) -> EvolveResult:
    """Run the evolve loop.

    Drains queued drift entries from ``<skopus_dir>/queue/drift/`` FIRST
    (Phase 3), then collects interactive entries from the user (Phase 0/1).
    Approved queue entries flow through the same write/commit path as
    interactive entries.

    Args:
        entries: If provided, used directly for the interactive part
            (skips the prompt). If None, the user is prompted.
        queue_decisions_iter: If provided, used as the per-entry decision
            source for queued drift. If None and a queue is present, the
            user is prompted interactively per entry. Pass an empty
            iterator to skip queue drain entirely (no entries → no
            decisions consumed).
        commit: Whether to git commit at the end.
    """
    # Lazy imports to avoid circular import with skopus.evolve_queue_prompt
    # (which imports EvolveEntry from this module).
    from skopus.evolve_queue import (
        delete_queue_entry,
        load_queue_entries,
    )
    from skopus.evolve_queue_prompt import review_queue_entries

    # --- Phase 3 step: drain the drift queue ---
    queued = load_queue_entries(skopus_dir)
    queue_approved: list[EvolveEntry] = []
    if queued:
        if queue_decisions_iter is None:
            # Interactive prompt — module built in Task 50.
            from skopus.evolve_queue_prompt_interactive import (
                interactive_decisions,
            )

            queue_decisions_iter = interactive_decisions(queued)
        review = review_queue_entries(queued, decisions_iter=queue_decisions_iter)
        queue_approved = [a.evolve_entry for a in review.approved]
        for a in review.approved:
            delete_queue_entry(a.source_queue_entry)
        for r in review.rejected:
            delete_queue_entry(r)
        # Deferred entries stay in the queue — no action.

    # --- Existing interactive prompt path (unchanged) ---
    if entries is None:
        entries = _prompt_entries()

    # Combine queue-derived + interactive entries so they share the
    # downstream write/commit path.
    all_entries = queue_approved + entries

    result = EvolveResult(entries=all_entries)
    if not all_entries:
        result.message = "No entries captured; charter unchanged."
        return result

    # Write feedback files
    for entry in all_entries:
        path = _write_feedback_file(skopus_dir, entry)
        result.feedback_files_written.append(path)

    # Append to charter sections
    result.charter_sections_updated = _append_to_charter(skopus_dir, all_entries)

    # Commit
    if commit:
        result.committed = _commit(
            skopus_dir,
            f"charter-evolve: {len(all_entries)} entr{'y' if len(all_entries) == 1 else 'ies'}",
        )

    result.message = (
        f"Captured {len(all_entries)} entries: "
        f"{len(result.feedback_files_written)} feedback file(s), "
        f"{len(result.charter_sections_updated)} charter section(s) updated"
    )
    return result
