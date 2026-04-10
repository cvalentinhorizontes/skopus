# Skopus

**Persistent four-lens context for AI coding assistants.** Charter, memory, vault, graph — one install, multi-agent, benchmark-driven.

> σκοπός *(skopos)* — Greek for *watcher*, *lookout*, *target*, *purpose*. The root of *scope*, *telescope*, *episcopal*. A system that gives agents durable scope across sessions.

---

## The problem

Every AI coding assistant — Claude Code, Cursor, Codex, Aider, Gemini CLI, Copilot CLI — loses context at the end of every session. You teach them your preferences, they forget. You correct them, they repeat the mistake next week. Your hard-won lessons evaporate into chat history.

The few persistent-memory systems that exist (claude-mem, Mem0, MemPalace, OpenAI memory) record conversations but don't encode *how you work* — the non-negotiables, the drift log, the anti-rationalization rules, the "do this, not that" patterns that actually make a collaboration compound. Meanwhile, structural knowledge about a codebase gets rediscovered every session via grep because nothing persists the map.

The result: agents that are smart per-message but stupid across sessions, and humans who spend half their time re-teaching.

## The promise

A unified **four-lens context system** any AI coding assistant can load at session start:

1. **Charter** — how you work together (non-negotiables, anti-rationalization table, drift log)
2. **Memory** — what happened before (feedback, corrections, project state)
3. **Vault** — what you decided and learned (narrative wiki, Karpathy `/raw` pattern)
4. **Graph** — what the code looks like (via [graphify](https://github.com/safishamsi/graphify))

One install. Works with 6+ agents. Ships with a benchmark suite that proves it works.

## Quickstart

```bash
pip install skopus
skopus init                    # interactive wizard (10 questions, ~5 min)
cd my-project && skopus link   # wire the current project to your charter + vault
skopus doctor                  # health check all four lenses
```

## What ships at v0.0.1 (alpha)

- ✅ **Charter templates** — high-level `CLAUDE.md`, full `workflow_partnership.md`, `user_profile.md`
- ✅ **Memory scaffold** — `MEMORY.md` index, feedback/project templates
- ✅ **Vault scaffold** — Karpathy `raw/wiki/output` layout with `/ingest`, `/compile`, `/query`, `/lint`, `/wiki` slash commands
- ✅ **Interactive wizard** — 10-question personalization flow
- ✅ **Claude Code adapter** — wires charter + vault refs into project `CLAUDE.md`
- 🚧 **Cursor / Codex / Aider / Gemini CLI / Copilot CLI adapters** — planned for v0.0.2
- 🚧 **Graphify integration** — planned for v0.0.2 (hard dependency in pyproject)
- 🚧 **`/charter-evolve` loop** — planned for v0.0.3
- 🚧 **Benchmark harness** — LongMemEval, LoCoMo, MSC, RULER, Correction-Persistence — planned for v0.1.0

See `docs/DESIGN.md` for the full spec and roadmap.

## The benchmark pillar

Skopus is designed to be **measurable**. The charter's core non-negotiable — *evidence over assumption* — is applied reflexively to the project itself. Every PR that touches the charter templates, adapter wiring, or wizard flow must move a benchmark number or explain why it's orthogonal.

At v0.1.0, the `skopus bench run` harness will run:

| Benchmark | What it tests |
|---|---|
| **LongMemEval** (Wu et al. 2024) | 6 memory abilities: single-session, multi-session, knowledge update, temporal reasoning, explicit/implicit refs |
| **LoCoMo** (Google 2024) | Long multi-session conversations |
| **MSC** (Facebook 2021) | Persona consistency across sessions |
| **RULER** (NVIDIA 2024) | Long-context retrieval, up to 128K ctx |
| **Skopus Correction-Persistence** (novel) | Does the agent apply yesterday's corrections to today's tasks? |

The ablation mode measures the additive contribution of each lens:

```bash
skopus bench run all --ablation --agent claude-code
# Runs vanilla / +charter / +memory / +vault / +graph — shows delta per lens
```

## Philosophy

Skopus combines three existing patterns into one coherent system:

- **Karpathy's LLM Knowledge Base** ([tweet](https://x.com/karpathy/status/2039805659525644595), [gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)) — the `raw/wiki/output` three-folder split with Ingest/Query/Lint operations, framed as a modern Vannevar Bush Memex.
- **The Partnership Charter** — evidence over assumption, premium quality, anti-rationalization tables, drift logs. A meta-workflow layer most agent setups don't have.
- **Graphify** ([safishamsi/graphify](https://github.com/safishamsi/graphify)) — automatic structural knowledge graph extraction from any codebase with honest audit trails (`EXTRACTED` / `INFERRED` / `AMBIGUOUS`).

Nothing here is new on its own. The contribution is the **coherent integration** plus the **benchmark commitment** to prove it works.

## Contributing

New platform adapters welcome. Each adapter is a single Python file implementing a 5-method ABC (`detect`, `install`, `uninstall`, `status`, `session_end_hook`). See `skopus/adapters/base.py` and `skopus/adapters/claude_code.py` for the reference implementation.

Benchmark dataset contributions welcome — especially for the Correction-Persistence benchmark, which ships with 100+ scenarios in `bench/correction_persistence/dataset.json`.

## License

MIT — see [LICENSE](LICENSE).
