"""Template rendering and file materialization.

Loads Jinja2 templates bundled as package data and writes rendered output to
~/.skopus/ — a SINGLE directory containing charter, memory, and vault.
Initializes as one git repository with an initial commit.

v0.2.0: vault merged into ~/.skopus/vault/ (previously ~/Vault/ as a
separate repo). One directory, one git repo, simpler mental model.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

from jinja2 import Template

from skopus import __version__
from skopus.wizard import WizardResult

# Full directory layout under ~/.skopus/ (charter + memory + vault, unified)
SKOPUS_LAYOUT = [
    "charter",
    "memory/feedback",
    "memory/project",
    "memory/reference",
    # Vault (Karpathy pattern) — now lives INSIDE ~/.skopus/
    "vault/raw/articles",
    "vault/raw/transcripts",
    "vault/raw/papers",
    "vault/raw/code-snippets",
    "vault/raw/session-notes",
    "vault/wiki/concepts",
    "vault/wiki/entities",
    "vault/wiki/sources",
    "vault/wiki/decisions",
    "vault/wiki/comparisons",
    "vault/output",
]

# Jinja2 templates: (package resource path, output path relative to ~/.skopus/)
TEMPLATES = [
    ("charter/CLAUDE.md.j2", "charter/CLAUDE.md"),
    ("charter/workflow_partnership.md.j2", "charter/workflow_partnership.md"),
    ("charter/user_profile.md.j2", "charter/user_profile.md"),
    ("memory/MEMORY.md.j2", "memory/MEMORY.md"),
    ("vault/CLAUDE.md.j2", "vault/CLAUDE.md"),
    ("vault/wiki/index.md.j2", "vault/wiki/index.md"),
    ("vault/log.md.j2", "vault/log.md"),
]

# Static files (no Jinja rendering): (package resource path, output relative to ~/.skopus/)
STATIC_FILES = [
    ("vault/.claude/commands/ingest.md", "vault/.claude/commands/ingest.md"),
    ("vault/.claude/commands/compile.md", "vault/.claude/commands/compile.md"),
    ("vault/.claude/commands/query.md", "vault/.claude/commands/query.md"),
    ("vault/.claude/commands/lint.md", "vault/.claude/commands/lint.md"),
    ("vault/.claude/commands/wiki.md", "vault/.claude/commands/wiki.md"),
    ("vault/.claude/commands/charter-evolve.md", "vault/.claude/commands/charter-evolve.md"),
    ("vault/.claude/commands/bench-contribute.md", "vault/.claude/commands/bench-contribute.md"),
]

# For backwards-compat: exported so cli.py update command can reference it
VAULT_STATIC = STATIC_FILES


def _load_template_text(rel_path: str) -> str:
    """Load a bundled template's raw text via importlib.resources."""
    return (files("skopus") / "templates" / rel_path).read_text(encoding="utf-8")


def read_adapters_lock(skopus_dir: Path) -> dict[str, object]:
    """Read ~/.skopus/adapters.lock. Returns {} if missing or invalid."""
    lock_path = skopus_dir / "adapters.lock"
    if not lock_path.exists():
        return {}
    try:
        return json.loads(lock_path.read_text())
    except json.JSONDecodeError:
        return {}


def _render(rel_path: str, ctx: dict[str, object]) -> str:
    """Render a Jinja2 template bundled in the package."""
    src = _load_template_text(rel_path)
    return Template(src, trim_blocks=True, lstrip_blocks=True).render(**ctx)


def _write(path: Path, content: str, *, force: bool = False) -> bool:
    """Write content to path. Returns True if written, False if skipped."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _git_init_and_commit(repo_dir: Path, message: str) -> None:
    """Initialize a git repo and commit. Best-effort, non-fatal."""
    identity_args = [
        "-c", "user.email=skopus@localhost",
        "-c", "user.name=Skopus",
        "-c", "commit.gpgsign=false",
    ]
    try:
        if not (repo_dir / ".git").exists():
            subprocess.run(
                ["git", "init", "-q", "-b", "main"],
                cwd=repo_dir, check=True, capture_output=True,
            )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_dir, check=True, capture_output=True,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_dir, check=True, capture_output=True, text=True,
        )
        if status.stdout.strip():
            subprocess.run(
                ["git", *identity_args, "commit", "-q", "-m", message],
                cwd=repo_dir, check=True, capture_output=True,
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


@dataclass
class MaterializeReport:
    """Summary of what was written vs. skipped."""

    written: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.written) + len(self.skipped)


def materialize(
    result: WizardResult,
    skopus_dir: Path,
    *,
    commit: bool = True,
    force: bool = False,
) -> MaterializeReport:
    """Render all templates, create directories, write files, git init.

    Everything goes into one directory (skopus_dir = ~/.skopus/).
    Charter at charter/, memory at memory/, vault at vault/.
    One git repo for the whole thing.
    """
    ctx = result.as_context()
    # Vault path for templates that reference it
    ctx["vault_location"] = str(skopus_dir / "vault")
    report = MaterializeReport()

    def _materialize_one(path: Path, content: str) -> None:
        if _write(path, content, force=force):
            report.written.append(path)
        else:
            report.skipped.append(path)

    # --- Create directory structure ---
    skopus_dir.mkdir(parents=True, exist_ok=True)
    for sub in SKOPUS_LAYOUT:
        (skopus_dir / sub).mkdir(parents=True, exist_ok=True)

    # --- Render Jinja2 templates ---
    for tmpl_rel, out_rel in TEMPLATES:
        rendered = _render(tmpl_rel, ctx)
        _materialize_one(skopus_dir / out_rel, rendered)

    # --- Seed feedback file ---
    seed_profile = result.seed_profile or "blank"
    seed_tmpl_name = f"memory/feedback_seed_{seed_profile.replace('-', '_')}.md"
    try:
        seed_content = _load_template_text(seed_tmpl_name)
        _materialize_one(
            skopus_dir / "memory" / "feedback" / f"{seed_profile}_seed.md",
            seed_content,
        )
    except FileNotFoundError:
        pass

    # --- Copy static files ---
    for tmpl_rel, out_rel in STATIC_FILES:
        content = _load_template_text(tmpl_rel)
        _materialize_one(skopus_dir / out_rel, content)

    # --- adapters.lock (always rewritten — managed state) ---
    adapters_lock = {
        "wired": [a.lower().replace(" ", "-") for a in result.agents],
        "initialized_at": ctx["date"],
        "skopus_version": __version__,
    }
    adapters_lock_path = skopus_dir / "adapters.lock"
    adapters_lock_path.write_text(json.dumps(adapters_lock, indent=2) + "\n")
    report.written.append(adapters_lock_path)

    # --- projects.json (only create if missing) ---
    projects_json_path = skopus_dir / "projects.json"
    if not projects_json_path.exists():
        projects_json_path.write_text("[]\n")
        report.written.append(projects_json_path)
    else:
        report.skipped.append(projects_json_path)

    # --- Global slash commands (~/.claude/commands/) ---
    global_cmds_dir = Path.home() / ".claude" / "commands"
    global_cmds_dir.mkdir(parents=True, exist_ok=True)
    for tmpl_rel, out_rel in STATIC_FILES:
        if ".claude/commands/" in out_rel:
            cmd_name = out_rel.split("/")[-1]
            content = _load_template_text(tmpl_rel)
            global_path = global_cmds_dir / cmd_name
            if _write(global_path, content, force=force):
                report.written.append(global_path)
            else:
                report.skipped.append(global_path)

    # --- Git init + commit (ONE repo for everything) ---
    if commit:
        _git_init_and_commit(skopus_dir, f"init: skopus bootstrap for {result.name}")

    return report


def resolve_skopus_path() -> Path:
    """~/.skopus/ — always user-home."""
    return Path.home() / ".skopus"
