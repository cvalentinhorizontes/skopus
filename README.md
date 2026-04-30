<div align="center">

```
███████╗██╗  ██╗ ██████╗ ██████╗ ██╗   ██╗███████╗
██╔════╝██║ ██╔╝██╔═══██╗██╔══██╗██║   ██║██╔════╝
███████╗█████╔╝ ██║   ██║██████╔╝██║   ██║███████╗
╚════██║██╔═██╗ ██║   ██║██╔═══╝ ██║   ██║╚════██║
███████║██║  ██╗╚██████╔╝██║     ╚██████╔╝███████║
╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝      ╚═════╝ ╚══════╝
```

**Persistent four-lens context for AI coding assistants.**
Your agent. Across every session. Across every tool.

[![PyPI](https://img.shields.io/pypi/v/skopus?color=06b6d4&label=PyPI)](https://pypi.org/project/skopus/)
[![Python](https://img.shields.io/pypi/pyversions/skopus?color=0ea5e9)](https://pypi.org/project/skopus/)
[![CI](https://img.shields.io/github/actions/workflow/status/elbalen/skopus/test.yml?branch=main&label=CI)](https://github.com/elbalen/skopus/actions)
[![License](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-f59e0b)](https://github.com/elbalen/skopus)

*σκοπός — Greek for **watcher**, **purpose**, **target**. The root of `scope`, `telescope`, `episcopal`.*

</div>

---

## The cold start problem

Every AI coding assistant forgets you at the end of every session.

You explain your stack on Monday. You explain it again on Tuesday.
You correct a mistake on Wednesday. The same mistake comes back Thursday.
You make an architectural decision on Friday. You re-derive it next month.

Modern coding agents are smart. They are also amnesiacs.

## The fix

```bash
pipx install skopus    # recommended
skopus init            # nine questions, one minute
```

That's the whole onboarding. From the next session forward, your agent shows up already knowing:

| Lens | Question it answers | Where it lives |
|---|---|---|
| **Charter** | *How do we work?* | `~/.skopus/charter/` |
| **Memory** | *What did you correct me on?* | `~/.skopus/memory/feedback/` |
| **Vault** | *What have we already learned?* | `~/.skopus/vault/wiki/` |
| **Graph** | *What does this codebase look like?* | `graphify` (auto-installed) |

No re-teaching. No copy-pasting context. No drift.

---

## Works with every coding agent

Skopus's adapter layer detects the agents installed on your machine and wires the right surface for each:

| Agent | Context file | Slash commands surface |
|---|---|---|
| **Claude Code** | `.claude/CLAUDE.md` | `~/.claude/commands/*.md` |
| **Cursor** | `.cursor/rules/skopus.mdc` | `~/.cursor/skills/<name>/SKILL.md` |
| **Codex CLI** (OpenAI) | `AGENTS.md` | `$CODEX_HOME/skills/<name>/SKILL.md` |
| **Gemini CLI** (Google) | `GEMINI.md` | `~/.gemini/commands/<name>.toml` |
| **Aider** | `AGENTS.md` | (no surface — falls back to context file) |
| **GitHub Copilot CLI** | `AGENTS.md` | (no surface — falls back to context file) |

> **Why six adapters?** Because your team uses Cursor and your CI uses Aider and your weekend project uses Codex. Skopus stays the same; the adapter layer handles the rest.

---

## 30-second tour

```bash
$ pipx install skopus
$ skopus init
  Skopus — Four-Lens Context for AI Coding Assistants
  Welcome — let's set up your charter and memory.
  > What's your name? Carlos
  > Your role? founder
  > Time zone? America/Puerto_Rico
  > Communication style preference? terse
  ...
  ✓ Wrote 14 files
  ✓ /graphify skill installed
  ✓ Linked current project (skopus): wired Skopus into .claude/CLAUDE.md

$ # open Claude Code (or Cursor, or Codex...) — it already knows you
```

That's it. Now during a session:

```
> /compile                      ← captures session knowledge into the vault
> /query "what did we decide about authentication?"
> /charter-evolve               ← end-of-session reflection, updates memory
> /ingest https://...           ← saves an article into your knowledge base
> /graphify .                   ← builds a structural map of the codebase
```

When the session ends, your knowledge stays.

---

## The four-lens architecture

```mermaid
flowchart TB
    user([Carlos]) -->|terse correction| agent
    agent[AI Agent<br/>Claude / Cursor / Codex / ...] -->|reads at session start| ctx
    agent -->|writes at session end| ctx

    subgraph ctx [~/.skopus]
      direction LR
      charter[charter/<br/><i>how we work</i>]
      memory[memory/<br/><i>corrections + wins</i>]
      vault[vault/<br/><i>distilled knowledge</i>]
      graph[graph/<br/><i>via graphify</i>]
    end

    style user fill:#06b6d4,stroke:#0e7490,color:#fff
    style agent fill:#1f2937,stroke:#06b6d4,color:#fff
    style charter fill:#fef3c7,stroke:#d97706
    style memory fill:#dcfce7,stroke:#16a34a
    style vault fill:#e0e7ff,stroke:#4f46e5
    style graph fill:#fce7f3,stroke:#db2777
```

```
~/.skopus/
├── charter/                    The contract between you and the agent
│   ├── CLAUDE.md                 Partnership rules (high-level)
│   ├── workflow_partnership.md   Drift log + anti-rationalization table
│   └── user_profile.md           Your role, stack, working style
│
├── memory/                     The ledger of corrections that compound
│   ├── MEMORY.md                 Index — read every session
│   ├── feedback/                 One file per validated rule or correction
│   └── projects/<slug>/          Project-scoped memory (per `skopus link`)
│
├── vault/                      A Karpathy-style LLM wiki you own
│   ├── raw/                      Immutable source documents
│   ├── wiki/                     Distilled concepts, entities, decisions
│   ├── log.md                    Append-only operation log
│   └── output/                   Query results worth keeping
│
└── adapters.lock               Which agents are wired
```

Everything is markdown. Everything is git-versioned. Everything is yours — `~/.skopus/` is a directory you can read, edit, back up, sync across machines, and commit.

---

## How it compares

The "memory for AI" space is crowded. Here's the honest map:

| Tool | Approach | Pricing | What's different about Skopus |
|---|---|---|---|
| [Mem0](https://mem0.ai) / OpenMemory | MCP memory server, hosted + self-hosted | Free tier + paid SaaS | Skopus owns the **partnership rules**, not just memories. The charter encodes *how* you work, not just *what* you said. |
| [Letta](https://letta.ai) | Stateful agent runtime (#1 on Terminal-Bench) | Open-source + cloud | Letta builds agents. Skopus configures *your existing* agents — Cursor, Codex, Claude — without replacing them. |
| [Memorix](https://github.com/usememorix/memorix) | Local-first MCP memory layer | Free, OSS | Memorix stores. Skopus also **measures**: ships the [Correction-Persistence benchmark](#benchmarks) so you can verify your agent actually applies yesterday's corrections today. |
| [claude-mem](https://github.com/aydendoesexist/claude-mem) | Claude Code-only persistent memory | Free, OSS | Skopus is **multi-agent** by design — Cursor, Codex, Gemini all get the same context. |
| Manual `CLAUDE.md` files | One file per project, edit by hand | Free | Skopus **compounds** corrections automatically via `/charter-evolve` and version-controls everything in `~/.skopus/`. |

### The thesis in one sentence

> Modern coding agents already share a context layer (markdown files, slash commands, MCP). Skopus turns that layer into something that **persists, compounds, and works across every tool you use**.

---

## Daily workflow

Skopus is built around **slash commands inside the agent** + **CLI for file operations**.

### Inside the agent

| Command | When to use it |
|---|---|
| `/compile [topic]` | After meaningful work — distills the session into wiki pages. The single most important command. |
| `/query <question>` | Asks the vault a question. Pulls relevant pages, follows wikilinks, synthesizes an answer. |
| `/charter-evolve` | End of session — captures corrections, validated calls, and new rules. Compounds your charter. |
| `/ingest <path-or-url>` | Pull an article, paper, or doc into the vault. |
| `/graphify .` | Build / refresh the structural code-graph of the current repo. |
| `/lint` | Wiki health check — find orphans, broken links, stale pages. |
| `/wiki` | Vault status — recent entries, search, stats. |

### From the shell

```bash
skopus init              # one-time: wizard + scaffold + link current project
skopus link [path]       # wire a different project into Skopus
skopus unlink [path]     # remove the wiring
skopus update            # refresh per-agent surfaces + re-link tracked projects
skopus self-upgrade      # bump the package version (detects pipx / pip / editable)
skopus doctor            # health check
skopus version           # show version + how to upgrade for your install method
skopus audit             # memory health (index sync, scope tags)
skopus bench run cp      # run the Correction-Persistence benchmark
```

`skopus self-upgrade` is install-method-aware. It detects whether you installed via pipx, pip, or editable (`pip install -e .`) and runs the right upgrade command — never clobbers an editable tree, surfaces PEP-668 errors with a pipx hint.

---

## Benchmarks

Most "memory for agents" products are sold on vibes. Skopus ships a benchmark suite that measures whether it actually works.

### Correction-Persistence (novel)

> *If you correct your agent on Monday, will it apply that correction on Tuesday?*

That's the question. Skopus's hypothesis: the value of persistent context is not retrieval accuracy — it's **whether yesterday's corrections show up in today's behavior.** No standard benchmark measures this. So we built one.

```bash
skopus bench run cp --ablation       # 5 lens configurations × 120 scenarios
skopus bench run cp --driver mock    # deterministic, free, runs on every PR
```

### Adapted from the literature

- **LongMemEval** — long-form memory across many sessions
- **LoCoMo** — conversational memory consistency
- Plus mock drivers for fast deterministic CI

```bash
skopus bench list      # see all benchmarks + their status
```

The CP harness, scenarios, and ablation lens configurations live at `bench/correction_persistence/`. Read [docs/DESIGN.md](docs/DESIGN.md) §4 for the full design.

---

## Why "Skopus"?

From Greek **σκοπός** *(skopos)* — *watcher*, *target*, *purpose*. The root of *scope*, *telescope*, *episcopal*.

A skopos is the lookout on a mast. Skopus does the same job for your agent: it watches across sessions, keeps purpose in view, and makes sure nothing essential drifts out of sight.

---

## Roadmap

Status: **alpha (v0.5.0)**. Production-ready for individual developers; teams welcome but expect rough edges.

**Shipped:**

- ✅ Four-lens architecture (charter / memory / vault / graph)
- ✅ Six platform adapters (Claude Code, Cursor, Codex, Aider, Gemini CLI, Copilot CLI)
- ✅ Per-agent slash-command surface — Cursor `SKILL.md`, Codex `SKILL.md`, Gemini TOML
- ✅ `skopus self-upgrade` — install-method-aware
- ✅ Correction-Persistence benchmark + LongMemEval + LoCoMo adapters
- ✅ Pre-Phase-0 wiring migration so old installs auto-clean

**On the roadmap:**

- ⏳ Skopus MCP server — `skopus_search_memory`, `skopus_query_vault`, `skopus_record_drift`
- ⏳ Team-shared vault sync (multi-developer charter merging)
- ⏳ More benchmark adapters (MSC, RULER)
- ⏳ Web dashboard for vault browsing

See [CHANGELOG.md](CHANGELOG.md) for what landed when.

---

## Contributing

- **New platform adapter?** One Python file subclassing `MarkdownAdapter` is enough for ~80% of agents. See [`skopus/adapters/claude_code.py`](skopus/adapters/claude_code.py) as the reference. Tests in [`tests/test_adapter_commands.py`](tests/test_adapter_commands.py) show what to verify.
- **Benchmark scenario?** Run `/bench-contribute` inside Claude Code. It generates anonymized scenarios from your real corrections, ready to PR into `bench/correction_persistence/scenarios/`.
- **Found a bug?** [Open an issue](https://github.com/elbalen/skopus/issues) — please include `skopus version` output and which agent you're using.
- **Want to discuss?** [GitHub Discussions](https://github.com/elbalen/skopus/discussions) is the right place for design questions and proposals.

PRs are reviewed against the project's CI gates: `ruff check`, `ruff format --check`, `pytest` across Python 3.10 / 3.11 / 3.12, plus the `bench-smoke` job.

---

## License

[MIT](LICENSE) — © 2026 Carlos Valentin and contributors.

<div align="center">

If Skopus saves you from explaining your stack one more time, [⭐ star the repo](https://github.com/elbalen/skopus) — it's the only metric that matters.

</div>
