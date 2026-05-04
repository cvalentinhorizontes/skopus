# Phase 2 — Manual smoke checklist (MCP server)

The pytest suite (`tests/test_mcp_*.py`) covers the **in-process MCP-client
contract**: server constructs, tools register, tools return the right shapes,
installers write/uninstall correctly. It does NOT prove that each agent
platform actually **discovers** Skopus's tools and the agent can **call** them
during a real session.

This checklist is the manual verification gate for that. Run once per release
of v0.8.x (and any time a tool's schema, the server skeleton, or an installer
config path changes). Record results in `phase2-gate.md` as new rows under
the "Manual-smoke list" section.

## Setup (once per smoke run)

```bash
# Fresh test project
rm -rf /tmp/skopus-mcp-smoke
mkdir /tmp/skopus-mcp-smoke && cd /tmp/skopus-mcp-smoke
git init -q
echo "# Skopus MCP smoke test project" > README.md
git add . && git commit -q -m "init"

# Fresh skopus install in a throwaway HOME (avoid contaminating ~/.skopus).
mkdir -p /tmp/skopus-mcp-home
HOME=/tmp/skopus-mcp-home pipx install skopus
HOME=/tmp/skopus-mcp-home skopus init --name SmokeTester --role founder
HOME=/tmp/skopus-mcp-home skopus link  # in /tmp/skopus-mcp-smoke
```

Verify the server binary works in isolation BEFORE wiring any agent:

```bash
# Stdio handshake — kills server after 3s; should see a JSON-RPC response
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"1.0"}}}' \
  | HOME=/tmp/skopus-mcp-home timeout 3 skopus mcp serve
```

Expected: a single line of JSON containing `"result"`, `"protocolVersion"`,
`"capabilities"`, `"serverInfo": {"name": "skopus", ...}`.

## Per-agent installer + smoke

Each agent gets its own `skopus link --mcp <agent>` invocation, then a
verification that the agent actually discovers and calls Skopus tools.

The **probe prompt** is the same across agents so results compare apples-to-apples:

> *Use the skopus tools to find any prior corrections about TDD or testing.*

The seeded charter from `--role founder` includes TDD as a non-negotiable, so
the agent should call `skopus_search_memory("tdd")` (or `"testing"`) and
return a non-empty match.

### Claude Code

1. Wire the MCP server:
   ```bash
   HOME=/tmp/skopus-mcp-home skopus link --mcp claude-code
   ```
   Expected: `✓ Wired Skopus MCP into claude-code at /tmp/skopus-mcp-home/.claude/settings.json (created)`.

2. Verify the config file:
   ```bash
   cat /tmp/skopus-mcp-home/.claude/settings.json
   ```
   Expected: contains `mcpServers.skopus.command = "skopus"` and `args = ["mcp", "serve"]`.

3. Verify doctor agrees:
   ```bash
   HOME=/tmp/skopus-mcp-home skopus doctor --agent claude-code
   ```
   Expected: 4-row table, "MCP installed" row reads `installed`.

4. Open Claude Code (with `HOME=/tmp/skopus-mcp-home` so it reads the
   throwaway config) at `/tmp/skopus-mcp-smoke`. In a new chat:
   - Confirm the Skopus MCP tools appear in the tool list (typically via
     `/mcp` or the tools panel — version-dependent).
   - Type the probe prompt.

5. **Expected:** Claude Code calls `skopus_search_memory` and returns the
   matching memory entry.

6. **Result:** ☐ pass / ☐ fail / ☐ partial — note the tool names visible
   in the agent's tool list (should include skopus_status, search_memory,
   query_vault, get_charter_section, record_drift).

### Cline

1. Wire:
   ```bash
   HOME=/tmp/skopus-mcp-home skopus link --mcp cline
   ```
   Expected: `✓ Wired Skopus MCP into cline at /tmp/skopus-mcp-home/.config/cline/cline_mcp_settings.json (created)`.

2. Verify the config file at `/tmp/skopus-mcp-home/.config/cline/cline_mcp_settings.json`.

3. Open Cline (in a host that respects `HOME` — VS Code launched from this
   shell will inherit it). Confirm Skopus tools appear in Cline's MCP panel.

4. Run the probe prompt. **Expected:** Cline calls a Skopus tool.

5. **Result:** ☐ pass / ☐ fail / ☐ partial.

### Cursor

1. Wire:
   ```bash
   HOME=/tmp/skopus-mcp-home skopus link --mcp cursor
   ```
   Expected: `✓ Wired Skopus MCP into cursor at /tmp/skopus-mcp-home/.cursor/mcp.json (created)`.

2. Verify the config file at `/tmp/skopus-mcp-home/.cursor/mcp.json`.

3. Open Cursor at `/tmp/skopus-mcp-smoke` (with `HOME` overridden if your
   launcher supports it; otherwise this test runs against your real Cursor
   config — see "Caveat" below).

4. Open Cursor's chat (Cmd+L on macOS, Ctrl+L on Linux/Windows). Confirm
   the Skopus MCP server appears in Cursor's MCP panel.

5. Run the probe prompt. **Expected:** Cursor calls a Skopus tool.

6. **Result:** ☐ pass / ☐ fail / ☐ partial — note any Cursor-specific
   gotchas (e.g., MCP requires explicit enable in settings).

## Caveat — agents that don't respect HOME

Some agents launched from desktop shortcuts ignore `HOME` overrides and
read the real `~/.cursor/`, `~/.config/cline/`, etc. If you're testing on
a machine where Skopus isn't already wired into your real config, this
is harmless. Otherwise, **back up your real config first**:

```bash
cp ~/.claude/settings.json ~/.claude/settings.json.pre-smoke
cp ~/.cursor/mcp.json ~/.cursor/mcp.json.pre-smoke
cp ~/.config/cline/cline_mcp_settings.json ~/.config/cline/cline_mcp_settings.json.pre-smoke
```

After the smoke run, restore from the `.pre-smoke` backups.

## What to do with the results

**All 3 pass:** the v0.8.0 MCP installation surface is honest. Update
`phase2-gate.md` with rows for this smoke run (date, adapter, result, notes).

**1 or more fails:** specifically — if `link --mcp <agent>` succeeds but
the agent doesn't discover the tools, the issue is likely the agent's
config-file-watching behavior or a config-format change since this
checklist was written. Capture:
- The exact `cat <config-file>` output after wiring.
- The agent's MCP panel screenshot (or text equivalent).
- The agent's startup log if available.

Open a follow-up issue with that evidence. The MCP installer for that
adapter should drop to documentation-only ("install manually") in
`phase2-gate.md` until repaired.

**Partial passes:** the agent loads the MCP server but the probe prompt
doesn't trigger a tool call. Could be:
- The model's tool-selection isn't biased toward Skopus tools (try a more
  direct prompt: "Call skopus_search_memory with query 'tdd'").
- The seeded charter doesn't have an entry that matches the probe.

Triage before deciding whether the wiring counts as broken.

## Cleanup

```bash
rm -rf /tmp/skopus-mcp-smoke /tmp/skopus-mcp-home
# If you backed up real configs:
mv ~/.claude/settings.json.pre-smoke ~/.claude/settings.json 2>/dev/null
mv ~/.cursor/mcp.json.pre-smoke ~/.cursor/mcp.json 2>/dev/null
mv ~/.config/cline/cline_mcp_settings.json.pre-smoke ~/.config/cline/cline_mcp_settings.json 2>/dev/null
```

## Why this isn't pytest

Skopus owns the MCP server (tool registration, schema, stdio transport)
and the installer (config file write/merge). All of that is automated
(`tests/test_mcp_*.py` + `tests/test_link_mcp_flag.py`). What Skopus does
NOT own: each agent's MCP discovery and tool-calling behavior. Those are
external systems with their own release cadences. Verifying them requires
the agent installed, an interactive session, and a human reading the
agent's tool list and chat output.

A future v1.x release may add a docker-based agent harness that automates
this — out of scope for v0.8.0. For now, manual is honest.
