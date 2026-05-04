"""Tests for the skopus_search_memory MCP tool."""

import asyncio

import pytest

from skopus.mcp.tools.memory import skopus_search_memory


@pytest.fixture
def populated_memory(tmp_path, monkeypatch):
    """Seed ~/.skopus/memory/feedback/ with three entries for ranking tests."""
    monkeypatch.setenv("HOME", str(tmp_path))
    feedback = tmp_path / ".skopus" / "memory" / "feedback"
    feedback.mkdir(parents=True)

    (feedback / "billing-rounding.md").write_text(
        "---\n"
        "name: rule-billing-rounding\n"
        "description: Never round currency to 2 decimals; use Decimal\n"
        "type: feedback\n"
        "captured: 2026-04-12\n"
        "scope: project\n"
        "---\n\n"
        "Billing code must use Decimal arithmetic, not float rounding.\n"
    )
    (feedback / "tdd.md").write_text(
        "---\n"
        "name: rule-tdd-first\n"
        "description: Always write the failing test before implementation\n"
        "type: feedback\n"
        "captured: 2026-04-15\n"
        "scope: user\n"
        "---\n\n"
        "Test-driven development is non-negotiable for this project.\n"
    )
    (feedback / "no-jargon.md").write_text(
        "---\n"
        "name: rule-no-jargon\n"
        "description: Plain language over technical jargon\n"
        "type: feedback\n"
        "captured: 2026-04-20\n"
        "scope: user\n"
        "---\n\n"
        "Communication style: explain in plain words.\n"
    )
    return tmp_path


def test_search_returns_relevant_entries(populated_memory):
    """Query 'billing currency' should rank the billing entry first."""
    result = asyncio.run(skopus_search_memory(query="billing currency"))
    assert len(result["matches"]) >= 1
    assert result["matches"][0]["id"] == "rule-billing-rounding"


def test_search_respects_scope_filter(populated_memory):
    """scope='user' should exclude the project-scoped billing entry."""
    result = asyncio.run(skopus_search_memory(query="rule", scope="user"))
    ids = [m["id"] for m in result["matches"]]
    assert "rule-billing-rounding" not in ids
    assert "rule-tdd-first" in ids
    assert "rule-no-jargon" in ids


def test_search_returns_empty_matches_on_no_query_hit(populated_memory):
    """A query that matches nothing returns an empty matches list, not an error."""
    result = asyncio.run(skopus_search_memory(query="nonexistent-term-xyz"))
    assert result["matches"] == []


def test_search_caps_results_at_default_top_k(populated_memory):
    """Default top_k is 10 (we have 3 entries — should return all 3 here)."""
    result = asyncio.run(skopus_search_memory(query="rule"))
    assert len(result["matches"]) <= 10
    assert len(result["matches"]) >= 3


def test_search_respects_explicit_top_k(populated_memory):
    """top_k=1 caps results at 1."""
    result = asyncio.run(skopus_search_memory(query="rule", top_k=1))
    assert len(result["matches"]) == 1


def test_search_when_skopus_dir_missing(tmp_path, monkeypatch):
    """If ~/.skopus does not exist, return empty matches with a hint."""
    monkeypatch.setenv("HOME", str(tmp_path))
    result = asyncio.run(skopus_search_memory(query="anything"))
    assert result["matches"] == []
    assert "hint" in result


def test_search_registered_in_server():
    """build_server() must register search_memory with name skopus_search_memory."""
    from skopus.mcp import build_server

    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = [t.name for t in tools]
    assert "skopus_search_memory" in names


def test_search_dedups_query_terms(populated_memory):
    """Repeating a query term must not inflate the score for that entry."""
    single = asyncio.run(skopus_search_memory(query="billing"))
    doubled = asyncio.run(skopus_search_memory(query="billing billing"))
    # Same matches, same order, same scores — duplicates in the query don't matter.
    assert len(single["matches"]) == len(doubled["matches"])
    assert single["matches"][0]["id"] == doubled["matches"][0]["id"]
    assert single["matches"][0]["score"] == doubled["matches"][0]["score"]
