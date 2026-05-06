# Phase 2 Gate — Evidence

**Date sealed:** 2026-05-04
**Branch:** `feat/v0.8.0-phase2-mcp-server`
**MCP server commit:** `a9948b3` — `feat(mcp): stdio MCP server with 5 core tools`
**Installers + doctor commit:** `b6d8b1e` — `feat(mcp): per-agent installers + doctor MCP visibility + schema migration`
**Gate-evidence commit:** *this doc — committed in Phase 2's third batched commit*

---

## v1.0 proposal Phase 2 exit gates

| Gate | Target | Actual | Status |
|---|---|---|---|
| Existing tests pass | green | **272 pass, 1 skipped** across full `tests/` (was 197 at Phase 1 close; +75 from Phase 2) | ✓ |
| 5 MCP tools live | status, search_memory, query_vault, get_charter_section, record_drift | confirmed by `tests/test_mcp_*_tool.py` integration tests; each tool's `test_*_registered_in_server` exercises `build_server() + list_tools()` | ✓ |
| MCP server runs over stdio | `skopus mcp serve` produces valid JSON-RPC initialize response | confirmed by manual smoke + `test_mcp_serve_help_renders` | ✓ |
| Schema-aware memory loader | reads YAML frontmatter, defaults missing v2 §4.1 fields, surfaces malformed entries via `logging.WARNING` | passes 6 tests in `tests/test_memory_index.py`; loads 90 of 94 corpus entries with 4 WARNING lines for entries that have unquoted YAML colons | ✓ |
| Per-agent MCP installer per ADVERTISED adapter | claude-code, cline, cursor | 22 tests across 3 installer suites; shared logic in `_common.py` (DRY); corrupt-config backup safety wired | ✓ |
| `skopus link --mcp <agent>` dispatch | wires correct installer; errors on unknown agent; mutual-exclusivity with `--agent` | confirmed by 6 tests in `tests/test_link_mcp_flag.py` including the `--mcp X --agent Y` collision check | ✓ |
| Doctor reports MCP visibility | 4th row in `skopus doctor --agent <name>` per-adapter table | confirmed by 4 tests in `tests/test_doctor_mcp.py`; covers installed / not_installed / config-unparseable / n/a states | ✓ |
| Schema migration script ships | runnable, idempotent, dry-run capable | `bench/scripts/migrate_memory_schema.py` smoke-tested against tmp dir; defaults match v2 §4.1 (source=imported, confidence=weak, etc.) | ✓ (script ready, run deferred to Carlos) |
| Manual-smoke list ships | per-agent verification procedure | `docs/proposals/skopus-v1/phase2-manual-smoke.md` — HOME-isolated procedure for all 3 ADVERTISED installers + Caveat for agents that ignore HOME | ✓ |
| Real-API CP gate (carried from Phase 0) | thin block ≥ 95% of pre-slim | **still deferred — `ANTHROPIC_API_KEY` not yet provisioned**; runnable via `python3 -m bench.scripts.measure_phase0_cp_gate` | ⚠ deferred (script ready since Phase 1) |

**Overall:** 9 of 10 gates pass on automated evidence. The 1 deferred gate
remains the same Phase 0 carryover (real-API CP run, awaiting API budget).
The migration script is also "ready, run deferred" but that's by design —
Carlos runs it manually at `/charter-evolve` time.

---

## What this branch ships

**MCP server (commit `a9948b3`):**
- `skopus/mcp/` package using FastMCP via Anthropic's `mcp>=1.0` SDK.
- 5 tools, each in its own module under `skopus/mcp/tools/`:
  - `skopus_status` — liveness + initialization check.
  - `skopus_search_memory` — keyword-rank over feedback entries with
    `scope` / `paths` / `task_type` filters; query terms de-dup'd.
  - `skopus_query_vault` — keyword-rank over wiki pages with section
    `scope` filter; query terms de-dup'd.
  - `skopus_get_charter_section` — case-insensitive heading match across
    charter files, first-hit-wins by `CHARTER_FILES` order.
  - `skopus_record_drift` — queues a JSON entry to `~/.skopus/queue/drift/`
    with source/confidence/scope validation BEFORE filesystem writes.
- Schema-aware memory loader (`skopus/mcp/memory_index.py`) defaults
  missing v2 §4.1 fields and logs malformed entries.
- Vault loader (`skopus/mcp/vault_index.py`) walks `wiki/**/*.md` with
  H1-or-stem title derivation.
- `skopus mcp serve` CLI subcommand with lazy import.

**Installers + doctor + migration (commit `b6d8b1e`):**
- Three per-agent MCP installers (`skopus/mcp/installers/`):
  - Shared logic in `_common.py`: `SERVER_NAME`, `SERVER_ENTRY`,
    `load_mcp_config`, `backup_corrupt_config`. Each per-agent file is
    ~50 lines of config-path override.
  - Corrupt-JSON safety: invalid existing config gets renamed to
    `<name>.bak-<unix-ts>` BEFORE the fresh write.
- `skopus link --mcp <agent>` dispatch with mutual-exclusivity guard
  against `--agent` non-default values.
- `skopus doctor --agent <name>` 4th row reports MCP install status with
  color coding (green / yellow / red / dim).
- `bench/scripts/migrate_memory_schema.py` — idempotent one-shot for
  populating v2 §4.1 defaults across the existing feedback corpus.
- `phase2-manual-smoke.md` per-release verification procedure.

---

## Manual-smoke results

The pytest suite covers the in-process MCP-client contract (server
constructs, tools register, tools return correct shapes, installers
write/uninstall correctly). Per-agent "MCP tools actually appear in
Claude Code's tool list" verification follows the procedure in
`docs/proposals/skopus-v1/phase2-manual-smoke.md`. Run once per v0.8.x
release. Record results below.

| Date | Adapter | Result | Notes |
|---|---|---|---|
| 2026-05-05 | claude-code | ✓ headless | All 5 MCP tools exercised end-to-end via raw stdio JSON-RPC: `skopus_status` (returns 0.8.0 after version-sync fix `cab9c8c`), `skopus_search_memory` (1 match for `"founder"` against seeded HOME), `skopus_get_charter_section` (`"2. Non-Negotiables"` returns full content), `skopus_record_drift` (queue file written at `~/.skopus/queue/drift/`). Live UI probe deferred (would need a fresh CC session against re-wired `~/.claude/settings.json`). |
| 2026-05-05 | cursor | ✓ **PROVEN live** (after `eeda5c2`) | First wired Cursor with `skopus link --mcp cursor`. Cursor reported "no Skopus tool" — surfaced the absolute-path bug. After fix `eeda5c2` re-wrote `~/.cursor/mcp.json` with `command: /home/dev-carlos/.local/bin/skopus`, restarted Cursor, asked "Use the skopus_search_memory tool to find any prior corrections about premium quality." Cursor responded: "skopus_search_memory is available and ran successfully." Returned 6 real corpus matches with correct shape (`id`/`scope`/`score`/`path`), top match `seed-founder` at score 9.0 from `/home/dev-carlos/.skopus/memory/feedback/founder_seed.md`. End-to-end MCP roundtrip proven through Cursor's UI. |
| *not yet run* | cline | — | needs Cline session to verify MCP tool discovery |

### Foundation bugs surfaced by this smoke run

| Bug | Fix commit | Description |
|---|---|---|
| Claude Code `status()` reports `not_installed` after `install_commands`/guard creates `.claude/` | `a70c497` | Adapter `status()` now checks both project-root and `.claude/` candidate paths. Regression test added. |
| `__version__` stuck at 0.5.1 despite v0.8.0 pyproject bump → MCP tool, CLI, adapters.lock all reported stale version | `cab9c8c` | Bumped `__version__` to 0.8.0 + added `tests/test_version_sync.py` that fails CI on future drift. |
| `skopus init` silently re-wires `cwd` project, cross-contaminating real projects when init runs from outside the intended dir | `f42e6cc` | Init now refuses to overwrite a project whose existing Skopus block points at a different `skopus_dir` (unless `--force`). New `--no-autolink` flag opts out of cwd auto-link entirely. 4 regression tests in `tests/test_init_no_contamination.py`. Live-replayed the original bug scenario after the fix — real project's CLAUDE.md unchanged. |
| MCP installer wrote bare `command: "skopus"` instead of absolute path → desktop agents (Cursor) couldn't spawn the server because their PATH didn't include `~/.local/bin`. Tools never registered. Doctor reported "MCP installed: installed" anyway because the config file was correctly written. Silent failure top-to-bottom. | `eeda5c2` | New `build_server_entry()` in `_common.py` resolves `skopus` to absolute path via `shutil.which` at install time. Raises `SkopusBinaryNotFoundError` with remediation guidance if not found — never silently falls back. 4 regression tests in `tests/test_mcp_installer_command_path.py` + 3 existing per-installer tests updated. Live-replayed: re-wired Cursor → Cursor saw 5 Skopus tools → `skopus_search_memory` probe returned 6 real corpus matches. End-to-end UI roundtrip confirmed. |

### Open follow-ups (from the smoke discovery, NOT blocking Phase 2 gate)

- **`scope: permanent` legacy values pass through search.** The wizard's seed templates use `scope: permanent` for founder_seed.md. The loader doesn't validate scope on read (only `record_drift` validates on write against `{user, project, team}`). Search returns these entries with the legacy scope value. Mild internal inconsistency — should normalize `permanent` → `user` (or extend `VALID_SCOPE` to include it) in a future migration sweep.
- **`skopus unlink --mcp <agent>` doesn't exist.** Installer modules expose `uninstall_*_mcp()` functions and they're tested, but no CLI surface. Today users hand-edit JSON to remove a wiring. Tracked for v0.8.x.
- **CC + Cline live MCP probes.** Cursor proved the spawn-path fix works in a real desktop environment. The same fix applies to CC and Cline by construction (same installer, same `build_server_entry()`). Probes still useful but lower priority — core MCP roundtrip is now proven on at least one desktop agent.

---

## Schema migration results (Carlos's manual step)

The migration script is shipped but the live migration against
`~/.skopus/memory/feedback/` has NOT yet been run. When run, record
results here.

| Date | --dry-run? | Entries scanned | Entries migrated | Skipped (bad frontmatter) |
|---|---|---|---|---|
| *not yet run* | — | — | — | — |

To run:
```bash
# Dry-run first (no writes)
python3 -m bench.scripts.migrate_memory_schema --dry-run

# Live migration (writes back to ~/.skopus/memory/feedback/*.md)
python3 -m bench.scripts.migrate_memory_schema
```

The 4 corpus entries that surfaced as `WARNING` lines in Task 29 testing
(`git-flow-main-develop.md`, `motion-graphics-quality.md`,
`2026-04-23-verify-plan-comments-against-wiring.md`,
`2026-05-04-ci-green-includes-codacy-threads.md`) have unquoted YAML
colons in their `description:` field; the migration script will SKIP
them. Carlos should hand-fix those before the live migration to capture
their v2 schema fields.

---

## What this branch does NOT ship (deferred to later phases)

- **Sub-harness format + Secretary** — Phase 4. Requires the MCP foundation
  this branch ships, then the harness abstraction on top.
- **Per-platform compilers** — Phase 5.
- **Autonomy daemon** — Phase 6.
- **Aider / Gemini / Codex / Continue MCP installers** — those agents
  either don't have MCP support yet or have unverified config formats.
  They remain at `EXPERIMENTAL` adapter tier from Phase 1.
- **Real-API CP measurement** — script shipped in Phase 1, still pending
  Carlos's API budget approval.
- **Cascade integration test** for shared-AGENTS.md scenarios — flagged
  during Task 13 review; tracked as follow-up before any release that
  documents `agents-md` as a recommended pairing with the AGENTS.md-writing
  experimental adapters.
- **Per-installer loggers** — flagged during Task 36 review as ergonomics
  improvement (currently all warnings emit under `_common`'s logger
  namespace). Tracked as v0.8.x or v0.9.x polish.
- **MCP installer registry consolidation** — flagged during Task 38
  review: 3 sources of truth for installer paths (`_link_mcp` dispatch,
  `_check_mcp_status` paths, installer module `_config_path` functions).
  Today they're byte-identical and tested; future refactor to single
  registry would prevent drift.
- **Live migration of `~/.skopus/memory/feedback/`** — script ships,
  Carlos runs manually.

---

## Test count growth (this branch)

| Snapshot | Total tests | Source |
|---|---|---|
| Phase 1 close (main @ `8a46b51`) | 197 pass, 1 skipped | baseline |
| Phase 2 close (this branch HEAD) | 272 pass, 1 skipped | +75 across 11 new test files (test_mcp_status_tool, test_mcp_cli, test_memory_index, test_mcp_search_memory_tool, test_mcp_query_vault_tool, test_mcp_charter_tool, test_mcp_drift_tool, test_mcp_installer_claude_code, test_mcp_installer_cline, test_mcp_installer_cursor, test_link_mcp_flag, test_doctor_mcp) |

---

## Next phase

**Phase 3 — Conservative learning loop in `/charter-evolve`.** Plan to be
written separately when Phase 2 closes.

Scope per the v1.0 proposal (`docs/proposals/skopus-v1/phasing.html`):
- Trigger-gap records — capture missed memory queries from session logs.
- Three confidence tiers: confirmed / probable / weak.
- `/charter-evolve` queue UI with diff view.
- Hook approval contract: preview, exact command, rollback.
- No auto-promotion from weak signals.
- Exit gate: trigger recall ≥ 90% on Tier-A agents (Claude Code, Cline)
  measured on CP suite; trigger precision ≥ 80%.

Phase 3 should also pick up the deferred Phase 0 real-API measurement on
its release-cut CI, since by then API budget is more likely to be
provisioned.

The migration script from this branch should also be RUN at the start
of Phase 3 — the learning loop assumes v2 §4.1 metadata is populated on
existing entries.
