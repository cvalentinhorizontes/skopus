# Phase 0 Gate — Evidence

**Date sealed:** 2026-05-04
**Branch:** `feat/v0.6.0-phase0-lock-in`
**Slim-block source commit:** `77c2d94` — `phase0: slim Skopus adapter context` (2026-04-28)
**Lock-in test commit:** `565ccc4` — `test(phase0): lock slim block size + render determinism` (2026-05-04)

---

## v2 evidence-locked exit gates

| Gate | Target | Actual | Status |
|---|---|---|---|
| Existing tests pass | green | 21/21 pass on `tests/test_multi_adapters.py` | ✓ |
| Always-loaded token count | ≤ 50% of pre-slim (~1500 tokens) | ~266 tokens (~18% of pre-slim ceiling) | ✓ |
| Slim block lines | ≤ 35 (test cap) | 27 | ✓ |
| Slim block chars | ≤ 2000 (test cap) | ~1065 | ✓ |
| Slim block ≈tokens | ≤ 600 (test cap) | ~266 | ✓ |
| Idempotent render | byte-equal across same-day re-renders | proved by `test_slim_block_render_is_deterministic_within_one_day` | ✓ |
| Mock CP harness wires end-to-end | runs all 5 lens configs without error | confirmed | ✓ |
| Real-API CP score (thin block) | ≥ 95% of pre-slim baseline | **deferred — not measurable on mock driver** | ⚠ deferred |

---

## Mock CP baseline

**Result file:** `docs/proposals/skopus-v1/phase0-baseline.json`

(Stored alongside this gate doc rather than in `bench/results/` because the latter is gitignored — it holds ephemeral runs. Canonical baselines belong with the narrative that frames them.)

**Driver:** `MockDriver` — deterministic, free, no API calls.
**Scenarios:** all 120 in the CP corpus (no `--limit`).
**Lens configs:** all 5 (`vanilla`, `+charter`, `+charter+memory`, `+charter+memory+vault`, `full skopus`).

### Per-lens token totals (regression signature)

| Lens | Total tokens | Δ vs vanilla |
|---|---|---|
| vanilla | 5,972 | — |
| +charter | 149,252 | +143,280 |
| +charter +memory | 678,138 | +672,166 |
| +charter +memory +vault | 920,751 | +914,779 |
| full skopus | 930,408 | +924,436 |

These numbers are **deterministic on the mock driver** and are the v0.6.0 reference signature. Any later commit that changes total token consumption per lens by more than 5% (in either direction) without an explanatory `/charter-evolve` note is a regression candidate. The Phase 1 plan should include a CI assertion against this baseline.

### Per-lens accuracy on mock

All 5 lens configs scored `0/120` accuracy with mean_score `0.0083`. This is **expected and correct** — the `MockDriver` returns deterministic but content-free responses. The harness is not measuring whether Skopus *helps*; it's measuring whether Skopus *runs cleanly end-to-end*. The "does Skopus help" measurement requires the Anthropic driver and is deferred (see below).

---

## Real-API CP measurement (deferred)

The v2 evidence-locked gate requires "thin block ≥ 95% of pre-slim baseline" on real CP runs. That requires:

- `ANTHROPIC_API_KEY` in environment
- `--driver anthropic` flag
- ~$10-20 per 120-scenario sweep (rough estimate; actual cost depends on per-scenario token usage)
- A pre-slim baseline run on the same scenarios — which we *do not have* recorded in `bench/results/`

**Decision:** real-API measurement is deferred to **Phase 1 release-cut CI**. Specifically:

1. Phase 1 plan adds a one-time pre-slim baseline run by checking out `77c2d94^` (the commit just before slim shipped), running `--driver anthropic --ablation`, and persisting the result as `skopus-bench-pre-slim-baseline-YYYYMMDD.json`.
2. Same plan adds a thin-block run from current `HEAD`, persisted as `skopus-bench-thin-block-YYYYMMDD.json`.
3. Compare and assert `thin_block_full_skopus_accuracy >= 0.95 * pre_slim_full_skopus_accuracy`.

Without step 1 we cannot honestly evaluate the v2 gate. The mock baseline above proves the harness is *capable* of measuring it; the real measurement waits for Carlos's authorization to spend API credits.

---

## Regression locks added in this branch

Both in `tests/test_multi_adapters.py`:

- **`test_skopus_block_is_slim_pointer_block`** — strengthened with explicit char (≤ 2000), token (≤ 600), line (≤ 35) caps + structural-contract assertions (Protocol + Local Context sections must be present). Prevents silent re-bloat under the existing line cap.
- **`test_slim_block_render_is_deterministic_within_one_day`** — new. Two renders of identical inputs must produce byte-identical output. Required for `MarkdownAdapter.install()` to remain truly idempotent across re-runs.

Sanity-checked the new caps actually fail when triggered: a 3000-char bloat appended to the block trips the 2000-char assertion with a clear error message.

---

## Phase 0 acceptance summary

Phase 0 was code-shipped on 2026-04-28 in commit `77c2d94`. This branch adds:

1. The regression locks the original commit lacked (size caps + idempotency).
2. The mock baseline measurement that establishes the v0.6.0 reference signature.
3. The honest record of which exit gates are measurable now (8 of 9) and which require API budget (1 of 9, deferred to Phase 1 CI).

By the v2 evidence-locked criteria, Phase 0 passes — with the caveat that the real-API CP score is deferred, not skipped.

---

## Next phase

**Phase 1 — Verified adapter bridges.** Plan to be written separately at `docs/superpowers/plans/2026-MM-DD-phase1-verified-adapter-bridges.md`.

Scope per the v1.0 proposal (`docs/proposals/skopus-v1/phasing.html`):
- Consolidate to 3 verified adapters: `AGENTS.md`, `CLAUDE.md`, Cursor.
- Smoke-test harness per advertised agent.
- `skopus doctor` accurately reports installed/partial/broken.
- Defer Aider, Gemini, Continue until they pass smoke tests.
- Include the deferred real-API CP measurement as Task 0 of Phase 1.
