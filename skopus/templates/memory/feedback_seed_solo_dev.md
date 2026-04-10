---
name: seed-solo-dev
description: Seed feedback for the solo-dev profile. Ship-first mindset, minimal scope, avoid premature optimization.
type: feedback-seed
---

# Solo-Dev Seed Feedback

> 🌱 *Seeded by `skopus init`. Edit or delete — this is a starting point, not a commitment.*

## Rule: Ship the atomic unit, then iterate

Default to the smallest working version that could be useful. Avoid multi-feature PRs and big-bang rewrites.

**Why:** Solo devs don't have review capacity for large changes. Smaller commits → easier to revert, easier to debug, easier to understand two weeks later.

**How to apply:**
- One PR per logical concern
- YAGNI ruthlessly — remove any feature that isn't on the current milestone
- No speculative abstractions — rule of three before generalizing
- Prefer iteration over upfront design for anything that can ship in < 1 day

## Rule: Test what matters, skip what doesn't

Write tests for the critical path and the places bugs have hidden before. Skip tests for trivial wiring code and one-off scripts.

**Why:** Solo devs can't maintain 100% test coverage without burning out. Test debt hurts less than over-testing.

**How to apply:**
- Unit test: business logic, edge cases, validation
- Skip: thin controllers, boilerplate, framework glue
- Integration test: the happy path and 2-3 critical failure modes
- If a bug escaped to production, write a test for it as part of the fix
