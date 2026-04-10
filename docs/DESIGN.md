# Skopus — Design Document

> Canonical design spec. Captures the decisions locked during the brainstorming session on 2026-04-10.
> Status: **v0.0.1 ships §§1-3 (charter/memory/vault scaffold, Claude Code adapter, wizard). v0.0.2 adds the graph lens and other platform adapters. v0.1.0 adds the benchmark harness.**

---

## 1. Vision

**The problem.** Every AI coding assistant loses four things at the end of a session: *how you work together*, *what happened before*, *what you decided*, and *what the code actually looks like*. The few persistent-memory systems that exist (claude-mem, Mem0, MemPalace, OpenAI memory) record conversations but don't encode the *how*. Structural knowledge about a codebase gets rediscovered via grep every session because nothing persists the map.

**The promise.** A unified four-lens context system any agent can load at session start:

1. **Charter** — how you work together (non-negotiables, anti-rationalization table, drift log)
2. **Memory** — what happened before (feedback, corrections, project state)
3. **Vault** — what you decided and learned (narrative wiki, Karpathy `/raw` pattern)
4. **Graph** — what the code looks like (via [graphify](https://github.com/safishamsi/graphify))

One install. Works with 6+ agents. Ships with a benchmark suite that proves it works.

**The test of every feature:** does the benchmark number move? If not, don't ship it. The charter's core non-negotiable — *evidence over assumption* — applied reflexively to the project itself.

---

## 2. Architecture

### Repo layout (monorepo, Python package)

```
skopus/
├── pyproject.toml
├── README.md
├── LICENSE                        # MIT
├── Makefile
├── install.sh                     # curl-pipe fallback for non-python users (v0.0.2)
├── skopus/                        # the package
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                     # typer entrypoint: init, link, doctor, bench, version
│   ├── wizard.py                  # interactive 10-question personalization
│   ├── renderer.py                # Jinja2 template rendering + file materialization
│   ├── evolve.py                  # /charter-evolve implementation (v0.0.3)
│   ├── templates/                 # Jinja2 markdown templates (bundled as package data)
│   │   ├── charter/               # CLAUDE.md, workflow_partnership.md, user_profile.md
│   │   ├── memory/                # MEMORY.md index + feedback/project templates
│   │   └── vault/                 # CLAUDE.md, wiki/index.md, log.md, .claude/commands/
│   └── adapters/                  # one file per platform
│       ├── base.py                # Adapter ABC
│       ├── claude_code.py         # v0.0.1 — the reference implementation
│       ├── cursor.py              # v0.0.2
│       ├── codex.py               # v0.0.2
│       ├── aider.py               # v0.0.2
│       ├── gemini.py              # v0.0.2
│       ├── copilot.py             # v0.0.2
│       └── opencode.py            # v0.0.2
├── bench/                         # benchmark harness (v0.1.0, first-class CI-gated)
│   ├── harness.py                 # unified runner
│   ├── longmemeval/
│   ├── locomo/
│   ├── msc/
│   ├── ruler/
│   └── correction_persistence/    # novel benchmark — see §4
├── tests/
└── docs/
    └── DESIGN.md                  # this file
```

### Install flow

```bash
pip install skopus                      # one install; graphify bundled in v0.0.2
skopus init                             # wizard: 10 questions, ~5 min, personalized output
cd my-project && skopus link            # wire vault ref into project CLAUDE.md/AGENTS.md
skopus doctor                           # health check all four lenses
skopus bench run all --baseline         # first benchmark run (v0.1.0)
```

### The two-repo split (user-invisible)

The user runs one command. Internally, `skopus init` materializes **two separate git repos** with different lifecycles:

| Location | Contents | Lifecycle |
|---|---|---|
| `~/.skopus/` | Charter + memory (personal, sensitive, small) | Rarely pushed; private backup |
| `~/Vault/` | Sources + wiki + outputs (potentially shareable, potentially large) | Often pushed to a private GitHub repo for backup |

Different privacy, different backup cadence, different remotes — but one install command. Templates are bundled as package data inside the wheel, so `pip install` is the single source of truth. No runtime clones, no network at init time, version skew impossible.

### The adapter abstraction

Every platform adapter implements a 5-method ABC (`skopus/adapters/base.py`):

| Method | What it does |
|---|---|
| `detect()` | Is this agent installed on the host? |
| `install(charter, vault)` | Wire the agent's context-loading mechanism (`CLAUDE.md` / `AGENTS.md` / `.cursor/rules/*.mdc` / `GEMINI.md` / `.codex/hooks.json`) |
| `uninstall()` | Reverse it cleanly, restore backed-up configs |
| `status()` | Is the wiring still intact? |
| `session_end_hook()` | How `/charter-evolve` is triggered at session end |

A new platform contribution = one Python file + one set of platform-specific templates. PRs adding adapters should be reviewable in ~50 lines.

### Session lifecycle

1. **Session start** → platform auto-loads `charter + memory + vault/index.md` via its native context mechanism
2. **During session** → agent queries vault via `/query`, reads memory on-demand, logs drift as it happens
3. **Session end** → `/charter-evolve` reviews transcript, appends validated-calls + corrections to charter/feedback, git-commits

---

## 3. Wizard, personalization, and files on disk

### The wizard — 10 questions, ~5 minutes

| # | Question | Purpose |
|---|---|---|
| 1 | What should I call you? | Address form throughout charter and memory files |
| 2 | Your primary role (solo dev / team lead / EM / researcher / founder / bug-hunter / other) | Seeds default non-negotiables and seed profile |
| 3 | Primary languages / stack | Seeds CI commands, lint rules, language-specific guardrails |
| 4 | Communication style (terse / detailed / mix) | Controls charter phrasing and expected response shape |
| 5 | Top 3 non-negotiables (with role-based suggestions) | Populates charter §2 directly |
| 6 | Time zone | Relative-date conversion, session timestamps |
| 7 | Which agents do you use? (multi-select) | Determines which adapters to wire |
| 8 | Vault location (default `~/Vault/`) | Overridable per user preference |
| 9 | Initial graphify scope (which codebases to map on first run) | v0.0.2 — graphify is mandatory, not optional |
| 10 | Seed profile (blank / solo-dev / team-lead / research / founder / bug-hunter) | Pre-populates feedback memory with typical entries |

### Files on disk after `skopus init`

```
~/.skopus/                       # charter + memory, git-tracked from day one
├── charter/
│   ├── CLAUDE.md                 # ~80-line high-level charter (rules, red flags, what not to do)
│   ├── workflow_partnership.md   # full charter: anti-rationalization table, drift log, 12 sections
│   └── user_profile.md           # Q1-4 output — name, role, style, stack
├── memory/
│   ├── MEMORY.md                 # index (auto-loaded)
│   ├── feedback/                 # seeded with 1-3 entries based on role
│   └── project/                  # empty, populated per-project via `skopus link`
├── adapters.lock                 # which platforms are wired + install paths
├── projects.json                 # list of linked projects for `skopus doctor`
└── .git/                         # git-tracked

~/Vault/                          # LLM Wiki, separate repo for portability
├── raw/ (articles/ transcripts/ papers/ code-snippets/ session-notes/)
├── wiki/ (concepts/ entities/ sources/ decisions/ comparisons/)
├── output/
├── CLAUDE.md                     # operating manual
├── wiki/index.md
├── log.md
├── .claude/commands/             # /ingest /compile /query /lint /wiki
└── .git/
```

### The "nothing is fixed" principle

Every file the wizard generates starts with a banner:

> 🌱 *Seeded by skopus init on YYYY-MM-DD. Everything here is editable. `/charter-evolve` will grow it over time based on your actual sessions.*

Wizard output is a **starting point**, not a commitment. The `/charter-evolve` loop then reviews each session's transcript and appends validated judgment calls + corrections automatically — the mechanism that makes this compound instead of going stale. First-week experience: wizard gets you to 30% context, `/charter-evolve` takes you to 80% over 5-10 sessions of normal work.

---

## 4. Benchmark strategy (the pillar)

Benchmarks are first-class, CI-gated, published at launch. The harness runs any agent with or without skopus, in any ablation config, to prove the additive contribution of each lens.

### Public benchmarks at launch (v0.1.0)

| Benchmark | What it tests | Why skopus needs it |
|---|---|---|
| **LongMemEval** (Wu et al. 2024) | 6 abilities: single-session, multi-session, knowledge update, temporal reasoning, explicit/implicit refs | Gold-standard memory eval; MemPalace scored 96.6% — baseline to beat |
| **LoCoMo** (Google 2024) | Long conversations, 9 topics, 35+ turns × multi-session | Retrieval + reasoning at realistic dialogue length |
| **MSC** (Facebook 2021) | Persona consistency across 5 sessions | Directly tests charter + user_profile layer |
| **RULER** (NVIDIA 2024) | Long-context retrieval, 13 tasks, up to 128K ctx | Tests graph + vault's ability to surface the right slice |

### The novel benchmark — Skopus Correction-Persistence (skopus-CP)

**No public benchmark measures this directly.** The thing users actually care about: *"stop making the same mistake twice."*

**The test:** agent attempts a task → makes a specific mistake → user corrects it → **new session opens** → agent gets a *similar but not identical* task → does the correction persist and generalize?

**Dataset:** 100+ scenarios across code, prose, reasoning, and tool-use. Each entry has:
- `initial_task` — the prompt
- `expected_mistake` — what vanilla agents typically get wrong
- `correction` — what the user says after the mistake
- `followup_task` — a similar task N sessions later
- `success_criterion` — what "remembered the correction" looks like

**Four metrics:**
- **Persistence rate** — % of corrections still applied in the next session
- **Generalization rate** — % applied to similar-but-different tasks
- **Decay rate** — % still applied after 5 / 10 / 20 sessions (staleness curve)
- **Cross-agent transfer** — correction made in Cursor → applied in Claude Code?

This is directly what skopus's charter + feedback memory + drift log is designed to do. **We built the benchmark we want to beat.**

### Ablation — proving each lens earns its place

```bash
skopus bench run all --ablation --agent claude-code
```

Runs every benchmark across five lens configurations:

1. **Vanilla agent** — no skopus
2. **+ Charter** only
3. **+ Charter + Memory**
4. **+ Charter + Memory + Vault**
5. **Full skopus** (+ Graph)

The delta between configs shows the *additive contribution of each lens*. If adding the vault doesn't move a metric on any benchmark, that's a signal — either the vault isn't earning its place, or we're measuring the wrong thing. Either way, we find out.

### CI strategy

- **PR smoke test** (~15 min, ~$10): Correction-Persistence only, 1 agent, 2 configs. Auto-posted as PR comment.
- **Release sweep** (weekly + pre-release): Full ablation, all agents, all benchmarks. Results published at `skopus.dev/benchmarks`.
- **Launch baseline**: 3 agents × 5 benchmarks × 5 configs = 75 data points at v0.1.0.

### Honest caveats

1. **The Correction-Persistence dataset doesn't exist yet.** Building 100 scenarios with ground truth is ~2-3 weeks of work. Worth it as the project's signature contribution.
2. **CI cost is real** — $500/week at full cadence. Mitigation: self-hosted runners, sponsorship from model providers, or cap to monthly sweeps at launch.
3. **Benchmark harness is agent-specific wiring** — each agent needs a thin driver (load skopus config, issue prompts, capture responses, score outputs). Reusable infrastructure, parallels the adapter abstraction.

---

## 5. `/charter-evolve` loop — *deferred to v0.0.3*

The mechanism that makes the charter compound without manual intervention. Design sketch:

- Slash command invoked at session end (or via platform session-end hook)
- Reviews conversation transcript for: validated judgment calls, corrections, non-obvious empirical facts, drift moments
- Proposes additions to charter sections (anti-rationalization, drift log) and feedback memory files
- Shows diff to user, waits for approval
- Appends, commits to `~/.skopus/.git`, notifies user

Full spec to be completed before v0.0.3 ships.

---

## 6. Contribution model, governance, launch — *deferred to v0.1.0*

- **Contribution model.** New adapters PR'd against `skopus/adapters/`. Each PR must pass the benchmark smoke test. New benchmarks against `bench/`. New seed profiles against `skopus/templates/seeds/`. Each PR triggers the CI smoke test (Correction-Persistence × full-skopus config) and posts the delta.
- **Governance.** BDFL (Carlos) for v0.x. Transition to maintainer team once there are 3+ active external contributors.
- **Launch plan.** v0.0.1 (alpha, today): charter + memory + vault scaffold, Claude Code adapter, wizard. v0.0.2 (next week): graph lens via graphify, 5 more adapters. v0.0.3 (week after): `/charter-evolve`. v0.1.0 (~1 month): full benchmark harness, 75 baseline data points, GitHub Pages results site, first public announcement.

Full spec to be completed before v0.1.0.

---

## Open questions (tracked, non-blocking)

1. **Seed profile content** — what exactly goes in `solo-dev`, `team-lead`, `research`, `founder`, `bug-hunter`? Needs 1 day of content design before v0.0.2.
2. **Correction-Persistence dataset build** — how to source scenarios without biasing toward skopus's strengths? Consider adversarial review from 3rd parties.
3. **CI infrastructure** — GitHub Actions limits vs self-hosted runners vs sponsor-funded cloud compute. Decide before v0.1.0.
4. **Upstream coordination with graphify maintainer** — reach out to Safi Shamsi before v0.0.2 ships to align on API stability.

---

**Design locked:** §§1-4. **Pending:** §§5-6.
**Design authored:** 2026-04-10.
**Next action:** ship v0.0.1.
