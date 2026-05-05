"""Tests for the `skopus mcp serve` CLI command (the MCP server entry point)."""

from typer.testing import CliRunner

from skopus.cli import app

runner = CliRunner()


def test_mcp_command_group_lists_serve_subcommand():
    """skopus mcp --help lists `serve` as a subcommand."""
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "serve" in result.output.lower()


def test_mcp_serve_help_renders():
    """skopus mcp serve --help works without spawning the server."""
    result = runner.invoke(app, ["mcp", "serve", "--help"])
    assert result.exit_code == 0
    # Help should mention either stdio or "serve" (the subcommand purpose)
    out = result.output.lower()
    assert "stdio" in out or "serve" in out
