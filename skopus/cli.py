"""Skopus CLI — typer entrypoint.

Commands:
    skopus init         Run the interactive wizard, scaffold charter + vault.
    skopus link [path]  Wire the charter + vault into a project's CLAUDE.md.
    skopus unlink       Remove the wiring from a project.
    skopus doctor       Health check the skopus installation.
    skopus version      Show the version.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from skopus import __version__
from skopus.adapters import ADAPTERS, get_adapter
from skopus.adapters.base import AdapterStatus
from skopus.graphify_bridge import (
    first_build_hint,
    graph_exists,
    graphify_available,
    install_graphify_for_claude,
)
from skopus.renderer import (
    materialize,
    read_adapters_lock,
    resolve_skopus_path,
    resolve_vault_path,
)
from skopus.wizard import WizardResult, default_result, run_wizard

app = typer.Typer(
    name="skopus",
    help="Persistent four-lens context for AI coding assistants.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()


def _track_linked_project(skopus_dir: Path, project_path: Path) -> None:
    """Add a project to ~/.skopus/projects.json if not already present."""
    projects_path = skopus_dir / "projects.json"
    try:
        projects: list[str] = (
            json.loads(projects_path.read_text()) if projects_path.exists() else []
        )
    except json.JSONDecodeError:
        projects = []
    project_str = str(project_path.resolve())
    if project_str not in projects:
        projects.append(project_str)
        projects_path.write_text(json.dumps(projects, indent=2) + "\n")


@app.command()
def version() -> None:
    """Show the version."""
    console.print(f"skopus [bold cyan]v{__version__}[/bold cyan]")


@app.command()
def init(
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "-n",
        help="Skip the wizard, use defaults. Useful for testing or CI.",
    ),
    name: str = typer.Option(
        "Developer",
        "--name",
        help="Name to seed in non-interactive mode.",
    ),
    profile: str = typer.Option(
        "blank",
        "--profile",
        help="Seed profile for non-interactive mode: blank, solo-dev, team-lead, research, founder, bug-hunter.",
    ),
    vault: str = typer.Option(
        "~/Vault",
        "--vault",
        help="Vault location (tilde expanded).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing files in the charter/memory/vault. Default is non-destructive merge.",
    ),
) -> None:
    """Initialize Skopus — scaffold the charter, memory, and vault."""
    console.print(
        Panel.fit(
            "[bold]Skopus — Four-Lens Context for AI Coding Assistants[/bold]\n\n"
            "Scaffolding your charter, memory, and vault.\n"
            "Everything is editable. [italic]/charter-evolve[/italic] will grow it over time.",
            title="skopus init",
            border_style="cyan",
        )
    )

    if non_interactive:
        result = default_result(name=name, seed_profile=profile)
        result.vault_location = vault
    else:
        result = run_wizard()

    skopus_dir = resolve_skopus_path()
    vault_dir = resolve_vault_path(result.vault_location)

    console.print(f"\n[dim]Charter + memory →[/dim] {skopus_dir}")
    console.print(f"[dim]Vault          →[/dim] {vault_dir}")

    if skopus_dir.exists() and any(skopus_dir.iterdir()):
        mode_note = (
            "[yellow]force mode[/yellow] — existing files will be overwritten"
            if force
            else "non-destructive mode — existing files will be preserved"
        )
        console.print(
            f"\n[yellow]⚠[/yellow]  {skopus_dir} already has content "
            f"({mode_note})."
        )

    report = materialize(result, skopus_dir, vault_dir, force=force)

    console.print(
        f"\n[green]✓[/green] Wrote {len(report.written)} files"
        + (
            f"  [dim]({len(report.skipped)} already present, kept)[/dim]"
            if report.skipped
            else ""
        )
    )

    # Wire adapters for the requested agents
    wired_any = False
    cwd = Path.cwd()
    for agent_name in result.agents:
        key = agent_name.lower().replace(" ", "-")
        if key not in ADAPTERS:
            console.print(
                f"  [dim]…[/dim] {agent_name}: adapter planned for v0.0.2 (skipped)"
            )
            continue
        adapter = get_adapter(key)
        if not adapter.detect():
            console.print(
                f"  [dim]…[/dim] {agent_name}: not detected on host (skipped)"
            )
            continue
        install_result = adapter.install(
            charter_path=skopus_dir / "charter",
            vault_path=vault_dir,
            project_path=cwd,
        )
        console.print(
            f"  [green]✓[/green] {agent_name}: {install_result.message}"
        )
        wired_any = True

    # If any adapter wired and cwd looks like a project, track it and wire graphify
    if wired_any and (cwd / ".git").exists():
        _track_linked_project(skopus_dir, cwd)

        # Wire the fourth lens (graphify) into the project
        if graphify_available():
            console.print("\n[bold]Wiring graphify (lens 4)...[/bold]")
            graphify_result = install_graphify_for_claude(
                project_path=cwd,
                scope=result.graphify_scope,
            )
            if graphify_result.installed:
                console.print(f"  [green]✓[/green] {graphify_result.message}")
                if not graphify_result.graph_exists:
                    scope_str = " ".join(result.graphify_scope) if result.graphify_scope else "."
                    console.print(
                        f"  [dim]First build pending. Inside Claude Code, run: "
                        f"[italic]/graphify {scope_str}[/italic][/dim]"
                    )
            else:
                console.print(f"  [yellow]⚠[/yellow] {graphify_result.message}")
        else:
            console.print(
                "\n[yellow]⚠[/yellow] graphify CLI not on PATH — lens 4 skipped. "
                "Reinstall skopus to pick up graphifyy."
            )

    # Final summary
    summary = Table(title="Skopus Installation Summary", show_header=False, box=None)
    summary.add_column("", style="dim")
    summary.add_column("")
    summary.add_row("Name:", result.name)
    summary.add_row("Role:", result.role)
    summary.add_row("Stack:", result.stack)
    summary.add_row("Charter:", str(skopus_dir / "charter" / "CLAUDE.md"))
    summary.add_row("Memory:", str(skopus_dir / "memory" / "MEMORY.md"))
    summary.add_row("Vault:", str(vault_dir / "wiki" / "index.md"))
    summary.add_row("Agents:", ", ".join(result.agents))
    console.print("\n")
    console.print(summary)

    console.print(
        "\n[bold cyan]Next steps:[/bold cyan]\n"
        "  1. Review your charter: [italic]cat "
        f"{skopus_dir / 'charter' / 'CLAUDE.md'}[/italic]\n"
        "  2. Link a project:     [italic]cd my-project && skopus link[/italic]\n"
        "  3. Health check:       [italic]skopus doctor[/italic]\n"
    )
    if not wired_any and result.agents:
        console.print(
            "[dim]No agent adapters were auto-wired (none detected or v0.0.2 deferred). "
            "Run `skopus link` inside a project to wire Claude Code manually.[/dim]"
        )


@app.command()
def link(
    project_path: Path = typer.Argument(
        Path("."),
        exists=False,
        file_okay=False,
        dir_okay=True,
        help="Project directory to link. Defaults to cwd.",
    ),
    agent: str = typer.Option(
        "claude-code",
        "--agent",
        "-a",
        help="Which adapter to use. Default: claude-code.",
    ),
) -> None:
    """Wire the Skopus charter + vault into a project's CLAUDE.md."""
    skopus_dir = resolve_skopus_path()
    if not skopus_dir.exists():
        console.print(
            "[red]✗[/red] Skopus is not initialized. Run [italic]skopus init[/italic] first."
        )
        raise typer.Exit(code=1)

    # Read adapters.lock to find the vault location from init
    lock_data = read_adapters_lock(skopus_dir)
    vault_hint = str(lock_data.get("vault_location") or "~/Vault")
    vault_dir = resolve_vault_path(vault_hint)
    if not vault_dir.exists():
        console.print(
            f"[yellow]⚠[/yellow]  Vault not found at {vault_dir}. "
            "Run [italic]skopus init[/italic] first, or specify --vault."
        )
        raise typer.Exit(code=1)

    resolved_project = project_path.resolve()
    console.print(f"Linking [bold]{resolved_project}[/bold] to Skopus via [bold]{agent}[/bold]...")

    try:
        adapter_impl = get_adapter(agent)
    except KeyError as e:
        console.print(f"[red]✗[/red] {e}")
        console.print(
            f"[dim]Available adapters: {', '.join(sorted(ADAPTERS))}. "
            "More adapters ship in v0.0.2.[/dim]"
        )
        raise typer.Exit(code=1) from None

    result = adapter_impl.install(
        charter_path=skopus_dir / "charter",
        vault_path=vault_dir,
        project_path=resolved_project,
    )
    console.print(f"[green]✓[/green] {result.message}")
    _track_linked_project(skopus_dir, resolved_project)


@app.command()
def unlink(
    project_path: Path = typer.Argument(
        Path("."),
        exists=False,
        file_okay=False,
        dir_okay=True,
        help="Project directory to unlink. Defaults to cwd.",
    ),
    agent: str = typer.Option("claude-code", "--agent", "-a"),
) -> None:
    """Remove Skopus wiring from a project."""
    resolved = project_path.resolve()
    try:
        adapter_impl = get_adapter(agent)
    except KeyError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1) from None

    result = adapter_impl.uninstall(project_path=resolved)
    console.print(f"[green]✓[/green] {result.message}")

    # Remove from projects.json
    skopus_dir = resolve_skopus_path()
    projects_path = skopus_dir / "projects.json"
    if projects_path.exists():
        try:
            projects: list[str] = json.loads(projects_path.read_text())
            project_str = str(resolved)
            if project_str in projects:
                projects.remove(project_str)
                projects_path.write_text(json.dumps(projects, indent=2) + "\n")
        except json.JSONDecodeError:
            pass


@app.command()
def doctor() -> None:
    """Health check the Skopus installation — charter, memory, vault, linked projects."""
    skopus_dir = resolve_skopus_path()
    if not skopus_dir.exists():
        console.print(
            "[red]✗[/red] Skopus is not initialized. Run [italic]skopus init[/italic] first."
        )
        raise typer.Exit(code=1)

    table = Table(title="Skopus Health Check", show_lines=False)
    table.add_column("Component", style="bold")
    table.add_column("Path")
    table.add_column("Status")

    # Charter
    charter_md = skopus_dir / "charter" / "CLAUDE.md"
    table.add_row(
        "Charter (high-level)",
        str(charter_md),
        "[green]✓[/green]" if charter_md.exists() else "[red]✗ missing[/red]",
    )
    full_charter = skopus_dir / "charter" / "workflow_partnership.md"
    table.add_row(
        "Charter (full)",
        str(full_charter),
        "[green]✓[/green]" if full_charter.exists() else "[red]✗ missing[/red]",
    )

    # Memory
    memory_md = skopus_dir / "memory" / "MEMORY.md"
    table.add_row(
        "Memory index",
        str(memory_md),
        "[green]✓[/green]" if memory_md.exists() else "[red]✗ missing[/red]",
    )

    # Vault location read from adapters.lock
    lock_data = read_adapters_lock(skopus_dir)
    vault_hint = str(lock_data.get("vault_location") or "~/Vault")
    vault_dir = resolve_vault_path(vault_hint)
    vault_index = vault_dir / "wiki" / "index.md"
    table.add_row(
        "Vault index",
        str(vault_index),
        "[green]✓[/green]" if vault_index.exists() else "[red]✗ missing[/red]",
    )

    # Graphify (v0.0.2+). Check across linked projects.
    if graphify_available():
        # Status is per-project; show aggregate
        graphify_status = "[green]✓ CLI available[/green]"
    else:
        graphify_status = "[red]✗ not installed[/red]"
    table.add_row(
        "Graphify (lens 4)",
        "per-project",
        graphify_status,
    )

    console.print(table)

    # Linked projects
    projects_path = skopus_dir / "projects.json"
    if projects_path.exists():
        try:
            projects: list[str] = json.loads(projects_path.read_text())
        except json.JSONDecodeError:
            projects = []

        if projects:
            console.print("\n[bold]Linked projects:[/bold]")
            adapter = get_adapter("claude-code")
            for project in projects:
                p = Path(project)
                status = adapter.status(project_path=p)
                badge = (
                    "[green]✓ installed[/green]"
                    if status == AdapterStatus.INSTALLED
                    else f"[yellow]{status.value}[/yellow]"
                )
                # Per-project graphify status
                if graphify_available():
                    if graph_exists(p):
                        graph_badge = "[green]graph ✓[/green]"
                    else:
                        hint = first_build_hint(p)
                        graph_badge = (
                            f"[yellow]graph pending — run /graphify {hint}[/yellow]"
                            if hint
                            else "[yellow]graph pending[/yellow]"
                        )
                else:
                    graph_badge = "[dim]graphify not installed[/dim]"
                console.print(f"  {badge}  {project}")
                console.print(f"    {graph_badge}")
        else:
            console.print(
                "\n[dim]No projects linked yet. "
                "Run [italic]skopus link[/italic] inside a project directory.[/dim]"
            )
