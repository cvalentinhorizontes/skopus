---
description: "Health-check the wiki and fix issues"
---

# /lint

Scan the wiki for integrity issues and report a health report with suggested fixes. Auto-fix safe cases on request.

No arguments.

## Steps

1. **Scan every `.md` file** in `wiki/` via `Glob: wiki/**/*.md`.

2. **Extract all `[[wikilinks]]`** from every page. Track source page and link target.

3. **Build inbound link counts** (excluding `index.md`).

4. **Check each wikilink target resolves** to an existing page.

5. **Check `updated:` frontmatter dates.** Flag pages older than 30 days.

6. **Scan for repeated terms** that don't have their own page yet (capitalized terms, technical terms appearing 3+ times).

7. **Look for potential contradictions** — same entity described differently across pages.

8. **Print a health report:**
   ```
   📊 Wiki Health Report

   Totals: Pages, Links, Words, Sources

   ❌ Broken wikilinks (N)
   🏝️  Orphan pages (N)
   🕸️  Stale pages (N)
   📝 Suggested new pages (N)
   ⚠️  Potential contradictions (N)
   ```

9. **Offer to auto-fix** safe cases:
   - Broken wikilinks → create stub pages OR remove links (user chooses)
   - Missing index entries → add them automatically

10. **Append lint results to `log.md`.**

11. **Git commit if any fixes were applied:** `lint: fix <N> <issue type>`.

## Rules

- Report before fixing. Always show the full report first.
- Auto-fixes are safe only. Creating stubs and updating index entries are safe. Deleting/merging require confirmation.
- Stub pages get `type: stub` and a `> ⚠️ Stub: needs content` callout.
- Don't flag pages created in the last 7 days as stale.
- `index.md` is excluded from orphan/inbound counts.
