"""LoCoMo benchmark runner.

Tests both retrieval quality (R@5, R@10) and end-to-end QA accuracy
across Skopus lens configurations.

LoCoMo (Snap Research, 2024) — Long Conversation Memory benchmark.
10 multi-session conversations, 1986 questions across 5 categories:
  - Cat 1: Single-hop (answer from one session)
  - Cat 2: Temporal (time-related questions)
  - Cat 3: Multi-hop (requires info from multiple sessions)
  - Cat 4: Open-domain knowledge (factual info about speakers)
  - Cat 5: Adversarial (unanswerable from context)

Retrieval: ChromaDB with all-MiniLM-L6-v2 (default embedding).
QA: LLM generates answer from top-K retrieved sessions, LLM judge scores.

Dataset source: desire2020/locomo-serialized on HuggingFace
(serialized version of the original adymaharana/locomo dataset).
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import chromadb

from bench.config import LensConfig
from bench.context import build_system_prompt
from bench.driver import LLMDriver

# LoCoMo category names (from the paper)
CATEGORY_NAMES: dict[int, str] = {
    1: "single-hop",
    2: "temporal",
    3: "multi-hop",
    4: "open-domain",
    5: "adversarial",
}


@dataclass
class LoCoMoQuestion:
    """A single question from the LoCoMo dataset."""

    conversation_id: str
    question_idx: int
    question: str
    answer: str
    category: int
    is_adversarial: bool
    evidence: list[str]  # e.g. ["D1:3", "D2:8"]

    @property
    def question_id(self) -> str:
        return f"{self.conversation_id}_q{self.question_idx}"

    @property
    def category_name(self) -> str:
        return CATEGORY_NAMES.get(self.category, f"cat-{self.category}")

    @property
    def evidence_session_ids(self) -> list[str]:
        """Extract session IDs from evidence refs like 'D1:3' -> 'D1'."""
        ids: list[str] = []
        for ev in self.evidence:
            match = re.match(r"(D\d+)", ev)
            if match:
                ids.append(match.group(1))
        return list(dict.fromkeys(ids))  # deduplicate, preserve order


@dataclass
class LoCoMoConversation:
    """A multi-session conversation with associated questions."""

    sample_id: str
    context: str
    questions: list[LoCoMoQuestion]
    speaker_a: str
    speaker_b: str
    sessions: list[tuple[str, str]] = field(default_factory=list)
    # (session_id like "D1", session_text)

    def __post_init__(self) -> None:
        if not self.sessions:
            self.sessions = _split_sessions(self.context)


@dataclass
class RetrievalResult:
    question_id: str
    category: int
    recall_any_5: float
    recall_any_10: float
    recall_all_5: float
    recall_all_10: float


@dataclass
class QAResult:
    question_id: str
    category: int
    lens: LensConfig
    correct: bool
    score: float
    notes: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0


@dataclass
class LoCoMoReport:
    retrieval_results: list[RetrievalResult] = field(default_factory=list)
    qa_results: list[QAResult] = field(default_factory=list)

    @property
    def recall_any_5(self) -> float:
        if not self.retrieval_results:
            return 0.0
        return sum(r.recall_any_5 for r in self.retrieval_results) / len(
            self.retrieval_results
        )

    @property
    def recall_any_10(self) -> float:
        if not self.retrieval_results:
            return 0.0
        return sum(r.recall_any_10 for r in self.retrieval_results) / len(
            self.retrieval_results
        )

    @property
    def qa_accuracy(self) -> float:
        if not self.qa_results:
            return 0.0
        return sum(1 for r in self.qa_results if r.correct) / len(self.qa_results)

    def qa_accuracy_by_category(self) -> dict[str, float]:
        by_cat: dict[str, list[bool]] = defaultdict(list)
        for r in self.qa_results:
            cat_name = CATEGORY_NAMES.get(r.category, f"cat-{r.category}")
            by_cat[cat_name].append(r.correct)
        return {t: sum(v) / len(v) for t, v in by_cat.items()}

    def retrieval_by_category(self) -> dict[str, float]:
        by_cat: dict[str, list[float]] = defaultdict(list)
        for r in self.retrieval_results:
            cat_name = CATEGORY_NAMES.get(r.category, f"cat-{r.category}")
            by_cat[cat_name].append(r.recall_any_5)
        return {t: sum(v) / len(v) for t, v in by_cat.items()}


def _split_sessions(context: str) -> list[tuple[str, str]]:
    """Split a LoCoMo context string into (session_id, text) pairs.

    Context format has DATE markers separating sessions:
        DATE: 1:56 pm on 8 May, 2023
        CONVERSATION:
        Speaker said, "..."
        ...
        DATE: ...
    """
    # Split on DATE markers, keeping the date text
    parts = re.split(r"(?=DATE:)", context)
    sessions: list[tuple[str, str]] = []
    session_num = 0

    for part in parts:
        part = part.strip()
        if not part or not part.startswith("DATE:"):
            continue
        session_num += 1
        session_id = f"D{session_num}"
        sessions.append((session_id, part))

    return sessions


def load_locomo(path: Path) -> list[LoCoMoConversation]:
    """Load the LoCoMo dataset from a JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    conversations: list[LoCoMoConversation] = []

    for entry in raw:
        questions: list[LoCoMoQuestion] = []
        for idx, q in enumerate(entry["qa"]):
            questions.append(
                LoCoMoQuestion(
                    conversation_id=entry["sample_id"],
                    question_idx=idx,
                    question=q["question"],
                    answer=q["answer"],
                    category=q["category"],
                    is_adversarial=q.get("is_adversarial", False),
                    evidence=q.get("evidence", []),
                )
            )
        conversations.append(
            LoCoMoConversation(
                sample_id=entry["sample_id"],
                context=entry["context"],
                questions=questions,
                speaker_a=entry["speaker_a"],
                speaker_b=entry["speaker_b"],
            )
        )

    return conversations


def _sanitize_collection_name(name: str) -> str:
    """Make a valid ChromaDB collection name (3-63 chars, alphanumeric + _ -)."""
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    if len(sanitized) < 3:
        sanitized = sanitized + "___"
    return sanitized[:63]


def evaluate_retrieval_entry(
    question: LoCoMoQuestion,
    sessions: list[tuple[str, str]],
) -> RetrievalResult:
    """Run retrieval for a single LoCoMo question using ChromaDB."""
    # Skip adversarial questions for retrieval (no correct session to find)
    if question.is_adversarial or not question.evidence_session_ids:
        return RetrievalResult(
            question_id=question.question_id,
            category=question.category,
            recall_any_5=0.0,
            recall_any_10=0.0,
            recall_all_5=0.0,
            recall_all_10=0.0,
        )

    client = chromadb.Client()
    col_name = _sanitize_collection_name(f"loco_{question.question_id}")

    # Clean up if exists from prior run
    try:
        client.delete_collection(col_name)
    except Exception:
        pass

    collection = client.create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"},
    )

    if not sessions:
        return RetrievalResult(
            question_id=question.question_id,
            category=question.category,
            recall_any_5=0.0,
            recall_any_10=0.0,
            recall_all_5=0.0,
            recall_all_10=0.0,
        )

    # Deduplicate session IDs
    seen: set[str] = set()
    deduped_ids: list[str] = []
    deduped_texts: list[str] = []
    for sid, text in sessions:
        if sid in seen:
            continue
        seen.add(sid)
        if text.strip():
            deduped_ids.append(sid)
            deduped_texts.append(text)

    if not deduped_ids:
        return RetrievalResult(
            question_id=question.question_id,
            category=question.category,
            recall_any_5=0.0,
            recall_any_10=0.0,
            recall_all_5=0.0,
            recall_all_10=0.0,
        )

    collection.add(ids=deduped_ids, documents=deduped_texts)

    results = collection.query(
        query_texts=[question.question],
        n_results=min(50, len(deduped_ids)),
    )
    ranked_ids = results["ids"][0] if results["ids"] else []

    # Cleanup
    try:
        client.delete_collection(col_name)
    except Exception:
        pass

    correct = set(question.evidence_session_ids)

    def recall_any_at_k(k: int) -> float:
        top_k = set(ranked_ids[:k])
        return 1.0 if any(c in top_k for c in correct) else 0.0

    def recall_all_at_k(k: int) -> float:
        top_k = set(ranked_ids[:k])
        return 1.0 if all(c in top_k for c in correct) else 0.0

    return RetrievalResult(
        question_id=question.question_id,
        category=question.category,
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
- If the reference says "No information available" and the assistant also says there's not enough info, that's correct.
- If the assistant says "I don't know" or gives wrong information, that's incorrect.
- For temporal questions, allow small date errors (off by one day).
- For adversarial questions (reference = "No information available"), the assistant should indicate the info is unavailable."""


def evaluate_qa_entry(
    question: LoCoMoQuestion,
    sessions: list[tuple[str, str]],
    driver: LLMDriver,
    lens: LensConfig,
    skopus_dir: Path,
    vault_dir: Path | None = None,
    top_k: int = 5,
) -> QAResult:
    """Run QA for a single question: retrieve top-K sessions, generate answer, return."""
    client = chromadb.Client()
    col_name = _sanitize_collection_name(f"qa_{question.question_id}")

    try:
        client.delete_collection(col_name)
    except Exception:
        pass

    collection = client.create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"},
    )

    # Deduplicate sessions
    seen: set[str] = set()
    deduped_ids: list[str] = []
    deduped_texts: list[str] = []
    for sid, text in sessions:
        if sid in seen:
            continue
        seen.add(sid)
        if text.strip():
            deduped_ids.append(sid)
            deduped_texts.append(text)

    if not deduped_ids:
        return QAResult(
            question_id=question.question_id,
            category=question.category,
            lens=lens,
            correct=False,
            score=0.0,
            notes="no sessions available",
        )

    collection.add(ids=deduped_ids, documents=deduped_texts)

    results = collection.query(
        query_texts=[question.question],
        n_results=min(top_k, len(deduped_ids)),
    )
    retrieved_texts = results["documents"][0] if results["documents"] else []

    # Cleanup
    try:
        client.delete_collection(col_name)
    except Exception:
        pass

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
            f"You are answering a question about past conversations between two people. "
            f"Here are the most relevant past conversation sessions:\n\n{context_block}"
        ),
    )

    user_prompt = (
        f"Based on the conversation history provided, answer this question concisely. "
        f"If the information is not available in the conversations, say so.\n\n"
        f"{question.question}"
    )

    response = driver.run(system_prompt, user_prompt, max_tokens=512)

    return QAResult(
        question_id=question.question_id,
        category=question.category,
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


def run_locomo(
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
) -> LoCoMoReport:
    """Run the LoCoMo benchmark.

    Args:
        data_path: Path to the locomo.json dataset file.
        driver: LLM driver for generating answers.
        skopus_dir: Path to skopus directory (for lens context).
        vault_dir: Optional vault directory.
        judge_driver: LLM driver for judging (defaults to same as driver).
        lens: Lens configuration to use.
        limit: Maximum number of questions to evaluate (across all conversations).
        top_k: Number of sessions to retrieve for QA context.
        parallel: Number of concurrent workers.
        retrieval_only: If True, only run retrieval eval (no LLM calls).
    """
    conversations = load_locomo(data_path)

    # Flatten all questions, pairing each with its conversation's sessions
    all_items: list[tuple[LoCoMoQuestion, list[tuple[str, str]]]] = []
    for conv in conversations:
        for q in conv.questions:
            all_items.append((q, conv.sessions))

    if limit:
        all_items = all_items[:limit]

    report = LoCoMoReport()

    # Phase 1: Retrieval evaluation (skip adversarial questions)
    retrieval_items = [
        (q, sessions)
        for q, sessions in all_items
        if not q.is_adversarial and q.evidence_session_ids
    ]

    if parallel <= 1:
        for q, sessions in retrieval_items:
            report.retrieval_results.append(evaluate_retrieval_entry(q, sessions))
    else:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {
                pool.submit(evaluate_retrieval_entry, q, sessions): q.question_id
                for q, sessions in retrieval_items
            }
            results_map: dict[str, RetrievalResult] = {}
            for future in as_completed(futures):
                r = future.result()
                results_map[r.question_id] = r
        # Preserve original order
        for q, _sessions in retrieval_items:
            if q.question_id in results_map:
                report.retrieval_results.append(results_map[q.question_id])

    if retrieval_only:
        return report

    # Phase 2: QA evaluation
    if not judge_driver:
        judge_driver = driver

    def _run_and_judge(
        question: LoCoMoQuestion, sessions: list[tuple[str, str]]
    ) -> QAResult:
        result = evaluate_qa_entry(
            question, sessions, driver, lens, skopus_dir, vault_dir, top_k
        )
        return judge_qa_result(result, question.answer, question.question, judge_driver)

    if parallel <= 1:
        for q, sessions in all_items:
            report.qa_results.append(_run_and_judge(q, sessions))
    else:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {
                pool.submit(_run_and_judge, q, sessions): q.question_id
                for q, sessions in all_items
            }
            results_map_qa: dict[str, QAResult] = {}
            for future in as_completed(futures):
                r = future.result()
                results_map_qa[r.question_id] = r
        # Preserve original order
        for q, _sessions in all_items:
            if q.question_id in results_map_qa:
                report.qa_results.append(results_map_qa[q.question_id])

    return report


def format_locomo_report(
    report: LoCoMoReport, lens: LensConfig | None = None
) -> str:
    """Format results as markdown."""
    lines = [
        "# LoCoMo Results",
        "",
    ]

    if report.retrieval_results:
        lines.extend(
            [
                "## Retrieval (ChromaDB + all-MiniLM-L6-v2)",
                "",
                f"**R@5: {report.recall_any_5:.1%}** | R@10: {report.recall_any_10:.1%}",
                "",
                "| Category | Count | R@5 | R@10 |",
                "|---|---|---|---|",
            ]
        )
        by_cat = report.retrieval_by_category()
        cat_counts = Counter(
            CATEGORY_NAMES.get(r.category, f"cat-{r.category}")
            for r in report.retrieval_results
        )
        r10_by_cat: dict[str, list[float]] = defaultdict(list)
        for r in report.retrieval_results:
            cat_name = CATEGORY_NAMES.get(r.category, f"cat-{r.category}")
            r10_by_cat[cat_name].append(r.recall_any_10)

        for t in sorted(by_cat.keys()):
            r10 = sum(r10_by_cat.get(t, [0])) / max(len(r10_by_cat.get(t, [1])), 1)
            lines.append(f"| {t} | {cat_counts[t]} | {by_cat[t]:.1%} | {r10:.1%} |")
        lines.append("")

    if report.qa_results:
        lens_label = lens.display_name if lens else "unknown"
        lines.extend(
            [
                f"## QA Accuracy (lens: {lens_label})",
                "",
                f"**Overall: {report.qa_accuracy:.1%}**",
                "",
                "| Category | Count | Accuracy |",
                "|---|---|---|",
            ]
        )
        qa_by_cat = report.qa_accuracy_by_category()
        qa_cat_counts = Counter(
            CATEGORY_NAMES.get(r.category, f"cat-{r.category}")
            for r in report.qa_results
        )
        for t in sorted(qa_by_cat.keys()):
            lines.append(f"| {t} | {qa_cat_counts[t]} | {qa_by_cat[t]:.1%} |")
        lines.append("")

    return "\n".join(lines)
