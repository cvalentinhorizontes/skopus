"""Claude Code adapter — the reference implementation.

Wires the skopus charter + vault references into a project's CLAUDE.md so
they're auto-loaded at session start. Backs up any existing CLAUDE.md before
editing and appends a clearly-marked Skopus section.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from skopus.adapters.base import Adapter, AdapterInstallResult, AdapterStatus

SKOPUS_SECTION_START = "<!-- skopus:begin -->"
SKOPUS_SECTION_END = "<!-- skopus:end -->"


def _build_skopus_block(charter_path: Path, vault_path: Path) -> str:
    """Construct the markdown block to inject into project CLAUDE.md."""
    memory_index = (charter_path.parent / "memory" / "MEMORY.md").resolve()
    return f"""{SKOPUS_SECTION_START}
## Skopus Context (auto-loaded)

This project is wired to Skopus. The agent loads four lenses at session start:

- **Charter:** @{charter_path}/CLAUDE.md
- **Full charter:** @{charter_path}/workflow_partnership.md
- **User profile:** @{charter_path}/user_profile.md
- **Memory index:** @{memory_index}
- **Vault index:** @{vault_path}/wiki/index.md

Role delineation (the anti-fragmentation rule):
- *How do we work?* → charter
- *What happened before?* → memory (via search)
- *What did we decide or learn?* → vault (via /query)
- *What does the code look like?* → graph (via graphify MCP, when installed)

Managed by Skopus — do not edit between these markers. Run `skopus unlink` to
remove or `skopus doctor` to verify the wiring.

*Wired: {datetime.now().strftime("%Y-%m-%d")}*
{SKOPUS_SECTION_END}
"""


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
        claude_md = project_path / "CLAUDE.md"
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
        claude_md = project_path / "CLAUDE.md"
        if not claude_md.exists():
            return AdapterInstallResult(
                status=AdapterStatus.NOT_INSTALLED,
                written=[],
                backed_up=[],
                message="No CLAUDE.md found; nothing to uninstall.",
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
        claude_md = project_path / "CLAUDE.md"
        if not claude_md.exists():
            return AdapterStatus.NOT_INSTALLED
        content = claude_md.read_text(encoding="utf-8")
        if SKOPUS_SECTION_START in content and SKOPUS_SECTION_END in content:
            return AdapterStatus.INSTALLED
        return AdapterStatus.NOT_INSTALLED

    def session_end_hook(self) -> str:
        """Claude Code uses slash commands; a future PreStop hook is planned."""
        return "/charter-evolve"
