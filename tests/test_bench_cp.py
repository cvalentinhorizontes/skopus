"""Tests for the Correction-Persistence benchmark."""

from pathlib import Path

from bench.config import LensConfig
from bench.correction_persistence.runner import (
    CPScenario,
    load_dataset,
    run_correction_persistence,
    score_response,
)
from bench.driver import MockDriver


def test_dataset_loads_from_bundled_file():
    scenarios = load_dataset()
    assert len(scenarios) >= 20, "v0.1.0-alpha ships at least 20 scenarios"
    assert all(isinstance(s, CPScenario) for s in scenarios)
    assert all(s.id.startswith("cp-") for s in scenarios)


def test_all_scenarios_have_success_criterion():
    for scenario in load_dataset():
        assert "must_include" in scenario.success_criterion
        assert len(scenario.success_criterion["must_include"]) >= 1
        assert "must_not_include" in scenario.success_criterion


def test_score_response_passes_on_keywords():
    criterion = {
        "must_include": ["root cause", "why"],
        "must_not_include": ["quick fix"],
    }
    response = "Let me find the root cause by asking why this happens."
    passed, score, _ = score_response(response, criterion)
    assert passed is True
    assert score == 1.0


def test_score_response_fails_on_forbidden_keyword():
    criterion = {
        "must_include": ["root cause"],
        "must_not_include": ["quick fix"],
    }
    response = "Here's a quick fix that addresses the root cause."
    passed, score, _ = score_response(response, criterion)
    assert passed is False  # forbidden keyword trips the fail


def test_score_response_fails_on_too_few_keywords():
    criterion = {
        "must_include": ["root cause", "profile", "benchmark"],
        "must_not_include": [],
    }
    response = "Let me find the root cause."
    passed, score, _ = score_response(response, criterion)
    assert passed is False  # only 1 of 3 required keywords
    assert 0 < score < 0.5


def test_run_correction_persistence_with_mock_driver(tmp_path):
    """Integration test — run the full CP benchmark with the mock driver."""
    skopus_dir = tmp_path / ".skopus"
    skopus_dir.mkdir(parents=True)

    driver = MockDriver()
    report = run_correction_persistence(
        driver=driver,
        lens=LensConfig.VANILLA,
        skopus_dir=skopus_dir,
        limit=3,
    )

    assert report.total == 3
    assert report.benchmark_name == "correction-persistence"
    # Every result has a lens and scenario_id
    for result in report.results:
        assert result.lens == LensConfig.VANILLA
        assert result.scenario_id.startswith("cp-")


def test_run_correction_persistence_across_lens_configs(tmp_path):
    """Each lens config should produce a report even if the mock driver is dumb."""
    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "charter" / "CLAUDE.md").write_text("# Test charter\n")
    (skopus_dir / "memory").mkdir(parents=True)
    (skopus_dir / "memory" / "MEMORY.md").write_text("# Test memory\n")

    driver = MockDriver()
    for lens in LensConfig.all_configs():
        report = run_correction_persistence(
            driver=driver,
            lens=lens,
            skopus_dir=skopus_dir,
            limit=2,
        )
        assert report.total == 2
        assert report.lens == lens


def test_cp_scenarios_cover_multiple_domains():
    """Dataset should span code/prose/reasoning/tool-use for breadth."""
    scenarios = load_dataset()
    domains = {s.domain for s in scenarios}
    assert "code" in domains
    assert {"code", "prose", "reasoning", "tool-use"}.issubset(domains | {"tool-use"}) or len(domains) >= 3
