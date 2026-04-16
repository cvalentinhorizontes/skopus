"""Skopus audit — memory health checks.

Three checks:
  1. sync_index   — diff feedback files on disk vs entries in MEMORY.md
  2. check_scope_tags — find feedback files missing the `scope:` field
  3. run_audit    — run all checks, print report, optionally fix
"""

from __future__ import annotations

import re
from pathlib import Path


def _parse_index_entries(memory_md: Path) -> list[str]:
    """Extract feedback file basenames referenced in MEMORY.md.

    Looks for lines matching: - [feedback/...](feedback/...) — ...
    Returns a sorted list of basenames (e.g. ["foo.md", "bar.md"]).
    """
    if not memory_md.exists():
        return []

    text = memory_md.read_text(encoding="utf-8")
    # Match markdown links like [feedback/some-file.md](feedback/some-file.md)
    pattern = re.compile(r"\[feedback/([^\]]+\.md)\]\(feedback/[^)]+\.md\)")
    return sorted(pattern.findall(text))


def _list_feedback_files(feedback_dir: Path) -> list[str]:
    """Return sorted basenames of all .md files in the feedback directory."""
    if not feedback_dir.exists():
        return []
    return sorted(f.name for f in feedback_dir.iterdir() if f.suffix == ".md")


def _read_frontmatter(path: Path) -> dict[str, str]:
    """Parse YAML frontmatter from a markdown file using basic string parsing.

    Splits on '---' delimiters and extracts key: value pairs.
    Returns a dict of frontmatter fields.
    """
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}

    frontmatter_text = parts[1].strip()
    result: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z_-]+)\s*:\s*(.+)$", line)
        if match:
            result[match.group(1)] = match.group(2).strip()
    return result


def _first_line_of_file(path: Path) -> str:
    """Read the first non-frontmatter heading from a feedback file for the index hook."""
    text = path.read_text(encoding="utf-8")
    # Skip frontmatter
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text

    for line in body.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    # Fallback: use the description from frontmatter
    fm = _read_frontmatter(path)
    return fm.get("description", path.stem)


def sync_index(
    skopus_dir: Path, *, fix: bool = False
) -> dict[str, list[str]]:
    """Diff feedback files on disk vs entries in MEMORY.md.

    Returns:
        {
            "missing_from_index": [...],  # files on disk but not in MEMORY.md
            "dangling_entries": [...],    # entries in MEMORY.md but no file on disk
        }

    If fix=True, adds missing entries and removes dangling ones from MEMORY.md.
    """
    memory_md = skopus_dir / "memory" / "MEMORY.md"
    feedback_dir = skopus_dir / "memory" / "feedback"

    index_basenames = _parse_index_entries(memory_md)
    disk_basenames = _list_feedback_files(feedback_dir)

    index_set = set(index_basenames)
    disk_set = set(disk_basenames)

    missing_from_index = sorted(disk_set - index_set)
    dangling_entries = sorted(index_set - disk_set)

    result = {
        "missing_from_index": missing_from_index,
        "dangling_entries": dangling_entries,
    }

    if fix and (missing_from_index or dangling_entries):
        text = memory_md.read_text(encoding="utf-8")

        # Remove dangling entries
        for basename in dangling_entries:
            # Remove lines referencing this file
            pattern = re.compile(
                r"^- \[feedback/" + re.escape(basename) + r"\].*\n?",
                re.MULTILINE,
            )
            text = pattern.sub("", text)

        # Add missing entries under "## Feedback Memory" section
        for basename in missing_from_index:
            file_path = feedback_dir / basename
            hook = _first_line_of_file(file_path)
            entry = f"- [feedback/{basename}](feedback/{basename}) — {hook}\n"

            # Insert before the next section (## Project Memory, ## Reference Memory, or ---)
            # Find the end of the Feedback Memory section
            fb_match = re.search(
                r"(## Feedback Memory.*?\n)(.*?)(\n## |\n---)",
                text,
                re.DOTALL,
            )
            if fb_match:
                insert_pos = fb_match.end(2)
                text = text[:insert_pos] + entry + text[insert_pos:]
            else:
                # Fallback: append before the first --- separator at end
                text += entry

        memory_md.write_text(text, encoding="utf-8")

    return result


def check_scope_tags(skopus_dir: Path) -> list[str]:
    """Find feedback files missing the `scope:` field in frontmatter.

    Returns a list of basenames of files without scope tags.
    """
    feedback_dir = skopus_dir / "memory" / "feedback"
    if not feedback_dir.exists():
        return []

    missing_scope: list[str] = []
    for f in sorted(feedback_dir.iterdir()):
        if f.suffix != ".md":
            continue
        fm = _read_frontmatter(f)
        if "scope" not in fm:
            missing_scope.append(f.name)

    return missing_scope


def run_audit(skopus_dir: Path, *, fix: bool = False) -> dict:
    """Run all audit checks and return a structured report.

    Returns:
        {
            "sync": {"missing_from_index": [...], "dangling_entries": [...]},
            "scope": [...],  # files missing scope tags
            "clean": bool,   # True if no issues found
        }
    """
    sync_result = sync_index(skopus_dir, fix=fix)
    scope_result = check_scope_tags(skopus_dir)

    clean = (
        not sync_result["missing_from_index"]
        and not sync_result["dangling_entries"]
        and not scope_result
    )

    return {
        "sync": sync_result,
        "scope": scope_result,
        "clean": clean,
    }
