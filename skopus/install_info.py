"""Detect how Skopus was installed so ``skopus self-upgrade`` can do the right thing.

Skopus's install surface has at least three flavors that need different
upgrade commands:

- **editable** — ``pip install -e .`` from a local clone. Upgrade = ``git pull``.
- **pipx** — ``pipx install skopus``, the recommended path for CLI tools.
  Upgrade = ``pipx upgrade skopus``.
- **pip** — anything else (``pip install`` in a venv, ``--user`` install).
  Upgrade = ``pip install --upgrade skopus`` against the same interpreter.

The OLD ``skopus update`` ran ``pip install --upgrade skopus`` unconditionally,
which (a) broke on PEP-668 managed Pythons and (b) would clobber an editable
install. Detection lets each install type get the upgrade command it needs.
"""

from __future__ import annotations

import importlib.metadata as md
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InstallInfo:
    method: str  # "editable", "pipx", "pip", "unknown"
    upgrade_command: list[str]  # argv-style list, ready for subprocess.run
    upgrade_hint: str  # human-readable rendering of upgrade_command
    location: Path | None  # editable: source dir; pipx/pip: site-packages; unknown: None
    notes: str = ""  # extra context (PEP 668, etc.)


def detect_install_method(executable: str | None = None) -> InstallInfo:
    """Detect Skopus's install method by inspecting package metadata + sys.executable.

    ``executable`` overrides ``sys.executable`` for testing.
    """
    py = executable or sys.executable

    try:
        dist = md.distribution("skopus")
    except md.PackageNotFoundError:
        return InstallInfo(
            method="unknown",
            upgrade_command=["pipx", "upgrade", "skopus"],
            upgrade_hint="pipx upgrade skopus",
            location=None,
            notes="skopus not registered with importlib.metadata",
        )

    editable_path = _editable_source_path(dist)
    if editable_path is not None:
        return InstallInfo(
            method="editable",
            upgrade_command=["git", "-C", str(editable_path), "pull"],
            upgrade_hint=f"cd {editable_path} && git pull",
            location=editable_path,
        )

    if _is_pipx_executable(py):
        return InstallInfo(
            method="pipx",
            upgrade_command=["pipx", "upgrade", "skopus"],
            upgrade_hint="pipx upgrade skopus",
            location=Path(py).parent,
        )

    return InstallInfo(
        method="pip",
        upgrade_command=[py, "-m", "pip", "install", "--upgrade", "skopus"],
        upgrade_hint=f"{py} -m pip install --upgrade skopus",
        location=Path(_dist_location(dist)) if _dist_location(dist) else None,
    )


def _editable_source_path(dist: md.Distribution) -> Path | None:
    """Return the local source directory if ``dist`` is an editable install, else None."""
    try:
        raw = dist.read_text("direct_url.json")
    except FileNotFoundError:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not data.get("dir_info", {}).get("editable"):
        return None
    url = data.get("url", "")
    if url.startswith("file://"):
        return Path(url[len("file://") :])
    return None


def _is_pipx_executable(executable: str) -> bool:
    """Return True if ``executable`` lives inside a pipx-managed venv."""
    parts = Path(executable).parts
    if "pipx" in parts and "venvs" in parts:
        return True
    return False


def _dist_location(dist: md.Distribution) -> str | None:
    """Best-effort site-packages directory for ``dist``."""
    try:
        return str(dist.locate_file(""))
    except Exception:  # noqa: BLE001 — defensive, this metadata is finicky
        return None
