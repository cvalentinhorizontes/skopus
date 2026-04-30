"""LongMemEval benchmark runner.

Tests both retrieval quality (R@5, R@10) and end-to-end QA accuracy
across Skopus lens configurations.

Retrieval: ChromaDB with all-MiniLM-L6-v2 (same as MemPalace baseline)
QA: LLM generates answer from top-K retrieved sessions, LLM judge scores.

MemPalace published numbers (retrieval R@5):
  - Raw semantic search: 96.6%
  - Hybrid v4 (held-out): 98.4%
  - Hybrid + LLM rerank: >=99%

Paper published numbers (QA accuracy with GPT-4o):
  - Oracle (evidence only): 91.8%
  - Full history (long-context): 64.0%
  - RAG top-5: 71.4%
"""

from __future__ import annotations

import contextlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import chromadb

from bench.config import LensConfig
from bench.context import build_system_prompt
from bench.driver import LLMDriver


@dataclass
class LMEEntry:
    question_id: str
    question_type: str
    question: str
    question_date: str
    answer: str
    answer_session_ids: list[str]
    haystack_dates: list[str]
    haystack_session_ids: list[str]
    haystack_sessions: list[list[dict]]


@dataclass
class RetrievalResult:
    question_id: str
    question_type: str
    recall_any_5: float
    recall_any_10: float
    recall_all_5: float
    recall_all_10: float


@dataclass
class QAResult:
    question_id: str
    question_type: str
    lens: LensConfig
    correct: bool
    score: float
    notes: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0


@dataclass
class LMEReport:
    retrieval_results: list[RetrievalResult] = field(default_factory=list)
    qa_results: list[QAResult] = field(default_factory=list)

    @property
    def recall_any_5(self) -> float:
        if not self.retrieval_results:
            return 0.0
        return sum(r.recall_any_5 for r in self.retrieval_results) / len(self.retrieval_results)

    @property
    def recall_any_10(self) -> float:
        if not self.retrieval_results:
            return 0.0
        return sum(r.recall_any_10 for r in self.retrieval_results) / len(self.retrieval_results)

    @property
    def qa_accuracy(self) -> float:
        if not self.qa_results:
            return 0.0
        return sum(1 for r in self.qa_results if r.correct) / len(self.qa_results)

    def qa_accuracy_by_type(self) -> dict[str, float]:
        from collections import defaultdict

        by_type: dict[str, list[bool]] = defaultdict(list)
        for r in self.qa_results:
            by_type[r.question_type].append(r.correct)
        return {t: sum(v) / len(v) for t, v in by_type.items()}

    def retrieval_by_type(self) -> dict[str, float]:
        from collections import defaultdict

        by_type: dict[str, list[float]] = defaultdict(list)
        for r in self.retrieval_results:
            by_type[r.question_type].append(r.recall_any_5)
        return {t: sum(v) / len(v) for t, v in by_type.items()}


def load_longmemeval(path: Path) -> list[LMEEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = []
    for d in raw:
        entries.append(
            LMEEntry(
                question_id=d["question_id"],
                question_type=d["question_type"],
                question=d["question"],
                question_date=d.get("question_date", ""),
                answer=d["answer"],
                answer_session_ids=d["answer_session_ids"],
                haystack_dates=d.get("haystack_dates", []),
                haystack_session_ids=d["haystack_session_ids"],
                haystack_sessions=d["haystack_sessions"],
            )
        )
    return entries


def _sessions_to_docs(entry: LMEEntry) -> list[tuple[str, str]]:
    """Convert haystack sessions to (session_id, text) pairs.
    Same approach as MemPalace: user turns only, joined by newlines.
    Deduplicates by session ID (some entries have repeated IDs)."""
    seen: set[str] = set()
    docs = []
    for sid, session in zip(entry.haystack_session_ids, entry.haystack_sessions, strict=False):
        if sid in seen:
            continue
        seen.add(sid)
        user_turns = []
        for turn in session:
            if turn.get("role") == "user":
                user_turns.append(turn.get("content", ""))
        text = "\n".join(user_turns)
        if text.strip():
            docs.append((sid, text))
    return docs


def evaluate_retrieval_entry(entry: LMEEntry) -> RetrievalResult:
    """Run retrieval for a single LongMemEval entry using ChromaDB."""
    client = chromadb.Client()
    col_name = f"lme_{entry.question_id.replace(' ', '_')[:50]}"
    # Clean up if exists from prior run
    with contextlib.suppress(Exception):
        client.delete_collection(col_name)
    collection = client.create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"},
    )

    docs = _sessions_to_docs(entry)
    if not docs:
        return RetrievalResult(entry.question_id, entry.question_type, 0, 0, 0, 0)

    ids = [d[0] for d in docs]
    texts = [d[1] for d in docs]
    collection.add(ids=ids, documents=texts)

    results = collection.query(query_texts=[entry.question], n_results=min(50, len(docs)))
    ranked_ids = results["ids"][0] if results["ids"] else []
    # Cleanup
    with contextlib.suppress(Exception):
        client.delete_collection(col_name)

    correct = set(entry.answer_session_ids)

    def recall_any_at_k(k: int) -> float:
        top_k = set(ranked_ids[:k])
        return 1.0 if any(c in top_k for c in correct) else 0.0

    def recall_all_at_k(k: int) -> float:
        top_k = set(ranked_ids[:k])
        return 1.0 if all(c in top_k for c in correct) else 0.0

    return RetrievalResult(
        question_id=entry.question_id,
        question_type=entry.question_type,
        recall_any_5=recall_any_at_k(5),
        recall_any_10=recall_any_at_k(10),
        recall_all_5=recall_all_at_k(5),
        recall_all_10=recall_all_at_k(10),
    )


_QA_JUDGE_SYSTEM = """You judge whether an AI assistant's answer to a memory question is correct.

You receive:
- QUESTION: what was asked
- REFERENCE ANSWER: the correct answer
- ASSISTANT ANSWER: what the assistant said

Respond with EXACTLY one JSON object:
{"correct": true/false, "score": 0.0-1.0, "reasoning": "one sentence"}

Rules:
- correct=true if the assistant's answer contains the key information from the reference
- Paraphrasing is fine. Exact wording is NOT required.
- If the reference says "Business Administration" and the assistant says "BA in Business Admin", that's correct.
- If the assistant says "I don't know" or gives wrong information, that's incorrect.
- For temporal questions, allow small date errors (off by one day)."""


def evaluate_qa_entry(
    entry: LMEEntry,
    driver: LLMDriver,
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    top_k: int = 5,
) -> QAResult:
    """Run QA for a single entry: retrieve top-K, generate answer, judge."""
    # Retrieve top-K sessions
    client = chromadb.Client()
    col_name = f"qa_{entry.question_id.replace(' ', '_')[:50]}"
    with contextlib.suppress(Exception):
        client.delete_collection(col_name)
    collection = client.create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"},
    )

    docs = _sessions_to_docs(entry)
    if not docs:
        return QAResult(entry.question_id, entry.question_type, lens, False, 0.0, "no docs")

    ids = [d[0] for d in docs]
    texts = [d[1] for d in docs]
    collection.add(ids=ids, documents=texts)

    results = collection.query(query_texts=[entry.question], n_results=min(top_k, len(docs)))
    retrieved_texts = results["documents"][0] if results["documents"] else []

    # Build context with retrieved sessions
    context_block = "\n\n---\n\n".join(
        f"[Session {i + 1}]\n{t}" for i, t in enumerate(retrieved_texts)
    )

    # Build system prompt with Skopus lens
    system_prompt = build_system_prompt(
        lens=lens,
        skopus_dir=skopus_dir,
        vault_dir=vault_dir,
        task_hint=(
            f"You are answering a question about past conversations. "
            f"Here are the most relevant past sessions:\n\n{context_block}"
        ),
    )

    user_prompt = (
        f"Based on the conversation history provided, answer this question concisely:\n\n"
        f"{entry.question}"
    )

    response = driver.run(system_prompt, user_prompt, max_tokens=512)

    return QAResult(
        question_id=entry.question_id,
        question_type=entry.question_type,
        lens=lens,
        correct=False,  # placeholder, filled by judge
        score=0.0,
        notes=response.text[:500],
        tokens_in=response.tokens_in,
        tokens_out=response.tokens_out,
        cost_usd=response.cost_usd,
        duration_ms=response.duration_ms,
    )


def judge_qa_result(
    result: QAResult,
    reference_answer: str,
    question: str,
    judge_driver: LLMDriver,
) -> QAResult:
    """Use LLM judge to evaluate a QA result."""
    user_prompt = (
        f"QUESTION: {question}\n\n"
        f"REFERENCE ANSWER: {reference_answer}\n\n"
        f"ASSISTANT ANSWER: {result.notes}"
    )

    judge_response = judge_driver.run(_QA_JUDGE_SYSTEM, user_prompt, max_tokens=256)

    try:
        text = judge_response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        result.correct = bool(parsed.get("correct", False))
        result.score = float(parsed.get("score", 0.0))
        result.notes = f"{parsed.get('reasoning', '')} | answer: {result.notes[:200]}"
    except (json.JSONDecodeError, KeyError, ValueError):
        result.correct = False
        result.score = 0.0
        result.notes = f"judge_parse_error | answer: {result.notes[:200]}"

    return result


def run_longmemeval(
    data_path: Path,
    driver: LLMDriver,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    *,
    judge_driver: LLMDriver | None = None,
    lens: LensConfig = LensConfig.FULL,
    limit: int | None = None,
    top_k: int = 5,
    parallel: int = 5,
    retrieval_only: bool = False,
) -> LMEReport:
    """Run the LongMemEval benchmark.

    Args:
        retrieval_only: If True, only run retrieval eval (no LLM calls for QA).
        parallel: concurrent workers for retrieval and QA.
    """
    entries = load_longmemeval(data_path)
    if limit:
        entries = entries[:limit]

    report = LMEReport()

    # Phase 1: Retrieval evaluation (always runs)
    if parallel <= 1:
        for entry in entries:
            report.retrieval_results.append(evaluate_retrieval_entry(entry))
    else:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {pool.submit(evaluate_retrieval_entry, e): e.question_id for e in entries}
            results_map: dict[str, RetrievalResult] = {}
            for future in as_completed(futures):
                r = future.result()
                results_map[r.question_id] = r
        for entry in entries:
            report.retrieval_results.append(results_map[entry.question_id])

    if retrieval_only:
        return report

    # Phase 2: QA evaluation
    if not judge_driver:
        judge_driver = driver

    def _run_and_judge(entry: LMEEntry) -> QAResult:
        result = evaluate_qa_entry(entry, driver, lens, skopus_dir, vault_dir, top_k)
        return judge_qa_result(result, entry.answer, entry.question, judge_driver)

    if parallel <= 1:
        for entry in entries:
            report.qa_results.append(_run_and_judge(entry))
    else:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {pool.submit(_run_and_judge, e): e.question_id for e in entries}
            results_map_qa: dict[str, QAResult] = {}
            for future in as_completed(futures):
                r = future.result()
                results_map_qa[r.question_id] = r
        for entry in entries:
            report.qa_results.append(results_map_qa[entry.question_id])

    return report


def format_longmemeval_report(report: LMEReport, lens: LensConfig | None = None) -> str:
    """Format results as markdown."""
    lines = [
        "# LongMemEval Results",
        "",
    ]

    if report.retrieval_results:
        lines.extend(
            [
                "## Retrieval (ChromaDB + all-MiniLM-L6-v2)",
                "",
                f"**R@5: {report.recall_any_5:.1%}** | R@10: {report.recall_any_10:.1%}",
                "",
                "| Question type | Count | R@5 | R@10 |",
                "|---|---|---|---|",
            ]
        )
        by_type = report.retrieval_by_type()
        type_counts = Counter(r.question_type for r in report.retrieval_results)
        for t in sorted(by_type.keys()):
            r10_by_type: dict[str, list[float]] = {}
            for r in report.retrieval_results:
                r10_by_type.setdefault(r.question_type, []).append(r.recall_any_10)
            r10 = sum(r10_by_type.get(t, [0])) / max(len(r10_by_type.get(t, [1])), 1)
            lines.append(f"| {t} | {type_counts[t]} | {by_type[t]:.1%} | {r10:.1%} |")
        lines.append("")

    if report.qa_results:
        lens_label = lens.display_name if lens else "unknown"
        lines.extend(
            [
                f"## QA Accuracy (lens: {lens_label})",
                "",
                f"**Overall: {report.qa_accuracy:.1%}**",
                "",
                "| Question type | Count | Accuracy |",
                "|---|---|---|",
            ]
        )
        qa_by_type = report.qa_accuracy_by_type()
        qa_type_counts = Counter(r.question_type for r in report.qa_results)
        for t in sorted(qa_by_type.keys()):
            lines.append(f"| {t} | {qa_type_counts[t]} | {qa_by_type[t]:.1%} |")
        lines.append("")

    return "\n".join(lines)
