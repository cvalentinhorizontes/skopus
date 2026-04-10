"""Adapter abstract base class + MarkdownAdapter DRY helper.

Every platform adapter implements 5 methods: detect, install, uninstall,
status, session_end_hook. New contributions = one file subclassing
MarkdownAdapter (for platforms that use a markdown context file) or Adapter
directly (for platforms with unusual integration).
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

SKOPUS_SECTION_START = "<!-- skopus:begin -->"
SKOPUS_SECTION_END = "<!-- skopus:end -->"


class AdapterStatus(str, Enum):
    """Status of an adapter's wiring into a host project."""

    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    PARTIAL = "partial"  # wired but some files missing
    BROKEN = "broken"  # wiring corrupt, needs reinstall


@dataclass
class AdapterInstallResult:
    """Result of calling `install()` on an adapter."""

    status: AdapterStatus
    written: list[Path] = field(default_factory=list)
    backed_up: list[Path] = field(default_factory=list)
    message: str = ""


class Adapter(ABC):
    """Base class for all platform adapters."""

    name: str = "abstract"
    display_name: str = "Abstract Adapter"

    @abstractmethod
    def detect(self) -> bool:
        """Return True if this platform appears installed on the host."""
        ...

    @abstractmethod
    def install(
        self,
        charter_path: Path,
        vault_path: Path,
        project_path: Path | None = None,
    ) -> AdapterInstallResult:
        """Wire the charter + vault into the platform's context mechanism."""
        ...

    @abstractmethod
    def uninstall(self, project_path: Path | None = None) -> AdapterInstallResult:
        """Reverse the installation, restoring any backed-up configs."""
        ...

    @abstractmethod
    def status(self, project_path: Path | None = None) -> AdapterStatus:
        """Check the current wiring status for a project."""
        ...

    def session_end_hook(self) -> str:
        """Command used to trigger /charter-evolve at session end."""
        return "/charter-evolve"


def build_skopus_block(
    charter_path: Path,
    vault_path: Path,
    *,
    format: str = "markdown",
) -> str:
    """Construct the skopus context block to inject into a platform's context file.

    The block is bracketed by HTML comment markers (<!-- skopus:begin --> /
    <!-- skopus:end -->) so it can be detected and updated idempotently.
    Markdown format works for .md files; Cursor's .mdc format inherits it.
    """
    memory_index = (charter_path.parent / "memory" / "MEMORY.md").resolve()
    date = datetime.now().strftime("%Y-%m-%d")

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

*Wired: {date}*
{SKOPUS_SECTION_END}
"""


class MarkdownAdapter(Adapter):
    """Base adapter for platforms that load context from a single markdown file.

    Subclasses configure:
      - context_file_name: the markdown file the platform auto-loads
        (e.g. "CLAUDE.md", "AGENTS.md", "GEMINI.md")
      - prefer_dotdir_name: optional subdir preference (e.g. ".claude") —
        if present in the project, the adapter writes to
        <project>/<prefer_dotdir_name>/<context_file_name>
      - detect_config_dirs: list of paths to check for platform installation
      - detect_binaries: list of CLI binary names to check on PATH

    The install/uninstall/status logic is handled here; subclasses only
    override detect() if they need custom detection logic.
    """

    context_file_name: str = "AGENTS.md"
    prefer_dotdir_name: str | None = None  # e.g. ".claude" for Claude Code
    detect_config_dirs: list[str] = []  # e.g. [".cursor", "~/.gemini"]
    detect_binaries: list[str] = []  # e.g. ["cursor", "gemini"]

    def _context_file_path(self, project_path: Path) -> Path:
        """Resolve where to write the context file for a given project."""
        if self.prefer_dotdir_name:
            dotdir = project_path / self.prefer_dotdir_name
            if dotdir.is_dir():
                return dotdir / self.context_file_name
        return project_path / self.context_file_name

    def detect(self) -> bool:
        """Default detection: config dir or binary on PATH."""
        for dir_path in self.detect_config_dirs:
            expanded = Path(dir_path).expanduser()
            if expanded.exists():
                return True
        for binary in self.detect_binaries:
            if shutil.which(binary):
                return True
        return False

    def install(
        self,
        charter_path: Path,
        vault_path: Path,
        project_path: Path | None = None,
    ) -> AdapterInstallResult:
        project_path = project_path or Path.cwd()
        project_path.mkdir(parents=True, exist_ok=True)
        target = self._context_file_path(project_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        backed_up: list[Path] = []
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if SKOPUS_SECTION_START not in existing:
                # Preserve any pre-existing user content via a backup copy
                backup = target.with_suffix(target.suffix + ".skopus-backup")
                shutil.copy2(target, backup)
                backed_up.append(backup)
        else:
            existing = ""

        block = build_skopus_block(charter_path, vault_path)

        if SKOPUS_SECTION_START in existing:
            start = existing.index(SKOPUS_SECTION_START)
            end = existing.index(SKOPUS_SECTION_END) + len(SKOPUS_SECTION_END)
            new_content = existing[:start] + block.rstrip() + existing[end:]
        else:
            separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
            new_content = existing + separator + block

        target.write_text(new_content, encoding="utf-8")

        return AdapterInstallResult(
            status=AdapterStatus.INSTALLED,
            written=[target],
            backed_up=backed_up,
            message=f"Wired Skopus into {target}",
        )

    def uninstall(self, project_path: Path | None = None) -> AdapterInstallResult:
        project_path = project_path or Path.cwd()
        target = self._context_file_path(project_path)
        if not target.exists():
            return AdapterInstallResult(
                status=AdapterStatus.NOT_INSTALLED,
                message=f"No {self.context_file_name} at {target}; nothing to uninstall.",
            )

        existing = target.read_text(encoding="utf-8")
        if SKOPUS_SECTION_START not in existing:
            return AdapterInstallResult(
                status=AdapterStatus.NOT_INSTALLED,
                message=f"Skopus block not found in {target}.",
            )

        start = existing.index(SKOPUS_SECTION_START)
        end = existing.index(SKOPUS_SECTION_END) + len(SKOPUS_SECTION_END)
        new_content = (existing[:start] + existing[end:]).rstrip() + "\n"

        if new_content.strip() == "":
            backup = target.with_suffix(target.suffix + ".skopus-backup")
            if backup.exists():
                shutil.copy2(backup, target)
                backup.unlink()
            else:
                target.unlink()
        else:
            target.write_text(new_content, encoding="utf-8")

        return AdapterInstallResult(
            status=AdapterStatus.NOT_INSTALLED,
            written=[target],
            message=f"Skopus block removed from {target}.",
        )

    def status(self, project_path: Path | None = None) -> AdapterStatus:
        project_path = project_path or Path.cwd()
        target = self._context_file_path(project_path)
        if not target.exists():
            return AdapterStatus.NOT_INSTALLED
        content = target.read_text(encoding="utf-8")
        if SKOPUS_SECTION_START in content and SKOPUS_SECTION_END in content:
            return AdapterStatus.INSTALLED
        return AdapterStatus.NOT_INSTALLED
