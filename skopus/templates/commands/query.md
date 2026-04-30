---
description: "Ask a question against the knowledge base"
---

# /query

Answer a question by synthesizing from the vault. `$ARGUMENTS` is the question.

## Steps

1. **Read `wiki/index.md`** to understand what's available.

2. **Identify relevant pages** by matching on titles, summaries, and implied tags.

3. **Read those pages.** Follow `[[wikilinks]]` **one level deep** if needed for the question. Don't go deeper unless explicitly required.

4. **Synthesize a comprehensive answer:**
   - Lead with a direct answer
   - Cite wiki pages inline using `[[wikilinks]]`
   - Show how pages connect when the answer spans multiple
   - Mention raw sources when cited in pages

5. **If the answer reveals a gap** (sub-question the wiki can't fully answer), note it:
   > 💡 *Gap noticed: no page exists for X. Consider `/ingest` or `/compile` to add it.*

6. **If the answer is substantial and reusable** (3+ paragraphs of synthesis), offer to save it:
   > This answer is reusable. Save as a new wiki page in `wiki/concepts/` or to `output/`?

7. **Do NOT modify any wiki files.** `/query` is read-only. User must explicitly accept the save offer.

## Rules

- Cite everything.
- Be honest about gaps — don't fabricate.
- One level deep on wikilink following.
- Prefer wiki over web search — trust curated knowledge first.
- If the answer contradicts a wiki page, flag it and recommend `/lint`.
