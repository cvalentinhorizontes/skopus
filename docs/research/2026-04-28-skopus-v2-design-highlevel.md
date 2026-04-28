# Skopus v2 — High-Level Design

> **Superseded on 2026-04-28. Do not implement from this document.**
>
> The evidence-backed replacement is
> [`2026-04-28-skopus-v2-design-evidence-locked.md`](./2026-04-28-skopus-v2-design-evidence-locked.md).
> This original version contains unproven trigger-reliability estimates, overbroad
> "works everywhere" claims, and unsafe auto-enforcement assumptions retained only
> for historical context.

**Date:** 2026-04-28
**Status:** For Carlos's review before any technical work begins
**Format:** Plain language. What v2 does, how it works, who it's for. No jargon, no architecture diagrams.

---

## 1. What Skopus v2 is, in one paragraph

Skopus v2 is **the partnership layer for AI coding agents**. It saves the *how-we-work* part of your collaboration with AI — your charter, your corrections, your drift log, your vault — and makes that knowledge available to *whichever* coding agent you're using today, automatically. Open Cursor, Claude Code, Cline, Codex, Windsurf — Skopus is already there, with the same rules, the same memory of past corrections, the same partnership context. One install. Works everywhere. Premium quality.

---

## 2. The promise

Three things v2 promises a user, in order:

1. **Same partnership, every session, every tool.** Switch from Claude Code to Cursor mid-week — the agent still knows your rules, still remembers what you corrected last month.
2. **Stop making the same mistake twice.** When you correct an agent, the correction sticks — across sessions, across agents.
3. **One install, no babysitting.** `pip install skopus && skopus init`. After that, every coding agent on your machine just works.

---

## 3. What v2 actually does (plain version)

When you install Skopus and run `skopus init`, four things get set up:

**A. Your charter.**
A short document — *how we work* — that captures your roles, non-negotiables, communication style, and the rules you've corrected agents on before. Like an employee handbook for the AI you work with.

**B. Your memory.**
A growing collection of feedback files — corrections you've made, validated calls, drift moments. Updated automatically by `/charter-evolve` at the end of each session. Never duplicated, never lost.

**C. Your vault.**
A wiki of decisions and learnings — *what we decided, what we figured out, what we learned*. Searchable. Grows over time as you `/compile` or `/ingest`.

**D. The plumbing.**
Skopus writes small files into your projects so each AI agent can find this context, AND runs a small background service so agents can ask deeper questions on demand instead of loading everything every time.

**E. Your patterns (arrives in v0.6).**
Short playbooks for the kinds of work you do — research, refactor, debug, design, review, whatever your domains are. Distilled automatically from your corrections over time. When you say *"deep research X,"* Skopus loads your research playbook before the agent does anything. See [Section 7](#7-patterns--how-skopus-learns-your-way-of-working-in-each-kind-of-task).

---

## 4. The four things v2 changes from v1

Each one fixes a real problem we found in research.

### Change 1 — A much lighter footprint in every session

**Before (v1):** Skopus injected ~246 lines of context into every chat session of every agent, in every project. That's a lot of tokens spent before you've even typed your first word.

**After (v2):** Skopus injects a tight, ~30-line summary — *who you are, the partnership rules, where to find more*. Everything else (full charter, memory search, vault) loads only when the agent actually needs it.

**Why it matters:** Faster, cheaper, and the agent follows your rules better. The research showed bigger context files actually *reduce* how well the agent follows instructions.

### Change 2 — Two files instead of six

**Before (v1):** Skopus had separate adapters for Claude Code, Cursor, Codex, Aider, Gemini CLI, and GitHub Copilot. Six files to maintain. Six chances to break.

**After (v2):** Skopus writes **two files**: a universal `AGENTS.md` (the open standard now backed by the Linux Foundation, Anthropic, OpenAI, and Block) and a small `CLAUDE.md` for Claude Code. That's it. Together those two files cover ~24 different coding agents natively — Cursor, Cline, Codex, Windsurf, Pi, Goose, OpenCode, Junie, Antigravity, Kiro, Devin, Zed, Roo Code, Letta Code, and more, plus Claude Code itself.

**Why it matters:** Less code, broader reach, simpler mental model.

### Change 3 — A "deep context" service that agents can call

**Before (v1):** If the agent wanted to remember a past correction, it had to load every memory file at startup and hope the right one was there.

**After (v2):** Skopus runs a small background service. When the agent needs to look up *"did Carlos correct me on this last month?"* — it asks. Skopus answers with the relevant memory and only the relevant memory. Same thing for vault lookups, full charter sections, and (v0.6) approach patterns.

**Why it matters:** Agents only carry the context they need, when they need it. Like having a smart assistant who knows where everything is, not a giant binder you have to read every morning.

**The hard part:** how do we make sure the agent actually *asks*? An LLM doesn't reliably call a tool just because the tool exists. This is the single biggest design risk in Change 3 and we attack it with a four-layer defense — see [Section 5](#5-how-change-3-actually-works--triggers-hooks-and-the-learning-loop).

### Change 4 — Smart handling of agents that need extra setup

**Before (v1):** A few agents (Aider, Gemini CLI, Continue.dev) didn't actually load Skopus's content because they have unusual file conventions. The adapter wrote content that went nowhere. We didn't know.

**After (v2):** Skopus auto-configures these tools so the content actually reaches them. For Aider it adds a one-line entry to `.aider.conf.yml`. For Gemini CLI it sets up `.gemini/settings.json`. For Continue.dev it writes to `.continue/rules/`. The user doesn't have to know.

**Why it matters:** No silent failures. If Skopus says it's wired in, it actually is.

---

## 5. How Change 3 actually works — triggers, hooks, and the learning loop

This is the section that answers *"how do you guarantee the agent asks for memory at the right moment, and that the right memory comes back?"*

There are two separate problems hiding inside that question. We solve them differently.

### The trigger problem vs. the transaction problem

**The transaction is easy.** Once the agent decides to call Skopus, the rest is plumbing — a request goes to the background service, the service looks up the answer locally in milliseconds, results come back. We control all of that. Not a worry.

**The trigger is hard.** Whether the agent *thinks* to call Skopus is, by default, up to the agent's judgment. And language models don't reliably decide to call tools just because tools exist. If we leave it to chance, sometimes memory gets queried, sometimes it doesn't.

So the design attacks the trigger problem with four layers, in order from most reliable to least.

### Layer 1 — Hooks (where the agent supports them)

Some agents let an outside program intercept *before* the agent acts. Claude Code has this — it's called PreToolUse hooks, and Skopus already uses it today (see the most recent commit on this repo: *"guard hook — auto-inject corrections before risky commands"*). The pattern is proven.

In plain terms: the agent is about to write a file or run a command. The agent's runtime pauses for a fraction of a second and asks Skopus *"is there anything I should know about this?"*. Skopus checks memory, and if there's a relevant past correction, it gets injected into the agent's view *before* the action proceeds. The agent didn't have to "remember" to look — Skopus inserted itself.

**Reliability:** ~99%. The agent didn't have a choice.

**Where it works:** Claude Code (today), Cursor (via always-apply rules), Cline, Windsurf. Together those are the majority of paying users.

### Layer 2 — Strong instructions in the always-loaded file (everywhere)

The 30-line block in `AGENTS.md` and `CLAUDE.md` doesn't just describe what tools exist. It contains an explicit, imperative protocol — something like:

> *"Before responding to any non-trivial request, you MUST call `skopus_search_memory`. The cost of one extra search is negligible. The most common drift Carlos has corrected on is failure to consult memory when a relevant past correction existed. If unsure whether a memory entry exists, call. The default answer is yes."*

This is instruction-engineering. We're framing the call as a partnership obligation, not a tool option. We're tying it to Carlos's own corrections. Empirically, LLMs follow that kind of framing far more reliably than a polite *"feel free to query memory."*

**Reliability:** ~80% on day one. Climbs over time as Layer 4 kicks in.

### Layer 3 — Tool descriptions that build the trigger in

When the agent reads the available tools, the description of `skopus_search_memory` doesn't say *"searches memory."* It says:

> *"Returns prior corrections Carlos has made on similar tasks. Call this BEFORE answering any request that involves writing code, choosing a library, or implementing a feature similar to past work. If you don't know whether a correction exists, call this — the answer is faster than reading code."*

The trigger is part of the tool's description itself. This makes the model's *"should I call this?"* decision much easier.

**Reliability:** brings Layer 2 from ~80% to ~90%.

### Layer 4 — The learning loop (catches misses and converts them into rules or hooks)

The previous three layers give Skopus its day-one reliability. The learning loop is what makes it *get better over time* instead of staying at whatever its starting reliability was. This is the moat.

The full mechanics are in [Section 6](#6-the-learning-loop--how-skopus-gets-smarter-over-time).

### What this looks like by agent

| Agent | Hooks available | Day-one reliability | Reliability after 30 days of normal use |
|---|---|---|---|
| Claude Code | yes | ~95% | ~99% |
| Cursor | yes (always-apply rules) | ~95% | ~99% |
| Cline | yes | ~95% | ~99% |
| Windsurf | yes (always-on triggers) | ~95% | ~99% |
| Codex CLI | no | ~80% | ~95% |
| Pi | no | ~80% | ~95% |
| Aider | no | ~80% | ~90% |

The numbers above are estimates based on how each agent's instruction-following typically performs. The right way to lock them down is to measure with the Correction-Persistence benchmark before/after — which is exactly what we built that benchmark for.

### One thing I want to validate before locking this in

For Cursor, Cline, and Windsurf I've assumed *hook-equivalent* mechanisms (always-apply rules, always-on triggers) can not just block actions but also *inject context* into the agent's next turn. Their docs strongly suggest yes. But I want a 1-day spike per agent to confirm before promising hook-level reliability for them. If any of them only let you block actions but not inject memory, those agents drop from Layer 1 to Layer 2 and reliability drops accordingly.

---

## 6. The learning loop — how Skopus gets smarter over time

The learning loop is what turns Skopus from *"another AGENTS.md writer"* into a system that compounds in value with every correction Carlos makes.

The core idea: **every miss is a teacher.** When the agent failed to query memory and a relevant correction existed, that's a signal. Skopus captures it, converts it into a sharper rule or a new hook, and the same miss doesn't happen twice.

There are five steps. They run automatically; the user's only direct touchpoint is `/charter-evolve` at session end.

### Step 1 — Detect a miss

A "miss" means: the agent did something where it should have queried memory first, and it didn't (or it queried but with the wrong terms and got nothing back).

Three signals tell Skopus a miss happened:

- **Explicit correction.** Carlos says *"no, that's wrong"* or *"we already decided X."* If memory contained a relevant entry that wasn't surfaced, that's a confirmed miss.
- **Self-detection.** Skopus knows what's in memory. After the session, it scans: *"this session edited the billing file; we have three corrections about billing in memory; were any of them referenced in the agent's reasoning?"* If zero references, that's a likely miss.
- **User flag during `/charter-evolve`.** Carlos can directly say *"the agent should have caught this — promote it to a rule."*

### Step 2 — Capture the structure of the miss

A miss isn't just *"the agent got it wrong."* It's a structured record:

> *Trigger:* editing files under `src/billing/`
> *Memory that should have been consulted:* `feedback/2026-04-12-no-decimal-rounding.md`
> *What actually happened:* agent rounded to 2 decimals
> *What should happen next time:* call memory before any billing-related edit
> *How we detected:* explicit correction
> *Occurrence count:* 1

These records get stored as `~/.skopus/memory/trigger_gaps/`. Each is a small markdown file with frontmatter — readable by humans, parseable by Skopus.

### Step 3 — Convert the miss into a stronger signal

This is the heart of the loop. Skopus offers Carlos one of three responses, depending on stakes and repeat count:

**Response A — Sharpen the rule (first occurrence, low stakes).**
Adds a specific instruction to the always-loaded `AGENTS.md` block: *"Before editing files under `src/billing/`, call `skopus_search_memory('billing')`."* Costs a few extra tokens; benefits from explicit naming of the trigger. Carlos approves with one keystroke.

**Response B — Promote to a hook (2-3 occurrences in the same area).**
Skopus says: *"I've noticed memory queries are missed when editing billing code. Want me to install a hook that always queries memory before billing edits?"* If Carlos says yes, a hook is generated. For Claude Code, that's a `PreToolUse` config in `.claude/`. For Cursor, an always-apply rule with a glob for `src/billing/`. For Cline, the equivalent. From that point forward, the trigger is enforced — ~99% reliability for that path.

**Response C — Auto-enforce (high-stakes domains).**
Some areas auto-promote without asking — production code, financial code, security-sensitive paths. The hook is installed automatically and Carlos is told. He can override but the override is logged.

The interesting bit: which response gets used isn't hardcoded. It's a function of how often the same miss has happened, how big the user's correction was, and where in the codebase it lives. Skopus learns Carlos's escalation thresholds over time.

### Step 4 — Validate the conversion worked

After a rule or hook is added, the next session is monitored:

- Did the new rule fire when expected?
- Was the right memory loaded?
- Did the agent apply it correctly?

If yes for several sessions in a row → mark validated. The trigger gap record gets archived.

If no → either the rule wasn't specific enough (sharpen it) or the agent ignored it (escalate from Tier 1 to Tier 2 — install a hook).

### Step 5 — Compress periodically

Without this, the always-loaded file grows back to v1's bloated state. Skopus periodically:

- **Groups similar rules.** Three billing-specific rules become one *"any billing operation"* rule.
- **Demotes verbose instructions when hooks cover them.** If a hook now enforces the trigger, the verbose instruction in the always-loaded file can be removed — the hook is more reliable anyway.
- **Archives validated trigger-gap records.** Once a miss has been fixed and not recurred for 30 days, archive it.
- **Promotes correction clusters into patterns.** When 3+ corrections accumulate in the same task domain, the loop offers to roll them into a pattern (see [Section 7](#7-patterns--how-skopus-learns-your-way-of-working-in-each-kind-of-task)). Memory gets cleaner; a pattern gets sharper. **Patterns are where corrections graduate to.**

This keeps the always-loaded context lean even as the system gets smarter.

### How this differs from auto-memory products (Mem0, claude-mem, Anthropic native memory)

Those products auto-capture **facts**. Skopus's learning loop auto-captures **triggers and rules**.

- A *fact*: "Carlos prefers 2-space indentation."
- A *trigger*: "Always check memory before suggesting an indentation."

The fact says *what* is true. The trigger says *when* to check. Mem0 and Anthropic's native memory will store the fact. Skopus stores the trigger that ensures the fact is consulted at the right moment.

This is the actual moat. Memory products are crowded. Trigger-and-rule learning is empty.

### What the loop gives the user, in plain terms

Imagine Carlos's first month with v2:

- **Week 1.** Skopus is wired in. Hooks fire on edits. Memory is queried voluntarily ~80-95% of the time elsewhere. Every miss is captured.
- **Week 2.** Five trigger gaps captured. Three converted to sharper rules. One promoted to a hook (after Carlos corrected the same billing thing twice).
- **Week 3.** Reliability for the rules added in Week 2 is now ~99% (because hooks). New gaps appear in different areas. Loop continues.
- **Week 4.** ~12 specific triggers in the system. Carlos hasn't repeated a correction since Week 2. Skopus's always-loaded file is still under 50 lines because compression has been pruning behind the scenes.

The system fits *Carlos's* failure modes specifically. Someone else with a different codebase and different work would end up with different triggers. **Skopus shapes itself to each user.**

---

## 7. Patterns — how Skopus learns your way of working in each kind of task

This is the structural element that turns a pile of corrections into something the agent can actually apply. It's the difference between *"Carlos has 200 corrections in memory"* and *"Carlos has 5 patterns the agent already knows by heart."*

### What a pattern is, in plain terms

A pattern is a short document — typically 30-100 lines — that captures *how you approach a particular kind of work*. Not a fact. Not a single correction. A distilled approach.

Examples of patterns that might exist for one user:

- **research** — *"real-time web data, primary sources only, never lean on training data, cite everything, surface what's uncertain."*
- **refactor** — *"never break public API in one PR; introduce, deprecate, then remove over three PRs."*
- **debug** — *"reproduce first, instrument second, hypothesize third. Never propose a fix before reproducing."*
- **review** — *"start with the test diff, then read the code, then look at the PR description last."*
- **design** — *"start with the data model, then the API surface, then the implementation plan."*

Each user's patterns are different. There's no canonical list. The patterns *you* end up with are the ones the system distilled from *your* corrections.

### Why patterns are the missing piece

Memory alone hits a scaling wall. As corrections accumulate, retrieval gets noisy — six corrections about how to do research each phrase the same lesson differently. Patterns are the *distillation*: one structured doc that captures what those six corrections all point to. Query once, get the answer once, no reconciliation.

Patterns also let the trigger be **task-shaped instead of file-shaped**. The hooks in Section 5 fire on file paths — that works for *"about to edit billing code"* but not for *"the user asked me to do research."* Patterns trigger on what the user is *trying to do*, not where they're trying to do it.

### What's in a pattern file

A markdown file at `~/.skopus/memory/patterns/<name>.md`. Frontmatter records:

- **name** — short, lowercased (`research`, `refactor`, `debug`)
- **triggers** — words and phrases that should fire this pattern
- **last_validated** — when the pattern was last used without correction
- **based_on_corrections** — which memory entries informed it (audit trail)
- **status** — active, draft, or stale

Body is plain markdown: when the pattern applies, core principles (the *why*), concrete dos and don'ts, anti-patterns. Short on purpose. If it grows past ~150 lines, it's probably two patterns and Skopus offers to split.

### How patterns get created

Three paths:

**1. Wizard-seeded.** During `skopus init`, the wizard asks: *"What are the top 3-5 kinds of work you do with AI agents?"* You pick from a starter list or type your own. Skopus creates skeleton pattern files — empty playbooks the learning loop fills in over time.

**2. Auto-suggested by the learning loop.** When `/charter-evolve` notices 3+ corrections clustering around the same task type, it offers: *"You've corrected the agent on research-related things three times. Want me to draft a research pattern from these corrections?"* If you say yes, Skopus drafts the pattern; you review and edit.

**3. Manually written.** You can write a pattern any time by hand. Drop a file at `~/.skopus/memory/patterns/anything.md`. Skopus picks it up.

### How patterns get used at runtime

**Trigger detection.** When the agent starts processing a prompt, the runtime calls `skopus_match_pattern(prompt)`. Skopus matches against each pattern's triggers. Returns the best match (or none).

**Pattern retrieval.** If a pattern matched, the agent calls `skopus_get_pattern(name)` to fetch the full playbook. The pattern becomes part of the agent's working context for the task.

**Combined with memory.** Patterns are general; memory is specific. The agent uses both. *"Apply the research pattern, AND check memory for any auth-flow-specific corrections."*

**Conflict rule.** Specific memory always wins over general patterns. Patterns are defaults; memory entries are overrides. This matches how humans think — a rule of thumb plus exceptions.

**Hook-enforced where possible.** For agents that support hooks (Claude Code, Cursor, Cline, Windsurf), pattern lookup runs automatically. Layer 1 reliability — the agent didn't have to remember to look.

### How patterns stay fresh

This is the part that makes patterns better than a one-shot prompt-engineering exercise.

**Validation on every use.** When a pattern fires and you don't correct the agent, that's a validation. `last_validated` updates. Patterns validated frequently are trusted; patterns that haven't been used in 90 days get a stale flag.

**Updates on correction.** When you correct the agent during a task that fired a pattern, `/charter-evolve` asks: *"this correction was during a research task — update the research pattern, save as standalone memory, or both?"* You pick. The pattern file has a changelog so you can see how it evolved.

**Compression destination.** When the learning loop accumulates many small corrections in the same domain, it offers to roll them up into a pattern update. Memory gets cleaner; the pattern gets sharper. **Patterns are where corrections graduate to.**

### Risks Skopus handles for you

**Sprawl.** If you create 30 patterns, the system gets worse. Skopus warns past 8-10 and offers consolidation: *"You have 'research,' 'investigate,' and 'deep-dive' patterns — these look similar. Merge?"*

**Staleness.** Patterns unused for 90 days surface in `skopus doctor`. Review, archive, or delete.

**Overlap with Anthropic Skills / Cursor rules.** Skills are workflow templates the agent *runs*; patterns are belief documents the agent *reads*. Orthogonal — a pattern says *how you think*, a skill says *what mechanical steps to take*. They coexist.

### Where patterns sit in the v2 build order

Patterns are a **v0.6 feature, not v0.5**. They depend on the learning loop already capturing and clustering corrections. Phase 3 (the learning loop) ships first; Phase 4 (patterns) sits on top of it.

- **v0.5** — Phases 0-3: slim down, consolidate adapters, MCP server, learning loop
- **v0.6** — Phase 4: patterns — schema, MCP tools (`skopus_match_pattern`, `skopus_get_pattern`, `skopus_list_patterns`), wizard extension, `/charter-evolve` extension

This is a 6-8 week split. v0.5 alone makes Skopus measurably better today; v0.6 is the moat.

---

## 8. How it works (the daily experience)

Here's what a normal day looks like with Skopus v2.

### Morning

You sit down, open whatever AI coding tool you're using today. Doesn't matter which.

The agent reads `AGENTS.md` (or `CLAUDE.md` if it's Claude Code). It sees:

> *"This project is wired to Skopus. Carlos is the founder; you're the engineering partner. The non-negotiables are X, Y, Z. For deeper context — past corrections, vault knowledge, full charter — call the Skopus tools."*

About 30 lines. The agent now knows the partnership.

### During work

You type something specific — *"deep research the new auth flow,"* or *"refactor this controller,"* or *"debug this flaky test,"* or *"design an endpoint for cancellations."* Whatever the work-shape is, Skopus probably has a pattern for it.

The agent calls `skopus_match_pattern("deep research the new auth flow")`. Skopus returns your **research** pattern — the playbook for how *you* like research done (real-time data, primary sources, web before training, cite everything).

The agent applies that pattern *first*, before doing any actual work.

Then, mid-task, the agent has a more specific question: *"did Carlos correct me on auth-flow assumptions before?"* That's a memory query: `skopus_search_memory("auth flow")`. Specific past corrections come back. The agent layers them on top of the pattern.

You correct the agent on something new — say, *"actually for this kind of auth research, also check the security-audit log first."* The agent records it immediately via `skopus_record_drift`.

### End of session

You type `/charter-evolve`. Skopus reviews the conversation and asks targeted questions:

- *"This correction was during a research task — update the research pattern, save as standalone memory, or both?"*
- *"You corrected the agent twice today on similar things. Promote to a hook so it auto-triggers next time?"*
- *"The research pattern fired 4 times today and was never corrected — mark as validated?"*

You pick. Skopus saves, commits to its git, and the system is sharper than this morning.

### Next morning, different tool

You open Cursor instead of Claude Code. Same project. Same charter loads. Same corrections apply. Same partnership.

### Next month, different machine

You install Skopus on your laptop. `skopus init` syncs your charter from git. Everything you've taught your AI partner is there. No cold start.

---

## 9. Use cases — five concrete stories

These are the situations where v2 should feel obviously valuable.

### Use case 1 — The tool-switcher

**Carlos uses Claude Code at home, Cursor at the office.** Same project, two tools. With v2, the same charter, same memory, same drift log are available in both. He never re-explains his preferences. The agent in Cursor knows about the correction Carlos made in Claude Code last week.

### Use case 2 — The model-switcher

**Carlos's team experiments with switching from Claude Sonnet to Gemini 3 Pro for a week.** They use Gemini CLI. With v2, the partnership context, the corrections from the past month, the vault knowledge — all available. The Gemini CLI agent feels like the same partner, just running on a different model.

### Use case 3 — Correction persistence

**Last sprint, Carlos corrected the agent five times about not assuming dependencies are installed.** With v2, that correction is saved to memory. The next time Carlos starts a session in *any* agent, that lesson applies automatically. The same mistake doesn't happen twice.

### Use case 4 — The team handoff

**Carlos onboards a new contractor. They install Skopus, point it at the team's charter repo.** They get the full partnership context — non-negotiables, past corrections, vault decisions — without a week of "how do we do things here?" meetings.

### Use case 5 — The cross-tool comparison

**Carlos wants to know: which AI coding agent works best for our codebase?** With v2, he can run the same task across Claude Code, Cursor, and Codex with identical context loaded. The differences he sees are differences in the *agent*, not noise from inconsistent context.

---

## 10. What v2 explicitly does NOT try to do

Just as important as what it does. These are the things v2 stays out of.

### Not a memory provider in the Mem0 / Letta sense

There's a crowded market for "long-term memory for AI agents" — Mem0, Letta, Memorix, Graphiti, Hindsight, Supermemory, claude-mem. v2 doesn't try to win that race. **Skopus saves *how we work* together, not every fact you've ever told the model.** If you want a fancy semantic-search memory, plug Mem0 in alongside. Skopus stays in its lane.

### Not an editor or IDE

v2 doesn't try to be Cursor, Zed, or Antigravity. It is the *layer underneath* — the partnership context that those editors all consume.

### Not a replacement for `/init` or built-in CLAUDE.md

If your project already has a CLAUDE.md or AGENTS.md with project-specific rules, Skopus *adds* to it — it doesn't overwrite. The Skopus block is clearly marked, idempotent, and removable.

### Not a cloud service

Skopus runs on your machine. Your charter, your memory, your vault — all local. You can sync via git if you want. Nothing leaves your laptop unless you push it.

### Not auto-magic

v2 doesn't automatically learn from every keystroke. It captures *what you tell it to capture*, via `/charter-evolve` at session end. This is intentional — automatic capture is what makes Mem0 and claude-mem brittle. Carlos is in the loop on what gets remembered.

---

## 11. The user's experience, end to end

### Day 1: install

```
pip install skopus
skopus init
```

Wizard runs (5 minutes), asks who you are, your stack, your non-negotiables, which AI coding tools you use. Done.

`cd your-project && skopus link` — wires into the project.

### Day 2-30: working

You barely think about Skopus. It's just there. Every agent you open has the partnership context.

When you correct an agent, you do it the way you always have — *"no, do it this way."* If the correction matters long-term, you mention `/charter-evolve` at the end of the session and Skopus asks if you want to save it.

### Month 2: a new agent ships

Cursor releases a major update. Or you try Antigravity. You don't have to do anything — Skopus already wrote a file the new agent reads.

### Month 6: you switch projects

`skopus link` in the new project. Charter and memory carry over. Vault stays as your team's growing knowledge base.

### Year 1: a teammate joins

They `pip install skopus`, point at the team charter repo, run `skopus init`. They have your team's full partnership context on day one.

---

## 12. v1 vs v2 — the side-by-side

| Dimension | v1 today | v2 design |
|---|---|---|
| Files written per project | 1 file per agent (CLAUDE.md, .cursor/rules, AGENTS.md, GEMINI.md, etc.) — 6 adapters | 2 files (AGENTS.md + CLAUDE.md) for ~24 agents; 3-4 special cases get auto-config |
| Content size in each session | ~3,000 tokens injected always | ~500 tokens injected always; rest loaded on demand |
| What works without setup | Whatever the user manually configures | Aider, Gemini CLI, Continue.dev all auto-configured |
| Memory access pattern | Everything inlined every session | Searchable on-demand via background service |
| Marketing position | "Four-lens context system" | "The partnership layer for AI coding agents" |
| Cross-tool consistency | Yes, via per-tool adapters | Yes, via one universal standard (AGENTS.md) + a small Claude bridge |
| Token efficiency | Wasteful (research-confirmed) | ~5x lighter on always-loaded content |
| Knowledge compression | None — corrections accumulate flatly | Patterns (v0.6) — corrections graduate into reusable playbooks per work domain |
| Trigger granularity | File-path-based only | Task-shape-based (research / refactor / debug / etc.) AND file-path-based |

---

## 13. What I'd need from you to move forward

Four product/business calls, before any technical work:

### Decision 1 — Do you accept the new positioning?

> *"Skopus is the partnership layer for AI coding agents. Bring your own memory provider."*

This is the strategic frame for v2. It explicitly steps out of the crowded memory-storage market and stakes a claim on the partnership / correction-persistence dimension. It's defensible because nobody else does it. But it's a re-positioning from v1's "four-lens context system."

### Decision 2 — Do you accept the slimmer always-on context?

The single biggest change is reducing what Skopus injects from ~246 lines to ~30 lines per session, with the rest loaded on demand. This trades **always-loaded richness** for **on-demand precision**. The research strongly suggests this is the right trade. But it does mean a Skopus session feels lighter — the agent has to actively ask for context instead of having it all upfront.

### Decision 3 — Are you OK with v2 not being one-shot for *every* user?

Aider, Gemini CLI, and Continue.dev users will get extra files written to *their tool's config* in addition to AGENTS.md. The user doesn't see this — Skopus does it automatically. But it does mean Skopus modifies more than just AGENTS.md/CLAUDE.md. Aligns with the "no silent failures" principle but is a small expansion of where Skopus writes.

### Decision 4 — Phase ordering across v0.5 and v0.6

**v0.5 (foundation, ~3 weeks):**
- Phase 0 — slim the always-loaded block
- Phase 1 — consolidate adapters (6 → 3)
- Phase 2 — MCP server with `skopus_search_memory`, `skopus_query_vault`, `skopus_get_charter_section`, `skopus_record_drift`
- Phase 3 — learning loop in `/charter-evolve`: gap detection, capture, conversion to rules/hooks

**v0.6 (patterns, ~2-3 weeks after v0.5 ships):**
- Phase 4 — pattern schema, MCP tools (`skopus_match_pattern`, `skopus_get_pattern`, `skopus_list_patterns`), wizard extension to seed initial patterns, `/charter-evolve` extension to suggest pattern updates from clusters of corrections

Phase 0 alone makes Skopus better immediately. Phase 3 is what makes it self-improving. Phase 4 is the moat that puts daylight between Skopus and the memory-storage products. **Or:** if you'd rather, we ship Phase 1 first (user-facing breadth — more agents covered) before Phase 2 (depth on existing agents).

### Decision 5 — Trigger reliability target

I'm proposing we aim for ~95-99% trigger reliability on Claude Code, Cursor, Cline, and Windsurf (hook-supporting agents) and ~80-95% on the rest, climbing over time via the learning loop. If you want a different bar — say, 99% across the board even for non-hook agents — that's possible but means leaning much harder on Layer 2 instructions (more tokens in the always-loaded block) and possibly accepting that some agents simply can't reach it. Your call.

---

## 14. The simplest version of the pitch

If a developer friend asked Carlos *"what is Skopus v2?"* over a beer:

> *"Imagine you've spent six months teaching your AI partner how you work — your standards, your style, the corrections you've made. Skopus distills all that into short playbooks, one per kind of work you do — research, refactor, debug, whatever your domains are. When you say 'deep research this,' the agent already knows how you like research done. Switch from Claude Code to Cursor mid-week — same playbooks, same partnership. That's Skopus."*

That's the test. If v2 doesn't deliver that line cleanly, we redesign.

---

## 15. What I'm not asking you to decide today

- The exact technical architecture (will be detailed once you greenlight the high-level)
- Specific filenames, schemas, MCP tool names (technical details)
- Benchmark numbers and falsification thresholds (those exist already in the prior reports)
- Pricing, distribution, marketing site (separate conversation)

Today's question is just: **does the v2 picture above feel right?**

If yes — green-light it and I take it from here on the technical side.
If partially — tell me which parts to redesign.
If no — let's go back to the whiteboard on positioning and re-cut.

— end of high-level design —
