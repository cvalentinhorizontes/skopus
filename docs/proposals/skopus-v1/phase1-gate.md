# Phase 1 Gate — Evidence

**Date sealed:** 2026-05-04
**Branch:** `feat/v0.7.0-phase1-verified-adapters`
**Adapters commit:** `f348f81` — `feat(adapters): tier-aware registry + AGENTS.md bridge + doctor --agent`
**Gate-evidence commit:** *this doc + measurement script + phase0-gate.md update — committed in Phase 1's second batched commit*

---

## v1.0 proposal Phase 1 exit gates

| Gate | Target | Actual | Status |
|---|---|---|---|
| Existing tests pass | green | **197 pass, 1 skipped** across full `tests/` (was 175 at Phase 0 close; +22 from Phase 1) | ✓ |
| 3 adapters marked ADVERTISED | claude-code, cursor, agents-md | confirmed by `tests/test_adapter_tier.py::test_advertised_adapters_for_v071` and `tests/test_smoke_advertised_adapters.py::test_advertised_adapter_has_advertised_tier[*]` | ✓ |
| Smoke suite per advertised adapter | install / status / uninstall + idempotent + structural | passes in `tests/test_smoke_advertised_adapters.py` (15 parametrized + 2 specific = 17 tests, all green) | ✓ |
| Doctor accurately reports per-adapter | tier + detect + project status with evidence | `skopus doctor --agent <name>` works for all 6 adapters + the `agents-md` registration; tests in `tests/test_doctor_agent.py` (4 green) | ✓ |
| Aider/Gemini/Codex/Copilot demoted | EXPERIMENTAL tier | confirmed by `tests/test_adapter_tier.py::test_advertised_adapters_for_v071` — all four assert `EXPERIMENTAL` | ✓ |
| `AdapterTier` enum drift safety | enum used directly, not string literals | `skopus/cli.py` uses `AdapterTier.ADVERTISED` identity checks and enum-keyed dict (no `.get()` fallback) — drift will fail loud | ✓ |
| `AGENTS.md` adapter is universal | no platform detection, no dotdir variants | confirmed by `tests/test_agents_md_adapter.py` (7 tests) and `tests/test_smoke_advertised_adapters.py::test_agents_md_adapter_does_not_use_dotdir_even_when_present` | ✓ |
| Real-API CP gate (carried from Phase 0) | thin block ≥ 95% of pre-slim | **script ships, run deferred — `ANTHROPIC_API_KEY` was not in the Phase 1 implementation shell**; runnable via `python3 -m bench.scripts.measure_phase0_cp_gate` when Carlos approves the API budget | ⚠ deferred (script ready) |

**Overall:** 7 of 8 gates pass on automated evidence. The 1 deferred gate has
moved from "TBD" (Phase 0 close) to "executable script awaiting API budget"
(Phase 1 close). The Phase 0 gate doc has been updated in the same commit as
this file to reflect the new procedure.

---

## What this branch ships

**Tier-aware adapter registry:**
- `AdapterTier` enum (ADVERTISED / EXPERIMENTAL / UNVERIFIED) with `UNVERIFIED` as the fail-closed default on the `Adapter` ABC.
- Every existing adapter explicitly marked: Claude Code + Cursor as ADVERTISED, the rest as EXPERIMENTAL.
- New `AgentsMdAdapter` (universal AGENTS.md fallback) registered as the third ADVERTISED bridge with name `agents-md` and alias `agents`.

**Doctor enhancement:**
- `skopus doctor --agent <name>` introspection. Three-row Rich table: Tier (colored by tier), Platform detected, Project status. Honest disclaimer line for non-ADVERTISED adapters.
- Backwards-compatible: `skopus doctor` without `--agent` runs the legacy system-wide check unchanged.

**Smoke-test harness:**
- `tests/test_smoke_advertised_adapters.py` — parametrized over the 3 ADVERTISED adapters. Asserts file-side contract: file written at expected path, valid Skopus markers, well-formed structure (Cursor MDC frontmatter regex-validated, no PyYAML dep), `status()` agrees with file state, idempotent install (3×).
- Single source of truth for the advertised list lives at the top of the file — adding a 4th advertised adapter is a one-line change that automatically gains 5 test cases.

**Manual-smoke procedure:**
- `docs/proposals/skopus-v1/phase1-manual-smoke.md` — the per-release "agent actually loads it" checklist. Probe prompt is the same across agents so results are comparable. Cleanup script included.

**Real-API CP gate plumbing (carried from Phase 0):**
- `bench/scripts/measure_phase0_cp_gate.py` — script that uses git worktree to check out the pre-slim ref, runs CP with the Anthropic driver against both states, copies the pre-slim result file out of the worktree before cleanup so the report's referenced files survive, streams subprocess output for live progress on the 5–10 minute run, exits 0/1 against the 95% threshold.

---

## Manual-smoke results

The pytest smoke suite covers file-side contracts only. Per-platform
"agent actually loads it" verification follows the procedure in
`docs/proposals/skopus-v1/phase1-manual-smoke.md`. Run once per v0.7.x
release. Record results below.

| Date | Adapter | Result | Notes |
|---|---|---|---|
| 2026-05-05 | claude-code | ✓ **PROVEN** | Probe-token method (see "Clean probe procedure" below). CC against `/tmp/skopus-smoke/` returned: `"The user's name as recorded in the partnership charter is PROBE-1777999019-XYZZY (founder, primary stack: Python/TypeScript, time zone: America/Puerto_Rico)."` Token only existed in the live charter — repo grep clean. Plus extra wizard-seeded fields not asked for, indicating CC read the full user_profile.md. |
| 2026-05-05 | cursor | ✓ **PROVEN** | Same probe. Cursor against `/tmp/skopus-smoke/` returned: `"In the partnership charter (/tmp/skopus-mcp-home/.skopus/charter/workflow_partnership.md), the human side of the partnership is recorded as PROBE-1777999019-XYZZY (founder role)."` Cited the exact wired charter path AND noted the cross-reference to user_profile.md. Plus meta-cognition: noted the token "reads like a seeded probe ID from skopus init, not a display name such as Carlos." |
| 2026-05-05 | agents-md (via Codex CLI) | ✓ **PROVEN** | Same probe. Codex against `/tmp/skopus-smoke/` returned: `"The partnership charter records the user's name as PROBE-1777999019-XYZZY. Reference: /tmp/skopus-mcp-home/.skopus/charter/workflow_partnership.md:10"` — exact file:line citation. |

### Clean probe procedure (post-2026-05-05 v1)

Earlier "PASS" entries (since reverted) ran probes against the Skopus dev repo itself and asked for content the agent could grep without any wiring (e.g. "non-negotiables"). Those proved nothing — see `feedback_evidence_ambiguity_in_repo_probes.md`. The clean probe:

1. **Bootstrap an isolated smoke project** at `/tmp/skopus-smoke/` (git-init only, one README, no Skopus source code).
2. **Generate a unique token** — e.g. `PROBE-$(date +%s)-XYZZY`. Verify it's nowhere in the repo (`grep -rln "$TOKEN" /home/dev-carlos/skopus/`).
3. **Run `skopus init --name "$TOKEN"`** with isolated HOME so the token lands in the rendered charter (and only there).
4. **Wire all 3 ADVERTISED adapters** to the smoke project.
5. **Open each agent against `/tmp/skopus-smoke/`** (not the dev repo).
6. **Probe**: "Read this project's Skopus context and tell me the user's name as recorded in the partnership charter."
7. **PASS** = agent returns the literal token. Only the wiring → rendered charter chain could have placed it there.

---

## What this branch does NOT ship (deferred to later phases)

- **Aider / Gemini / Continue / Codex auto-config bridges** — would require their own smoke tests; remain at `EXPERIMENTAL` tier. Phase 2+ contingent on each passing the manual smoke list.
- **MCP server** — Phase 2.
- **Sub-harness format** — Phase 4.
- **Per-platform compilers** — Phase 5.
- **Autonomy daemon** — Phase 6.
- **Real-API CP measurement** — script ships in this branch, run waits for Carlos to authorize API budget.
- **Cascade integration test** for shared-AGENTS.md scenarios (`agents-md` + `codex`/`aider`/`copilot` all writing the same file) — flagged during code review of Task 13. Tracked as a follow-up integration test before any release that documents `agents-md` as a recommended pairing with the AGENTS.md-writing experimental adapters.

---

## Test count growth (this branch)

| Snapshot | Total tests | Source |
|---|---|---|
| Phase 0 close (main @ `7050158`) | 175 pass, 1 skipped | baseline |
| Phase 1 close (this branch HEAD) | 197 pass, 1 skipped | +22 across the 5 new test files (test_adapter_tier, test_agents_md_adapter, test_smoke_advertised_adapters, test_doctor_agent + the registry-extension test in test_multi_adapters) |

---

## Next phase

**Phase 2 — MCP server with 5 core tools.** Plan to be written separately when
Phase 1 closes.

Scope per the v1.0 proposal (`docs/proposals/skopus-v1/phasing.html`):
- `skopus_route_task` (Secretary), `skopus_get_harness`, `skopus_search_memory`,
  `skopus_query_vault`, `skopus_get_charter_section`, `skopus_record_drift`.
- Local stdio MCP server.
- Per-agent installer: `skopus link --mcp claude-code` etc.
- Schema metadata (§4.1 in v2 doc) — required for every durable record. Migration
  pass for existing memory entries.
- Exit gate: MCP visible/callable in Claude Code + Cursor + Cline (each verified);
  CP benchmark with MCP ≥ current CP at ≤ 50% always-loaded tokens.

Phase 2 should also pick up the deferred Phase 0 real-API measurement on its
release-cut CI, since by then Carlos will likely have provisioned API budget
for ongoing benchmarks.
