"""Graphify bridge — wires the fourth lens into a project.

Skopus does not build graphs directly. Graphify's architecture is LLM-driven:
the actual graph extraction runs as a slash command (`/graphify <path>`) from
inside the host AI coding assistant, which reads the skill file that
`graphify claude install` copies into place.

This module's job is to:
  1. Verify graphify is installed
  2. Invoke `graphify <platform> install` inside a project directory
  3. Install the git hook for auto-rebuild on commit/branch switch
  4. Track the graphify scope (which codebases the user wants mapped)
     as a hint that skopus doctor and the first-build reminder can read
  5. Report whether a graph has been built yet (graphify-out/graph.json exists)

When the user first opens the project in their AI assistant after `skopus init`,
the PreToolUse hook installed by graphify fires before any Glob/Grep and
prompts the agent to run `/graphify <scope>` for the first build. The build
itself costs real API tokens and is deliberately lazy — it happens when the
user is in an agent session with appropriate credentials, not during skopus
init from the shell.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GraphifyInstallResult:
    """Outcome of wiring graphify into a project."""

    installed: bool
    git_hook_installed: bool
    scope_hint: list[str]
    message: str
    graph_exists: bool = False


def graphify_available() -> bool:
    """Return True if the graphify CLI is on PATH."""
    return shutil.which("graphify") is not None


def graphify_python_importable() -> bool:
    """Return True if the graphify Python package is importable."""
    try:
        import graphify  # noqa: F401

        return True
    except ImportError:
        return False


def graph_exists(project_path: Path) -> bool:
    """Return True if a graphify-out/graph.json exists in the project."""
    return (project_path / "graphify-out" / "graph.json").exists()


GRAPHIFY_SECTION_MARKER = "## graphify"


def _consolidate_graphify_block(project_path: Path) -> bool:
    """If graphify wrote its block to root CLAUDE.md but .claude/CLAUDE.md
    exists (skopus convention), move the block into .claude/CLAUDE.md and
    delete the root file. Keeps the project root clean.

    Returns True if consolidation happened, False otherwise.
    """
    root_claude = project_path / "CLAUDE.md"
    claude_dir_claude = project_path / ".claude" / "CLAUDE.md"

    if not root_claude.exists() or not claude_dir_claude.exists():
        return False

    root_content = root_claude.read_text(encoding="utf-8")
    if GRAPHIFY_SECTION_MARKER not in root_content:
        return False

    # Extract the graphify block (from marker to end or next top-level section)
    lines = root_content.splitlines(keepends=True)
    block_lines: list[str] = []
    in_block = False
    for line in lines:
        if line.strip() == GRAPHIFY_SECTION_MARKER:
            in_block = True
        if in_block:
            block_lines.append(line)

    if not block_lines:
        return False

    graphify_block = "".join(block_lines).rstrip() + "\n"

    # Append to .claude/CLAUDE.md if not already present
    dest_content = claude_dir_claude.read_text(encoding="utf-8")
    if GRAPHIFY_SECTION_MARKER not in dest_content:
        separator = "\n\n" if not dest_content.endswith("\n\n") else ""
        claude_dir_claude.write_text(
            dest_content + separator + graphify_block, encoding="utf-8"
        )

    # If root file had ONLY the graphify block, delete it; otherwise rewrite without it
    non_graphify = [line for line in lines if line not in block_lines]
    remaining = "".join(non_graphify).strip()
    if not remaining:
        root_claude.unlink()
    else:
        root_claude.write_text("".join(non_graphify), encoding="utf-8")

    return True


def ensure_graphify_skill_installed() -> bool:
    """Ensure the graphify skill file is copied to ~/.claude/skills/graphify/.

    This is the **global**, **one-time**, **idempotent** setup step that makes
    ``/graphify`` actually work as a slash command in Claude Code. Graphify's
    `claude install` (per-project) only writes the CLAUDE.md block + PreToolUse
    hook — it does NOT copy the skill file. The skill file is copied by the
    top-level `graphify install` (no platform arg), which is what we call here.

    Safe to call on every ``skopus init``. Returns True if the skill is in
    place after the call (either already there or newly installed), False if
    the install failed.
    """
    skill_target = Path.home() / ".claude" / "skills" / "graphify" / "SKILL.md"
    if skill_target.exists():
        return True

    if not graphify_available():
        return False

    try:
        result = subprocess.run(
            ["graphify", "install"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

    if result.returncode != 0:
        return False

    return skill_target.exists()


def install_graphify_for_claude(
    project_path: Path,
    scope: list[str] | None = None,
) -> GraphifyInstallResult:
    """Run `graphify claude install` inside a project directory.

    Two steps:

    1. **Global, one-time:** copy graphify's skill file into
       ``~/.claude/skills/graphify/SKILL.md`` so ``/graphify`` is invokable
       as a Claude Code slash command. (Calls ``graphify install``.)
    2. **Per-project:** write the graphify section into CLAUDE.md and install
       the PreToolUse hook. (Calls ``graphify claude install``.)

    If the project has a ``.claude/CLAUDE.md`` (skopus convention), the
    graphify block is consolidated there and the root file is cleaned up.

    The scope hint is stored in ``graphify-out/.skopus_scope`` so the
    first-build reminder can tell the user which path to pass to `/graphify`.
    """
    scope = scope or []

    if not graphify_available():
        return GraphifyInstallResult(
            installed=False,
            git_hook_installed=False,
            scope_hint=scope,
            message="graphify CLI not found on PATH — install graphifyy and retry",
        )

    # 1. Global skill file (idempotent one-time step — makes /graphify
    #    invokable as a slash command in Claude Code)
    skill_installed = ensure_graphify_skill_installed()

    # 2. Per-project: graphify claude install
    try:
        install_run = subprocess.run(
            ["graphify", "claude", "install"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return GraphifyInstallResult(
            installed=False,
            git_hook_installed=False,
            scope_hint=scope,
            message="graphify claude install timed out after 60s",
        )
    except FileNotFoundError:
        return GraphifyInstallResult(
            installed=False,
            git_hook_installed=False,
            scope_hint=scope,
            message="graphify CLI disappeared between check and invocation",
        )

    if install_run.returncode != 0:
        return GraphifyInstallResult(
            installed=False,
            git_hook_installed=False,
            scope_hint=scope,
            message=f"graphify claude install failed: {install_run.stderr.strip()[:200]}",
        )

    # 2b. Consolidate graphify block into .claude/CLAUDE.md if that's where
    # skopus wrote (skopus convention), keeping the project root clean.
    _consolidate_graphify_block(project_path)

    # 2. graphify hook install (git auto-rebuild)
    hook_installed = False
    try:
        hook_run = subprocess.run(
            ["graphify", "hook", "install"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        hook_installed = hook_run.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        hook_installed = False

    # 3. Persist scope hint
    if scope:
        scope_file = project_path / "graphify-out" / ".skopus_scope"
        scope_file.parent.mkdir(parents=True, exist_ok=True)
        scope_file.write_text("\n".join(scope) + "\n")

    skill_msg = "" if skill_installed else " (skill file install failed — /graphify slash command may not work)"
    return GraphifyInstallResult(
        installed=True,
        git_hook_installed=hook_installed,
        scope_hint=scope,
        message=(
            f"graphify wired into project (CLAUDE.md + PreToolUse hook + git hook){skill_msg}"
            if hook_installed
            else f"graphify wired into project (CLAUDE.md + PreToolUse hook); git hook install skipped{skill_msg}"
        ),
        graph_exists=graph_exists(project_path),
    )


def uninstall_graphify_for_claude(project_path: Path) -> GraphifyInstallResult:
    """Reverse `graphify claude install` and `graphify hook install`."""
    if not graphify_available():
        return GraphifyInstallResult(
            installed=False,
            git_hook_installed=False,
            scope_hint=[],
            message="graphify CLI not found — nothing to uninstall",
        )

    for subcmd in [["claude", "uninstall"], ["hook", "uninstall"]]:
        try:
            subprocess.run(
                ["graphify", *subcmd],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return GraphifyInstallResult(
        installed=False,
        git_hook_installed=False,
        scope_hint=[],
        message="graphify removed from project",
    )


def first_build_hint(project_path: Path) -> str | None:
    """Return the scope hint written by skopus init, if any.

    Used by skopus doctor and the init next-steps message to tell the user
    which path to pass to `/graphify` for their first build.
    """
    scope_file = project_path / "graphify-out" / ".skopus_scope"
    if not scope_file.exists():
        return None
    paths = [line.strip() for line in scope_file.read_text().splitlines() if line.strip()]
    return " ".join(paths) if paths else None
