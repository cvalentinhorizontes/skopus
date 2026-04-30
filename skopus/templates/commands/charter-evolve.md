---
description: "Session-end reflection — capture corrections, validated calls, and new rules from this session"
---

# /charter-evolve

The compounding mechanism for the partnership charter. Run this at the end of every substantive session. It captures what happened so the next session starts smarter.

**This runs inside the agent, not the shell.** The agent reviews the full conversation history and extracts knowledge — no manual input needed.

## Steps

1. **Review the full conversation history.** Look for:
   - **Corrections** — moments where the user said "no", "don't do that", "use X instead", or pushed back on an approach. Each correction is a drift.
   - **Validated calls** — moments where the agent made a non-obvious choice and the user confirmed it worked ("yes exactly", "perfect", "keep doing that", accepted without pushback). These are easy to miss — watch for them.
   - **New rules** — any explicit instruction the user gave about how to work going forward ("always X", "never Y", "from now on Z").

2. **For each item found, write a feedback file** at `~/.skopus/memory/feedback/YYYY-MM-DD-<slug>.md` using this format:

   ```markdown
   ---
   name: <kind>-<slug>
   description: <one-line description>
   type: feedback
   captured: YYYY-MM-DD
   ---

   # <Title>

   **Why:** <why this matters — the reason the user gave or the context>

   **How to apply:** <when and where this rule kicks in — be specific>
   ```

3. **Append drift entries to the charter.** Open `~/.skopus/charter/workflow_partnership.md` and append each correction to **Section 7 (Where We've Drifted)** in this format:

   ```
   > **YYYY-MM-DD — <what I did wrong>.** <context>. **Correction:** <what the user said>. **Fix:** <the rule to follow next time>.
   ```

4. **Append validated calls to the charter.** In the same file, append each win to **Section 8 (What Has Worked):**

   ```
   - **YYYY-MM-DD — <what I did right>.** <why it worked>. *(How: <how to repeat it>)*
   ```

5. **Update the memory index.** Add a one-line entry for each new feedback file to `~/.skopus/memory/MEMORY.md` under the **Feedback Memory** section:

   ```
   - [feedback/YYYY-MM-DD-<slug>.md](feedback/YYYY-MM-DD-<slug>.md) — <one-line hook>
   ```

6. **Git commit** the changes to `~/.skopus/`:

   ```bash
   cd ~/.skopus && git add -A && git commit -m "charter-evolve: <N> entries from <date>"
   ```

7. **Print a summary:**

   ```
   Charter evolved:
     Corrections saved: N
     Validated calls saved: N
     New rules saved: N
     Feedback files written: [list]
     Charter sections updated: §7 (drift log), §8 (what has worked)
   ```

## Rules

- **Be honest.** If nothing worth capturing happened in this session, say so and skip the commit. Don't inflate.
- **Capture the user's words, not your interpretation.** When saving a correction, quote what the user actually said.
- **Be specific in How to apply.** "Don't do X" is not enough. "When Y happens, do Z instead of X" is useful.
- **Save validated calls, not just corrections.** Corrections are easy to notice. Confirmations are quieter — look for acceptance, approval, "exactly", or the user moving on without pushback after a non-obvious choice.
- **Convert relative dates to absolute dates.** "Yesterday" → "2026-04-09".
- **Don't save trivial items.** "Fixed a typo" is not worth a feedback file. "Discovered that GPT-4o returns empty content alongside tool_calls" IS worth it.

## When to run

At the end of every session where:
- The user corrected you on something
- A non-obvious judgment call worked
- You learned something empirical that contradicted an assumption
- A new workflow pattern was established
- The user explicitly asked you to remember something

If none of these happened, skip it. Not every session produces charter-worthy knowledge.
