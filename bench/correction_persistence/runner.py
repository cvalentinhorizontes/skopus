"""Correction-Persistence benchmark runner.

For each scenario, run the follow-up task with the configured lens and check
if the response indicates the correction was persisted.

This runner deliberately does NOT simulate the "initial task → mistake →
correction" part of the flow. That's already encoded into the lens config
(the charter + feedback memory IS the correction). The test is: given the
correction is present in the context, does the agent apply it to the new task?

Skopus's story: if the correction is in feedback memory, the +memory and
+full configurations should score higher than vanilla and +charter alone.

Scoring modes:
  - "keyword" (default): fast, deterministic, no API cost, but brittle on
    synonyms and contrastive negation ("I won't use X" triggers "X").
  - "llm": uses a judge model to evaluate semantic correction application.
    More accurate but adds one API call per scenario.
  - "both": runs both scorers and reports each. Use for calibration.
"""

from __future__ import annotations

import asyncio
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


# ---------------------------------------------------------------------------
# Keyword scorer (original, fast, deterministic)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# LLM-as-judge scorer (semantic, handles synonyms + contrastive negation)
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM = """You are a benchmark scorer. You evaluate whether an AI assistant's response
correctly applies a previously given correction to a new task.

You will receive:
- The CORRECTION the user gave previously
- The FOLLOW-UP TASK the assistant was given
- The EXPECTED MISTAKE PATTERN (what the assistant would do WITHOUT the correction)
- The RESPONSE the assistant actually produced

Score the response on one dimension: did the assistant apply the correction?

Respond with EXACTLY one JSON object, no other text:
{"applied": true/false, "score": 0.0-1.0, "reasoning": "one sentence"}

Rules:
- applied=true if the response demonstrates the corrected behavior, even with different wording
- applied=false if the response repeats the expected mistake pattern
- Mentioning the anti-pattern to contrast it ("I won't do X, instead I'll do Y") counts as APPLIED
- Using synonyms of the correction keywords counts as APPLIED
- score=1.0 means perfect application, 0.5 means partial, 0.0 means no application"""


def score_response_llm(
    response_text: str,
    scenario: CPScenario,
    judge_driver: LLMDriver,
) -> tuple[bool, float, str]:
    """Score using an LLM judge for semantic evaluation."""
    user_prompt = (
        f"CORRECTION: {scenario.correction}\n\n"
        f"FOLLOW-UP TASK: {scenario.followup_task}\n\n"
        f"EXPECTED MISTAKE PATTERN: {scenario.expected_mistake_pattern}\n\n"
        f"RESPONSE:\n{response_text[:3000]}"
    )

    judge_response = judge_driver.run(_JUDGE_SYSTEM, user_prompt, max_tokens=256)

    try:
        # Extract JSON from response
        text = judge_response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        applied = bool(result.get("applied", False))
        llm_score = float(result.get("score", 0.0))
        reasoning = result.get("reasoning", "")
        return applied, llm_score, f"llm_judge: {reasoning}"
    except (json.JSONDecodeError, KeyError, ValueError):
        return False, 0.0, f"llm_judge: parse error — {judge_response.text[:100]}"


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------

def run_scenario(
    scenario: CPScenario,
    driver: LLMDriver,
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    judge_driver: LLMDriver | None = None,
    scoring: str = "keyword",
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

    # Score based on selected mode
    if scoring == "llm" and judge_driver:
        passed, score, notes = score_response_llm(response.text, scenario, judge_driver)
    elif scoring == "both" and judge_driver:
        kw_passed, kw_score, kw_notes = score_response(response.text, scenario.success_criterion)
        llm_passed, llm_score, llm_notes = score_response_llm(response.text, scenario, judge_driver)
        passed = llm_passed  # LLM judge is authoritative
        score = llm_score
        notes = f"keyword: {kw_notes} | {llm_notes} | kw_passed={kw_passed}"
    else:
        passed, score, notes = score_response(response.text, scenario.success_criterion)

    return BenchmarkResult(
        scenario_id=scenario.id,
        lens=lens,
        passed=passed,
        score=score,
        notes=notes,
        tokens_in=response.tokens_in + (0 if scoring == "keyword" else 0),
        tokens_out=response.tokens_out,
        cost_usd=response.cost_usd,
        duration_ms=response.duration_ms,
    )


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------

def _run_scenario_sync(args: tuple) -> BenchmarkResult:
    """Wrapper for concurrent.futures — unpacks args tuple."""
    scenario, driver, lens, skopus_dir, vault_dir, judge_driver, scoring = args
    return run_scenario(scenario, driver, lens, skopus_dir, vault_dir, judge_driver, scoring)


def run_correction_persistence(
    driver: LLMDriver,
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    *,
    dataset_path: Path | None = None,
    limit: int | None = None,
    judge_driver: LLMDriver | None = None,
    scoring: str = "keyword",
    parallel: int = 1,
) -> BenchmarkReport:
    """Run the full CP benchmark for a given driver + lens config.

    Args:
        parallel: max concurrent API calls. 1 = sequential (original behavior).
                  Set to 10-20 for fast runs. Each scenario is independent.
    """
    scenarios = load_dataset(dataset_path)
    if limit is not None:
        scenarios = scenarios[:limit]

    report = BenchmarkReport(benchmark_name="correction-persistence", lens=lens)

    if parallel <= 1:
        for scenario in scenarios:
            result = run_scenario(scenario, driver, lens, skopus_dir, vault_dir, judge_driver, scoring)
            report.results.append(result)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        args_list = [
            (s, driver, lens, skopus_dir, vault_dir, judge_driver, scoring)
            for s in scenarios
        ]
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {pool.submit(_run_scenario_sync, a): a[0].id for a in args_list}
            results_map: dict[str, BenchmarkResult] = {}
            for future in as_completed(futures):
                result = future.result()
                results_map[result.scenario_id] = result
        # Preserve original scenario order
        for scenario in scenarios:
            report.results.append(results_map[scenario.id])

    return report
