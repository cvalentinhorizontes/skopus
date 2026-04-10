"""Correction-Persistence benchmark.

The novel benchmark that skopus ships as its research contribution. Measures
whether an agent applies yesterday's corrections to today's similar-but-not-
identical tasks — the thing users actually care about ("stop making the same
mistake twice").

No public benchmark measures this directly. This is what the charter +
feedback memory + drift log is designed for, and this benchmark is how we
prove it works.

Dataset: ``dataset.json`` — starts at 20 scenarios, targets 100+ for v1.0.
Runner: ``runner.py``  — executes scenarios against an LLM driver.
Scorer: ``scorer.py``  — persistence, generalization, decay, cross-agent metrics.
"""
