"""Command-line interface for Memory Box."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lib.api import MemoryBox
from lib.models import Command
from server.context import get_current_context

app = typer.Typer(
    name="memory-box",
    help="A personal knowledge base for commands and workflows.",
    add_completion=False,
)

console = Console()


def get_memory_box() -> MemoryBox:
    """Get Memory Box API client."""
    return MemoryBox()


@app.command()
def add(
    command: str = typer.Argument(..., help="The command to save"),
    description: str = typer.Option(
        ..., "--desc", "-d", help="Description of what the command does"
    ),
    tags: list[str] | None = typer.Option(
        None, "--tag", "-t", help="Tags (can be used multiple times)"
    ),
    os: str | None = typer.Option(None, "--os", help="Operating system (linux, macos, windows)"),
    project_type: str | None = typer.Option(
        None, "--project", "-p", help="Project type (python, node, etc.)"
    ),
    context: str | None = typer.Option(None, "--context", "-c", help="Additional context"),
    category: str | None = typer.Option(None, "--category", help="Category (git, docker, etc.)"),
    status: str | None = typer.Option(None, "--status", help="Execution status (success, failed)"),
    auto_context: bool = typer.Option(
        True, "--auto-context/--no-auto-context", help="Auto-detect context"
    ),
) -> None:
    """Add a new command to your memory box."""

    mb = get_memory_box()

    # Auto-detect context if enabled
    if auto_context:
        current_context = get_current_context()
        if os is None:
            os = current_context.get("os")
        if project_type is None:
            project_type = current_context.get("project_type")

    cmd = Command(
        command=command,
        description=description,
        tags=tags or [],
        os=os,
        project_type=project_type,
        context=context,
        category=category,
        status=status,
    )

    command_id = mb.add_command(cmd)

    console.print("[green]✓[/green] Command added successfully!")
    console.print(f"[dim]ID: {command_id}[/dim]")

    mb.close()


@app.command()
def search(
    query: str | None = typer.Argument(None, help="Search query"),
    os: str | None = typer.Option(None, "--os", help="Filter by OS"),
    project_type: str | None = typer.Option(None, "--project", "-p", help="Filter by project type"),
    category: str | None = typer.Option(None, "--category", "-c", help="Filter by category"),
    tags: list[str] | None = typer.Option(None, "--tag", "-t", help="Filter by tags"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum results"),
    current: bool = typer.Option(False, "--current", help="Use current context"),
) -> None:
    """Search for commands in your memory box."""

    mb = get_memory_box()

    # Use current context if requested
    if current:
        current_context = get_current_context()
        if os is None:
            os = current_context.get("os")
        if project_type is None:
            project_type = current_context.get("project_type")

    commands = mb.search_commands(
        query=query, os=os, project_type=project_type, category=category, tags=tags, limit=limit
    )

    if not commands:
        console.print("[yellow]No commands found.[/yellow]")
        mb.close()
        return

    table = Table(
        title=f"Found {len(commands)} command(s)", show_header=True, header_style="bold magenta"
    )
    table.add_column("Description", style="cyan", no_wrap=False)
    table.add_column("Command", style="green", no_wrap=False)
    table.add_column("Context", style="yellow")
    table.add_column("Used", justify="right", style="dim")

    for cmd in commands:
        context_parts = []
        if cmd.os:
            context_parts.append(f"OS:{cmd.os}")
        if cmd.project_type:
            context_parts.append(f"Proj:{cmd.project_type}")
        if cmd.category:
            context_parts.append(f"Cat:{cmd.category}")
        if cmd.tags:
            context_parts.append(f"Tags:{','.join(cmd.tags[:2])}")

        context_str = "\n".join(context_parts) if context_parts else "-"

        table.add_row(cmd.description, cmd.command, context_str, str(cmd.execution_count))

    console.print(table)
    mb.close()


@app.command()
def get(command_id: str = typer.Argument(..., help="Command ID")) -> None:
    """Get a specific command by ID."""

    mb = get_memory_box()
    cmd = mb.get_command(command_id)

    if not cmd:
        console.print(f"[red]Command {command_id} not found.[/red]")
        mb.close()
        return

    # Create a detailed view
    details = f"""[bold cyan]Command:[/bold cyan]
{cmd.command}

[bold cyan]Description:[/bold cyan]
{cmd.description}

[bold cyan]ID:[/bold cyan] {cmd.id}
"""

    if cmd.os:
        details += f"[bold cyan]OS:[/bold cyan] {cmd.os}\n"
    if cmd.project_type:
        details += f"[bold cyan]Project:[/bold cyan] {cmd.project_type}\n"
    if cmd.category:
        details += f"[bold cyan]Category:[/bold cyan] {cmd.category}\n"
    if cmd.tags:
        details += f"[bold cyan]Tags:[/bold cyan] {', '.join(cmd.tags)}\n"
    if cmd.context:
        details += f"[bold cyan]Context:[/bold cyan] {cmd.context}\n"

    details += f"\n[dim]Executed {cmd.execution_count} time(s) • Created {cmd.created_at}[/dim]"

    console.print(Panel(details, title="Command Details", border_style="blue"))
    mb.close()


@app.command()
def delete(command_id: str = typer.Argument(..., help="Command ID to delete")) -> None:
    """Delete a command from your memory box."""

    # Confirm deletion
    confirm = typer.confirm(f"Are you sure you want to delete command {command_id}?")
    if not confirm:
        console.print("[yellow]Deletion cancelled.[/yellow]")
        return

    mb = get_memory_box()
    success = mb.delete_command(command_id)

    if success:
        console.print(f"[green]✓[/green] Command {command_id} deleted.")
    else:
        console.print(f"[red]Command {command_id} not found.[/red]")

    mb.close()


@app.command()
def tags() -> None:
    """List all tags in your memory box."""

    mb = get_memory_box()
    tag_list = mb.get_all_tags()

    if not tag_list:
        console.print("[yellow]No tags found.[/yellow]")
        mb.close()
        return

    console.print(f"\n[bold]Tags ({len(tag_list)}):[/bold]")
    for tag in tag_list:
        console.print(f"  • {tag}")
    console.print()

    mb.close()


@app.command()
def categories() -> None:
    """List all categories in your memory box."""

    mb = get_memory_box()
    cat_list = mb.get_all_categories()

    if not cat_list:
        console.print("[yellow]No categories found.[/yellow]")
        mb.close()
        return

    console.print(f"\n[bold]Categories ({len(cat_list)}):[/bold]")
    for cat in cat_list:
        console.print(f"  • {cat}")
    console.print()

    mb.close()


@app.command()
def context() -> None:
    """Show current system and project context."""

    current = get_current_context()

    info = f"""[bold cyan]Operating System:[/bold cyan] {current.get("os", "unknown")}
[bold cyan]Project Type:[/bold cyan] {current.get("project_type", "none detected")}
[bold cyan]Current Directory:[/bold cyan] {current.get("cwd", "unknown")}
"""

    console.print(Panel(info, title="Current Context", border_style="green"))


@app.command()
def suggest() -> None:
    """Get command suggestions based on current context."""

    current_context = get_current_context()

    mb = get_memory_box()
    commands = mb.search_commands(
        os=current_context.get("os"), project_type=current_context.get("project_type"), limit=10
    )

    if not commands:
        console.print("[yellow]No commands found for current context:[/yellow]")
        console.print(f"  OS: {current_context.get('os')}")
        console.print(f"  Project: {current_context.get('project_type') or 'none detected'}")
        mb.close()
        return

    console.print(
        Panel(
            f"[cyan]OS:[/cyan] {current_context.get('os')}\n"
            f"[cyan]Project:[/cyan] {current_context.get('project_type') or 'none detected'}",
            title="Context-Aware Suggestions",
            border_style="green",
        )
    )

    for i, cmd in enumerate(commands, 1):
        console.print(f"\n[bold]{i}. {cmd.description}[/bold]")
        console.print(f"   [green]{cmd.command}[/green]")
        if cmd.tags:
            console.print(f"   [dim]Tags: {', '.join(cmd.tags)}[/dim]")

    console.print()
    mb.close()


def run_cli() -> None:
    """Run the CLI application."""
    app()


@app.command()
def capture(
    command: str = typer.Argument(..., help="The command that was executed"),
    exit_code: int = typer.Option(..., "--exit-code", help="Exit code of the command"),
    cwd: str = typer.Option(..., "--cwd", help="Working directory where command was run"),
    success_only: bool = typer.Option(
        False, "--success-only", help="Only capture successful commands (exit code 0)"
    ),
) -> None:
    """Capture a command from shell integration (used by bash/zsh hooks)."""
    # Skip empty commands
    if not command or not command.strip():
        return

    # Skip failed commands if in success-only mode
    if success_only and exit_code != 0:
        return

    mb = get_memory_box()

    # Determine category based on exit code
    category = "success" if exit_code == 0 else "failed"

    # Capture command silently
    mb.add_command(command, description="", context=cwd, category=category)
    mb.close()


if __name__ == "__main__":
    app()
