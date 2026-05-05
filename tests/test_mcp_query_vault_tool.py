"""Tests for the skopus_query_vault MCP tool."""

import asyncio

import pytest

from skopus.mcp.tools.vault import skopus_query_vault


@pytest.fixture
def populated_vault(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    vault = tmp_path / ".skopus" / "vault" / "wiki"
    (vault / "decisions").mkdir(parents=True)
    (vault / "concepts").mkdir(parents=True)

    (vault / "decisions" / "api-versioning.md").write_text(
        "# API versioning policy\n\nThree-PR cadence: introduce, deprecate, remove.\n"
    )
    (vault / "concepts" / "skopus-overview.md").write_text(
        "# Skopus overview\n\nFour-lens architecture: charter, memory, vault, graph.\n"
    )
    return tmp_path


def test_query_returns_relevant_pages(populated_vault):
    result = asyncio.run(skopus_query_vault(query="API versioning"))
    assert len(result["matches"]) >= 1
    assert "api-versioning" in result["matches"][0]["path"]


def test_query_respects_top_k(populated_vault):
    result = asyncio.run(skopus_query_vault(query="skopus", top_k=1))
    assert len(result["matches"]) <= 1


def test_query_handles_missing_vault(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = asyncio.run(skopus_query_vault(query="anything"))
    assert result["matches"] == []
    assert "hint" in result


def test_query_returns_empty_on_no_match(populated_vault):
    result = asyncio.run(skopus_query_vault(query="nonexistent-zyx"))
    assert result["matches"] == []


def test_query_dedups_query_terms(populated_vault):
    """Repeated query terms must not inflate the score."""
    single = asyncio.run(skopus_query_vault(query="skopus"))
    doubled = asyncio.run(skopus_query_vault(query="skopus skopus"))
    assert single["matches"][0]["score"] == doubled["matches"][0]["score"]


def test_query_uses_h1_as_title(populated_vault):
    result = asyncio.run(skopus_query_vault(query="API"))
    assert result["matches"][0]["title"] == "API versioning policy"


def test_query_falls_back_to_filename_when_no_h1(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    vault = tmp_path / ".skopus" / "vault" / "wiki" / "notes"
    vault.mkdir(parents=True)
    (vault / "no-heading.md").write_text("Just body text, no H1.\n")
    result = asyncio.run(skopus_query_vault(query="body"))
    assert result["matches"][0]["title"] == "no-heading"


def test_query_registered_in_server():
    from skopus.mcp import build_server

    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = [t.name for t in tools]
    assert "skopus_query_vault" in names


def test_query_respects_scope_filter(populated_vault):
    """scope='decisions' should exclude the concepts/skopus-overview page."""
    result = asyncio.run(skopus_query_vault(query="skopus", scope="decisions"))
    sections = {m["section"] for m in result["matches"]}
    assert sections == {"decisions"} or sections == set()
    # And without the scope filter, both sections show up.
    unfiltered = asyncio.run(skopus_query_vault(query="skopus"))
    unfiltered_sections = {m["section"] for m in unfiltered["matches"]}
    assert "concepts" in unfiltered_sections
