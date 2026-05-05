"""Test that `skopus.__version__` matches `pyproject.toml` version.

Surfaced 2026-05-05 by the Phase 2 manual smoke run: pyproject was
bumped to 0.8.0 in v0.8.0 release prep but `__version__` stayed at
0.5.1, so MCP `skopus_status` and `skopus version` reported a stale
number. The two literals MUST stay in lockstep; this test enforces it.
"""

from __future__ import annotations

import re
from pathlib import Path

import skopus

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _read_pyproject_version() -> str:
    """Parse the version line out of pyproject.toml without a TOML lib."""
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, 'pyproject.toml has no top-level `version = "..."` line'
    return match.group(1)


def test_runtime_version_matches_pyproject():
    """skopus.__version__ literal must equal pyproject.toml's version.

    If this fails: bump `__version__` in skopus/__init__.py to match
    [project].version in pyproject.toml. Both are single sources of truth
    for their respective consumers (pyproject for pip/wheel metadata,
    __init__ for runtime imports); they must agree.
    """
    pyproject_v = _read_pyproject_version()
    assert skopus.__version__ == pyproject_v, (
        f"skopus.__version__={skopus.__version__!r} does not match "
        f"pyproject.toml version={pyproject_v!r}. Bump the literal in "
        "skopus/__init__.py."
    )
