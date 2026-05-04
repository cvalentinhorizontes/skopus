# Phase 1 — Manual smoke checklist

The pytest smoke suite in `tests/test_smoke_advertised_adapters.py` covers
the **file-side contract**: file written at expected path, valid markers,
well-formed structure, idempotent, status agrees. It does NOT prove that
each agent platform *actually loads* the file at session start.

This checklist is the manual verification gate for that. Run it once per
release of v0.7.x (and any time an adapter's `install()` or block format
changes). Record results in `phase1-gate.md` as new rows under the
"Manual-smoke list" section.

## Setup (once per smoke run)

```bash
# Fresh test project
rm -rf /tmp/skopus-smoke
mkdir /tmp/skopus-smoke && cd /tmp/skopus-smoke
git init -q
echo "# Skopus smoke test project" > README.md
git add . && git commit -q -m "init"

# Fresh skopus install (use a throwaway HOME to avoid contaminating
# your real ~/.skopus). Replace /tmp/skopus-home with any empty dir.
mkdir -p /tmp/skopus-home
HOME=/tmp/skopus-home pipx install skopus
HOME=/tmp/skopus-home skopus init --name SmokeTester --role founder
HOME=/tmp/skopus-home skopus link  # in /tmp/skopus-smoke
```

Verify the wiring before the per-adapter steps:

```bash
HOME=/tmp/skopus-home skopus doctor
HOME=/tmp/skopus-home skopus doctor --agent claude-code
HOME=/tmp/skopus-home skopus doctor --agent cursor
HOME=/tmp/skopus-home skopus doctor --agent agents-md
```

Each should report `INSTALLED` for the project at `/tmp/skopus-smoke`.

## Per-adapter smoke

For each, the **probe prompt** is the same so you can compare apples-to-apples
across agents:

> *What does the partnership charter say about non-negotiables?*

The charter content lives in `/tmp/skopus-home/.skopus/charter/CLAUDE.md`
(seeded from the wizard's `--role founder` defaults). The agent should
reference at least one specific non-negotiable, not just say "I see a
CLAUDE.md / AGENTS.md exists."

### Claude Code

1. Open Claude Code with `/tmp/skopus-smoke` as the working directory.
2. Verify `.claude/CLAUDE.md` exists and contains the Skopus block (`<!-- skopus:begin -->` ... `<!-- skopus:end -->`).
3. In Claude Code chat, type the probe prompt.
4. **Expected:** the agent quotes or paraphrases at least one non-negotiable from the charter.
5. **Result:** ☐ pass / ☐ fail / ☐ partial — write notes (especially if the agent referenced *a* CLAUDE.md but not *yours*).

### Cursor

1. Open Cursor with `/tmp/skopus-smoke`.
2. Verify `.cursor/rules/skopus.mdc` exists with `alwaysApply: true` in the YAML frontmatter.
3. Open Cursor chat (Cmd+L on macOS, Ctrl+L on Linux/Windows), type the probe prompt.
4. **Expected:** the agent quotes or paraphrases at least one non-negotiable.
5. **Result:** ☐ pass / ☐ fail / ☐ partial — note if `alwaysApply` didn't fire and you had to invoke the rule manually.

### AGENTS.md (via Codex CLI as one consumer)

1. Verify `/tmp/skopus-smoke/AGENTS.md` exists with the Skopus block.
2. Run `codex` in `/tmp/skopus-smoke` (or whichever AGENTS.md-consumer is most convenient — Cline, Aider with `--read AGENTS.md`, etc.).
3. Ask the probe prompt.
4. **Expected:** the agent quotes or paraphrases at least one non-negotiable.
5. **Result:** ☐ pass / ☐ fail / ☐ partial — note which AGENTS.md consumer you tested with.

## What to do with the results

**All 3 pass:** the v0.7.0 advertised tier is honest. Update `phase1-gate.md`
with a row for this smoke run (date, adapter, result, notes).

**1 or more fails:** that adapter drops to `EXPERIMENTAL` until repaired.
Edit the adapter's `tier` attribute back to `AdapterTier.EXPERIMENTAL`,
re-run the pytest smoke suite to confirm it still passes, and update
marketing copy / README to reflect the change. Open a follow-up issue with
the failing probe prompt's transcript so the regression can be diagnosed.

**Partial passes:** the agent loaded the file but didn't surface the
non-negotiable cleanly. Could be a charter wording issue, a prompt
sensitivity issue, or a partial-context-load issue. Triage before deciding
whether to demote.

## Cleanup

```bash
rm -rf /tmp/skopus-smoke /tmp/skopus-home
```

(Both are throwaway. Do not run cleanup on `~/.skopus` or your real project
directory.)

## Why this isn't pytest

Skopus owns the file-side contract — what it writes, where, in what shape.
That contract is automated (see `tests/test_smoke_advertised_adapters.py`).
What Skopus does NOT own: each agent platform's session-start context
loading behavior. Those are external systems. Verifying them requires the
platform installed, an interactive session, and a human reading the
agent's output for "did it actually use my charter?"

A future v1.x release may add a docker-based agent harness that automates
this — but that's out of scope for v0.7.0. For now, manual is honest.
