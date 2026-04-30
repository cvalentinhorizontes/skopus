"""Unified benchmark harness.

Dispatches to individual benchmark implementations, aggregates results
across lens configurations, and emits a markdown report.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from bench.config import BenchmarkReport, BenchmarkResult, LensConfig, bench_results_dir
from bench.correction_persistence.runner import run_correction_persistence
from bench.driver import LLMDriver
from bench.locomo.runner import run_locomo as _run_locomo_impl

AVAILABLE_BENCHMARKS = {
    "cp": "Correction-Persistence (novel, 20 scenarios at v0.1.0-alpha)",
    "correction-persistence": "Correction-Persistence (alias)",
    "longmemeval": "LongMemEval — dataset wrapper stub (v0.1.0-alpha)",
    "locomo": "LoCoMo — 10 conversations, 1986 questions, 5 categories",
    "msc": "MSC — dataset wrapper stub (v0.1.0-alpha)",
    "ruler": "RULER — dataset wrapper stub (v0.1.0-alpha)",
    "all": "All benchmarks",
}


def list_benchmarks() -> dict[str, str]:
    """Return the available benchmarks and their descriptions."""
    return dict(AVAILABLE_BENCHMARKS)


def run_benchmark(
    name: str,
    driver: LLMDriver,
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    *,
    limit: int | None = None,
    judge_driver: LLMDriver | None = None,
    scoring: str = "keyword",
    parallel: int = 1,
) -> BenchmarkReport:
    """Dispatch to the named benchmark implementation."""
    normalized = name.lower().replace("_", "-")
    if normalized in {"cp", "correction-persistence"}:
        return run_correction_persistence(
            driver=driver,
            lens=lens,
            skopus_dir=skopus_dir,
            vault_dir=vault_dir,
            limit=limit,
            judge_driver=judge_driver,
            scoring=scoring,
            parallel=parallel,
        )
    if normalized == "longmemeval":
        return _stub_report("longmemeval", lens, "LongMemEval wrapper planned for v0.1.0")
    if normalized == "locomo":
        return _run_locomo(
            driver=driver,
            lens=lens,
            skopus_dir=skopus_dir,
            vault_dir=vault_dir,
            limit=limit,
            judge_driver=judge_driver,
            scoring=scoring,
            parallel=parallel,
        )
    if normalized == "msc":
        return _stub_report("msc", lens, "MSC wrapper planned for v0.1.0")
    if normalized == "ruler":
        return _stub_report("ruler", lens, "RULER wrapper planned for v0.1.0")
    raise KeyError(f"unknown benchmark: {name}")


def _run_locomo(
    driver: LLMDriver,
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    *,
    limit: int | None = None,
    judge_driver: LLMDriver | None = None,
    scoring: str = "keyword",
    parallel: int = 1,
) -> BenchmarkReport:
    """Bridge LoCoMo runner output into the standard BenchmarkReport format."""
    data_path = Path(__file__).parent / "data" / "locomo" / "locomo.json"
    if not data_path.exists():
        return _stub_report("locomo", lens, f"Dataset not found at {data_path}")

    locomo_report = _run_locomo_impl(
        data_path=data_path,
        driver=driver,
        skopus_dir=skopus_dir,
        vault_dir=vault_dir,
        judge_driver=judge_driver,
        lens=lens,
        limit=limit,
        parallel=parallel,
        retrieval_only=(scoring == "retrieval_only"),
    )

    report = BenchmarkReport(benchmark_name="locomo", lens=lens)

    # Convert retrieval results
    for rr in locomo_report.retrieval_results:
        report.results.append(
            BenchmarkResult(
                scenario_id=f"retrieval_{rr.question_id}",
                lens=lens,
                passed=rr.recall_any_5 > 0,
                score=rr.recall_any_5,
                notes=f"R@5={rr.recall_any_5:.0%} R@10={rr.recall_any_10:.0%} cat={rr.category}",
            )
        )

    # Convert QA results
    for qa in locomo_report.qa_results:
        report.results.append(
            BenchmarkResult(
                scenario_id=f"qa_{qa.question_id}",
                lens=lens,
                passed=qa.correct,
                score=qa.score,
                notes=qa.notes[:300],
                tokens_in=qa.tokens_in,
                tokens_out=qa.tokens_out,
                cost_usd=qa.cost_usd,
                duration_ms=qa.duration_ms,
            )
        )

    return report


def _stub_report(name: str, lens: LensConfig, reason: str) -> BenchmarkReport:
    """Placeholder report for benchmarks not yet implemented."""
    report = BenchmarkReport(benchmark_name=name, lens=lens)
    return report


def run_all(
    driver: LLMDriver,
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    *,
    limit: int | None = None,
) -> list[BenchmarkReport]:
    """Run every available benchmark with the given lens config."""
    reports: list[BenchmarkReport] = []
    for name in ["cp", "longmemeval", "locomo", "msc", "ruler"]:
        reports.append(
            run_benchmark(name, driver, lens, skopus_dir, vault_dir=vault_dir, limit=limit)
        )
    return reports


def run_ablation(
    driver: LLMDriver,
    benchmark_name: str,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    *,
    limit: int | None = None,
    judge_driver: LLMDriver | None = None,
    scoring: str = "keyword",
    parallel: int = 1,
) -> dict[LensConfig, BenchmarkReport]:
    """Run a single benchmark across all 5 lens configurations."""
    results: dict[LensConfig, BenchmarkReport] = {}
    for lens in LensConfig.all_configs():
        results[lens] = run_benchmark(
            benchmark_name,
            driver,
            lens,
            skopus_dir,
            vault_dir=vault_dir,
            limit=limit,
            judge_driver=judge_driver,
            scoring=scoring,
            parallel=parallel,
        )
    return results


def save_report(
    report: BenchmarkReport | list[BenchmarkReport] | dict,
    results_dir: Path | None = None,
) -> Path:
    """Persist a report or collection of reports to bench/results/ as JSON."""
    target_dir = results_dir or bench_results_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target_dir / f"skopus-bench-{timestamp}.json"

    if isinstance(report, BenchmarkReport):
        payload = _report_to_dict(report)
    elif isinstance(report, list):
        payload = {"reports": [_report_to_dict(r) for r in report]}
    elif isinstance(report, dict):
        payload = {"ablation": {lens.value: _report_to_dict(r) for lens, r in report.items()}}
    else:
        raise TypeError(f"unsupported report type: {type(report)}")

    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def _report_to_dict(report: BenchmarkReport) -> dict:
    return {
        "benchmark": report.benchmark_name,
        "lens": report.lens.value,
        "total": report.total,
        "passed": report.passed,
        "accuracy": round(report.accuracy, 4),
        "mean_score": round(report.mean_score, 4),
        "total_tokens": report.total_tokens,
        "total_cost_usd": round(report.total_cost_usd, 4),
        "results": [asdict(r) for r in report.results],
    }


def format_markdown_report(
    ablation: dict[LensConfig, BenchmarkReport],
    benchmark_name: str,
) -> str:
    """Render an ablation result as a markdown comparison table."""
    lines = [
        f"# {benchmark_name} — Ablation Results",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "| Lens config | Passed | Total | Accuracy | Mean score | Δ vs vanilla | Tokens | Cost (USD) |",
        "|---|---|---|---|---|---|---|---|",
    ]

    baseline_acc = ablation[LensConfig.VANILLA].accuracy if LensConfig.VANILLA in ablation else 0.0
    for lens in LensConfig.all_configs():
        if lens not in ablation:
            continue
        r = ablation[lens]
        delta = r.accuracy - baseline_acc
        delta_str = f"+{delta:.1%}" if delta > 0 else f"{delta:.1%}"
        lines.append(
            f"| {lens.display_name} | {r.passed} | {r.total} | "
            f"{r.accuracy:.1%} | {r.mean_score:.3f} | {delta_str} | "
            f"{r.total_tokens:,} | ${r.total_cost_usd:.4f} |"
        )

    return "\n".join(lines) + "\n"
