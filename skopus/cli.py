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
from skopus.evolve import run_evolve
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
)
from skopus.wizard import WizardResult, default_result, run_wizard

# Lazy imports for bench subcommand (bench deps are optional)
def _load_bench():
    from bench.config import LensConfig
    from bench.driver import pick_driver
    from bench.harness import (
        format_markdown_report,
        list_benchmarks,
        run_ablation,
        run_benchmark,
        save_report,
    )

    return {
        "LensConfig": LensConfig,
        "pick_driver": pick_driver,
        "format_markdown_report": format_markdown_report,
        "list_benchmarks": list_benchmarks,
        "run_ablation": run_ablation,
        "run_benchmark": run_benchmark,
        "save_report": save_report,
    }

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
def update() -> None:
    """Update skopus to the latest version and re-install all global components.

    Runs pip upgrade, then re-installs the graphify skill file and vault
    slash commands so any new features from the update are immediately available.
    """
    import subprocess
    import sys

    console.print("[bold]Updating skopus...[/bold]\n")

    # Step 1: pip upgrade
    console.print("[dim]Step 1/3:[/dim] Upgrading skopus via pip...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "skopus"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            # Check what version we got
            version_check = subprocess.run(
                [sys.executable, "-c", "import skopus; print(skopus.__version__)"],
                capture_output=True,
                text=True,
            )
            new_ver = version_check.stdout.strip() if version_check.returncode == 0 else "unknown"
            if f"already satisfied" in result.stdout.lower() or "already up-to-date" in result.stdout.lower():
                console.print(f"  [green]✓[/green] Already on latest ({new_ver})")
            else:
                console.print(f"  [green]✓[/green] Upgraded to v{new_ver}")
        else:
            console.print(f"  [yellow]⚠[/yellow] pip upgrade returned non-zero: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        console.print("  [yellow]⚠[/yellow] pip upgrade timed out (300s)")
    except FileNotFoundError:
        console.print("  [red]✗[/red] pip not found")

    # Step 2: re-install graphify skill globally
    console.print("[dim]Step 2/3:[/dim] Installing graphify skill...")
    from skopus.graphify_bridge import ensure_graphify_skill_installed

    if graphify_available():
        if ensure_graphify_skill_installed():
            console.print("  [green]✓[/green] /graphify skill installed at ~/.claude/skills/graphify/")
        else:
            console.print("  [yellow]⚠[/yellow] graphify skill install failed — try: graphify install")
    else:
        console.print("  [yellow]⚠[/yellow] graphify CLI not on PATH")

    # Step 3: re-install vault slash commands globally
    console.print("[dim]Step 3/3:[/dim] Installing vault commands globally...")
    from skopus.renderer import _load_template_text, VAULT_STATIC, _write

    global_cmds_dir = Path.home() / ".claude" / "commands"
    global_cmds_dir.mkdir(parents=True, exist_ok=True)
    installed_count = 0
    for _, out_rel in VAULT_STATIC:
        if out_rel.startswith(".claude/commands/"):
            cmd_name = out_rel.split("/")[-1]
            content = _load_template_text(f"vault/{out_rel}")
            global_path = global_cmds_dir / cmd_name
            _write(global_path, content, force=True)  # always refresh on update
            installed_count += 1
    console.print(f"  [green]✓[/green] {installed_count} commands at ~/.claude/commands/")

    console.print(
        "\n[bold green]Update complete.[/bold green] "
        "Restart your Claude Code session to pick up any changes."
    )


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
        help="Seed profile: blank, solo-dev, team-lead, research, founder, bug-hunter.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing files. Default is non-destructive merge.",
    ),
) -> None:
    """Initialize Skopus — one command, everything set up."""
    console.print(
        Panel.fit(
            "[bold]Skopus — Four-Lens Context for AI Coding Assistants[/bold]\n\n"
            "One command. Charter, memory, vault, and graph — all set up.\n"
            "Everything is editable. [italic]/charter-evolve[/italic] compounds it over time.",
            title="skopus init",
            border_style="cyan",
        )
    )

    if non_interactive:
        result = default_result(name=name, seed_profile=profile)
    else:
        result = run_wizard()

    skopus_dir = resolve_skopus_path()
    console.print(f"\n[dim]Everything goes to →[/dim] {skopus_dir}")

    if skopus_dir.exists() and any(skopus_dir.iterdir()):
        mode = "force — overwriting" if force else "non-destructive — preserving edits"
        console.print(f"[dim]  ({mode})[/dim]")

    # --- Step 1: Scaffold files ---
    report = materialize(result, skopus_dir, force=force)
    console.print(
        f"\n[green]✓[/green] Wrote {len(report.written)} files"
        + (f"  [dim]({len(report.skipped)} kept)[/dim]" if report.skipped else "")
    )

    # --- Step 2: Install graphify skill globally ---
    from skopus.graphify_bridge import ensure_graphify_skill_installed

    if graphify_available():
        if ensure_graphify_skill_installed():
            console.print("[green]✓[/green] /graphify skill installed")
        else:
            console.print("[yellow]⚠[/yellow] graphify skill install failed")
    else:
        console.print("[yellow]⚠[/yellow] graphify not available")

    # --- Step 3: Auto-link current project if inside a git repo ---
    cwd = Path.cwd()
    wired_any = False
    if (cwd / ".git").exists():
        console.print(f"\n[bold]Linking current project:[/bold] {cwd.name}")
        for agent_name in result.agents:
            key = agent_name.lower().replace(" ", "-")
            if key not in ADAPTERS:
                continue
            adapter = get_adapter(key)
            if not adapter.detect():
                continue
            install_result = adapter.install(
                charter_path=skopus_dir / "charter",
                vault_path=skopus_dir / "vault",
                project_path=cwd,
            )
            console.print(f"  [green]✓[/green] {agent_name}: {install_result.message}")
            wired_any = True

        if wired_any:
            _track_linked_project(skopus_dir, cwd)

            # Wire graphify into the project
            if graphify_available():
                graphify_result = install_graphify_for_claude(
                    project_path=cwd,
                    scope=result.graphify_scope,
                )
                if graphify_result.installed:
                    console.print(f"  [green]✓[/green] {graphify_result.message}")
    else:
        console.print(
            "\n[dim]Not inside a git repo — run [italic]skopus link[/italic] "
            "inside a project to wire it.[/dim]"
        )

    # --- Summary ---
    console.print(f"\n[bold green]Done.[/bold green] Skopus is ready.")
    console.print(
        f"  Charter:  {skopus_dir / 'charter' / 'CLAUDE.md'}\n"
        f"  Memory:   {skopus_dir / 'memory' / 'MEMORY.md'}\n"
        f"  Vault:    {skopus_dir / 'vault' / 'wiki' / 'index.md'}\n"
    )
    if wired_any and not graph_exists(cwd):
        console.print(
            "[bold cyan]Next:[/bold cyan] Open Claude Code and type "
            "[italic]/graphify .[/italic] to build your code map."
        )
    elif not wired_any:
        console.print(
            "[bold cyan]Next:[/bold cyan] [italic]cd my-project && skopus link[/italic]"
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
    """Wire Skopus into a project's CLAUDE.md."""
    skopus_dir = resolve_skopus_path()
    if not skopus_dir.exists():
        console.print("[red]✗[/red] Run [italic]skopus init[/italic] first.")
        raise typer.Exit(code=1)

    vault_dir = skopus_dir / "vault"
    resolved_project = project_path.resolve()
    console.print(f"Linking [bold]{resolved_project.name}[/bold] to Skopus...")

    try:
        adapter_impl = get_adapter(agent)
    except KeyError as e:
        console.print(f"[red]✗[/red] {e}")
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


charter_app = typer.Typer(
    name="charter",
    help="Charter operations — evolve, view, validate.",
    no_args_is_help=True,
)
app.add_typer(charter_app, name="charter")

bench_app = typer.Typer(
    name="bench",
    help="Benchmark harness — run, list, report on skopus benchmarks.",
    no_args_is_help=True,
)
app.add_typer(bench_app, name="bench")


@bench_app.command("list")
def bench_list() -> None:
    """Show available benchmarks."""
    b = _load_bench()
    benchmarks = b["list_benchmarks"]()
    table = Table(title="Skopus Benchmarks", show_lines=False)
    table.add_column("Name", style="bold cyan")
    table.add_column("Description")
    for name, desc in benchmarks.items():
        table.add_row(name, desc)
    console.print(table)


@bench_app.command("run")
def bench_run(
    benchmark: str = typer.Argument(
        "cp",
        help="Benchmark name: cp, correction-persistence, longmemeval, locomo, msc, ruler, all",
    ),
    lens: str = typer.Option(
        "full",
        "--lens",
        help="Lens config: vanilla, charter, charter+memory, charter+memory+vault, full",
    ),
    ablation: bool = typer.Option(
        False,
        "--ablation",
        help="Run across all 5 lens configs (ignores --lens).",
    ),
    driver: str = typer.Option(
        "auto",
        "--driver",
        help="LLM driver: auto (anthropic if available, else mock), anthropic, mock",
    ),
    limit: int = typer.Option(
        None,
        "--limit",
        help="Run only the first N scenarios (for quick smoke tests).",
    ),
    save: bool = typer.Option(
        True,
        "--save/--no-save",
        help="Persist results to bench/results/.",
    ),
) -> None:
    """Run a benchmark against the current skopus installation."""
    b = _load_bench()
    LensConfig = b["LensConfig"]

    skopus_dir = resolve_skopus_path()
    if not skopus_dir.exists():
        console.print("[red]✗[/red] Skopus not initialized. Run `skopus init` first.")
        raise typer.Exit(code=1)

    vault_dir = skopus_dir / "vault"
    driver_impl = b["pick_driver"](driver)
    console.print(
        Panel.fit(
            f"[bold]Benchmark:[/bold] {benchmark}\n"
            f"[bold]Driver:[/bold] {driver_impl.name} "
            f"({'available' if driver_impl.available() else 'UNAVAILABLE'})\n"
            f"[bold]Mode:[/bold] {'ablation (all 5 lens configs)' if ablation else f'single ({lens})'}\n"
            f"[bold]Scope:[/bold] "
            f"{'all scenarios' if limit is None else f'first {limit}'}",
            title="skopus bench run",
            border_style="cyan",
        )
    )

    if ablation:
        results = b["run_ablation"](
            driver=driver_impl,
            benchmark_name=benchmark,
            skopus_dir=skopus_dir,
            vault_dir=vault_dir,
            limit=limit,
        )
        report_md = b["format_markdown_report"](results, benchmark)
        console.print("\n")
        console.print(report_md)
        if save:
            path = b["save_report"](results)
            console.print(f"\n[green]✓[/green] Results saved: {path}")
    else:
        lens_enum = LensConfig(lens.replace(" ", ""))
        report = b["run_benchmark"](
            name=benchmark,
            driver=driver_impl,
            lens=lens_enum,
            skopus_dir=skopus_dir,
            vault_dir=vault_dir,
            limit=limit,
        )
        console.print(
            f"\n[bold]{benchmark} / {lens_enum.display_name}:[/bold] "
            f"{report.passed}/{report.total} passed ({report.accuracy:.1%}) | "
            f"mean score {report.mean_score:.3f} | "
            f"{report.total_tokens:,} tokens | ${report.total_cost_usd:.4f}"
        )
        if save:
            path = b["save_report"](report)
            console.print(f"[green]✓[/green] Results saved: {path}")


@charter_app.command("evolve")
def charter_evolve(
    no_commit: bool = typer.Option(
        False,
        "--no-commit",
        help="Capture entries but skip the git commit.",
    ),
) -> None:
    """Session-end reflection loop. Captures validated calls, drifts, and
    new rules into feedback memory and the charter's drift log."""
    skopus_dir = resolve_skopus_path()
    if not skopus_dir.exists():
        console.print(
            "[red]✗[/red] Skopus not initialized. Run [italic]skopus init[/italic] first."
        )
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            "[bold]Charter Evolve[/bold] — capture what happened before it evaporates.\n\n"
            "Three quick sections: [italic]validated calls[/italic], "
            "[italic]drifts/corrections[/italic], [italic]new rules[/italic].\n"
            "Skip any section with 'no'. Keep answers short.",
            title="skopus charter evolve",
            border_style="cyan",
        )
    )

    result = run_evolve(skopus_dir, commit=not no_commit)

    if not result.entries:
        console.print("\n[dim]No entries captured. Charter unchanged.[/dim]")
        return

    console.print(f"\n[green]✓[/green] {result.message}")
    for path in result.feedback_files_written:
        console.print(f"  [dim]→[/dim] {path}")
    for section in result.charter_sections_updated:
        console.print(f"  [dim]→[/dim] charter {section}")
    if result.committed:
        console.print("[green]✓[/green] Committed to [dim]~/.skopus/.git[/dim]")
    elif not no_commit:
        console.print("[yellow]⚠[/yellow] Nothing to commit (charter unchanged).")


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
    vault_dir = skopus_dir / "vault"
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
