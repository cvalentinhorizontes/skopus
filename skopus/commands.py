"""Shared loaders + format converters for Skopus's portable command surface.

Skopus owns a single canonical set of slash-command templates at
``skopus/templates/commands/*.md``. Each adapter's ``install_commands``
renders those templates into its agent's user-command surface. The
formats supported here are:

- **Markdown passthrough** for Claude Code (``~/.claude/commands/<name>.md``).
- **SKILL.md** for Cursor and Codex CLI (``~/.cursor/skills/<name>/SKILL.md``,
  ``$CODEX_HOME/skills/<name>/SKILL.md`` — same Anthropic SKILL.md convention
  adopted by both products).
- **TOML** for Gemini CLI (``~/.gemini/commands/<name>.toml``).

Aider and Copilot CLI do not expose a user-defined slash-command surface;
their adapters inherit the no-op default in ``Adapter.install_commands``.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

CommandName = str


@dataclass(frozen=True)
class CommandTemplate:
    """A single canonical Skopus slash command, parsed from Markdown."""

    name: CommandName  # e.g. "compile"
    description: str  # one-line, drives Cursor/Codex SKILL discovery + Gemini help
    body: str  # the prompt body (markdown without the leading frontmatter block)


def load_command_templates() -> list[CommandTemplate]:
    """Load every canonical command template bundled with the package."""
    root = files("skopus") / "templates" / "commands"
    out: list[CommandTemplate] = []
    for resource in sorted(root.iterdir(), key=lambda r: r.name):  # type: ignore[arg-type]
        if not resource.name.endswith(".md"):
            continue
        text = resource.read_text(encoding="utf-8")
        out.append(_parse_template(resource.name.removesuffix(".md"), text))
    return out


def _parse_template(name: str, text: str) -> CommandTemplate:
    """Split YAML frontmatter and body. Frontmatter must use --- fences."""
    description = ""
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            front = text[4:end]
            body = text[end + 4 :].lstrip("\n")
            for line in front.splitlines():
                key, sep, value = line.partition(":")
                if sep and key.strip() == "description":
                    description = value.strip().strip('"').strip("'")
                    break
    return CommandTemplate(name=name, description=description, body=body)


def render_skill_md(template: CommandTemplate) -> str:
    """Render a SKILL.md for Cursor/Codex from a Skopus command template.

    The frontmatter keeps to the minimum the SKILL.md spec requires (``name``
    and ``description``); both Cursor and Codex accept additional metadata
    but Skopus stays portable by emitting only the required fields.
    """
    description = template.description or f"Skopus /{template.name} command."
    description_block = _indent_yaml_block(description)
    return (
        "---\n"
        f"name: {template.name}\n"
        f"description: {description_block}\n"
        "---\n\n"
        f"{template.body}"
    ).rstrip() + "\n"


def render_gemini_toml(template: CommandTemplate) -> str:
    """Render a Gemini CLI custom-command TOML file from a template.

    Per Gemini's spec, ``description`` is optional and ``prompt`` is the
    required body. Skopus injects the canonical Markdown body unchanged; it
    contains agent-directed instructions that any modern LLM treats as a
    prompt regardless of surface format.
    """
    parts = []
    if template.description:
        parts.append(f"description = {_toml_string(template.description)}")
    parts.append(f"prompt = {_toml_multiline(template.body)}")
    return "\n".join(parts) + "\n"


def _indent_yaml_block(value: str) -> str:
    """Quote a single-line YAML scalar safely.

    All current command descriptions fit on one line; we keep the renderer
    simple and quote them so colons or hashes inside don't break the parser.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_multiline(value: str) -> str:
    """Triple-quoted TOML literal string, escaping the only forbidden sequence."""
    safe = value.replace('"""', '\\"\\"\\"')
    return f'"""\n{safe.rstrip()}\n"""'


def write_markdown_command(target_dir: Path, template: CommandTemplate, *, force: bool = True) -> Path:
    """Write a Markdown command file (Claude Code surface)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{template.name}.md"
    if path.exists() and not force:
        return path
    path.write_text(_reassemble_markdown(template), encoding="utf-8")
    return path


def write_skill_md(skills_dir: Path, template: CommandTemplate, *, force: bool = True) -> Path:
    """Write a ``<skills_dir>/<name>/SKILL.md`` (Cursor + Codex surface)."""
    skill_dir = skills_dir / template.name
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    if path.exists() and not force:
        return path
    path.write_text(render_skill_md(template), encoding="utf-8")
    return path


def write_gemini_toml(commands_dir: Path, template: CommandTemplate, *, force: bool = True) -> Path:
    """Write a ``<commands_dir>/<name>.toml`` (Gemini CLI surface)."""
    commands_dir.mkdir(parents=True, exist_ok=True)
    path = commands_dir / f"{template.name}.toml"
    if path.exists() and not force:
        return path
    path.write_text(render_gemini_toml(template), encoding="utf-8")
    return path


def _reassemble_markdown(template: CommandTemplate) -> str:
    """Rebuild a Claude Code command file (frontmatter + body) from a template."""
    if not template.description:
        return template.body
    return (
        "---\n"
        f'description: {_indent_yaml_block(template.description)}\n'
        "---\n\n"
        f"{template.body}"
    )
