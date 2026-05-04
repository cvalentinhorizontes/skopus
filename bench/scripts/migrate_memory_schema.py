"""One-shot script to migrate ~/.skopus/memory/feedback/*.md frontmatter
to the v2 evidence-locked §4.1 schema.

Reads each entry, identifies missing fields (id, source, confidence,
applies_to, supersedes, sensitivity, last_validated_at), and writes
back with conservative defaults:

  source: 'imported'
  confidence: 'weak'
  applies_to: {paths: [], task_types: [], keywords: []}
  supersedes: []
  sensitivity: 'normal'
  last_validated_at: '' (unset)

Defaults are intentionally weak so the new fields don't lie. Carlos
sharpens them by hand at /charter-evolve as he reviews each entry.

Run:
    python3 -m bench.scripts.migrate_memory_schema --dry-run
    python3 -m bench.scripts.migrate_memory_schema           # writes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

DEFAULTS = {
    "source": "imported",
    "confidence": "weak",
    "applies_to": {"paths": [], "task_types": [], "keywords": []},
    "supersedes": [],
    "sensitivity": "normal",
    "last_validated_at": "",
}


def _split(text: str) -> tuple[dict | None, str]:
    """Split frontmatter-prefixed markdown into (meta, body).

    Returns (None, text) for missing/malformed frontmatter (caller skips).
    """
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    front = text[4:end]
    body = text[end + 5 :]
    try:
        meta = yaml.safe_load(front)
    except yaml.YAMLError:
        return None, text
    return meta if isinstance(meta, dict) else None, body


def _migrate_one(meta: dict) -> tuple[dict, list[str]]:
    """Apply v2 §4.1 defaults to meta. Returns (new_meta, list_of_added_keys)."""
    added: list[str] = []
    new = dict(meta)
    if "id" not in new and "name" in new:
        new["id"] = new["name"]
        added.append("id")
    for key, default in DEFAULTS.items():
        if key not in new:
            new[key] = default
            added.append(key)
    return new, added


def _write_back(path: Path, meta: dict, body: str) -> None:
    """Rewrite the file with new frontmatter + original body."""
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).rstrip()
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    parser.add_argument(
        "--memory-dir",
        type=Path,
        default=Path.home() / ".skopus" / "memory",
        help="Path to ~/.skopus/memory/. Default uses HOME.",
    )
    args = parser.parse_args()

    feedback = args.memory_dir / "feedback"
    if not feedback.is_dir():
        sys.stderr.write(f"ERROR: {feedback} does not exist\n")
        return 1

    files = sorted(feedback.glob("*.md"))
    print(f"Scanning {len(files)} feedback entries in {feedback}\n")

    changed = 0
    skipped = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"  SKIP  (read error: {exc})  {f.name}")
            skipped += 1
            continue
        meta, body = _split(text)
        if meta is None:
            print(f"  SKIP  (no frontmatter / bad YAML)  {f.name}")
            skipped += 1
            continue
        new_meta, added = _migrate_one(meta)
        if not added:
            continue
        if args.dry_run:
            print(f"  WOULD-WRITE  {f.name}  +{','.join(added)}")
        else:
            _write_back(f, new_meta, body)
            print(f"  WROTE        {f.name}  +{','.join(added)}")
        changed += 1

    verb = "Would migrate" if args.dry_run else "Migrated"
    print(f"\n{verb} {changed} entries (skipped {skipped}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
