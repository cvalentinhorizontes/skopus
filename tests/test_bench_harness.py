"""Tests for the unified benchmark harness."""

from pathlib import Path

import pytest

from bench.config import BenchmarkReport, LensConfig
from bench.driver import AnthropicDriver, MockDriver, pick_driver
from bench.harness import (
    format_markdown_report,
    list_benchmarks,
    run_ablation,
    run_all,
    run_benchmark,
    save_report,
)


def test_list_benchmarks_returns_dict():
    benchmarks = list_benchmarks()
    assert isinstance(benchmarks, dict)
    assert "cp" in benchmarks
    assert "correction-persistence" in benchmarks
    assert "longmemeval" in benchmarks
    assert "locomo" in benchmarks
    assert "msc" in benchmarks
    assert "ruler" in benchmarks


def test_pick_driver_returns_mock_when_anthropic_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    driver = pick_driver("auto")
    # Should fall back to mock when anthropic is unavailable
    assert driver.available() is True


def test_mock_driver_always_available():
    driver = MockDriver()
    assert driver.available() is True


def test_mock_driver_returns_canned_response():
    driver = MockDriver(responses={"trigger": "this is the canned reply"})
    response = driver.run("system", "user says trigger")
    assert response.text == "this is the canned reply"


def test_run_benchmark_cp_with_mock(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    skopus_dir.mkdir()
    driver = MockDriver()
    report = run_benchmark(
        name="cp",
        driver=driver,
        lens=LensConfig.VANILLA,
        skopus_dir=skopus_dir,
        limit=5,
    )
    assert report.total == 5
    assert report.benchmark_name == "correction-persistence"


def test_run_benchmark_stub_returns_empty_report(tmp_path):
    """LongMemEval/LoCoMo/MSC/RULER are stubs in v0.1.0-alpha — empty reports."""
    skopus_dir = tmp_path / ".skopus"
    skopus_dir.mkdir()
    driver = MockDriver()
    for name in ["longmemeval", "locomo", "msc", "ruler"]:
        report = run_benchmark(
            name=name,
            driver=driver,
            lens=LensConfig.VANILLA,
            skopus_dir=skopus_dir,
        )
        assert report.benchmark_name == name
        assert report.total == 0


def test_run_benchmark_raises_on_unknown_name(tmp_path):
    with pytest.raises(KeyError):
        run_benchmark(
            name="nonexistent",
            driver=MockDriver(),
            lens=LensConfig.VANILLA,
            skopus_dir=tmp_path,
        )


def test_run_ablation_produces_5_reports(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "charter").mkdir(parents=True)
    driver = MockDriver()
    results = run_ablation(
        driver=driver,
        benchmark_name="cp",
        skopus_dir=skopus_dir,
        limit=3,
    )
    assert len(results) == 5
    assert set(results.keys()) == set(LensConfig.all_configs())
    for lens, report in results.items():
        assert report.lens == lens
        assert report.total == 3


def test_run_all_produces_one_report_per_benchmark(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    skopus_dir.mkdir()
    driver = MockDriver()
    reports = run_all(
        driver=driver,
        lens=LensConfig.VANILLA,
        skopus_dir=skopus_dir,
        limit=2,
    )
    assert len(reports) == 5
    names = {r.benchmark_name for r in reports}
    assert "correction-persistence" in names


def test_format_markdown_report_renders_ablation(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    skopus_dir.mkdir()
    driver = MockDriver()
    ablation = run_ablation(
        driver=driver,
        benchmark_name="cp",
        skopus_dir=skopus_dir,
        limit=2,
    )
    markdown = format_markdown_report(ablation, "cp")
    assert "# cp — Ablation Results" in markdown
    assert "| Lens config |" in markdown
    assert "vanilla" in markdown
    assert "full skopus" in markdown


def test_save_report_writes_json(tmp_path):
    skopus_dir = tmp_path / ".skopus"
    skopus_dir.mkdir()
    driver = MockDriver()
    report = run_benchmark(
        name="cp",
        driver=driver,
        lens=LensConfig.VANILLA,
        skopus_dir=skopus_dir,
        limit=2,
    )
    results_dir = tmp_path / "bench_results"
    path = save_report(report, results_dir=results_dir)
    assert path.exists()
    content = path.read_text()
    assert "correction-persistence" in content
    assert "vanilla" in content


def test_benchmark_report_aggregates():
    from bench.config import BenchmarkResult

    report = BenchmarkReport(benchmark_name="test", lens=LensConfig.VANILLA)
    report.results.append(
        BenchmarkResult(scenario_id="t1", lens=LensConfig.VANILLA, passed=True, score=1.0)
    )
    report.results.append(
        BenchmarkResult(scenario_id="t2", lens=LensConfig.VANILLA, passed=False, score=0.3)
    )
    assert report.total == 2
    assert report.passed == 1
    assert report.accuracy == 0.5
    assert abs(report.mean_score - 0.65) < 0.01


def test_anthropic_driver_not_available_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    driver = AnthropicDriver()
    assert driver.available() is False
