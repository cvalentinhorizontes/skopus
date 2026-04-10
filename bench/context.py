"""Lens context builder — converts a LensConfig into a system prompt string.

This is how skopus's four lenses actually get injected into a benchmark run.
Each lens config produces a different amount of context in the system prompt,
which is how we measure the additive contribution of each lens.
"""

from __future__ import annotations

from pathlib import Path

from bench.config import LensConfig


def _read_if_exists(path: Path, max_chars: int = 8000) -> str:
    """Read a file if it exists, truncating if too long."""
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8")
    if len(content) > max_chars:
        return content[:max_chars] + "\n[... truncated for context budget ...]"
    return content


def build_system_prompt(
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    task_hint: str = "",
) -> str:
    """Build a system prompt for a given lens configuration.

    The system prompt includes more of the skopus context as the lens
    configuration expands, from "nothing" (vanilla) to "everything" (full).
    """
    if lens == LensConfig.VANILLA:
        return (
            "You are a helpful AI coding assistant. Answer the user's question "
            "directly and concisely."
        )

    parts: list[str] = [
        "You are a helpful AI coding assistant with persistent context from Skopus.",
    ]

    # --- CHARTER (lens 1) ---
    if lens in {LensConfig.CHARTER, LensConfig.CHARTER_MEMORY, LensConfig.CHARTER_MEMORY_VAULT, LensConfig.FULL}:
        charter_md = skopus_dir / "charter" / "CLAUDE.md"
        charter_text = _read_if_exists(charter_md)
        if charter_text:
            parts.append("## Partnership Charter (how we work)\n" + charter_text)

    # --- MEMORY (lens 2) ---
    if lens in {LensConfig.CHARTER_MEMORY, LensConfig.CHARTER_MEMORY_VAULT, LensConfig.FULL}:
        memory_idx = skopus_dir / "memory" / "MEMORY.md"
        memory_text = _read_if_exists(memory_idx)
        if memory_text:
            parts.append("## Memory Index\n" + memory_text)

        # Include feedback files
        feedback_dir = skopus_dir / "memory" / "feedback"
        if feedback_dir.exists():
            feedback_parts: list[str] = []
            for fb_file in sorted(feedback_dir.glob("*.md")):
                fb_text = _read_if_exists(fb_file, max_chars=2000)
                if fb_text:
                    feedback_parts.append(f"### {fb_file.stem}\n{fb_text}")
            if feedback_parts:
                parts.append(
                    "## Feedback Memory (corrections and validated calls)\n"
                    + "\n\n".join(feedback_parts[:10])  # cap at 10 entries
                )

    # --- VAULT (lens 3) ---
    if lens in {LensConfig.CHARTER_MEMORY_VAULT, LensConfig.FULL}:
        if vault_dir:
            vault_idx = vault_dir / "wiki" / "index.md"
            vault_text = _read_if_exists(vault_idx)
            if vault_text:
                parts.append("## Vault Index (decisions and learnings)\n" + vault_text)

    # --- GRAPH (lens 4, full only) ---
    if lens == LensConfig.FULL:
        parts.append(
            "## Structural Knowledge Graph\n"
            "A graphify knowledge graph is available for this codebase. When "
            "answering architecture questions, prefer querying the graph over "
            "reading raw files. Graph outputs include god nodes, communities, "
            "and surprising connections with confidence-tagged edges "
            "(EXTRACTED / INFERRED / AMBIGUOUS)."
        )

    if task_hint:
        parts.append(f"## Current Task Context\n{task_hint}")

    return "\n\n---\n\n".join(parts)
