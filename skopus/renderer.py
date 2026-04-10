"""Template rendering and file materialization.

Loads Jinja2 templates bundled as package data and writes rendered output to
~/.skopus/ (charter + memory) and the configured vault location. Initializes
both as git repositories with an initial commit.
"""

from __future__ import annotations

import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

from jinja2 import Template

from skopus import __version__
from skopus.wizard import WizardResult

# Structural layout under ~/.skopus/
SKOPUS_LAYOUT = {
    "charter": [],
    "memory/feedback": [],
    "memory/project": [],
    "memory/reference": [],
}

# Structural layout under the vault
VAULT_LAYOUT = [
    "raw/articles",
    "raw/transcripts",
    "raw/papers",
    "raw/code-snippets",
    "raw/session-notes",
    "wiki/concepts",
    "wiki/entities",
    "wiki/sources",
    "wiki/decisions",
    "wiki/comparisons",
    "output",
    ".claude/commands",
]

# Jinja2 templates: (package resource path, relative output path under ~/.skopus/)
CHARTER_TEMPLATES = [
    ("charter/CLAUDE.md.j2", "charter/CLAUDE.md"),
    ("charter/workflow_partnership.md.j2", "charter/workflow_partnership.md"),
    ("charter/user_profile.md.j2", "charter/user_profile.md"),
]

MEMORY_TEMPLATES = [
    ("memory/MEMORY.md.j2", "memory/MEMORY.md"),
]

# Jinja2 templates for the vault: (package resource path, relative output path under vault)
VAULT_TEMPLATES = [
    ("vault/CLAUDE.md.j2", "CLAUDE.md"),
    ("vault/wiki/index.md.j2", "wiki/index.md"),
    ("vault/log.md.j2", "log.md"),
]

# Static files copied verbatim (no Jinja rendering): (package resource path, relative output path)
VAULT_STATIC = [
    ("vault/.claude/commands/ingest.md", ".claude/commands/ingest.md"),
    ("vault/.claude/commands/compile.md", ".claude/commands/compile.md"),
    ("vault/.claude/commands/query.md", ".claude/commands/query.md"),
    ("vault/.claude/commands/lint.md", ".claude/commands/lint.md"),
    ("vault/.claude/commands/wiki.md", ".claude/commands/wiki.md"),
]


def _load_template_text(rel_path: str) -> str:
    """Load a bundled template's raw text via importlib.resources."""
    return (files("skopus") / "templates" / rel_path).read_text(encoding="utf-8")


def read_adapters_lock(skopus_dir: Path) -> dict[str, object]:
    """Read ~/.skopus/adapters.lock. Returns {} if missing or invalid."""
    import json

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


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git_init_and_commit(repo_dir: Path, message: str) -> None:
    """Initialize a git repo (if not already) and commit everything.

    Best-effort: if git isn't available, we log and continue. Uses inline
    `-c user.email` / `-c user.name` flags so the commit succeeds even when
    the host has no global git identity configured.
    """
    identity_args = [
        "-c",
        "user.email=skopus@localhost",
        "-c",
        "user.name=Skopus",
        "-c",
        "commit.gpgsign=false",
    ]
    try:
        if not (repo_dir / ".git").exists():
            subprocess.run(
                ["git", "init", "-q", "-b", "main"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )
        # Only commit if there's something to commit
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        if status.stdout.strip():
            subprocess.run(
                ["git", *identity_args, "commit", "-q", "-m", message],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Git not available or commit failed — non-fatal, the files still materialize
        pass


def materialize(
    result: WizardResult,
    skopus_dir: Path,
    vault_dir: Path,
    *,
    commit: bool = True,
) -> list[Path]:
    """Render all templates, create directory structure, write files, git init.

    Returns the list of written paths.
    """
    ctx = result.as_context()
    written: list[Path] = []

    # --- Charter + memory (~/.skopus/) ---
    skopus_dir.mkdir(parents=True, exist_ok=True)
    for sub in SKOPUS_LAYOUT:
        (skopus_dir / sub).mkdir(parents=True, exist_ok=True)

    for tmpl_rel, out_rel in CHARTER_TEMPLATES + MEMORY_TEMPLATES:
        rendered = _render(tmpl_rel, ctx)
        out_path = skopus_dir / out_rel
        _write(out_path, rendered)
        written.append(out_path)

    # Seed feedback file based on profile (static, copied verbatim)
    seed_profile = result.seed_profile or "blank"
    seed_tmpl_name = f"memory/feedback_seed_{seed_profile.replace('-', '_')}.md"
    try:
        seed_content = _load_template_text(seed_tmpl_name)
        seed_out = skopus_dir / "memory" / "feedback" / f"{seed_profile}_seed.md"
        _write(seed_out, seed_content)
        written.append(seed_out)
    except FileNotFoundError:
        # Unknown profile — skip silently
        pass

    # adapters.lock — track which platforms were wired AND where the vault lives
    adapters_lock = {
        "wired": [a.lower().replace(" ", "-") for a in result.agents],
        "vault_location": str(vault_dir),
        "initialized_at": ctx["date"],
        "skopus_version": __version__,
    }
    import json

    adapters_lock_path = skopus_dir / "adapters.lock"
    _write(adapters_lock_path, json.dumps(adapters_lock, indent=2) + "\n")
    written.append(adapters_lock_path)

    # projects.json — list of linked projects (starts empty)
    projects_json_path = skopus_dir / "projects.json"
    _write(projects_json_path, "[]\n")
    written.append(projects_json_path)

    if commit:
        _git_init_and_commit(skopus_dir, f"init: skopus bootstrap for {result.name}")

    # --- Vault (~/Vault/) ---
    vault_dir.mkdir(parents=True, exist_ok=True)
    for sub in VAULT_LAYOUT:
        (vault_dir / sub).mkdir(parents=True, exist_ok=True)

    for tmpl_rel, out_rel in VAULT_TEMPLATES:
        rendered = _render(tmpl_rel, ctx)
        out_path = vault_dir / out_rel
        _write(out_path, rendered)
        written.append(out_path)

    for tmpl_rel, out_rel in VAULT_STATIC:
        content = _load_template_text(tmpl_rel)
        out_path = vault_dir / out_rel
        _write(out_path, content)
        written.append(out_path)

    if commit:
        _git_init_and_commit(vault_dir, f"init: vault bootstrap for {result.name}")

    return written


def resolve_vault_path(vault_location: str) -> Path:
    """Expand ~ and env vars in the vault location string."""
    import os

    expanded = os.path.expanduser(os.path.expandvars(vault_location))
    return Path(expanded).resolve()


def resolve_skopus_path() -> Path:
    """~/.skopus/ — always user-home."""
    return Path.home() / ".skopus"
