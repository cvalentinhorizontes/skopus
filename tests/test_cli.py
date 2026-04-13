"""CLI smoke tests using typer's CliRunner (v0.2.0 — unified directory)."""

from pathlib import Path

from typer.testing import CliRunner

from skopus.cli import app


def test_version_command():
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "skopus" in result.stdout


def test_init_non_interactive(tmp_path, monkeypatch):
    """End-to-end: skopus init --non-interactive creates all expected files."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "init",
            "--non-interactive",
            "--name",
            "SmokeTest",
            "--profile",
            "solo-dev",
        ],
    )

    if result.exit_code != 0:
        print("STDOUT:", result.stdout)
        print("EXCEPTION:", result.exception)
    assert result.exit_code == 0

    skopus_dir = tmp_path / ".skopus"
    assert (skopus_dir / "charter" / "CLAUDE.md").exists()
    assert (skopus_dir / "memory" / "MEMORY.md").exists()
    # Vault is now inside ~/.skopus/vault/
    assert (skopus_dir / "vault" / "CLAUDE.md").exists()
    assert (skopus_dir / "vault" / "wiki" / "index.md").exists()

    charter_text = (skopus_dir / "charter" / "CLAUDE.md").read_text()
    assert "SmokeTest" in charter_text


def test_doctor_reports_missing_installation(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1


def test_doctor_reports_installed_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    init_result = runner.invoke(
        app,
        ["init", "--non-interactive", "--name", "DocTest"],
    )
    assert init_result.exit_code == 0

    doctor_result = runner.invoke(app, ["doctor"])
    assert doctor_result.exit_code == 0
    assert "Charter" in doctor_result.stdout
