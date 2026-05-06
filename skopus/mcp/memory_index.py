"""Schema-aware loader for ~/.skopus/memory/feedback/*.md.

Reads YAML frontmatter, normalizes to the v2 evidence-locked §4.1 schema
with defaults for fields existing entries don't yet carry. Returned
MemoryEntry objects are the input to skopus_search_memory.

Migration of existing entries to populate the missing v2 fields will be
shipped later in Phase 2 as a one-shot script. Until then, the defaults
keep legacy entries queryable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """One feedback entry from ~/.skopus/memory/feedback/<slug>.md.

    Field defaults match the v2 §4.1 schema's fallback values so legacy
    entries (no source/confidence/applies_to) remain queryable.
    """

    id: str
    name: str
    description: str
    body: str
    path: Path
    scope: str = "user"
    type: str = "feedback"
    captured: str = ""
    source: str = "imported"
    confidence: str = "weak"
    applies_to_paths: list[str] = field(default_factory=list)
    applies_to_task_types: list[str] = field(default_factory=list)
    applies_to_keywords: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    sensitivity: str = "normal"
    last_validated_at: str = ""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a frontmatter-prefixed markdown file into (metadata, body).

    Returns ({}, text) if no frontmatter delimiter or YAML is malformed.
    """
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    front = text[4:end]
    body = text[end + 5 :]
    try:
        meta = yaml.safe_load(front)
    except yaml.YAMLError as exc:
        logger.warning("skopus.mcp.memory_index: malformed YAML frontmatter (%s)", exc)
        return {}, text
    if not isinstance(meta, dict):
        return {}, text
    return meta, body


def load_memory_entries(memory_dir: Path) -> list[MemoryEntry]:
    """Load all feedback entries under <memory_dir>/feedback/.

    Skips files without valid frontmatter. Defaults missing v2 §4.1
    fields. Never crashes on a single bad file — survives the corpus.
    """
    feedback_dir = memory_dir / "feedback"
    if not feedback_dir.is_dir():
        return []

    entries: list[MemoryEntry] = []
    for md in sorted(feedback_dir.glob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("skopus.mcp.memory_index: cannot read %s: %s", md, exc)
            continue
        meta, body = _parse_frontmatter(text)
        if not meta:
            continue

        applies_to = meta.get("applies_to") or {}
        if not isinstance(applies_to, dict):
            applies_to = {}

        entries.append(
            MemoryEntry(
                id=str(meta.get("id") or meta.get("name") or md.stem),
                name=str(meta.get("name") or md.stem),
                description=str(meta.get("description") or ""),
                body=body,
                path=md,
                scope=str(meta.get("scope") or "user"),
                type=str(meta.get("type") or "feedback"),
                captured=str(meta.get("captured") or ""),
                source=str(meta.get("source") or "imported"),
                confidence=str(meta.get("confidence") or "weak"),
                applies_to_paths=list(applies_to.get("paths") or []),
                applies_to_task_types=list(applies_to.get("task_types") or []),
                applies_to_keywords=list(applies_to.get("keywords") or []),
                supersedes=list(meta.get("supersedes") or []),
                sensitivity=str(meta.get("sensitivity") or "normal"),
                last_validated_at=str(meta.get("last_validated_at") or ""),
            )
        )
    return entries
