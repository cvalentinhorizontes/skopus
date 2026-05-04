"""Tests for the skopus_get_charter_section MCP tool."""

import asyncio

import pytest

from skopus.mcp.tools.charter import skopus_get_charter_section


@pytest.fixture
def populated_charter(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    charter = tmp_path / ".skopus" / "charter"
    charter.mkdir(parents=True)
    (charter / "CLAUDE.md").write_text(
        "# Charter\n\n"
        "## Non-negotiables\n\n"
        "1. Premium quality.\n"
        "2. Evidence over assumption.\n\n"
        "## Communication\n\n"
        "Plain language.\n"
    )
    (charter / "user_profile.md").write_text("## User profile\n\nName: Carlos.\n")
    return tmp_path


def test_get_section_finds_named_h2(populated_charter):
    result = asyncio.run(skopus_get_charter_section("Non-negotiables"))
    assert result["found"] is True
    assert "Premium quality" in result["content"]
    # Must not bleed into the next section
    assert "Communication" not in result["content"]


def test_get_section_searches_across_files(populated_charter):
    result = asyncio.run(skopus_get_charter_section("User profile"))
    assert result["found"] is True
    assert "Carlos" in result["content"]


def test_get_section_returns_not_found_with_known_sections(populated_charter):
    result = asyncio.run(skopus_get_charter_section("nonexistent-section"))
    assert result["found"] is False
    assert "available_sections" in result
    assert "Non-negotiables" in result["available_sections"]


def test_get_section_when_charter_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = asyncio.run(skopus_get_charter_section("any"))
    assert result["found"] is False
    assert "hint" in result


def test_get_section_is_case_insensitive(populated_charter):
    """Heading match is case-insensitive on user input."""
    result = asyncio.run(skopus_get_charter_section("non-negotiables"))
    assert result["found"] is True


def test_get_section_returns_source_file(populated_charter):
    result = asyncio.run(skopus_get_charter_section("Communication"))
    assert result["found"] is True
    assert "CLAUDE.md" in result["source_file"]


def test_get_charter_section_registered_in_server():
    from skopus.mcp import build_server

    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = [t.name for t in tools]
    assert "skopus_get_charter_section" in names


def test_get_section_first_hit_wins_across_files(tmp_path, monkeypatch):
    """When the same heading exists in multiple charter files, the first
    file in CHARTER_FILES order (CLAUDE.md > workflow_partnership.md >
    user_profile.md) wins. Pins the documented behavior against future
    iteration-order regressions."""
    monkeypatch.setenv("HOME", str(tmp_path))
    charter = tmp_path / ".skopus" / "charter"
    charter.mkdir(parents=True)
    (charter / "CLAUDE.md").write_text("## Shared section\n\nFrom CLAUDE.md.\n")
    (charter / "workflow_partnership.md").write_text(
        "## Shared section\n\nFrom workflow_partnership.md.\n"
    )

    result = asyncio.run(skopus_get_charter_section("Shared section"))

    assert result["found"] is True
    assert "From CLAUDE.md." in result["content"]
    assert "From workflow_partnership.md." not in result["content"]
    assert "CLAUDE.md" in result["source_file"]
    assert "workflow_partnership.md" not in result["source_file"]
