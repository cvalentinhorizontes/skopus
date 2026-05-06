"""Loader for ~/.skopus/vault/wiki/<section>/*.md pages.

Pages do not require YAML frontmatter. Title is the first H1 (`# Title`)
in the body, or the filename stem if none. Section is the immediate
parent directory name (concepts / entities / sources / decisions /
comparisons by convention, but any subdir works)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VaultPage:
    """One wiki page."""

    path: Path
    section: str
    title: str
    body: str


def load_vault_pages(vault_dir: Path) -> list[VaultPage]:
    """Load all wiki pages under <vault_dir>/wiki/**/*.md.

    Skips files that fail to read (logged at WARNING).
    """
    wiki = vault_dir / "wiki"
    if not wiki.is_dir():
        return []

    pages: list[VaultPage] = []
    for md in sorted(wiki.rglob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("skopus.mcp.vault_index: cannot read %s: %s", md, exc)
            continue
        section = md.parent.name
        title = md.stem
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break
        pages.append(VaultPage(path=md, section=section, title=title, body=text))
    return pages
