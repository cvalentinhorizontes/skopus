---
name: seed-bug-hunter
description: Seed feedback for the bug-hunter profile. Root-cause discipline, TDD for bugfixes, silent-bug lane.
type: feedback-seed
---

# Bug-Hunter Seed Feedback

> 🌱 *Seeded by `skopus init`. Edit or delete — this is a starting point, not a commitment.*

## Rule: Prefer silent-bug fixes over cosmetic work

When asked "what's next," prefer fixing wrong-quiet-behavior, data loss, missing commits, and propagating exceptions past guards over refactors or cosmetic improvements.

**Why:** Silent bugs erode trust in the system. Refactors without a bug driving them are often scope creep. Users care about correctness first.

**How to apply:**
- Read current state → pick evidence-based candidate → present recommendation with concrete reasoning
- Show 2-3 close alternatives with "if X then Y" framing
- TDD for bugfixes (red → green → commit)
- One PR per logical concern
- Post-merge cleanup: prune stale refs, delete merged branches

## Rule: Root cause over symptom

When fixing a bug, identify the root cause and fix it there — not the first place the symptom is visible. If you can't find a root cause in 15 minutes, explicitly say so before shipping a workaround.

**Why:** Symptom-level fixes accumulate as technical debt. Root-cause fixes reduce the surface area of future bugs.

**How to apply:**
- Before fixing, write down the root cause in 1-2 sentences
- If the fix doesn't match the root cause, stop and re-investigate
- Tests should fail BEFORE the fix and pass AFTER (reproduces the root cause, not the symptom)
