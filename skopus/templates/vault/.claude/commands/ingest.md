---
description: "Ingest a source (file path or URL) into the knowledge base"
---

# /ingest

Ingest a source into the vault. Creates a source summary page and distills knowledge into concept/entity/decision pages with `[[wikilinks]]` cross-references.

`$ARGUMENTS` is a file path (relative to the vault's `raw/` or absolute) OR a URL.

## Steps

1. **Resolve the source.**
   - If `$ARGUMENTS` is a URL → fetch with `WebFetch`, save cleaned markdown to `raw/articles/<slug>.md`.
   - If `$ARGUMENTS` is a path → verify the file exists under `raw/` (copy it there if outside). Never modify the original raw file.

2. **Read the source completely.**

3. **Identify what to distill:** entities (products, tools, services, people), concepts (techniques, patterns, frameworks), decisions (architectural choices with rationale), comparisons (side-by-side analyses).

4. **Create `wiki/sources/<slug>.md`** using the wiki page template. Include `type: source`, source path, Key Points, Details (~200-500 words), Related section.

5. **For each identified topic:** check if a wiki page exists. Update existing pages with new knowledge (preferred) or create new ones. Cross-link everything with `[[wikilinks]]`.

6. **Update `wiki/index.md`** with new pages.

7. **Append to `log.md`** with the ingest operation.

8. **Git commit:** `ingest: <source title>`.

9. **Print a summary** of pages created/updated.

## Rules

- Never modify files in `raw/`.
- Prefer updating existing pages over creating new ones.
- Over-link, don't under-link.
- Cite — every wiki page lists the raw source in frontmatter.
- Keep summaries concise.
