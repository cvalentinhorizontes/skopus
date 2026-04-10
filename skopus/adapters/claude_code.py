"""Claude Code adapter — the reference implementation.

Wires the skopus charter + vault references into a project's CLAUDE.md so
they're auto-loaded at session start. Backs up any existing CLAUDE.md before
editing and appends a clearly-marked Skopus section.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from skopus.adapters.base import (
    SKOPUS_SECTION_END,
    SKOPUS_SECTION_START,
    Adapter,
    AdapterInstallResult,
    AdapterStatus,
    build_skopus_block,
)


def claude_md_path(project_path: Path) -> Path:
    """Return the project's Claude Code context file.

    Prefers ``<project>/.claude/CLAUDE.md`` when the ``.claude/`` directory
    already exists (Claude Code's convention for project-scoped context).
    Falls back to ``<project>/CLAUDE.md`` otherwise.
    """
    claude_dir = project_path / ".claude"
    if claude_dir.is_dir():
        return claude_dir / "CLAUDE.md"
    return project_path / "CLAUDE.md"


# Backwards-compat alias — some tests and callers reference the underscore name
_build_skopus_block = build_skopus_block


class ClaudeCodeAdapter(Adapter):
    """Reference adapter for Claude Code."""

    name = "claude-code"
    display_name = "Claude Code"

    def detect(self) -> bool:
        """Claude Code stores global state under ~/.claude/."""
        return (Path.home() / ".claude").exists()

    def install(
        self,
        charter_path: Path,
        vault_path: Path,
        project_path: Path | None = None,
    ) -> AdapterInstallResult:
        """Append a Skopus context block to the project's CLAUDE.md.

        Creates CLAUDE.md if missing. Backs up any existing file before editing.
        If a previous Skopus block exists, it's replaced in place (idempotent).
        """
        project_path = project_path or Path.cwd()
        project_path.mkdir(parents=True, exist_ok=True)
        claude_md = claude_md_path(project_path)
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        backed_up: list[Path] = []

        # Backup existing CLAUDE.md on first install
        if claude_md.exists():
            existing = claude_md.read_text(encoding="utf-8")
            # Only back up if no previous Skopus block (first install)
            if SKOPUS_SECTION_START not in existing:
                backup_path = claude_md.with_suffix(".md.skopus-backup")
                shutil.copy2(claude_md, backup_path)
                backed_up.append(backup_path)
        else:
            existing = ""

        block = _build_skopus_block(charter_path, vault_path)

        if SKOPUS_SECTION_START in existing:
            # Idempotent update: replace existing block
            start = existing.index(SKOPUS_SECTION_START)
            end = existing.index(SKOPUS_SECTION_END) + len(SKOPUS_SECTION_END)
            new_content = existing[:start] + block.rstrip() + existing[end:]
        else:
            # First install: append block with a leading newline if needed
            separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
            new_content = existing + separator + block

        claude_md.write_text(new_content, encoding="utf-8")

        return AdapterInstallResult(
            status=AdapterStatus.INSTALLED,
            written=[claude_md],
            backed_up=backed_up,
            message=f"Wired Skopus into {claude_md}",
        )

    def uninstall(self, project_path: Path | None = None) -> AdapterInstallResult:
        """Remove the Skopus block from the project's CLAUDE.md.

        Leaves the rest of the file intact. If CLAUDE.md becomes empty after
        removal AND a backup exists, restore the backup.
        """
        project_path = project_path or Path.cwd()
        claude_md = claude_md_path(project_path)
        if not claude_md.exists():
            return AdapterInstallResult(
                status=AdapterStatus.NOT_INSTALLED,
                written=[],
                backed_up=[],
                message=f"No CLAUDE.md found at {claude_md}; nothing to uninstall.",
            )

        existing = claude_md.read_text(encoding="utf-8")
        if SKOPUS_SECTION_START not in existing:
            return AdapterInstallResult(
                status=AdapterStatus.NOT_INSTALLED,
                written=[],
                backed_up=[],
                message="Skopus block not found in CLAUDE.md.",
            )

        start = existing.index(SKOPUS_SECTION_START)
        end = existing.index(SKOPUS_SECTION_END) + len(SKOPUS_SECTION_END)
        new_content = (existing[:start] + existing[end:]).rstrip() + "\n"

        if new_content.strip() == "":
            # File is empty after removal — restore backup if we have one
            backup_path = claude_md.with_suffix(".md.skopus-backup")
            if backup_path.exists():
                shutil.copy2(backup_path, claude_md)
                backup_path.unlink()
            else:
                claude_md.unlink()
        else:
            claude_md.write_text(new_content, encoding="utf-8")

        return AdapterInstallResult(
            status=AdapterStatus.NOT_INSTALLED,
            written=[claude_md],
            backed_up=[],
            message="Skopus block removed from CLAUDE.md.",
        )

    def status(self, project_path: Path | None = None) -> AdapterStatus:
        """Report whether the wiring is intact in the project."""
        project_path = project_path or Path.cwd()
        claude_md = claude_md_path(project_path)
        if not claude_md.exists():
            return AdapterStatus.NOT_INSTALLED
        content = claude_md.read_text(encoding="utf-8")
        if SKOPUS_SECTION_START in content and SKOPUS_SECTION_END in content:
            return AdapterStatus.INSTALLED
        return AdapterStatus.NOT_INSTALLED

    def session_end_hook(self) -> str:
        """Claude Code uses slash commands; a future PreStop hook is planned."""
        return "/charter-evolve"
