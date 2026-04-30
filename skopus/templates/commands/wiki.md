---
description: "Wiki operations: status, search, recent activity, stats"
---

# /wiki

Utility operations on the vault. Accepts a subcommand as `$ARGUMENTS`.

## Subcommands

### `status`
- Total pages by type (concepts, entities, sources, decisions, comparisons)
- Orphan count
- Last entry in `log.md`
- `git status` of the vault

### `search <terms>`
- Grep across all `wiki/` files
- Case-insensitive match
- Show page names + matching lines with 2 lines of context

### `recent`
- Last 10 entries from `log.md`

### `stats`
- Pages by type (one count per wiki/ subdirectory)
- Total word count across all `wiki/*.md`
- Number of raw sources ingested
- Number of `[[wikilinks]]`
- Number of entries in `log.md`

## Execution

1. Parse `$ARGUMENTS`. If empty, default to `status`.
2. Execute via Read, Glob, Grep, and Bash tools.
3. Print a clean, scannable report.
4. Do NOT modify any files — `/wiki` is read-only.
