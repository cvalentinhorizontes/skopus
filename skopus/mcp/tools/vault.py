"""skopus_query_vault — keyword-rank search over wiki pages.

Mirrors skopus_search_memory's TF-style scoring approach with de-dup'd
query terms (so "billing billing" scores the same as "billing"). Future
phases may swap in vector search behind the same tool signature."""

from __future__ import annotations

from pathlib import Path

from skopus.mcp.vault_index import VaultPage, load_vault_pages

DEFAULT_TOP_K = 10
SNIPPET_LEN = 200


def _score(page: VaultPage, query_terms: list[str]) -> float:
    if not query_terms:
        return 0.0
    haystack = f"{page.title}\n{page.body}".lower()
    return float(sum(haystack.count(t) for t in query_terms))


async def skopus_query_vault(
    query: str,
    scope: str | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    """Search vault wiki pages for `query`. Returns ranked matches.

    If `scope` is set, only pages under that section (concepts / entities /
    sources / decisions / comparisons / etc.) are considered.

    Returns:
        {"matches": [{"title", "section", "path", "score", "snippet"}, ...]}
        or {"matches": [], "hint": ...} when ~/.skopus/vault/ is missing.
    """
    skopus_dir = Path.home() / ".skopus"
    vault_dir = skopus_dir / "vault"
    if not vault_dir.is_dir():
        return {
            "matches": [],
            "hint": f"Vault not found at {vault_dir}. Run `skopus init` first.",
        }

    pages = load_vault_pages(vault_dir)
    query_terms = list({t.lower() for t in query.split() if t.strip()})

    scored: list[tuple[float, VaultPage]] = []
    for page in pages:
        if scope is not None and page.section != scope:
            continue
        score = _score(page, query_terms)
        if score > 0:
            scored.append((score, page))

    scored.sort(key=lambda x: x[0], reverse=True)

    matches = [
        {
            "title": p.title,
            "section": p.section,
            "path": str(p.path),
            "score": s,
            "snippet": p.body[:SNIPPET_LEN].strip(),
        }
        for s, p in scored[:top_k]
    ]
    return {"matches": matches}
