"""Skopus benchmark harness.

Measures the additive contribution of each lens (charter, memory, vault,
graph) against an LLM baseline across five benchmarks:

  - LongMemEval (Wu et al. 2024)   — cross-session memory
  - LoCoMo (Google 2024)           — long multi-session conversations
  - MSC (Facebook 2021)            — persona consistency
  - RULER (NVIDIA 2024)            — long-context retrieval
  - Correction-Persistence (novel) — does yesterday's correction persist today?

The harness ships with five lens configurations for ablation:

  1. vanilla              — LLM call, no skopus context
  2. +charter             — charter loaded into system prompt
  3. +charter +memory     — + feedback/project memory files
  4. +charter +memory +vault — + relevant vault pages
  5. full skopus          — + graphify MCP tools available

Running:

    skopus bench run cp                        # Correction-Persistence only
    skopus bench run all                       # All 5 benchmarks
    skopus bench run all --ablation            # Ablation across 5 configs
    skopus bench list                          # Show available benchmarks
    skopus bench report                        # Render markdown report from results
"""

__version__ = "0.1.0-alpha"
