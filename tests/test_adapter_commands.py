"""Tests for ``Adapter.install_commands`` across every supported agent.

Each adapter renders Skopus's canonical command templates into its
agent's user-command surface. The format differs per agent (Markdown,
SKILL.md, TOML), but the surface content originates in a single place —
``skopus/templates/commands/*.md`` — so format conversions are tested in
one file alongside the per-adapter installers.
"""

from __future__ import annotations

from pathlib import Path

from skopus.adapters import get_adapter
from skopus.adapters.aider import AiderAdapter
from skopus.adapters.copilot import CopilotCliAdapter
from skopus.commands import (
    CommandTemplate,
    load_command_templates,
    render_gemini_toml,
    render_skill_md,
)

CANONICAL_COMMANDS = {
    "bench-contribute",
    "charter-evolve",
    "compile",
    "ingest",
    "lint",
    "query",
    "wiki",
}


def test_load_command_templates_returns_canonical_set():
    names = {t.name for t in load_command_templates()}
    assert names == CANONICAL_COMMANDS


def test_every_template_has_a_description():
    for t in load_command_templates():
        assert t.description, f"template {t.name} is missing a description"
        # Single-line — multi-line descriptions break Cursor + Codex frontmatter
        assert "\n" not in t.description


def test_render_skill_md_emits_required_frontmatter():
    t = CommandTemplate(name="example", description="Hello: world", body="Body content here.\n")
    rendered = render_skill_md(t)
    assert rendered.startswith("---\n")
    assert "name: example\n" in rendered
    # Description is quoted so its colon doesn't break YAML parsing
    assert 'description: "Hello: world"\n' in rendered
    assert rendered.rstrip().endswith("Body content here.")


def test_render_gemini_toml_uses_prompt_and_description_keys():
    t = CommandTemplate(name="example", description="Hello", body='Use "$ARGS".\n')
    rendered = render_gemini_toml(t)
    assert 'description = "Hello"' in rendered
    assert 'prompt = """' in rendered
    # Body literal is preserved
    assert 'Use "$ARGS".' in rendered


def test_claude_code_install_commands_writes_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    adapter = get_adapter("claude-code")
    paths = adapter.install_commands(skopus_dir=tmp_path / ".skopus")
    assert {p.name for p in paths} == {f"{n}.md" for n in CANONICAL_COMMANDS}
    for p in paths:
        assert p.parent == tmp_path / ".claude" / "commands"
        text = p.read_text()
        # Markdown frontmatter is preserved
        assert text.startswith("---\n") and "description:" in text
        assert text.count("---\n") >= 2  # opening + closing fence


def test_cursor_install_commands_writes_skill_md_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    adapter = get_adapter("cursor")
    paths = adapter.install_commands(skopus_dir=tmp_path / ".skopus")
    assert len(paths) == len(CANONICAL_COMMANDS)
    for p in paths:
        # Each command lives in its own directory under ~/.cursor/skills/
        assert p.name == "SKILL.md"
        assert p.parent.parent == tmp_path / ".cursor" / "skills"
        assert p.parent.name in CANONICAL_COMMANDS
        text = p.read_text()
        assert text.startswith("---\n")
        assert f"name: {p.parent.name}\n" in text


def test_codex_install_commands_uses_codex_home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    adapter = get_adapter("codex")
    paths = adapter.install_commands(skopus_dir=tmp_path / ".skopus")
    assert len(paths) == len(CANONICAL_COMMANDS)
    for p in paths:
        assert p.name == "SKILL.md"
        assert p.parent.parent == tmp_path / ".codex" / "skills"


def test_codex_install_commands_respects_codex_home_env(tmp_path, monkeypatch):
    custom_home = tmp_path / "custom-codex"
    monkeypatch.setenv("CODEX_HOME", str(custom_home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake-home")
    adapter = get_adapter("codex")
    paths = adapter.install_commands(skopus_dir=tmp_path / ".skopus")
    for p in paths:
        assert p.parent.parent == custom_home / "skills"


def test_gemini_install_commands_writes_toml(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    adapter = get_adapter("gemini-cli")
    paths = adapter.install_commands(skopus_dir=tmp_path / ".skopus")
    assert {p.name for p in paths} == {f"{n}.toml" for n in CANONICAL_COMMANDS}
    for p in paths:
        assert p.parent == tmp_path / ".gemini" / "commands"
        text = p.read_text()
        assert 'prompt = """' in text
        assert text.rstrip().endswith('"""')


def test_aider_install_commands_is_noop():
    adapter = AiderAdapter()
    assert adapter.install_commands(skopus_dir=Path("/tmp/whatever")) == []


def test_copilot_install_commands_is_noop():
    adapter = CopilotCliAdapter()
    assert adapter.install_commands(skopus_dir=Path("/tmp/whatever")) == []


def test_link_invokes_install_commands(tmp_path, monkeypatch):
    """Integration: ``skopus link`` must wire the agent's command surface.

    This catches architectural cascade bugs where install_commands is
    implemented per-adapter but never actually called from the CLI flow
    (the bug class the original ``Plan Comments Are Aspirational Until
    Wired`` correction memory exists to prevent).
    """
    from typer.testing import CliRunner

    from skopus.cli import app

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    skopus_dir = tmp_path / ".skopus"
    (skopus_dir / "charter").mkdir(parents=True)
    (skopus_dir / "vault").mkdir(parents=True)
    (skopus_dir / "memory").mkdir(parents=True)
    project = tmp_path / "myproject"
    project.mkdir()

    runner = CliRunner()
    result = runner.invoke(app, ["link", str(project), "--agent", "claude-code"])
    assert result.exit_code == 0, result.stdout

    commands_dir = tmp_path / ".claude" / "commands"
    assert commands_dir.is_dir(), "skopus link did not invoke claude-code install_commands"
    written = {p.stem for p in commands_dir.glob("*.md")}
    assert written >= CANONICAL_COMMANDS


def test_install_commands_is_idempotent_across_runs(tmp_path, monkeypatch):
    """Re-running install_commands must produce byte-identical output."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    adapter = get_adapter("cursor")
    first = adapter.install_commands(skopus_dir=tmp_path / ".skopus")
    snapshot = {p: p.read_text() for p in first}

    second = adapter.install_commands(skopus_dir=tmp_path / ".skopus")
    assert set(first) == set(second)
    for p in second:
        assert p.read_text() == snapshot[p], f"{p.name} changed across runs"

    # And the SKILL.md frontmatter must still be exactly one block.
    for p in second:
        text = p.read_text()
        # Frontmatter is the first --- block; count opening fences at column 0
        assert text.startswith("---\n")
        # The second --- closes the SKILL.md frontmatter; anything after is body
        end = text.find("\n---\n", 4)
        assert end != -1, f"{p.name} missing SKILL.md closing fence"
        front = text[4:end]
        assert "name:" in front and "description:" in front
        # Frontmatter block itself must not contain any extra fence
        assert "\n---\n" not in front
