# Changelog

All notable changes to Skopus are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] — 2026-05-04

Two-phase release: v0.6.0 (Phase 0 lock-in) + v0.7.0 (verified adapter
bridges) + v0.8.0 (MCP server). Released as a single tag because the
intermediate phases were never published.

### Added

**Phase 0 — Slim adapter context (v0.6.0):**
- Hard caps on the slim Skopus context block: ≤ 35 lines, ≤ 2000 chars,
  ≤ 600 tokens — enforced by regression test so silent re-bloat trips CI.
- Determinism test on the block render so `MarkdownAdapter.install()`
  remains truly idempotent.

**Phase 1 — Verified adapter bridges (v0.7.0):**
- `AdapterTier` enum (`ADVERTISED` / `EXPERIMENTAL` / `UNVERIFIED`) with
  `UNVERIFIED` as fail-closed default. Marketing claims of support
  require the `ADVERTISED` tier.
- `AgentsMdAdapter` — universal AGENTS.md fallback writer (Linux
  Foundation cross-agent standard). Claude Code + Cursor + AGENTS.md are
  the three v0.7.0 advertised bridges.
- `skopus doctor --agent <name>` — per-adapter introspection table with
  tier, detect, project status.
- Pytest smoke harness (`tests/test_smoke_advertised_adapters.py`) for
  the file-side contract per advertised adapter.
- `bench/scripts/measure_phase0_cp_gate.py` — script for the deferred
  Phase 0 real-API CP measurement (runs the pre-slim baseline via git
  worktree against the Anthropic driver).

**Phase 2 — MCP server (v0.8.0):**
- Stdio MCP server (`skopus mcp serve`) using Anthropic's `mcp>=1.0`
  SDK (FastMCP). Exposes 5 tools: `skopus_status`,
  `skopus_search_memory`, `skopus_query_vault`,
  `skopus_get_charter_section`, `skopus_record_drift`.
- Schema-aware memory loader (`skopus/mcp/memory_index.py`) reads
  existing YAML frontmatter and defaults missing v2 §4.1 fields.
  Logs malformed entries at WARNING (4 entries in current corpus
  surface this way) instead of silently dropping them.
- Per-agent MCP installers (`skopus link --mcp claude-code|cline|cursor`)
  with corrupt-config backup safety: invalid existing JSON gets renamed
  to `<name>.bak-<unix-ts>` before the fresh write.
- `skopus doctor --agent <name>` gains a 4th row reporting MCP install
  status (installed / not_installed / config-unparseable / n/a).
- `bench/scripts/migrate_memory_schema.py` — idempotent one-shot for
  populating v2 §4.1 defaults across existing feedback frontmatter.
  Defaults intentionally weak (`source=imported`, `confidence=weak`,
  etc.) so they don't lie. Shipped but run manually by the user at
  `/charter-evolve` time.

### Changed

- README adapter table now includes a **Tier** column and the AGENTS.md
  universal-fallback row. Roadmap refreshed for v0.8.0.
- Wizard `AGENT_CHOICES` drops the stale `OpenCode` option (no
  registered adapter) and adds `AGENTS.md`.
- CLI `skopus link` gains `--mcp <agent>` with mutual-exclusivity
  against `--agent` to prevent silent flag-dropping.

### Dependencies

- Added `mcp>=1.0` (Anthropic's MCP SDK).

### Deferred

- Real-API Correction-Persistence gate measurement against the pre-slim
  baseline. Script ships in `bench/scripts/measure_phase0_cp_gate.py`
  but the run requires `ANTHROPIC_API_KEY` and ~$5-15 in API spend;
  awaits user authorization.
- Live migration of `~/.skopus/memory/feedback/` to the v2 §4.1 schema.
  Script shipped; user runs it manually after reviewing `--dry-run`
  output.
- Manual smoke verification per agent for the MCP server. Procedure
  shipped in `docs/proposals/skopus-v1/phase2-manual-smoke.md`; run
  before tagging v0.8.0.

### Tests

- 197 → 272 passing tests (+75 across Phase 2). Phase 0 added 2 lock-in
  tests; Phase 1 added 22 (tier + AGENTS.md adapter + smoke + doctor +
  agent registration); Phase 2 added 75 (MCP server + 5 tools +
  schema-aware loader + 3 installers + link --mcp + doctor MCP row).

## [0.5.1] — 2026-04-30

Docs + metadata patch release. No code changes; safe upgrade for everyone.

### Added
- **Custom SVG hero logo** at `docs/assets/skopus-logo.svg` — ANSI-Shadow
  SKOPUS letterforms rendered with a white body, olive-green gradient
  stroke (`#a8b86b → #6b8e23 → #4a6519`), and an olive outer glow.
  Centered in the README and width-bounded so it scales cleanly.

### Changed
- Initial commits of the v0.5.0 README landed on `main` without the
  intended hero asset; this release ships the full version with the
  SVG in place.

### Fixed
- **`pyproject.toml` repository URLs** updated from
  `cvalentinhorizontes/skopus` to `elbalen/skopus` (Homepage,
  Documentation, Issues, Repository). The v0.5.0 PyPI page links to the
  pre-transfer repo via redirect; v0.5.1 points at the canonical URL
  directly.

## [0.5.0] — 2026-04-30

Multi-agent slash-command surface, install-method-aware self-upgrade, and
two robustness fixes that came out of pre-existing user installations.

### Added
- **Per-agent slash-command surface.** Skopus now installs its slash
  commands (`/compile`, `/query`, `/ingest`, `/charter-evolve`,
  `/bench-contribute`, `/lint`, `/wiki`) into each detected agent's native
  surface, not just Claude Code:
    - **Claude Code** — `~/.claude/commands/<name>.md` (markdown)
    - **Cursor** — `~/.cursor/skills/<name>/SKILL.md` (Anthropic SKILL.md)
    - **Codex CLI** — `$CODEX_HOME/skills/<name>/SKILL.md` (Anthropic SKILL.md)
    - **Gemini CLI** — `~/.gemini/commands/<name>.toml` (Gemini TOML spec)
    - Aider and GitHub Copilot CLI have no user-defined command surface and
      are skipped silently.
- **`skopus self-upgrade`** — install-method-aware package upgrade.
  Detects editable / pipx / pip / unknown via `importlib.metadata` +
  `sys.executable`, runs the right command (or prints the right command
  for editable installs and exits cleanly), surfaces PEP-668 errors
  with a pipx-recommendation hint, and refreshes per-agent surfaces
  automatically after a successful upgrade.
- **`skopus version`** now prints the detected install method,
  installation location, and the upgrade command for that method.
- **`Adapter.install_commands(skopus_dir) -> list[Path]`** — new base
  method (no-op default) that adapters override to render canonical
  command templates into their agent's surface.
- **`skopus.commands` module** — single source of truth for command
  templates plus per-format renderers (markdown passthrough, SKILL.md,
  Gemini TOML).
- **`skopus.install_info` module** — pure-function install detection
  used by `self-upgrade` and `version`.

### Changed
- **`skopus update` no longer pip-upgrades.** The previous behavior ran
  `pip install --upgrade skopus` unconditionally, which broke on
  PEP-668-managed Pythons and would clobber editable installs. `update`
  now refreshes per-agent surfaces (slash-commands, graphify skill) and
  re-links every tracked project. Use `skopus self-upgrade` to change the
  package version.
- **Command templates moved** from `skopus/templates/vault/.claude/commands/*.md`
  to `skopus/templates/commands/*.md`. The old location was an artifact
  of when Claude Code was the only target; the new location is
  agent-neutral.

### Fixed
- **Phase-0 root `CLAUDE.md` orphans cleaned during `skopus link`.**
  Pre-Phase-0 wirings wrote into `<project>/CLAUDE.md`; the current
  adapter prefers `<project>/.claude/CLAUDE.md`. Re-linking now strips
  any leftover Skopus block from the legacy root location and removes
  the file when it had no other content.
- **Aspirational MCP-tool references removed from the adapter prompt.**
  The Phase-0 thin block told agents to "prefer MCP tools when available"
  for `skopus_search_memory`, `skopus_query_vault`, etc. — none of which
  ship yet. Pedantic agents read the line, found no tools, and reported
  Skopus as inactive even when fully wired. Add references back when the
  MCP server actually lands.
- **`update` no longer double-processes alias keys.** The `ADAPTERS`
  registry has alias keys (`copilot` + `copilot-cli`, `gemini` +
  `gemini-cli`); the per-agent loop now dedupes by class so each adapter
  runs exactly once.

### Testing
- **167 tests passing**, 1 skipped. New: `test_adapter_commands.py`
  covers every format converter, per-adapter target paths,
  `CODEX_HOME` env override, idempotency, and an integration test that
  runs `skopus link` end-to-end and asserts the command surface
  populates. `test_install_info.py` covers detection across all four
  install methods plus the editable-inside-pipx edge case and corrupt
  `direct_url.json`.

## [0.4.0] — 2026-04-28

Audit CLI, expanded benchmark coverage. _(Backfilled changelog entry — original release was committed but not published to PyPI.)_

### Added
- `skopus audit` CLI — health-check memory index sync and scope tags.
- 120 Correction-Persistence scenarios (up from prior set).
- LoCoMo and LongMemEval benchmark adapters.
- Guard hook for risky commands (`8744db7`) — auto-injects relevant
  feedback memory before destructive shell calls.
- Phase-0 thin context block (`77c2d94`) — adapter target moved from
  `<project>/CLAUDE.md` to `<project>/.claude/CLAUDE.md` (when present);
  block size reduced from ~3K tokens to ~500 tokens via pointer-only
  references to charter/memory/vault paths.

## [0.3.0] — 2026-04-13

Project-scoped memory and lifecycle commands.

### Added
- `skopus link <project>` creates `~/.skopus/memory/projects/<slug>/`
  with project-specific MEMORY, feedback, and context.
- CLAUDE.md injection includes a "Project Memory" section alongside
  global memory.
- `skopus uninstall` — removes wiring from every linked project,
  optionally deletes `~/.skopus/`, and uninstalls the pip package.
- `_write_feedback_file()` accepts a `project_slug` for
  project-scoped feedback writes.

## [0.2.0] — 2026-04-13

Simplification release: one directory, one command. (`29683e0`)

### Changed
- Vault merged into `~/.skopus/vault/` — one directory, one git repo.
- `skopus init` is one-shot: wizard + scaffold + auto-link current
  project + install graphify.
- 9-question wizard (down from 10 — vault location question removed).
- Charter content inlined into project CLAUDE.md (no `@` external
  references, zero permission prompts).
- `_graphify_cmd()` falls back to `python -m graphify` for pipx
  installs.

## [0.1.5] — 2026-04-13

Three real-user bugs from team installation testing. (`a0cc6a6`)

## [0.1.4] — 2026-04-13

`/charter-evolve` and `/bench-contribute` shipped as proper Claude Code
slash commands. (`72ea4bf`)

## [0.1.3] — 2026-04-12

Added `skopus update` command. (`7271b9e` — note: this command's pip-upgrade
behavior was later replaced in v0.5.0 by `skopus self-upgrade`.)

## [0.1.2] — 2026-04-11

Bug-fix bundle: graphify install made unconditional, full deps required,
README typo fixed. (`1846149`)

## [0.1.1] — 2026-04-10

Bug-fix release: `/graphify` was not actually invokable as a slash command
in Claude Code after `skopus init`.

### Fixed
- **`/graphify` slash command missing in Claude Code** — graphify has two
  install commands that do different things: `graphify install` (global,
  one-time, copies the skill file to `~/.claude/skills/graphify/SKILL.md`)
  and `graphify claude install` (per-project, writes CLAUDE.md block +
  PreToolUse hook). Skopus was only calling the per-project one, which
  meant `/graphify` was never a real slash command in Claude Code — only
  the hook and CLAUDE.md block were installed. Fix: skopus now calls
  `graphify install` (the global one-time step) before
  `graphify claude install` during `skopus init`.

### Added
- `skopus.graphify_bridge.ensure_graphify_skill_installed()` — idempotent
  helper that copies the graphify skill file if missing. Safe to call on
  every `skopus init`. Short-circuits when the skill file already exists.
- Two new tests covering the short-circuit and bool-return contract.

### Testing
- **97 tests passing**, 1 skipped (up from 95 in v0.1.0)

---

## [0.1.0] — 2026-04-10

The **benchmark release**. Skopus is now measurable, reproducible, and
compound-over-sessions with a full benchmark harness and a novel
Correction-Persistence dataset.

### Added
- `bench/` package with a unified benchmark harness
- **Correction-Persistence** benchmark (novel, skopus's research contribution):
  - 20 scenarios at v0.1.0-alpha (target: 100+ for v1.0)
  - Domains: code, prose, reasoning, tool-use
  - Runner, scorer, and dataset loader
- `LensConfig` — 5-config ablation framework:
  - `vanilla` (no skopus)
  - `charter` (+charter only)
  - `charter+memory` (+charter +feedback memory)
  - `charter+memory+vault` (+decisions and learnings)
  - `full` (+graph via graphify MCP)
- `LLMDriver` abstraction with two implementations:
  - `MockDriver` — deterministic responses for testing without API cost
  - `AnthropicDriver` — real Claude API calls (requires `ANTHROPIC_API_KEY`)
- `bench.harness` — `run_benchmark`, `run_all`, `run_ablation`, `save_report`,
  `format_markdown_report`
- `bench.context.build_system_prompt` — converts a `LensConfig` to a system
  prompt that encodes the corresponding amount of skopus context
- Stub wrappers for `LongMemEval`, `LoCoMo`, `MSC`, and `RULER` with
  integration paths documented (full runners planned for v0.1.1)
- New CLI subcommands under `skopus bench`:
  - `skopus bench list` — show available benchmarks
  - `skopus bench run <name> [--lens | --ablation] [--driver] [--limit]`
  - JSON results auto-saved to `bench/results/`
- GitHub Actions workflow `.github/workflows/test.yml` — lint + typecheck +
  full pytest on every push and PR
- CHANGELOG.md

### Changed
- Package layout: `bench/` now shipped as a sibling package inside the wheel
- `skopus init` auto-tracks the current directory as a linked project when
  an adapter is wired (previously only `skopus link` did)

### Testing
- **95 tests passing**, 1 skipped (up from 72 in v0.0.3)
- New test files:
  - `tests/test_bench_cp.py` — Correction-Persistence coverage
  - `tests/test_bench_harness.py` — harness dispatch, ablation, reports

---

## [0.0.3] — 2026-04-10

Multi-agent expansion — five new platform adapters plus the session-end
reflection loop.

### Added
- `MarkdownAdapter` DRY base class in `skopus.adapters.base`
- Five new platform adapters:
  - `CursorAdapter` — `.cursor/rules/skopus.mdc` with `alwaysApply: true`
  - `CodexAdapter` — `AGENTS.md`
  - `AiderAdapter` — `AGENTS.md` with custom detect for `.aider.conf.yml`
  - `GeminiCliAdapter` — `GEMINI.md`
  - `CopilotCliAdapter` — `AGENTS.md` with gh/copilot binary detection
- `skopus.evolve` — session-end reflection loop:
  - Interactive 3-question prompt (validated calls, drifts, rules)
  - Writes feedback files to `~/.skopus/memory/feedback/YYYY-MM-DD-<slug>.md`
  - Appends drifts to `workflow_partnership.md §7`, wins to `§8`
  - Auto-commits to `~/.skopus/.git`
  - Programmatic mode for testing: `run_evolve(entries=[...])`
- `skopus charter evolve` CLI command
- `SKOPUS_SECTION_START/END` markers and `build_skopus_block()` moved from
  `claude_code.py` to `base.py` (shared by all adapters)
- 22 new tests covering the multi-adapter pattern + evolve

### Changed
- `claude_code.py` refactored to import shared helpers from `base.py`
- Registry includes aliases (`gemini` → `gemini-cli`, `copilot` → `copilot-cli`)

---

## [0.0.2] — 2026-04-10

Graphify integration + non-destructive init + `.claude/CLAUDE.md` preference.

### Added
- **Graphify as a hard dependency** (`graphifyy>=0.1`) — the fourth lens
  ships with every install
- `skopus.graphify_bridge` — installation helpers:
  - `install_graphify_for_claude()` — runs `graphify claude install` +
    `graphify hook install` in a project
  - `_consolidate_graphify_block()` — moves graphify's block from root
    `CLAUDE.md` into `.claude/CLAUDE.md` (skopus convention)
  - `first_build_hint()` — reads scope hint for the first-build reminder
- `skopus init` auto-wires graphify into linked projects
- `skopus doctor` reports per-project graph status
- `--force` flag on `skopus init` for explicit overwrite
- `MaterializeReport` return type with `written` and `skipped` lists
- `claude_md_path()` helper preferring `.claude/CLAUDE.md` over root
- 11 new tests covering graphify bridge, path resolution, non-destructive merge

### Changed
- `renderer.materialize()` is non-destructive by default — existing files are
  preserved unless `force=True` is passed
- `claude_code.adapter.install()` now prefers `<project>/.claude/CLAUDE.md`
- `adapters.lock` now tracks the vault location explicitly

### Fixed
- `git commit` during init now uses inline identity flags so it works
  without a configured global git user/email
- Initial branch set to `main` (instead of `master`)
- `skopus init` + `skopus link` both update `projects.json` via
  the shared `_track_linked_project()` helper

---

## [0.0.1] — 2026-04-10

Initial bootstrap. The four-lens model as runnable code.

### Added
- Core Python package scaffold (`skopus/`, `pyproject.toml`, `Makefile`,
  `docs/DESIGN.md`, MIT `LICENSE`, `README.md`)
- Bundled Jinja2 markdown templates for charter, memory, and vault
- `skopus init` — interactive wizard (10 questions, `questionary`)
- `skopus link` / `skopus unlink` — per-project adapter wiring
- `skopus doctor` — health check
- `Adapter` ABC + `ClaudeCodeAdapter` reference implementation
- 24 initial tests

### Design decisions locked
- Four-lens mental model: charter, memory, vault, graph
- Monorepo with Python package + bench subpackage
- Non-destructive-by-default init
- Multi-agent from day one
- Benchmarks as first-class CI-gated deliverable
- Graphify integration as the structural knowledge layer
- Personalization via interactive wizard + `/charter-evolve` loop

See [`docs/DESIGN.md`](docs/DESIGN.md) for the full spec.
