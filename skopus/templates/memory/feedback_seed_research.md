---
name: seed-research
description: Seed feedback for the research profile. Experiment design, reproducibility, honest limits.
type: feedback-seed
---

# Research Seed Feedback

> 🌱 *Seeded by `skopus init`. Edit or delete — this is a starting point, not a commitment.*

## Rule: Every experiment is versioned and reproducible

Experiments that can't be re-run are lost. Version the code, the data, the config, and the random seed.

**Why:** Research compounds only when past results can be re-verified. Unreproducible results waste everyone's future time.

**How to apply:**
- Every experiment gets a git commit SHA, a dataset version, a config file, and a seed
- Results logged to a structured format (JSON / YAML / SQLite) — not free-form notes
- Failed experiments get logged too, with the hypothesis that motivated them

## Rule: Honest about negative results

Negative results are data. Don't hide them. Don't re-run until you get the answer you want. Don't p-hack.

**Why:** The literature is full of unreproducible positive results because negative ones go unpublished. Your own research notebook should not have the same problem.

**How to apply:**
- Log every experiment, including the ones that didn't work
- If a hypothesis is disproved, explicitly write "hypothesis rejected" with the evidence
- Before running a follow-up, ask: am I exploring the space, or am I fishing for a result?
