# Skopus v2 - Evidence-Locked Design

**Date:** 2026-04-28
**Status:** Authoritative replacement for `2026-04-28-skopus-v2-design-highlevel.md`
**Decision:** Phase 0 can proceed. Every later phase is gated by proof.

This document replaces optimistic claims with an implementable design whose value is measured by benchmarks, adapter smoke tests, hook logs, and `skopus doctor`.

---

## 1. Corrected Direction

Skopus v2 is still the right product direction, but the original high-level design was too confident about cross-agent trigger reliability.

The corrected product is:

> Skopus is a portable partnership-context layer for coding agents. It keeps the user's charter, corrections, and decision memory in one canonical place, then exposes that context through each agent's strongest verified integration path.

That means:

- Do not promise "works everywhere" until each agent passes a smoke test.
- Do not promise "the same mistake never happens twice." Promise measurable reduction in repeated corrections.
- Do not treat static rules, MCP tools, and hooks as equivalent. They have different reliability and failure modes.
- Do not install enforcement hooks automatically. Hooks need explicit approval, a diff preview, and rollback.
- Do not ship pattern learning until retrieval and trigger capture are proven.

The design now ships in verified tiers, not as a blanket claim.

---

## 2. Evidence Base

| Area | Evidence | Design implication |
|---|---|---|
| AGENTS.md | `agents.md` says AGENTS.md is standard Markdown, root/nested AGENTS.md files are read by many agents, closest file wins, and user prompts override file instructions. OpenAI says AGENTS.md is under Agentic AI Foundation stewardship and broadly adopted. | AGENTS.md is the right canonical static context file, but it is not a control plane. It gives broad reach, not guaranteed behavior. |
| Claude Code hooks | Claude Code supports `UserPromptSubmit`, `SessionStart`, `PreToolUse`, `PostToolUse`, and other lifecycle events. `UserPromptSubmit` can add context. `PreToolUse` can block/deny a tool and show Claude the reason. | Claude Code is Tier A for prompt-time context injection and Tier B for tool-time intervention. It is the first agent to prove the trigger loop. |
| Claude Code MCP | Claude Code supports local, project, and user-scoped MCP servers, with approval behavior for project-scoped servers. | The Skopus MCP server must be installable at explicit scope, and `doctor` must verify visibility to Claude. |
| Cursor rules | Cursor Project Rules live in `.cursor/rules/*.mdc`; they support Always, Auto Attached, Agent Requested, and Manual rule types. Cursor also supports root `AGENTS.md` as a simple alternative, but docs describe AGENTS.md as less structured and without scoping. | Keep a Cursor adapter. AGENTS.md alone is not enough if we want scoped trigger behavior. Cursor is static-rule Tier, not hook Tier, unless a future Cursor hook API is verified. |
| Cline hooks | Cline hooks return JSON with `contextModification`, which is injected into the conversation. Cline also supports PreToolUse, UserPromptSubmit, and other hook types. | Cline is Tier A for context injection. It should be the second agent to prove the trigger loop. |
| Cline MCP | Cline does not ship MCP servers by default; users configure servers in `cline_mcp_settings.json`, and Cline detects available tools after configuration. | `skopus link` must write/verify MCP config or provide exact manual fallback. |
| Windsurf rules | Windsurf Rules support `always_on`, `glob`, `model_decision`, and `manual`. Root AGENTS.md is always-on; nested AGENTS.md is location-scoped. | Windsurf has strong static-rule behavior. Use rules/AGENTS.md for context. |
| Windsurf hooks | Cascade hooks can block, log, run commands, observe MCP usage, and capture responses/transcripts. The docs show blocking and observability, not successful context injection into the next model call. | Windsurf is not Tier A until a spike proves context injection. Treat it as static rules + observability + blocking only. |
| Aider | Aider docs recommend `/read CONVENTIONS.md`, `aider --read`, or `.aider.conf.yml` with `read: CONVENTIONS.md`. `agents.md` says Aider can be configured with `read: AGENTS.md`. | Aider needs explicit config bridging. It is not automatic AGENTS.md consumption. |
| Gemini CLI | Gemini CLI loads `GEMINI.md` by default, supports hierarchical context files, and can customize context filenames to include AGENTS.md. | Gemini needs `.gemini/settings.json` bridging if AGENTS.md is the canonical file. |
| Continue | Continue local rules live in `.continue/rules`; rules can use `globs`, `description`, and `alwaysApply`. | Continue needs a rules adapter. AGENTS.md is not the primary path. |
| Local Skopus repo | The repo already has a Correction-Persistence benchmark and tests around adapters and rendering. | Phase gates must run through existing tests and the CP benchmark before any behavior claim is made. |

Primary sources:

- https://agents.md/
- https://openai.com/index/agentic-ai-foundation/
- https://code.claude.com/docs/en/hooks
- https://docs.anthropic.com/en/docs/claude-code/mcp
- https://docs.cursor.com/context/rules-for-ai
- https://docs.cline.bot/customization/hooks
- https://docs.cline.bot/mcp/adding-and-configuring-servers
- https://docs.windsurf.com/windsurf/cascade/memories
- https://docs.windsurf.com/windsurf/cascade/hooks
- https://aider.chat/docs/usage/conventions.html
- https://geminicli.com/docs/cli/gemini-md/
- https://docs.continue.dev/customize/deep-dives/rules

---

## 3. Corrected Product Promise

The original promise was too absolute. This is the corrected promise:

1. **Portable partnership context across verified agents.** The user's charter, corrections, and vault are stored once and rendered into each agent's verified integration path.
2. **Fewer repeated corrections, measured by Correction-Persistence.** Skopus must beat baseline context loading on correction-specific tasks before we claim value.
3. **Visible setup with proof.** `skopus link` may write several files, but every write is shown, idempotent, reversible, and checked by `skopus doctor`.

What we do **not** claim:

- No "every agent just works" without a smoke test.
- No "never duplicated, never lost."
- No "99% reliable" trigger claims without instrumentation.
- No automatic high-stakes enforcement.

---

## 4. Architecture That Can Actually Work

### 4.1 Canonical Knowledge Model

Skopus owns canonical data under `~/.skopus/`:

- `charter/` - how the user/team wants agents to work.
- `memory/feedback/` - durable corrections and drift moments.
- `memory/trigger_gaps/` - cases where a correction should have been consulted but was not.
- `vault/` - decisions, learnings, and reference knowledge.
- `memory/patterns/` - v0.6 only, after trigger capture is proven.

Every durable memory item needs structured metadata:

```yaml
id: feedback-2026-04-28-example
scope: user | project | team
source: explicit-correction | charter-evolve | imported | inferred
confidence: confirmed | probable | weak
applies_to:
  paths: ["src/billing/**"]
  task_types: ["debug", "review"]
  keywords: ["rounding", "currency"]
supersedes: []
sensitivity: normal | private | secret-adjacent
created_at: 2026-04-28
last_validated_at:
```

Without scope, source, confidence, and supersession, the memory system will rot.

### 4.2 Delivery Surfaces

Skopus exposes canonical data through three surfaces:

| Surface | What it does | Reliability class |
|---|---|---|
| Static context | Writes short context/rules files the agent loads at session start or when scoped. | Broad reach, low control. |
| On-demand retrieval | MCP tools such as `skopus_search_memory`, `skopus_query_vault`, `skopus_get_charter_section`. | Strong when configured, but depends on the model choosing or being prompted to call tools. |
| Triggered intervention | Hooks or rule engines that run on prompt submission or tool use. | Strong only where docs prove context injection or effective blocking. |

### 4.3 Adapter Strategy

The design no longer means "two files for everyone."

It means:

> One canonical renderer, multiple thin adapters.

The canonical renderer produces the same short Skopus payload. Adapters place it in the strongest verified location for each agent:

| Agent/tool | v2 adapter behavior |
|---|---|
| AGENTS.md-native agents | Write root `AGENTS.md` with a short Skopus block. Use nested AGENTS.md only after smoke tests. |
| Claude Code | Write `CLAUDE.md` bridge or thin inline block. Configure MCP and approved hooks when explicitly enabled. |
| Cursor | Keep `.cursor/rules/skopus.mdc` for scoped/always rules. Also write AGENTS.md for cross-tool portability. |
| Cline | Use AGENTS.md/rules for static context, MCP config for retrieval, and hooks for context injection after explicit enablement. |
| Windsurf | Use AGENTS.md and/or `.windsurf/rules`. Use hooks first for observability; context injection requires a spike before claim. |
| Aider | Add `read: AGENTS.md` or equivalent to `.aider.conf.yml` with visible diff. |
| Gemini CLI | Add `.gemini/settings.json` context filename config with visible diff. |
| Continue | Write `.continue/rules/skopus.md` with frontmatter. |

This reduces duplicated adapter bodies. It does not pretend all agents behave identically.

---

## 5. Trigger Design

The old design treated the trigger problem as solved by four layers and attached made-up reliability percentages. That is gone.

### 5.1 Capability Tiers

| Tier | Capability | Agents currently eligible |
|---|---|---|
| Tier A - prompt-time context injection | A hook can run before the agent processes a user prompt and add context to the conversation. | Claude Code, Cline. Windsurf not eligible until spike proves injection. |
| Tier B - tool-time intervention | A hook can run before write/command/tool use and either inject context or block/deny with feedback. | Claude Code, Cline. Windsurf can block/observe, but injection not proven. |
| Tier C - static scoped rules | Rules are loaded always, by glob, or by model decision. | Cursor, Windsurf, Continue, Gemini, AGENTS.md-native agents. |
| Tier D - instruction only | Agent sees instructions telling it when to call MCP or read memory, but no deterministic trigger exists. | Aider and any agent without hooks/rules/MCP verification. |

### 5.2 Runtime Trigger Policy

Skopus should run the cheapest reliable trigger available:

1. **Prompt-shape trigger:** research, debug, design, review, refactor, implementation, migration, security, billing, dependency choice.
2. **Path trigger:** before reading/editing files matching paths tied to corrections.
3. **Tool trigger:** before high-risk commands, dependency installs, migrations, destructive operations, or MCP calls.
4. **Explicit user trigger:** "remember this", "we already decided", "you missed", "wrong", "not how we do it".

The action depends on the agent tier:

- Tier A: inject relevant charter/memory/pattern context before the model starts.
- Tier B: inject if supported; otherwise deny/block with actionable feedback and let the agent retry with the memory.
- Tier C: render concise always/glob/model-decision rules.
- Tier D: rely on static instruction and post-session capture only.

### 5.3 No Reliability Numbers Until Measured

Replace all "~95-99%" claims with metrics:

| Metric | Definition | Minimum gate |
|---|---|---|
| Trigger recall | Of tasks where a known correction applies, did Skopus surface it before the relevant action? | >= 90% for Tier A agents before claiming "automatic." |
| Trigger precision | Of surfaced memories, how often were they relevant? | >= 80% before enabling default surfacing. |
| CP score delta | Correction-Persistence score versus baseline. | v2 >= v1 score with <= 50% always-loaded tokens. |
| MCP visibility | Agent can see and call Skopus tools in a fresh project. | 100% for each advertised MCP-enabled agent. |
| Setup success | Fresh install/link/doctor with no manual edits. | 100% on supported OS/agent matrix before "one install" claim. |

---

## 6. Deep Context Service

The deep context service is an MCP server plus local search/indexing. It is not optional if the static block is slimmed down.

Required tools for v0.5:

- `skopus_search_memory(query, scope?, paths?, task_type?)`
- `skopus_query_vault(query, scope?)`
- `skopus_get_charter_section(section)`
- `skopus_record_drift(summary, source, confidence, scope?)`
- `skopus_status()` - lets agents and `doctor` verify the service is alive.

Required failure behavior:

- If MCP is not configured, static context must tell the agent where the fallback files are.
- If the service is down, `skopus doctor` must show exact remediation.
- If a query returns nothing, the agent should proceed but record a low-confidence gap only if later corrected.
- MCP output must be capped and summarized; no tool should dump the entire vault.

Operational requirements:

- Explicit install scope: user, project, or local.
- No secrets in project-shared MCP config.
- Versioned index format.
- Rebuild command: `skopus index rebuild`.
- Health check: `skopus doctor --agent <agent>`.

---

## 7. Learning Loop

The learning loop is still valuable, but it must be conservative.

### 7.1 Detection Confidence

| Signal | Confidence | Allowed action |
|---|---|---|
| User explicitly corrects the agent and references a prior decision/correction. | Confirmed | Save feedback; suggest rule/hook if repeated. |
| `/charter-evolve` captures user-approved correction. | Confirmed | Save feedback; may update charter after review. |
| Transcript/action analysis finds a likely missed memory. | Probable | Create trigger-gap draft only. No automatic rule. |
| A pattern fired and the user did not object. | Weak | Count as weak validation only. Never promote by itself. |
| Agent did not mention memory in reasoning. | Weak | Observability only. Do not infer failure alone. |

### 7.2 Promotion Rules

1. First confirmed miss: write a memory entry.
2. Repeated confirmed misses in the same scope: propose a static rule.
3. Repeated misses where a hook-capable agent exists: propose a hook with preview.
4. High-stakes paths: increase warning severity, but still require explicit approval.

No auto-enforce. The previous design's "auto-promote without asking" is removed.

### 7.3 Hook Approval Contract

Before installing a hook, Skopus must show:

- Files/config to be changed.
- Exact hook command.
- What event triggers it.
- Whether it can block actions.
- Whether it can read transcripts/file contents.
- Rollback command.

Every hook install must be reversible through `skopus unlink` or `skopus hook remove`.

### 7.4 Validation

"No user correction" is not proof that a rule worked.

Validation requires at least one of:

- Explicit user acceptance in `/charter-evolve`.
- Benchmark/probe task where the expected trigger fires.
- Hook log proving the right memory was surfaced before the relevant action and the final output used it.

---

## 8. Patterns

Patterns remain a good v0.6 feature, but they are not part of the v0.5 product promise.

Patterns can ship only after:

- Memory search works.
- Trigger gaps are captured with confidence metadata.
- At least two Tier A agents prove prompt-time pattern injection.
- Pattern conflicts can be resolved by scope, specificity, recency, and supersession.

Correct conflict rule:

> More specific, higher-confidence, more recent, in-scope memory beats a general pattern. Team/project policy can beat personal preference only when the scope says so.

The old rule "specific memory always wins" is too vague for teams and stale memories.

---

## 9. User Experience

### Install

```bash
pip install skopus
skopus init
cd your-project
skopus link
skopus doctor
```

`skopus link` must print every file it will write or modify. `skopus doctor` must prove the result.

### During Work

Best case on Tier A agents:

1. User submits a prompt.
2. Skopus prompt hook classifies the task.
3. Skopus injects the relevant charter/memory/pattern snippet.
4. Agent works with that context already present.

Fallback on Tier C/D agents:

1. Agent receives short static instructions.
2. Agent may call MCP or read files if it follows instructions.
3. Misses are captured only through explicit correction or session-end review.

### End Of Session

`/charter-evolve` remains the canonical capture point. It should not pretend to know everything. It should ask targeted questions and mark confidence.

---

## 10. `skopus doctor` Is Product-Critical

`skopus doctor` must become the proof surface.

It should check:

- Which agents are detected.
- Which files Skopus wrote.
- Whether Skopus markers are intact and idempotent.
- Whether duplicate rule systems exist and may double-load context.
- Whether MCP tools are visible to each supported agent.
- Whether hooks are registered, executable, and scoped correctly.
- Whether hooks can inject context or only block/log.
- Whether static context exceeds token/character budget.
- Whether memory/vault indexes are fresh.
- Whether team/project/user scopes are mixed dangerously.

No "wired in" claim without doctor evidence.

---

## 11. Phase Plan With Gates

### Phase 0 - Slim Static Context

Scope:

- Replace the current large inlined block with a short canonical block.
- Keep fallback file paths.
- Preserve idempotent markers.

Gate:

- Existing tests pass.
- Correction-Persistence: thin block score >= 95% of current block.
- Always-loaded token count <= 50% of current block.

If CP drops below 90%, stop and redesign.

### Phase 1 - Verified Adapter Bridges

Scope:

- One canonical renderer.
- Thin adapters for AGENTS.md, Claude, Cursor, Cline, Windsurf, Aider, Gemini, Continue.
- No silent writes.

Gate:

- Fresh-project smoke test per advertised agent.
- `skopus doctor` accurately reports installed/partial/broken.
- Any agent not passing is removed from marketing claims.

### Phase 2 - MCP Deep Context

Scope:

- Local MCP server.
- Memory/vault/charter tools.
- Agent-specific MCP setup where official docs support it.

Gate:

- MCP tool visible and callable in each advertised MCP-capable agent.
- Service-down fallback tested.
- Tool output capped.
- CP with MCP >= current CP and <= 50% always-loaded tokens.

### Phase 3 - Conservative Learning Loop

Scope:

- Trigger-gap records.
- Confirmed/probable/weak confidence.
- Explicit approval for rules/hooks.

Gate:

- No auto-promotion from weak signals.
- Hook install/remove tested.
- Trigger recall/precision measured on Claude Code and Cline before claiming automatic behavior.

### Phase 4 - Patterns

Scope:

- Pattern schema.
- Pattern match/get/list tools.
- Pattern update flow in `/charter-evolve`.

Gate:

- Pattern benchmark shows improvement over raw memory retrieval.
- Pattern sprawl/staleness/conflict handling tested.
- At least two agents prove prompt-time pattern injection.

---

## 12. What Was Removed From The Original Design

- Removed invented day-one and 30-day reliability percentages.
- Removed "two files cover everyone" as an implementation claim.
- Removed "agent did not have a choice" language except for proven blocking hooks.
- Removed automatic high-stakes hook installation.
- Removed "no correction means validation."
- Removed "never duplicated, never lost."
- Removed "one install, every coding agent just works."
- Moved patterns out of the v0.5 promise.

---

## 13. What Counts As Proof

Proof is not a persuasive paragraph. Proof is one of:

- A passing benchmark report.
- A fresh-project smoke test transcript.
- A `skopus doctor` report showing exact integration state.
- A hook log proving context was surfaced before the risky action.
- A failing test that would catch regression.

Minimum local proof before Phase 0 implementation is accepted:

```bash
pytest tests/test_bench_cp.py tests/test_multi_adapters.py tests/test_renderer.py
skopus bench run cp --driver mock --limit 5 --no-save
```

Mock benchmark results prove the harness still works, not product value. Product value requires a real model driver and the CP ablation gate.

---

## 14. Final Call

Proceed with v2 only under this rule:

> Every claim in the product must map to a checked capability, a passing benchmark, or an explicit unsupported state.

Phase 0 is the right first move because current context bloat is already a known defect. Everything after that must earn its way in with evidence.
