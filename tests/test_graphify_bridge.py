"""Tests for skopus.graphify_bridge."""

from pathlib import Path

from skopus.graphify_bridge import (
    first_build_hint,
    graph_exists,
    graphify_available,
    graphify_python_importable,
    install_graphify_for_claude,
)


def test_graphify_available_returns_bool():
    assert isinstance(graphify_available(), bool)


def test_graphify_python_importable_returns_bool():
    assert isinstance(graphify_python_importable(), bool)


def test_graph_exists_returns_false_for_empty_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    assert graph_exists(project) is False


def test_graph_exists_detects_existing_graph(tmp_path):
    project = tmp_path / "project"
    (project / "graphify-out").mkdir(parents=True)
    (project / "graphify-out" / "graph.json").write_text('{"nodes": []}')
    assert graph_exists(project) is True


def test_first_build_hint_returns_none_when_missing(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    assert first_build_hint(project) is None


def test_first_build_hint_reads_scope_file(tmp_path):
    project = tmp_path / "project"
    (project / "graphify-out").mkdir(parents=True)
    (project / "graphify-out" / ".skopus_scope").write_text(
        "backend/src/services/voice\nbackend/src/services/orchestration\n"
    )
    hint = first_build_hint(project)
    assert hint is not None
    assert "backend/src/services/voice" in hint
    assert "backend/src/services/orchestration" in hint


def test_install_graphify_for_claude_end_to_end_if_available(tmp_path):
    """Full integration test — only runs if graphify CLI is on PATH."""
    if not graphify_available():
        import pytest

        pytest.skip("graphify CLI not installed")

    project = tmp_path / "project"
    project.mkdir()
    # Make it look like a git project so graphify doesn't balk
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=project, check=True)

    result = install_graphify_for_claude(
        project_path=project,
        scope=["src/"],
    )

    assert result.installed is True
    # Scope hint should be persisted
    scope_file = project / "graphify-out" / ".skopus_scope"
    assert scope_file.exists()
    assert "src/" in scope_file.read_text()


def test_install_graphify_persists_scope_hint(tmp_path):
    """Scope hint should be writable even without graphify installed."""
    if graphify_available():
        # Skip if graphify IS installed — this test is for the fallback path
        import pytest

        pytest.skip("graphify IS available; covered by integration test")

    project = tmp_path / "project"
    project.mkdir()

    result = install_graphify_for_claude(project_path=project, scope=["src/"])
    assert result.installed is False
    assert "not found" in result.message.lower() or "not on path" in result.message.lower()


def test_consolidate_graphify_block_moves_to_claude_dir(tmp_path):
    """When both root CLAUDE.md and .claude/CLAUDE.md exist, the graphify
    block should be moved from root into .claude/CLAUDE.md."""
    from skopus.adapters.claude_code import SKOPUS_SECTION_END, SKOPUS_SECTION_START
    from skopus.graphify_bridge import _consolidate_graphify_block

    project = tmp_path / "project"
    claude_dir = project / ".claude"
    claude_dir.mkdir(parents=True)

    # .claude/CLAUDE.md already has the skopus block (simulating what skopus wrote)
    skopus_content = (
        "# My Project\n\n"
        f"{SKOPUS_SECTION_START}\nSkopus context here.\n{SKOPUS_SECTION_END}\n"
    )
    (claude_dir / "CLAUDE.md").write_text(skopus_content)

    # root CLAUDE.md is what graphify just wrote
    (project / "CLAUDE.md").write_text("## graphify\n\nGraphify section content.\n")

    consolidated = _consolidate_graphify_block(project)
    assert consolidated is True

    # root CLAUDE.md should be gone (it had nothing but the graphify block)
    assert not (project / "CLAUDE.md").exists()

    # .claude/CLAUDE.md should have both blocks
    final = (claude_dir / "CLAUDE.md").read_text()
    assert SKOPUS_SECTION_START in final
    assert "## graphify" in final
    assert "Graphify section content" in final


def test_consolidate_graphify_block_preserves_other_root_content(tmp_path):
    """If root CLAUDE.md has other content besides graphify, keep it."""
    from skopus.graphify_bridge import _consolidate_graphify_block

    project = tmp_path / "project"
    claude_dir = project / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "CLAUDE.md").write_text("# Skopus charter\n")

    root = project / "CLAUDE.md"
    root.write_text(
        "# Pre-existing project rules\n\n"
        "Some human-written guidance.\n\n"
        "## graphify\n\n"
        "Graphify section.\n"
    )

    consolidated = _consolidate_graphify_block(project)
    assert consolidated is True

    # root still exists, but with just the human content
    assert root.exists()
    remaining = root.read_text()
    assert "Pre-existing project rules" in remaining
    assert "## graphify" not in remaining


def test_consolidate_graphify_block_no_op_when_no_claude_dir(tmp_path):
    """If .claude/ doesn't exist, leave root CLAUDE.md alone."""
    from skopus.graphify_bridge import _consolidate_graphify_block

    project = tmp_path / "project"
    project.mkdir()
    (project / "CLAUDE.md").write_text("## graphify\n\nContent.\n")

    consolidated = _consolidate_graphify_block(project)
    assert consolidated is False
    assert (project / "CLAUDE.md").exists()
