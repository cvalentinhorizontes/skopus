"""skopus_search_memory — keyword-rank search over feedback entries.

Phase 2 uses simple TF-style scoring (no embeddings). Future phases may
swap in vector search behind the same tool signature. Filters by scope,
applies_to.paths, and applies_to.task_types when those fields are set.

Returns a structured result that the agent can use directly without
needing to read the source files."""

from __future__ import annotations

from pathlib import Path

from skopus.mcp.memory_index import MemoryEntry, load_memory_entries

DEFAULT_TOP_K = 10


def _score(entry: MemoryEntry, query_terms: list[str]) -> float:
    """Crude TF score: count term hits in name + description + body."""
    if not query_terms:
        return 0.0
    haystack = (
        f"{entry.name}\n{entry.description}\n{entry.body}\n{' '.join(entry.applies_to_keywords)}"
    ).lower()
    return float(sum(haystack.count(t) for t in query_terms))


def _filter(
    entry: MemoryEntry,
    scope: str | None,
    paths: list[str] | None,
    task_type: str | None,
) -> bool:
    """Return True if entry passes the optional filters."""
    if scope is not None and entry.scope != scope:
        return False
    if (
        paths is not None
        and entry.applies_to_paths
        and not any(p in entry.applies_to_paths for p in paths)
    ):
        return False
    return not (
        task_type is not None
        and entry.applies_to_task_types
        and task_type not in entry.applies_to_task_types
    )


async def skopus_search_memory(
    query: str,
    scope: str | None = None,
    paths: list[str] | None = None,
    task_type: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    """Search feedback memory for entries matching the query, with optional filters.

    Returns:
        {
            "matches": [
                {"id", "name", "description", "scope", "score", "path", "snippet"},
                ...
            ],
            "hint": <only present on edge cases like missing ~/.skopus>
        }
    """
    skopus_dir = Path.home() / ".skopus"
    if not skopus_dir.is_dir():
        return {
            "matches": [],
            "hint": f"~/.skopus/ not found at {skopus_dir}. Run `skopus init` first.",
        }

    entries = load_memory_entries(skopus_dir / "memory")
    query_terms = list({t.lower() for t in query.split() if t.strip()})

    scored: list[tuple[float, MemoryEntry]] = []
    for entry in entries:
        if not _filter(entry, scope, paths, task_type):
            continue
        score = _score(entry, query_terms)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    matches = [
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "scope": e.scope,
            "score": s,
            "path": str(e.path),
            "snippet": e.body[:200].strip(),
        }
        for s, e in scored[:top_k]
    ]
    return {"matches": matches}
