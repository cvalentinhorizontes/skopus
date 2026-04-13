# Skopus

**Persistent context for AI coding assistants.** Install it, run it, your agent remembers you.

> σκοπός *(skopos)* — Greek for *watcher*, *purpose*. A system that gives agents durable scope across sessions.

## The problem

Every AI coding assistant forgets you at the end of every session. You teach it your preferences, it forgets. You correct it, it repeats the mistake next week.

## The fix

```bash
pip install skopus        # or: pipx install skopus
skopus init               # answer 9 questions, everything set up
```

That's it. Next time you open your AI assistant, it already knows:
- **How you work** (your non-negotiables, communication style, anti-patterns to avoid)
- **What you've corrected** (mistakes it won't repeat)
- **What you've decided** (a knowledge base that grows over time)
- **What your code looks like** (automatic codebase map via [graphify](https://github.com/safishamsi/graphify))

Works with **Claude Code**, **Cursor**, **Codex**, **Aider**, **Gemini CLI**, and **Copilot CLI**.

## How it works

Skopus writes one file into your project (`CLAUDE.md` / `AGENTS.md` / `.cursor/rules/`) that teaches the AI assistant who you are. The assistant reads it automatically at session start. No re-teaching.

Everything lives in one directory: `~/.skopus/`

```
~/.skopus/
├── charter/     Your rules, non-negotiables, working style
├── memory/      Corrections and wins that compound over time
└── vault/       Your knowledge base (decisions, learnings, sources)
```

## Commands

**Setup (run once):**

```bash
skopus init              # wizard + scaffold + wire current project
skopus link              # wire a different project (if not done during init)
```

**Daily use (inside your AI assistant):**

| Command | What it does |
|---|---|
| `/charter-evolve` | End of session: captures corrections and wins automatically |
| `/compile` | Captures knowledge from the session into your vault |
| `/graphify .` | Builds a map of your codebase (first time only) |
| `/query <question>` | Asks your knowledge base a question |
| `/ingest <url>` | Saves an article/doc into your knowledge base |

**Maintenance:**

```bash
skopus update            # upgrade + re-install everything
skopus doctor            # health check
```

## Benchmarks

Skopus ships with a benchmark suite that measures whether it actually works. The novel **Correction-Persistence** benchmark tests: *does the agent apply yesterday's corrections to today's tasks?*

```bash
skopus bench run cp --ablation    # run across 5 lens configurations
skopus bench list                 # see all available benchmarks
```

## Contributing

- **New platform adapters:** one Python file implementing a 5-method ABC. See `skopus/adapters/claude_code.py`.
- **Benchmark scenarios:** real corrections from real sessions. Run `/bench-contribute` inside Claude Code to generate anonymized scenarios from your feedback.
- **Bug reports:** [github.com/cvalentinhorizontes/skopus/issues](https://github.com/cvalentinhorizontes/skopus/issues)

## License

MIT — see [LICENSE](LICENSE).
