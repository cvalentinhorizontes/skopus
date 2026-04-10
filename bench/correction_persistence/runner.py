"""Correction-Persistence benchmark runner.

For each scenario, run the follow-up task with the configured lens and check
if the response indicates the correction was persisted.

This runner deliberately does NOT simulate the "initial task → mistake →
correction" part of the flow. That's already encoded into the lens config
(the charter + feedback memory IS the correction). The test is: given the
correction is present in the context, does the agent apply it to the new task?

Skopus's story: if the correction is in feedback memory, the +memory and
+full configurations should score higher than vanilla and +charter alone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from bench.config import BenchmarkReport, BenchmarkResult, LensConfig
from bench.context import build_system_prompt
from bench.driver import LLMDriver


@dataclass
class CPScenario:
    """A single correction-persistence scenario."""

    id: str
    domain: str
    title: str
    initial_task: str
    expected_mistake_pattern: str
    correction: str
    followup_task: str
    success_criterion: dict[str, list[str]]
    charter_relevance: str

    @classmethod
    def from_dict(cls, data: dict) -> CPScenario:
        return cls(**{k: data[k] for k in cls.__annotations__ if k in data})


def load_dataset(dataset_path: Path | None = None) -> list[CPScenario]:
    """Load the CP dataset from disk or the bundled default."""
    if dataset_path is None:
        dataset_path = Path(str(files("bench") / "correction_persistence" / "dataset.json"))
    raw = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    return [CPScenario.from_dict(s) for s in raw["scenarios"]]


def score_response(response_text: str, criterion: dict[str, list[str]]) -> tuple[bool, float, str]:
    """Score a response against the scenario's success criterion.

    Returns (passed, score, notes). Score is 0.0 to 1.0.
    """
    must_include = criterion.get("must_include", [])
    must_not_include = criterion.get("must_not_include", [])

    response_lower = response_text.lower()

    include_hits = sum(1 for kw in must_include if kw.lower() in response_lower)
    exclude_hits = sum(1 for kw in must_not_include if kw.lower() in response_lower)

    # Score = fraction of required keywords present - penalty for forbidden keywords
    include_score = include_hits / len(must_include) if must_include else 1.0
    exclude_penalty = (exclude_hits / len(must_not_include)) if must_not_include else 0.0

    score = max(0.0, include_score - exclude_penalty)

    # Pass threshold: at least half the required keywords and zero forbidden
    passed = include_score >= 0.5 and exclude_hits == 0

    notes = (
        f"include: {include_hits}/{len(must_include)}, "
        f"exclude_hits: {exclude_hits}/{len(must_not_include)}"
    )
    return passed, score, notes


def run_scenario(
    scenario: CPScenario,
    driver: LLMDriver,
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
) -> BenchmarkResult:
    """Run a single CP scenario through the configured lens."""
    system_prompt = build_system_prompt(
        lens=lens,
        skopus_dir=skopus_dir,
        vault_dir=vault_dir,
        task_hint=(
            f"Context: the user previously corrected a similar case with: "
            f"'{scenario.correction}'. Apply this learning to the new task."
            if lens in {LensConfig.CHARTER_MEMORY, LensConfig.CHARTER_MEMORY_VAULT, LensConfig.FULL}
            else ""
        ),
    )

    response = driver.run(system_prompt, scenario.followup_task)
    passed, score, notes = score_response(response.text, scenario.success_criterion)

    return BenchmarkResult(
        scenario_id=scenario.id,
        lens=lens,
        passed=passed,
        score=score,
        notes=notes,
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=response.cost_usd,
        duration_ms=response.duration_ms,
    )


def run_correction_persistence(
    driver: LLMDriver,
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    *,
    dataset_path: Path | None = None,
    limit: int | None = None,
) -> BenchmarkReport:
    """Run the full CP benchmark for a given driver + lens config."""
    scenarios = load_dataset(dataset_path)
    if limit is not None:
        scenarios = scenarios[:limit]

    report = BenchmarkReport(benchmark_name="correction-persistence", lens=lens)
    for scenario in scenarios:
        result = run_scenario(scenario, driver, lens, skopus_dir, vault_dir)
        report.results.append(result)

    return report
