"""skopus_get_charter_section — return a named section from charter files.

Splits each charter file into sections by ## (H2) and # (H1) headings.
Match on heading is case-insensitive. First file containing the heading
wins (CLAUDE.md > workflow_partnership.md > user_profile.md by lookup order).

Returns the section content if found, or a list of available section
names if not — so the agent can retry with a real section name."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

CHARTER_FILES = ("CLAUDE.md", "workflow_partnership.md", "user_profile.md")
HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*$", re.MULTILINE)


def _split_sections(text: str) -> dict[str, str]:
    """Split markdown into {heading: content} by H1 + H2 headings.

    Heading is the matched text (case-preserved). Content is everything
    until the next heading or end of file.
    """
    sections: dict[str, str] = {}
    matches = list(HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[heading] = text[start:end].strip()
    return sections


async def skopus_get_charter_section(section: str) -> dict:
    """Return the named section from any charter file.

    Match is case-insensitive on the heading text. Searches across all
    charter files (in CHARTER_FILES order); first hit wins. Returns
    `found: False` with `available_sections` list when no match.

    Returns:
        {"found": True, "section": <matched heading>, "source_file": <path>,
         "content": <section body>}
        or {"found": False, "available_sections": [...]}
        or {"found": False, "hint": "..."} when ~/.skopus/charter/ missing.
    """
    skopus_dir = Path.home() / ".skopus"
    charter_dir = skopus_dir / "charter"
    if not charter_dir.is_dir():
        return {
            "found": False,
            "hint": f"Charter not found at {charter_dir}. Run `skopus init` first.",
        }

    target = section.strip().lower()
    all_sections: list[str] = []

    for fname in CHARTER_FILES:
        fpath = charter_dir / fname
        if not fpath.is_file():
            continue
        try:
            text = fpath.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("skopus.mcp.tools.charter: cannot read %s: %s", fpath, exc)
            continue
        sections = _split_sections(text)
        for heading, content in sections.items():
            all_sections.append(heading)
            if heading.lower() == target:
                return {
                    "found": True,
                    "section": heading,
                    "source_file": str(fpath),
                    "content": content,
                }

    return {
        "found": False,
        "available_sections": sorted(set(all_sections)),
    }
