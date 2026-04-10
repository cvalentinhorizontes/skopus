---
description: "Capture knowledge from the current session into the wiki"
---

# /compile

Capture valuable knowledge from the current session into the vault before it evaporates into chat history. **The most important wiki command** — it's what makes the wiki compound across sessions.

`$ARGUMENTS` is an optional topic focus.

## Steps

1. **Review the conversation** for:
   - Architectural decisions (with rationale and tradeoffs)
   - Patterns discovered
   - Gotchas encountered
   - Problems solved (fix + root cause)
   - Tools evaluated (chosen, rejected, why)
   - Configurations that worked
   - Non-obvious empirical facts (latencies, limits, version quirks)

2. **Filter noise.** Skip trivial fixes and anything already in git history. Bar: *would future-me want to find this in 3 months?*

3. **If `$ARGUMENTS` is provided,** scope extraction to that topic.

4. **For each piece of knowledge:** check `wiki/index.md` for existing pages. Update existing (preferred) or create new. If contradicted, add `> ⚠️ Contradiction:` callout.

5. **Cross-link** with `[[wikilinks]]`.

6. **Update `wiki/index.md`.**

7. **Append to `log.md`:**
   ```
   ## [YYYY-MM-DD HH:MM] compile | <Topic or "Session knowledge">
   <Brief description.>
   Pages touched: [[page-1]], [[page-2]]
   ```

8. **Git commit:** `compile: <topic or 'session knowledge'>`.

9. **Print a summary** of what was captured.

## Rules

- Be honest about what's new vs. already-known.
- Don't inflate — if a session produced nothing wiki-worthy, say so and skip the commit.
- Capture the *why*, not just the *what*.
- Capture surprises — the most valuable entries are things that contradicted assumptions.
