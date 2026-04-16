"""Tests for the LongMemEval benchmark runner."""

import json
from pathlib import Path

import pytest

from bench.config import LensConfig
from bench.driver import MockDriver
from bench.longmemeval.runner import (
    LMEEntry,
    LMEReport,
    QAResult,
    RetrievalResult,
    _sessions_to_docs,
    evaluate_retrieval_entry,
    format_longmemeval_report,
    load_longmemeval,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_entry(
    question_id: str = "q-1",
    question_type: str = "single-session",
    question: str = "What is my dog's name?",
    answer: str = "Buddy",
    answer_session_ids: list[str] | None = None,
    haystack_session_ids: list[str] | None = None,
    haystack_sessions: list[list[dict]] | None = None,
) -> LMEEntry:
    """Build a small synthetic LMEEntry for testing."""
    if answer_session_ids is None:
        answer_session_ids = ["s1"]
    if haystack_session_ids is None:
        haystack_session_ids = ["s1", "s2", "s3"]
    if haystack_sessions is None:
        haystack_sessions = [
            [
                {"role": "user", "content": "My dog's name is Buddy."},
                {"role": "assistant", "content": "That's a great name!"},
            ],
            [
                {"role": "user", "content": "I went hiking yesterday."},
                {"role": "assistant", "content": "Nice! Where?"},
            ],
            [
                {"role": "user", "content": "I like coffee."},
                {"role": "assistant", "content": "What kind?"},
            ],
        ]
    return LMEEntry(
        question_id=question_id,
        question_type=question_type,
        question=question,
        question_date="2024-01-01",
        answer=answer,
        answer_session_ids=answer_session_ids,
        haystack_dates=["2024-01-01", "2024-01-02", "2024-01-03"],
        haystack_session_ids=haystack_session_ids,
        haystack_sessions=haystack_sessions,
    )


# ---------------------------------------------------------------------------
# load_longmemeval
# ---------------------------------------------------------------------------

class TestLoadLongmemeval:
    def test_loads_and_parses_entries(self, tmp_path: Path):
        data = [
            {
                "question_id": "q-1",
                "question_type": "single-session",
                "question": "What is my dog's name?",
                "question_date": "2024-01-15",
                "answer": "Buddy",
                "answer_session_ids": ["s1"],
                "haystack_dates": ["2024-01-01"],
                "haystack_session_ids": ["s1"],
                "haystack_sessions": [
                    [{"role": "user", "content": "My dog Buddy is great."}]
                ],
            },
            {
                "question_id": "q-2",
                "question_type": "multi-session",
                "question": "Where do I work?",
                "answer": "Acme Corp",
                "answer_session_ids": ["s2", "s3"],
                "haystack_session_ids": ["s2", "s3"],
                "haystack_sessions": [
                    [{"role": "user", "content": "I work at Acme Corp."}],
                    [{"role": "user", "content": "My office is on 5th floor."}],
                ],
            },
        ]
        path = tmp_path / "lme_test.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        entries = load_longmemeval(path)

        assert len(entries) == 2
        assert all(isinstance(e, LMEEntry) for e in entries)
        assert entries[0].question_id == "q-1"
        assert entries[0].answer == "Buddy"
        assert entries[1].question_type == "multi-session"
        assert entries[1].answer_session_ids == ["s2", "s3"]

    def test_handles_missing_optional_fields(self, tmp_path: Path):
        """question_date and haystack_dates are optional in the schema."""
        data = [
            {
                "question_id": "q-opt",
                "question_type": "single-session",
                "question": "Test?",
                "answer": "Yes",
                "answer_session_ids": ["s1"],
                "haystack_session_ids": ["s1"],
                "haystack_sessions": [[{"role": "user", "content": "test"}]],
            }
        ]
        path = tmp_path / "lme_optional.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        entries = load_longmemeval(path)
        assert entries[0].question_date == ""
        assert entries[0].haystack_dates == []


# ---------------------------------------------------------------------------
# _sessions_to_docs
# ---------------------------------------------------------------------------

class TestSessionsToDocs:
    def test_extracts_user_turns_only(self):
        entry = _make_entry()
        docs = _sessions_to_docs(entry)

        # 3 sessions, all have user turns
        assert len(docs) == 3
        # Each doc is (session_id, text)
        ids = [d[0] for d in docs]
        assert ids == ["s1", "s2", "s3"]

        # First session should contain user turn only, not assistant turn
        assert "My dog's name is Buddy." in docs[0][1]
        assert "That's a great name!" not in docs[0][1]

    def test_deduplicates_session_ids(self):
        """When haystack_session_ids has duplicates, only the first is kept."""
        entry = _make_entry(
            haystack_session_ids=["s1", "s1", "s2"],
            haystack_sessions=[
                [{"role": "user", "content": "First"}],
                [{"role": "user", "content": "Duplicate"}],
                [{"role": "user", "content": "Second"}],
            ],
        )
        docs = _sessions_to_docs(entry)

        assert len(docs) == 2
        ids = [d[0] for d in docs]
        assert ids == ["s1", "s2"]
        # The first occurrence wins
        assert "First" in docs[0][1]
        assert "Duplicate" not in docs[0][1]

    def test_skips_empty_sessions(self):
        """Sessions with no user turns produce empty text and are skipped."""
        entry = _make_entry(
            haystack_session_ids=["s1", "s2"],
            haystack_sessions=[
                [{"role": "assistant", "content": "Hello!"}],  # no user turn
                [{"role": "user", "content": "Hi there."}],
            ],
        )
        docs = _sessions_to_docs(entry)

        assert len(docs) == 1
        assert docs[0][0] == "s2"


# ---------------------------------------------------------------------------
# evaluate_retrieval_entry
# ---------------------------------------------------------------------------

class TestEvaluateRetrievalEntry:
    def test_retrieves_correct_session(self):
        """With a small haystack, the answer session should appear in top-5."""
        entry = _make_entry()
        result = evaluate_retrieval_entry(entry)

        assert isinstance(result, RetrievalResult)
        assert result.question_id == "q-1"
        assert result.question_type == "single-session"
        # The question "What is my dog's name?" should match
        # the session containing "My dog's name is Buddy."
        assert result.recall_any_5 == 1.0

    def test_recall_scores_are_binary(self):
        """Each recall score is either 0.0 or 1.0."""
        entry = _make_entry()
        result = evaluate_retrieval_entry(entry)

        assert result.recall_any_5 in (0.0, 1.0)
        assert result.recall_any_10 in (0.0, 1.0)
        assert result.recall_all_5 in (0.0, 1.0)
        assert result.recall_all_10 in (0.0, 1.0)

    def test_returns_zeros_when_no_docs(self):
        """Entry with no valid docs (no user turns) returns zero recall."""
        entry = _make_entry(
            haystack_session_ids=["s1"],
            haystack_sessions=[
                [{"role": "assistant", "content": "only assistant"}],
            ],
        )
        result = evaluate_retrieval_entry(entry)

        assert result.recall_any_5 == 0.0
        assert result.recall_any_10 == 0.0
        assert result.recall_all_5 == 0.0
        assert result.recall_all_10 == 0.0


# ---------------------------------------------------------------------------
# format_longmemeval_report
# ---------------------------------------------------------------------------

class TestFormatLongmemevalReport:
    def test_empty_report_produces_header(self):
        report = LMEReport()
        md = format_longmemeval_report(report)

        assert "# LongMemEval Results" in md
        # No tables if no results
        assert "Retrieval" not in md
        assert "QA Accuracy" not in md

    def test_retrieval_only_report(self):
        report = LMEReport(
            retrieval_results=[
                RetrievalResult("q-1", "single-session", 1.0, 1.0, 1.0, 1.0),
                RetrievalResult("q-2", "multi-session", 0.0, 1.0, 0.0, 0.0),
            ]
        )
        md = format_longmemeval_report(report)

        assert "## Retrieval" in md
        assert "R@5:" in md
        assert "R@10:" in md
        # Table headers
        assert "| Question type |" in md
        # Both types should appear
        assert "single-session" in md
        assert "multi-session" in md
        # No QA section
        assert "QA Accuracy" not in md

    def test_qa_report_section(self):
        report = LMEReport(
            qa_results=[
                QAResult("q-1", "single-session", LensConfig.FULL, True, 1.0, "correct"),
                QAResult("q-2", "single-session", LensConfig.FULL, False, 0.0, "wrong"),
            ]
        )
        md = format_longmemeval_report(report, lens=LensConfig.FULL)

        assert "## QA Accuracy" in md
        assert "full skopus" in md  # display_name for FULL
        assert "Overall: 50.0%" in md
        assert "| single-session |" in md

    def test_combined_report(self):
        report = LMEReport(
            retrieval_results=[
                RetrievalResult("q-1", "single-session", 1.0, 1.0, 1.0, 1.0),
            ],
            qa_results=[
                QAResult("q-1", "single-session", LensConfig.CHARTER, True, 0.9, "good"),
            ],
        )
        md = format_longmemeval_report(report, lens=LensConfig.CHARTER)

        assert "## Retrieval" in md
        assert "## QA Accuracy" in md
        assert "+charter" in md


# ---------------------------------------------------------------------------
# LMEReport properties
# ---------------------------------------------------------------------------

class TestLMEReportProperties:
    def test_recall_any_5_average(self):
        report = LMEReport(
            retrieval_results=[
                RetrievalResult("q-1", "a", 1.0, 1.0, 1.0, 1.0),
                RetrievalResult("q-2", "a", 0.0, 1.0, 0.0, 0.0),
            ]
        )
        assert report.recall_any_5 == pytest.approx(0.5)
        assert report.recall_any_10 == pytest.approx(1.0)

    def test_qa_accuracy(self):
        report = LMEReport(
            qa_results=[
                QAResult("q-1", "a", LensConfig.FULL, True, 1.0, ""),
                QAResult("q-2", "a", LensConfig.FULL, True, 0.8, ""),
                QAResult("q-3", "a", LensConfig.FULL, False, 0.0, ""),
            ]
        )
        assert report.qa_accuracy == pytest.approx(2 / 3)

    def test_qa_accuracy_by_type(self):
        report = LMEReport(
            qa_results=[
                QAResult("q-1", "single", LensConfig.FULL, True, 1.0, ""),
                QAResult("q-2", "single", LensConfig.FULL, False, 0.0, ""),
                QAResult("q-3", "multi", LensConfig.FULL, True, 1.0, ""),
            ]
        )
        by_type = report.qa_accuracy_by_type()
        assert by_type["single"] == pytest.approx(0.5)
        assert by_type["multi"] == pytest.approx(1.0)

    def test_empty_report_returns_zeros(self):
        report = LMEReport()
        assert report.recall_any_5 == 0.0
        assert report.recall_any_10 == 0.0
        assert report.qa_accuracy == 0.0
