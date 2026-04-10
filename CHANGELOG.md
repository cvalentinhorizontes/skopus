# Changelog

All notable changes to Skopus are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
