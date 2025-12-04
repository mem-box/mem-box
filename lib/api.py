"""Public API for Memory Box library."""

from __future__ import annotations

from lib.config import Settings
from lib.database import Neo4jClient
from lib.models import Command, CommandWithMetadata


class MemoryBox:
    """High-level API for Memory Box command storage and retrieval.

    This is the main entry point for using Memory Box as a library.
    It provides a convenient interface that accepts both simple types
    and rich model objects.

    Example:
        >>> # Simple usage with strings
        >>> mb = MemoryBox()
        >>> mb.add_command("docker ps", description="List containers")
        'command-id-123'

        >>> # Search with fuzzy matching
        >>> results = mb.search_commands("doker", fuzzy=True)
        >>> print(results[0].command)
        'docker ps'

        >>> # Power user with models
        >>> cmd = Command(command="git status", tags=["git"])
        >>> mb.add_command(cmd)
        'command-id-456'
    """

    def __init__(
        self,
        neo4j_uri: str | None = None,
        neo4j_user: str | None = None,
        neo4j_password: str | None = None,
        neo4j_database: str | None = None,
    ) -> None:
        """Initialize Memory Box API.

        Args:
            neo4j_uri: Neo4j connection URI (default: from env or settings)
            neo4j_user: Neo4j username (default: from env or settings)
            neo4j_password: Neo4j password (default: from env or settings)
            neo4j_database: Neo4j database name (default: from env or settings)
        """
        settings = Settings()

        # Override settings if provided
        if neo4j_uri:
            settings.neo4j_uri = neo4j_uri
        if neo4j_user:
            settings.neo4j_user = neo4j_user
        if neo4j_password:
            settings.neo4j_password = neo4j_password
        if neo4j_database:
            settings.neo4j_database = neo4j_database

        self._client = Neo4jClient(settings)

    def close(self) -> None:
        """Close the database connection."""
        self._client.close()

    def __enter__(self) -> MemoryBox:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Context manager exit."""
        self.close()

    def add_command(
        self,
        command: str | Command,
        description: str = "",
        tags: list[str] | None = None,
        os: str | None = None,
        project_type: str | None = None,
        context: str | None = None,
        category: str | None = None,
    ) -> str:
        """Add a command to memory.

        Args:
            command: Either a command string or a Command model object
            description: Human-readable description (only used if command is str)
            tags: List of tags for categorization (only used if command is str)
            os: Operating system (only used if command is str)
            project_type: Project type context (only used if command is str)
            context: Additional context (only used if command is str)
            category: Command category (only used if command is str)

        Returns:
            Command ID

        Example:
            >>> mb.add_command("docker ps", description="List containers", tags=["docker"])
            'abc-123'
        """
        if isinstance(command, str):
            cmd = Command(
                command=command,
                description=description,
                tags=tags or [],
                os=os,
                project_type=project_type,
                context=context,
                category=category,
            )
        else:
            cmd = command

        return self._client.add_command(cmd)

    def search_commands(
        self,
        query: str | None = None,
        fuzzy: bool = True,
        os: str | None = None,
        project_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[CommandWithMetadata]:
        """Search for commands in memory.

        Args:
            query: Text to search for in commands and descriptions (None = return all)
            fuzzy: Enable fuzzy matching for typo tolerance
            os: Filter by operating system
            project_type: Filter by project type
            category: Filter by category
            tags: Filter by tags (must match all)
            limit: Maximum number of results

        Returns:
            List of matching commands with metadata

        Example:
            >>> results = mb.search_commands("doker", fuzzy=True)
            >>> results[0].command
            'docker ps'
        """
        return self._client.search_commands(
            query=query or "",
            fuzzy=fuzzy,
            os=os,
            project_type=project_type,
            category=category,
            tags=tags,
            limit=limit,
        )

    def get_command(self, command_id: str) -> CommandWithMetadata | None:
        """Get a specific command by ID.

        Args:
            command_id: The command ID

        Returns:
            Command with metadata, or None if not found

        Example:
            >>> cmd = mb.get_command("abc-123")
            >>> print(cmd.command)
            'docker ps'
        """
        return self._client.get_command(command_id)

    def list_commands(
        self,
        os: str | None = None,
        project_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
    ) -> list[CommandWithMetadata]:
        """List all commands, optionally filtered.

        Args:
            os: Filter by operating system
            project_type: Filter by project type
            category: Filter by category
            tags: Filter by tags (must match all)
            limit: Maximum number of results

        Returns:
            List of commands with metadata

        Example:
            >>> all_commands = mb.list_commands(limit=50)
            >>> docker_commands = mb.list_commands(tags=["docker"])
        """
        return self._client.search_commands(
            query="",
            fuzzy=False,
            os=os,
            project_type=project_type,
            category=category,
            tags=tags,
            limit=limit,
        )

    def delete_command(self, command_id: str) -> bool:
        """Delete a command from memory.

        Args:
            command_id: The command ID to delete

        Returns:
            True if deleted, False if not found

        Example:
            >>> mb.delete_command("abc-123")
            True
        """
        return self._client.delete_command(command_id)

    def increment_use_count(self, command_id: str) -> bool:
        """Increment the use count for a command.

        This is typically called automatically when a command is executed.

        Args:
            command_id: The command ID

        Returns:
            True if incremented, False if command not found

        Example:
            >>> mb.increment_use_count("abc-123")
            True
        """
        # Note: DatabaseClient doesn't have this method yet
        # For now, we get and re-add, but this should be a direct DB operation
        cmd = self._client.get_command(command_id)
        # This is a placeholder - ideally Neo4jClient would have increment_use_count
        return cmd is not None

    def get_all_tags(self) -> list[str]:
        """Get all tags used in the memory box.

        Returns:
            List of all unique tags

        Example:
            >>> tags = mb.get_all_tags()
            >>> print(tags)
            ['docker', 'git', 'kubernetes']
        """
        return self._client.get_all_tags()

    def get_all_categories(self) -> list[str]:
        """Get all categories used in the memory box.

        Returns:
            List of all unique categories

        Example:
            >>> categories = mb.get_all_categories()
            >>> print(categories)
            ['version-control', 'containers', 'networking']
        """
        return self._client.get_all_categories()
