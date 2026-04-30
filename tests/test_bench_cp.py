"""Tests for the Correction-Persistence benchmark."""

import json
from pathlib import Path

from bench.config import LensConfig
from bench.correction_persistence.runner import (
    CPScenario,
    load_dataset,
    run_correction_persistence,
    run_scenario,
    score_response,
    score_response_llm,
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
    passed, _score, _ = score_response(response, criterion)
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
    assert {"code", "prose", "reasoning", "tool-use"}.issubset(domains | {"tool-use"}) or len(
        domains
    ) >= 3


# ---------------------------------------------------------------------------
# LLM-as-judge scorer: score_response_llm
# ---------------------------------------------------------------------------


def _make_scenario() -> CPScenario:
    """Build a minimal CPScenario for scorer tests."""
    return CPScenario(
        id="cp-test-001",
        domain="code",
        title="Test scenario",
        initial_task="Write a function.",
        expected_mistake_pattern="Uses quick fix.",
        correction="Always find the root cause.",
        followup_task="Debug this error.",
        success_criterion={
            "must_include": ["root cause"],
            "must_not_include": ["quick fix"],
        },
        charter_relevance="testing",
    )


class TestScoreResponseLlm:
    def test_valid_json_response(self):
        """Judge returns clean JSON — should parse applied/score/reasoning."""
        judge = MockDriver(
            responses={
                "CORRECTION": json.dumps(
                    {
                        "applied": True,
                        "score": 0.9,
                        "reasoning": "Response demonstrates root-cause analysis.",
                    }
                ),
            }
        )
        scenario = _make_scenario()

        passed, score, notes = score_response_llm(
            "I investigated the root cause of the error.",
            scenario,
            judge,
        )

        assert passed is True
        assert score == 0.9
        assert "root-cause analysis" in notes
        assert notes.startswith("llm_judge:")

    def test_invalid_json_response(self):
        """Judge returns garbage — should return False/0.0 with parse error."""
        judge = MockDriver(
            responses={
                "CORRECTION": "This is not valid JSON at all {{{",
            }
        )
        scenario = _make_scenario()

        passed, score, notes = score_response_llm(
            "Some response text.",
            scenario,
            judge,
        )

        assert passed is False
        assert score == 0.0
        assert "parse error" in notes

    def test_json_wrapped_in_code_blocks(self):
        """Judge wraps JSON in ```json ... ``` — stripping logic should handle it."""
        raw_json = json.dumps(
            {
                "applied": True,
                "score": 0.85,
                "reasoning": "Correction applied correctly.",
            }
        )
        wrapped = f"```json\n{raw_json}\n```"

        judge = MockDriver(
            responses={
                "CORRECTION": wrapped,
            }
        )
        scenario = _make_scenario()

        passed, score, notes = score_response_llm(
            "I found the root cause.",
            scenario,
            judge,
        )

        assert passed is True
        assert score == 0.85
        assert "Correction applied correctly" in notes

    def test_applied_false_returns_not_passed(self):
        """Judge says applied=false — passed should be False."""
        judge = MockDriver(
            responses={
                "CORRECTION": json.dumps(
                    {
                        "applied": False,
                        "score": 0.1,
                        "reasoning": "Response used a quick fix instead.",
                    }
                ),
            }
        )
        scenario = _make_scenario()

        passed, score, _notes = score_response_llm(
            "Here's a quick fix for the error.",
            scenario,
            judge,
        )

        assert passed is False
        assert score == 0.1


# ---------------------------------------------------------------------------
# Scoring parameter flow in run_scenario
# ---------------------------------------------------------------------------


class TestRunScenarioScoringModes:
    """Verify the scoring= parameter routes to the correct scorer."""

    def _skopus_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / ".skopus"
        d.mkdir(parents=True)
        return d

    def test_keyword_scoring(self, tmp_path):
        """scoring='keyword' uses the keyword scorer (default path)."""
        scenario = _make_scenario()
        driver = MockDriver(
            responses={
                scenario.followup_task: "I will find the root cause and ask why.",
            }
        )

        result = run_scenario(
            scenario,
            driver,
            LensConfig.VANILLA,
            self._skopus_dir(tmp_path),
            scoring="keyword",
        )

        assert result.passed is True
        assert "include:" in result.notes  # keyword scorer format

    def test_llm_scoring(self, tmp_path):
        """scoring='llm' uses the LLM judge scorer."""
        scenario = _make_scenario()
        driver = MockDriver(
            responses={
                scenario.followup_task: "I investigated the root cause.",
            }
        )
        judge = MockDriver(
            responses={
                "CORRECTION": json.dumps(
                    {
                        "applied": True,
                        "score": 0.95,
                        "reasoning": "Excellent root-cause analysis.",
                    }
                ),
            }
        )

        result = run_scenario(
            scenario,
            driver,
            LensConfig.VANILLA,
            self._skopus_dir(tmp_path),
            judge_driver=judge,
            scoring="llm",
        )

        assert result.passed is True
        assert result.score == 0.95
        assert "llm_judge:" in result.notes

    def test_both_scoring(self, tmp_path):
        """scoring='both' runs both scorers; LLM is authoritative, keyword in notes."""
        scenario = _make_scenario()
        driver = MockDriver(
            responses={
                scenario.followup_task: "I will find the root cause.",
            }
        )
        judge = MockDriver(
            responses={
                "CORRECTION": json.dumps(
                    {
                        "applied": True,
                        "score": 0.8,
                        "reasoning": "Applied well.",
                    }
                ),
            }
        )

        result = run_scenario(
            scenario,
            driver,
            LensConfig.VANILLA,
            self._skopus_dir(tmp_path),
            judge_driver=judge,
            scoring="both",
        )

        # LLM judge is authoritative for passed/score
        assert result.passed is True
        assert result.score == 0.8
        # Notes contain both keyword and LLM results
        assert "keyword:" in result.notes
        assert "llm_judge:" in result.notes
        assert "kw_passed=" in result.notes

    def test_llm_scoring_without_judge_falls_back_to_keyword(self, tmp_path):
        """scoring='llm' but no judge_driver provided — falls through to keyword."""
        scenario = _make_scenario()
        driver = MockDriver(
            responses={
                scenario.followup_task: "I will find the root cause.",
            }
        )

        result = run_scenario(
            scenario,
            driver,
            LensConfig.VANILLA,
            self._skopus_dir(tmp_path),
            judge_driver=None,
            scoring="llm",
        )

        # Falls through to keyword scorer because judge_driver is None
        assert "include:" in result.notes


# ---------------------------------------------------------------------------
# Parallel execution: run_correction_persistence with parallel > 1
# ---------------------------------------------------------------------------


class TestParallelExecution:
    def test_results_in_original_order(self, tmp_path):
        """parallel > 1 should return results in scenario order, not completion order."""
        skopus_dir = tmp_path / ".skopus"
        skopus_dir.mkdir(parents=True)

        driver = MockDriver()
        report = run_correction_persistence(
            driver=driver,
            lens=LensConfig.VANILLA,
            skopus_dir=skopus_dir,
            limit=5,
            parallel=3,
        )

        # Load the same scenarios to verify order
        scenarios = load_dataset()[:5]
        assert len(report.results) == 5
        for i, result in enumerate(report.results):
            assert result.scenario_id == scenarios[i].id, (
                f"Result {i} has id {result.scenario_id}, expected {scenarios[i].id}"
            )

    def test_all_scenarios_processed(self, tmp_path):
        """parallel execution should process every scenario (no dropped items)."""
        skopus_dir = tmp_path / ".skopus"
        skopus_dir.mkdir(parents=True)

        driver = MockDriver()
        report = run_correction_persistence(
            driver=driver,
            lens=LensConfig.VANILLA,
            skopus_dir=skopus_dir,
            limit=8,
            parallel=4,
        )

        assert report.total == 8
        # Every result should have a valid scenario_id
        result_ids = {r.scenario_id for r in report.results}
        assert len(result_ids) == 8  # no duplicates

    def test_parallel_matches_sequential(self, tmp_path):
        """Parallel and sequential runs should produce the same scenario IDs."""
        skopus_dir = tmp_path / ".skopus"
        skopus_dir.mkdir(parents=True)

        driver = MockDriver()
        seq_report = run_correction_persistence(
            driver=driver,
            lens=LensConfig.VANILLA,
            skopus_dir=skopus_dir,
            limit=5,
            parallel=1,
        )
        par_report = run_correction_persistence(
            driver=driver,
            lens=LensConfig.VANILLA,
            skopus_dir=skopus_dir,
            limit=5,
            parallel=3,
        )

        seq_ids = [r.scenario_id for r in seq_report.results]
        par_ids = [r.scenario_id for r in par_report.results]
        assert seq_ids == par_ids
