"""Cursor adapter — writes .cursor/rules/skopus.mdc with alwaysApply: true.

Cursor's rules format uses MDC (markdown with YAML frontmatter) and supports
alwaysApply which makes the rule included in every conversation without a
hook. See https://docs.cursor.com/context/rules
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

CURSOR_RULE_PATH = ".cursor/rules/skopus.mdc"


class CursorAdapter(Adapter):
    """Cursor (cursor.com) — always-apply rule in .cursor/rules/."""

    name = "cursor"
    display_name = "Cursor"

    def detect(self) -> bool:
        """Cursor stores per-project rules in .cursor/ and may have a binary."""
        if shutil.which("cursor"):
            return True
        if (Path.home() / ".cursor").exists():
            return True
        return False

    def _rule_path(self, project_path: Path) -> Path:
        return project_path / CURSOR_RULE_PATH

    def install(
        self,
        charter_path: Path,
        vault_path: Path,
        project_path: Path | None = None,
    ) -> AdapterInstallResult:
        project_path = project_path or Path.cwd()
        rule_path = self._rule_path(project_path)
        rule_path.parent.mkdir(parents=True, exist_ok=True)

        inner_block = build_skopus_block(charter_path, vault_path)
        content = (
            "---\n"
            "description: Skopus context — charter, memory, vault, graph\n"
            "alwaysApply: true\n"
            "---\n\n"
            f"{inner_block}"
        )

        backed_up: list[Path] = []
        if rule_path.exists():
            existing = rule_path.read_text(encoding="utf-8")
            if SKOPUS_SECTION_START not in existing:
                backup = rule_path.with_suffix(rule_path.suffix + ".skopus-backup")
                shutil.copy2(rule_path, backup)
                backed_up.append(backup)

        rule_path.write_text(content, encoding="utf-8")

        return AdapterInstallResult(
            status=AdapterStatus.INSTALLED,
            written=[rule_path],
            backed_up=backed_up,
            message=f"Wired Skopus into {rule_path} (alwaysApply: true)",
        )

    def uninstall(self, project_path: Path | None = None) -> AdapterInstallResult:
        project_path = project_path or Path.cwd()
        rule_path = self._rule_path(project_path)
        if not rule_path.exists():
            return AdapterInstallResult(
                status=AdapterStatus.NOT_INSTALLED,
                message=f"No Cursor rule at {rule_path}; nothing to uninstall.",
            )

        content = rule_path.read_text(encoding="utf-8")
        if SKOPUS_SECTION_START not in content:
            return AdapterInstallResult(
                status=AdapterStatus.NOT_INSTALLED,
                message="Skopus block not found in Cursor rule.",
            )

        # Cursor rule is entirely skopus-managed — just delete it.
        # If a backup exists, restore it.
        backup = rule_path.with_suffix(rule_path.suffix + ".skopus-backup")
        if backup.exists():
            shutil.copy2(backup, rule_path)
            backup.unlink()
        else:
            rule_path.unlink()

        return AdapterInstallResult(
            status=AdapterStatus.NOT_INSTALLED,
            written=[rule_path],
            message=f"Skopus Cursor rule removed from {rule_path}.",
        )

    def status(self, project_path: Path | None = None) -> AdapterStatus:
        project_path = project_path or Path.cwd()
        rule_path = self._rule_path(project_path)
        if not rule_path.exists():
            return AdapterStatus.NOT_INSTALLED
        content = rule_path.read_text(encoding="utf-8")
        if SKOPUS_SECTION_START in content and SKOPUS_SECTION_END in content:
            return AdapterStatus.INSTALLED
        return AdapterStatus.NOT_INSTALLED
