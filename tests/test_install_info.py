"""Tests for ``skopus.install_info.detect_install_method``.

The detection logic underpins ``skopus self-upgrade`` — getting it wrong
either prints the wrong upgrade command (annoying) or runs a destructive
one against the wrong install (e.g. clobbering an editable install with a
PyPI snapshot, the bug we removed in 6aa33fe).
"""

from __future__ import annotations

import importlib.metadata as md
import json
from pathlib import Path

import pytest

from skopus.install_info import detect_install_method


class _StubDist:
    def __init__(self, *, direct_url: str | None = None, location: str | None = None):
        self._direct_url = direct_url
        self._location = location

    def read_text(self, name: str) -> str | None:
        if name == "direct_url.json":
            return self._direct_url
        return None

    def locate_file(self, name: str) -> str:
        if self._location is None:
            raise RuntimeError("no location")
        return self._location


def _patch_distribution(monkeypatch, stub: _StubDist | None) -> None:
    def _fake(name: str):
        if stub is None:
            raise md.PackageNotFoundError(name)
        return stub
    monkeypatch.setattr("skopus.install_info.md.distribution", _fake)


def test_detects_editable_install(monkeypatch, tmp_path):
    direct_url = json.dumps(
        {
            "url": f"file://{tmp_path}",
            "dir_info": {"editable": True},
        }
    )
    _patch_distribution(monkeypatch, _StubDist(direct_url=direct_url))
    info = detect_install_method(executable="/usr/bin/python3")
    assert info.method == "editable"
    assert info.location == tmp_path
    assert info.upgrade_command == ["git", "-C", str(tmp_path), "pull"]
    assert "git pull" in info.upgrade_hint


def test_detects_pipx_install(monkeypatch):
    # Non-editable distribution
    _patch_distribution(monkeypatch, _StubDist(direct_url=None, location="/some/site-packages"))
    info = detect_install_method(executable="/home/user/.local/share/pipx/venvs/skopus/bin/python")
    assert info.method == "pipx"
    assert info.upgrade_command == ["pipx", "upgrade", "skopus"]


def test_detects_pip_install_in_venv(monkeypatch):
    _patch_distribution(monkeypatch, _StubDist(direct_url=None, location="/venv/lib/site-packages"))
    info = detect_install_method(executable="/venv/bin/python")
    assert info.method == "pip"
    assert info.upgrade_command == ["/venv/bin/python", "-m", "pip", "install", "--upgrade", "skopus"]


def test_detects_unknown_when_distribution_missing(monkeypatch):
    _patch_distribution(monkeypatch, None)
    info = detect_install_method(executable="/usr/bin/python3")
    assert info.method == "unknown"
    assert "skopus" in info.upgrade_hint
    assert info.location is None


def test_editable_takes_precedence_over_pipx_path(monkeypatch, tmp_path):
    """An editable install inside a pipx venv must still be classified as editable.

    This is unusual but possible (``pipx install -e ./skopus``); a wrong
    classification here would auto-run ``pipx upgrade skopus`` and overwrite
    the user's local source tree.
    """
    direct_url = json.dumps(
        {
            "url": f"file://{tmp_path}",
            "dir_info": {"editable": True},
        }
    )
    _patch_distribution(monkeypatch, _StubDist(direct_url=direct_url))
    info = detect_install_method(
        executable="/home/user/.local/share/pipx/venvs/skopus/bin/python"
    )
    assert info.method == "editable"


def test_non_editable_direct_url_falls_through_to_pip(monkeypatch):
    """A direct_url.json without ``dir_info.editable`` must not trigger editable mode."""
    direct_url = json.dumps({"url": "https://files.pythonhosted.org/packages/...", "archive_info": {}})
    _patch_distribution(monkeypatch, _StubDist(direct_url=direct_url, location="/site"))
    info = detect_install_method(executable="/venv/bin/python")
    assert info.method == "pip"


def test_corrupt_direct_url_does_not_crash(monkeypatch):
    _patch_distribution(monkeypatch, _StubDist(direct_url="not-json", location="/site"))
    info = detect_install_method(executable="/venv/bin/python")
    assert info.method == "pip"


# --- CLI integration -------------------------------------------------------


def test_self_upgrade_on_editable_install_aborts_cleanly(monkeypatch, tmp_path):
    """``self-upgrade`` on an editable install must not run any subprocess."""
    from typer.testing import CliRunner

    from skopus.cli import app
    from skopus.install_info import InstallInfo

    fake_info = InstallInfo(
        method="editable",
        upgrade_command=["git", "-C", str(tmp_path), "pull"],
        upgrade_hint=f"cd {tmp_path} && git pull",
        location=tmp_path,
    )
    monkeypatch.setattr("skopus.cli.detect_install_method", lambda: fake_info, raising=False)
    # Belt-and-suspenders: also patch where the function is imported from
    monkeypatch.setattr("skopus.install_info.detect_install_method", lambda **_: fake_info)

    called = {"subprocess_run": 0}

    def _fail_run(*args, **kwargs):
        called["subprocess_run"] += 1
        raise AssertionError("subprocess.run must not be called for editable installs")

    monkeypatch.setattr("subprocess.run", _fail_run)

    result = CliRunner().invoke(app, ["self-upgrade", "--yes"])
    assert result.exit_code == 0
    assert "Editable install detected" in result.stdout
    assert called["subprocess_run"] == 0


def test_self_upgrade_runs_detected_command_for_pipx(monkeypatch):
    """``self-upgrade`` must invoke the exact command from detect_install_method."""
    from typer.testing import CliRunner

    from skopus.cli import app
    from skopus.install_info import InstallInfo

    fake_info = InstallInfo(
        method="pipx",
        upgrade_command=["pipx", "upgrade", "skopus"],
        upgrade_hint="pipx upgrade skopus",
        location=Path("/home/user/.local/share/pipx/venvs/skopus/bin"),
    )
    monkeypatch.setattr("skopus.install_info.detect_install_method", lambda **_: fake_info)

    captured: dict[str, list[str]] = {}

    class _FakeResult:
        returncode = 0
        stderr = ""
        stdout = "successfully upgraded\n"

    def _fake_run(cmd, capture_output, text):
        captured["cmd"] = list(cmd)
        return _FakeResult()

    monkeypatch.setattr("subprocess.run", _fake_run)
    # Stub out the post-upgrade refresh so the test doesn't touch the real filesystem
    monkeypatch.setattr("skopus.cli.update", lambda: None)

    result = CliRunner().invoke(app, ["self-upgrade", "--yes"])
    assert result.exit_code == 0, result.stdout
    assert captured["cmd"] == ["pipx", "upgrade", "skopus"]
