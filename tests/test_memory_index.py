"""Tests for the schema-aware memory loader.

Reads YAML frontmatter from ~/.skopus/memory/feedback/*.md, normalizes
to the v2 §4.1 schema with sensible defaults for missing fields, and
exposes a list of MemoryEntry objects for searching."""

from skopus.mcp.memory_index import MemoryEntry, load_memory_entries


def test_load_returns_empty_list_when_no_feedback_dir(tmp_path):
    entries = load_memory_entries(tmp_path)
    assert entries == []


def test_load_parses_frontmatter_and_body(tmp_path):
    feedback = tmp_path / "feedback"
    feedback.mkdir()
    (feedback / "rule-x.md").write_text(
        "---\n"
        "name: rule-x\n"
        "description: Do the X thing\n"
        "type: feedback\n"
        "captured: 2026-04-13\n"
        "scope: skopus\n"
        "---\n\n"
        "# Rule X\n\nBody content here.\n"
    )

    entries = load_memory_entries(tmp_path)
    assert len(entries) == 1
    e = entries[0]
    assert isinstance(e, MemoryEntry)
    assert e.id == "rule-x"
    assert e.name == "rule-x"
    assert e.description == "Do the X thing"
    assert e.scope == "skopus"
    assert "Body content here." in e.body
    assert e.path == feedback / "rule-x.md"


def test_load_defaults_missing_v2_fields(tmp_path):
    """Old entries lack source/confidence/applies_to/supersedes — default
    them so search/filter logic doesn't crash on legacy data."""
    feedback = tmp_path / "feedback"
    feedback.mkdir()
    (feedback / "old.md").write_text(
        "---\n"
        "name: old\n"
        "description: legacy\n"
        "type: feedback\n"
        "captured: 2026-04-01\n"
        "scope: user\n"
        "---\n\n"
        "Body.\n"
    )

    entries = load_memory_entries(tmp_path)
    e = entries[0]
    assert e.source == "imported"
    assert e.confidence == "weak"
    assert e.applies_to_paths == []
    assert e.applies_to_task_types == []
    assert e.applies_to_keywords == []
    assert e.supersedes == []


def test_load_skips_files_without_frontmatter(tmp_path):
    feedback = tmp_path / "feedback"
    feedback.mkdir()
    (feedback / "raw.md").write_text("# Just markdown, no frontmatter\n")

    entries = load_memory_entries(tmp_path)
    assert entries == []


def test_load_handles_malformed_frontmatter_gracefully(tmp_path):
    feedback = tmp_path / "feedback"
    feedback.mkdir()
    (feedback / "broken.md").write_text("---\n: invalid yaml :\n---\nBody.\n")

    entries = load_memory_entries(tmp_path)
    assert entries == []


def test_load_skips_non_utf8_files(tmp_path):
    """A non-UTF-8 file must not crash the corpus load."""
    feedback = tmp_path / "feedback"
    feedback.mkdir()
    (feedback / "good.md").write_text(
        "---\nname: good\ndescription: ok\ntype: feedback\nscope: user\n---\nbody\n"
    )
    # Write invalid UTF-8 bytes
    (feedback / "bad-encoding.md").write_bytes(b"---\nname: bad\n\xff\xfe\n---\nbody\n")

    entries = load_memory_entries(tmp_path)
    # The good entry survives; the bad one is skipped, not crashed.
    assert len(entries) == 1
    assert entries[0].name == "good"
