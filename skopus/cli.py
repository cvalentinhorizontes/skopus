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
import re
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
from skopus.guard import install_guard, HOOK_CAPABLE_AGENTS
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


def _slugify_project(name: str) -> str:
    """Convert a project name to a kebab-case slug for directory naming."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


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


def _init_project_memory(skopus_dir: Path, project_path: Path) -> Path | None:
    """Create project-scoped memory directory if it doesn't exist.

    Returns the project memory path, or None if it already existed.
    """
    project_slug = _slugify_project(project_path.name)
    project_memory_dir = skopus_dir / "memory" / "projects" / project_slug

    if project_memory_dir.exists():
        return None

    project_memory_dir.mkdir(parents=True)
    (project_memory_dir / "feedback").mkdir()
    (project_memory_dir / "MEMORY.md").write_text(
        f"# Project Memory — {project_path.name}\n\n"
        f"Project-scoped corrections and context. Read by agents alongside global memory.\n\n"
        f"## Feedback\n\n*(populated by /charter-evolve and dreamer)*\n",
        encoding="utf-8",
    )
    (project_memory_dir / "context.md").write_text(
        f"# Project Context — {project_path.name}\n\n"
        f"## Stack\n- (edit this)\n\n"
        f"## Key Commands\n- (edit this)\n\n"
        f"## Conventions\n- (edit this)\n",
        encoding="utf-8",
    )
    return project_memory_dir


@app.command()
def version() -> None:
    """Show the version."""
    console.print(f"skopus [bold cyan]v{__version__}[/bold cyan]")


@app.command()
def update() -> None:
    """Re-install all global components for every detected agent.

    This command refreshes:
      - the graphify skill (Claude Code surface)
      - the Skopus slash-command set, rendered into each detected agent's
        own user-command surface (Markdown for Claude Code, SKILL.md for
        Cursor and Codex, TOML for Gemini CLI; Aider and Copilot CLI have
        no user-command surface and are skipped silently).

    No pip upgrade — Skopus often runs as an editable install or under PEP
    668-managed Pythons; bumping the package version is the user's job
    (``pipx upgrade skopus`` / ``pip install -U skopus``).
    """
    console.print("[bold]Refreshing Skopus components...[/bold]\n")

    # Graphify skill (Claude Code only)
    console.print("[dim]Step 1/2:[/dim] Installing graphify skill...")
    from skopus.graphify_bridge import ensure_graphify_skill_installed

    if graphify_available():
        if ensure_graphify_skill_installed():
            console.print("  [green]✓[/green] /graphify skill installed at ~/.claude/skills/graphify/")
        else:
            console.print("  [yellow]⚠[/yellow] graphify skill install failed — try: graphify install")
    else:
        console.print("  [yellow]⚠[/yellow] graphify CLI not on PATH")

    # Per-adapter slash command / skill installation. ADAPTERS contains
    # alias keys (e.g. "copilot" + "copilot-cli"); dedupe by class so each
    # adapter runs exactly once.
    console.print("[dim]Step 2/2:[/dim] Installing Skopus commands per agent...")
    skopus_dir = resolve_skopus_path()
    any_written = False
    seen: set[type] = set()
    for agent_key, adapter_cls in ADAPTERS.items():
        if adapter_cls in seen:
            continue
        seen.add(adapter_cls)
        adapter = get_adapter(agent_key)
        if not adapter.detect():
            continue
        try:
            paths = adapter.install_commands(skopus_dir)
        except Exception as exc:  # noqa: BLE001 — surface adapter-level failure, keep going
            console.print(f"  [red]✗[/red] {adapter.display_name}: {exc}")
            continue
        if paths:
            any_written = True
            # SKILL.md surfaces ship one file per <name>/ subdir; flat surfaces
            # ship one file per command directly. Show the shared root in both
            # cases.
            root = paths[0].parent.parent if paths[0].name == "SKILL.md" else paths[0].parent
            console.print(
                f"  [green]✓[/green] {adapter.display_name}: {len(paths)} commands at "
                f"[dim]{root}[/dim]"
            )
        else:
            console.print(f"  [dim]⊘ {adapter.display_name}: no user-command surface[/dim]")
    if not any_written:
        console.print(
            "  [yellow]⚠[/yellow] No detected agents have a user-command surface."
        )

    # Re-link every tracked project so context-file blocks pick up new template
    projects_path = skopus_dir / "projects.json"
    if projects_path.exists():
        try:
            projects: list[str] = json.loads(projects_path.read_text())
        except json.JSONDecodeError:
            projects = []
        if projects:
            console.print(f"\nRe-linking {len(projects)} tracked project(s)...")
            for project_str in projects:
                project = Path(project_str)
                if not project.exists():
                    console.print(f"  [dim]⊘[/dim] {project.name} (not found)")
                    continue
                try:
                    adapter_impl = get_adapter("claude-code")
                    adapter_impl.install(
                        charter_path=skopus_dir / "charter",
                        vault_path=skopus_dir / "vault",
                        project_path=project,
                    )
                    console.print(f"  [green]✓[/green] {project.name}")
                except Exception as exc:  # noqa: BLE001
                    console.print(f"  [red]✗[/red] {project.name}: {exc}")

    console.print(
        "\n[bold green]Refresh complete.[/bold green] "
        "Restart your agent session to pick up any changes."
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
            try:
                cmd_paths = adapter.install_commands(skopus_dir)
            except Exception as exc:  # noqa: BLE001
                console.print(f"    [yellow]⚠[/yellow] commands install failed: {exc}")
                cmd_paths = []
            if cmd_paths:
                console.print(f"    [green]✓[/green] {len(cmd_paths)} commands installed")
            wired_any = True

        if wired_any:
            _track_linked_project(skopus_dir, cwd)

            # Install guard hooks for hook-capable agents
            for agent_name in result.agents:
                key = agent_name.lower().replace(" ", "-")
                if key in HOOK_CAPABLE_AGENTS:
                    if install_guard(cwd, key):
                        console.print(f"  [green]✓[/green] {agent_name}: guard hook installed")

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

    # Create project-scoped memory
    project_mem = _init_project_memory(skopus_dir, resolved_project)
    if project_mem:
        console.print(f"  Created project memory at [dim]{project_mem}[/dim]")

    result = adapter_impl.install(
        charter_path=skopus_dir / "charter",
        vault_path=vault_dir,
        project_path=resolved_project,
    )
    console.print(f"[green]✓[/green] {result.message}")

    # Install / refresh slash-command surface for this agent (no-op for adapters
    # whose agents lack a user-command surface, e.g. Aider, Copilot CLI)
    try:
        cmd_paths = adapter_impl.install_commands(skopus_dir)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]⚠[/yellow] commands install failed: {exc}")
        cmd_paths = []
    if cmd_paths:
        console.print(f"[green]✓[/green] {len(cmd_paths)} commands installed")

    # Install guard hook if the agent supports it
    if install_guard(resolved_project, agent):
        console.print(f"[green]✓[/green] Guard hook installed (corrections auto-inject before risky commands)")

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

    # Remove guard hook
    from skopus.guard import uninstall_guard
    if uninstall_guard(resolved, agent):
        console.print(f"[green]✓[/green] Guard hook removed")

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


@app.command("uninstall")
def uninstall_skopus(
    keep_data: bool = typer.Option(
        False,
        "--keep-data",
        help="Keep ~/.skopus/ directory (only uninstall the package).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Uninstall Skopus — remove wiring from all projects and optionally delete all data."""
    import subprocess
    import sys

    skopus_dir = resolve_skopus_path()

    if not force:
        import questionary

        confirm = questionary.confirm(
            "This will remove Skopus wiring from all linked projects"
            + ("." if keep_data else " and DELETE ~/.skopus/ (charter, memory, vault)."),
            default=False,
        ).ask()
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(code=0)

    # Unlink all projects
    if skopus_dir.exists():
        projects_path = skopus_dir / "projects.json"
        if projects_path.exists():
            try:
                projects: list[str] = json.loads(projects_path.read_text())
            except json.JSONDecodeError:
                projects = []

            for project_str in projects:
                project = Path(project_str)
                if project.exists():
                    try:
                        adapter_impl = get_adapter("claude-code")
                        adapter_impl.uninstall(project_path=project)
                        console.print(f"  [green]✓[/green] Unlinked {project.name}")
                    except (OSError, KeyError, ValueError):
                        console.print(f"  [dim]⊘[/dim] {project.name} (skip)")

        # Delete data unless --keep-data
        if not keep_data:
            import shutil

            shutil.rmtree(skopus_dir)
            console.print(f"[green]✓[/green] Deleted {skopus_dir}")
        else:
            console.print(f"[dim]Kept {skopus_dir}[/dim]")

    # Uninstall pip package
    result = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "skopus", "-y"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print("[green]✓[/green] Skopus uninstalled.")
    else:
        console.print(f"[yellow]⚠[/yellow] pip uninstall: {result.stderr.strip()}")


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


@app.command()
def audit(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Auto-fix issues (add missing index entries, remove dangling ones).",
    ),
) -> None:
    """Audit memory health — index sync and scope tags."""
    from skopus.audit import run_audit

    skopus_dir = resolve_skopus_path()
    if not skopus_dir.exists():
        console.print(
            "[red]✗[/red] Skopus is not initialized. Run [italic]skopus init[/italic] first."
        )
        raise typer.Exit(code=1)

    mode = "fix" if fix else "report"
    console.print(
        Panel.fit(
            f"[bold]Memory Audit[/bold] — mode: {mode}",
            title="skopus audit",
            border_style="cyan",
        )
    )

    report = run_audit(skopus_dir, fix=fix)

    # Index sync
    missing = report["sync"]["missing_from_index"]
    dangling = report["sync"]["dangling_entries"]

    if missing or dangling:
        console.print("\n[bold]Index sync:[/bold]")
        for f in missing:
            action = "[green]added[/green]" if fix else "[yellow]missing from index[/yellow]"
            console.print(f"  {action}  feedback/{f}")
        for f in dangling:
            action = "[green]removed[/green]" if fix else "[yellow]dangling entry[/yellow]"
            console.print(f"  {action}  feedback/{f}")
    else:
        console.print("\n[green]✓[/green] Index sync: clean")

    # Scope tags
    scope_missing = report["scope"]
    if scope_missing:
        console.print("\n[bold]Missing scope tags:[/bold]")
        for f in scope_missing:
            console.print(f"  [yellow]⚠[/yellow]  feedback/{f}")
    else:
        console.print("[green]✓[/green] Scope tags: all present")

    # Summary
    if report["clean"]:
        console.print("\n[bold green]All checks passed.[/bold green]")
    else:
        issues = len(missing) + len(dangling) + len(scope_missing)
        if fix:
            fixed = len(missing) + len(dangling)
            remaining = len(scope_missing)
            console.print(
                f"\n[bold]Fixed {fixed} issue(s).[/bold]"
                + (f" {remaining} scope tag(s) need manual attention." if remaining else "")
            )
        else:
            console.print(
                f"\n[bold]{issues} issue(s) found.[/bold] "
                "Run [italic]skopus audit --fix[/italic] to auto-fix index issues."
            )
