"""Adapter abstract base class.

Every platform adapter implements 5 methods: detect, install, uninstall,
status, session_end_hook. New contributions = one file implementing this ABC.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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
    written: list[Path]
    backed_up: list[Path]
    message: str = ""


class Adapter(ABC):
    """Base class for all platform adapters.

    Each adapter wires the skopus charter + vault references into a specific
    AI coding assistant's context-loading mechanism.
    """

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
        """Wire the charter + vault into the platform's context mechanism.

        If project_path is None, use the current working directory.
        Implementations must back up any existing config files before editing.
        """
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
        """Return the command or mechanism used to trigger /charter-evolve at session end.

        Default: the slash command. Subclasses override if the platform has a
        native session-end hook.
        """
        return "/charter-evolve"
