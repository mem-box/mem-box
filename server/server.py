"""MCP Server for Memory Box."""

from fastmcp import FastMCP

from lib.api import MemoryBox
from lib.models import Command, Stack
from server.context import get_current_context

# Initialize FastMCP server
mcp = FastMCP("Memory Box")

# Global Memory Box client
memory_box = MemoryBox()


def get_memory_box() -> MemoryBox:
    """Get the Memory Box API client."""
    return memory_box


@mcp.tool()
def add_command(
    command: str,
    description: str,
    tags: list[str] | None = None,
    os: str | None = None,
    project_type: str | None = None,
    context: str | None = None,
    category: str | None = None,
    auto_detect_context: bool = True,
) -> str:
    """
    Add a new command to your memory box.

    Args:
        command: The actual command or code snippet to save
        description: A clear description of what this command does
        tags: List of tags for categorization (e.g., ["git", "branch"])
        os: Operating system (linux, macos, windows) - auto-detected if not provided
        project_type: Project type (python, node, rust, etc.) - auto-detected if not provided
        context: Additional context about when to use this command
        category: Category (e.g., git, docker, kubernetes)
        auto_detect_context: Whether to auto-detect OS and project type

    Returns:
        Success message with the command ID
    """
    mb = get_memory_box()

    if tags is None:
        tags = []

    # Auto-detect context if requested
    if auto_detect_context:
        current_context = get_current_context()
        if os is None:
            os = current_context.get("os")
        if project_type is None:
            project_type = current_context.get("project_type")

    cmd = Command(
        command=command,
        description=description,
        tags=tags,
        os=os,
        project_type=project_type,
        context=context,
        category=category,
    )

    command_id = mb.add_command(cmd)

    return f"✓ Command added successfully! ID: {command_id}"


def _resolve_search_context(
    os: str | None, project_type: str | None, use_current_context: bool
) -> tuple[str | None, str | None]:
    """Resolve OS and project type from current context if needed."""
    if not use_current_context:
        return os, project_type

    current_context = get_current_context()
    resolved_os = os if os is not None else current_context.get("os")
    resolved_project = (
        project_type if project_type is not None else current_context.get("project_type")
    )
    return resolved_os, resolved_project


@mcp.tool()
def search_commands(
    query: str | None = None,
    os: str | None = None,
    project_type: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    limit: int = 10,
    use_current_context: bool = False,
) -> str:
    """
    Search for commands in your memory box.

    Args:
        query: Text to search for in command, description, or context
        os: Filter by operating system (linux, macos, windows)
        project_type: Filter by project type (python, node, rust, etc.)
        category: Filter by category (git, docker, etc.)
        tags: Filter by tags (all tags must match)
        limit: Maximum number of results to return
        use_current_context: Auto-detect and use current OS and project type

    Returns:
        Formatted list of matching commands
    """
    mb = get_memory_box()

    # Resolve context if needed
    os, project_type = _resolve_search_context(os, project_type, use_current_context)

    commands = mb.search_commands(
        query=query, os=os, project_type=project_type, category=category, tags=tags, limit=limit
    )

    if not commands:
        return "No commands found matching your criteria."

    result = [f"Found {len(commands)} command(s):\n"]

    for i, cmd in enumerate(commands, 1):
        result.append(f"\n{i}. {cmd.description}")
        result.append(f"   Command: {cmd.command}")
        result.append(f"   ID: {cmd.id}")

        metadata = []
        if cmd.os:
            metadata.append(f"OS: {cmd.os}")
        if cmd.project_type:
            metadata.append(f"Project: {cmd.project_type}")
        if cmd.category:
            metadata.append(f"Category: {cmd.category}")
        if cmd.tags:
            metadata.append(f"Tags: {', '.join(cmd.tags)}")

        if metadata:
            result.append(f"   {' | '.join(metadata)}")

        if cmd.context:
            result.append(f"   Context: {cmd.context}")

        result.append(f"   Used {cmd.use_count} time(s)")

    return "\n".join(result)


@mcp.tool()
def get_command_by_id(command_id: str) -> str:
    """
    Get a specific command by its ID. This increments the use count.

    Args:
        command_id: The unique ID of the command

    Returns:
        The command details
    """
    mb = get_memory_box()
    cmd = mb.get_command(command_id)

    if not cmd:
        return f"Command with ID {command_id} not found."

    result = [
        f"Command: {cmd.command}",
        f"Description: {cmd.description}",
        f"ID: {cmd.id}",
    ]

    if cmd.os:
        result.append(f"OS: {cmd.os}")
    if cmd.project_type:
        result.append(f"Project Type: {cmd.project_type}")
    if cmd.category:
        result.append(f"Category: {cmd.category}")
    if cmd.tags:
        result.append(f"Tags: {', '.join(cmd.tags)}")
    if cmd.context:
        result.append(f"Context: {cmd.context}")

    result.append(f"Used: {cmd.use_count} time(s)")
    result.append(f"Created: {cmd.created_at}")
    if cmd.last_used:
        result.append(f"Last Used: {cmd.last_used}")

    return "\n".join(result)


@mcp.tool()
def delete_command(command_id: str) -> str:
    """
    Delete a command from your memory box.

    Args:
        command_id: The unique ID of the command to delete

    Returns:
        Success or error message
    """
    mb = get_memory_box()
    success = mb.delete_command(command_id)

    if success:
        return f"✓ Command {command_id} deleted successfully."
    return f"✗ Command {command_id} not found."


@mcp.tool()
def list_tags() -> str:
    """
    List all tags used in your memory box.

    Returns:
        Formatted list of all tags
    """
    mb = get_memory_box()
    tags = mb.get_all_tags()

    if not tags:
        return "No tags found."

    return f"Tags ({len(tags)}):\n" + "\n".join(f"  • {tag}" for tag in tags)


@mcp.tool()
def list_categories() -> str:
    """
    List all categories used in your memory box.

    Returns:
        Formatted list of all categories
    """
    mb = get_memory_box()
    categories = mb.get_all_categories()

    if not categories:
        return "No categories found."

    return f"Categories ({len(categories)}):\n" + "\n".join(f"  • {cat}" for cat in categories)


@mcp.tool()
def get_context_suggestions() -> str:
    """
    Get command suggestions based on your current context (OS and project type).

    Returns:
        Commands relevant to your current context
    """
    current_context = get_current_context()

    mb = get_memory_box()
    commands = mb.search_commands(
        os=current_context.get("os"), project_type=current_context.get("project_type"), limit=10
    )

    if not commands:
        project = current_context.get("project_type") or "none detected"
        context_info = f"OS: {current_context.get('os')}, Project: {project}"
        return f"No commands found for your current context ({context_info})."

    result = [
        "Commands for your context:",
        f"  OS: {current_context.get('os')}",
        f"  Project: {current_context.get('project_type') or 'none detected'}",
        f"  Directory: {current_context.get('cwd')}",
        "",
    ]

    for i, cmd in enumerate(commands, 1):
        result.append(f"{i}. {cmd.description}")
        result.append(f"   {cmd.command}")
        if cmd.tags:
            result.append(f"   Tags: {', '.join(cmd.tags)}")
        result.append("")

    return "\n".join(result)


@mcp.tool()
def list_stacks() -> str:
    """
    List all technology stacks found in your commands.

    Stacks are automatically detected from your commands (e.g., Docker, Python, Git).
    They help organize commands by technology.

    Returns:
        Formatted list of all stacks with their types
    """
    mb = get_memory_box()
    stacks = mb.list_stacks()

    if not stacks:
        return "No stacks found yet. Add some commands to automatically create stacks!"

    result = ["Technology Stacks:", ""]

    # Group by type
    by_type: dict[str, list[Stack]] = {}
    for stack in stacks:
        if stack.type not in by_type:
            by_type[stack.type] = []
        by_type[stack.type].append(stack)

    for stack_type in sorted(by_type.keys()):
        result.append(f"{stack_type.capitalize()}s:")
        for stack in sorted(by_type[stack_type], key=lambda s: s.name):
            desc = f" - {stack.description}" if stack.description else ""
            result.append(f"  • {stack.name}{desc}")
        result.append("")

    return "\n".join(result)


@mcp.tool()
def get_commands_by_stack(stack_name: str, relationship_type: str | None = None) -> str:
    """
    Get all commands for a specific technology stack.

    Commands are automatically organized by stack (Docker, Python, Git, etc.)
    based on their content and tags. You can filter by relationship type:
    - BUILD: Commands that build/compile (e.g., docker build, npm run build)
    - RUN: Commands that run/execute (e.g., docker run, python script.py)
    - TEST: Commands that test (e.g., pytest, npm test)
    - DEPLOY: Commands that deploy (e.g., git push, kubectl apply)

    Args:
        stack_name: Name of the stack (e.g., "Docker", "Python", "Git")
        relationship_type: Optional filter by type (BUILD, RUN, TEST, DEPLOY)

    Returns:
        Formatted list of commands for the stack
    """
    mb = get_memory_box()
    commands = mb.get_commands_by_stack(stack_name, relationship_type)

    if not commands:
        rel_info = f" with {relationship_type} relationship" if relationship_type else ""
        return f"No commands found for {stack_name}{rel_info}."

    rel_filter = f" ({relationship_type})" if relationship_type else ""
    result = [f"Commands for {stack_name}{rel_filter}:", ""]

    for i, cmd in enumerate(commands, 1):
        result.append(f"{i}. {cmd.description}")
        result.append(f"   {cmd.command}")
        if cmd.tags:
            result.append(f"   Tags: {', '.join(cmd.tags)}")
        result.append(f"   Used {cmd.use_count} times")
        result.append("")

    return "\n".join(result)


def main() -> None:
    """Run the MCP server."""
    # The server will be started by the MCP runtime
    mcp.run()


if __name__ == "__main__":
    main()
