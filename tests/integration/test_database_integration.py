"""Integration tests for Neo4j database."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from testcontainers.neo4j import Neo4jContainer

import lib.config
from lib.database import Neo4jClient
from lib.models import Command, CommandWithMetadata
from lib.settings import Settings


@pytest.fixture(scope="module")
def neo4j_container() -> Generator[Neo4jContainer, None, None]:
    """Start a Neo4j container for testing."""
    with Neo4jContainer("neo4j:5-community") as container:
        yield container


@pytest.fixture(scope="module")
def neo4j_settings(neo4j_container: Neo4jContainer) -> Settings:
    """Create settings for Neo4j test database."""
    return Settings(
        neo4j_uri=neo4j_container.get_connection_url(),
        neo4j_user=neo4j_container.username,
        neo4j_password=neo4j_container.password,
        neo4j_database="neo4j",
    )


@pytest.fixture
def db_client(neo4j_settings: Settings) -> Generator[Neo4jClient, None, None]:
    """Create a database client and clean up after tests."""
    client = Neo4jClient(neo4j_settings)
    yield client

    # Cleanup: Delete all test data
    with client.driver.session(database=client.database) as session:
        session.run("MATCH (n:Command) DETACH DELETE n")
        session.run("MATCH (n:Tag) DELETE n")
        session.run("MATCH (n:Category) DELETE n")
        session.run("MATCH (n:OS) DELETE n")
        session.run("MATCH (n:ProjectType) DELETE n")

    client.close()


class TestNeo4jIntegration:
    """Integration tests for Neo4j database operations."""

    def test_add_and_retrieve_command(self, db_client: Neo4jClient) -> None:
        """Test adding a command and retrieving it."""
        cmd = Command(
            command="git status",
            description="Show the working tree status",
            tags=["git", "status"],
            os="linux",
            project_type="python",
            category="git",
        )

        command_id = db_client.add_command(cmd)
        assert command_id is not None
        assert isinstance(command_id, str)

        # Retrieve the command
        retrieved = db_client.get_command(command_id)
        assert retrieved is not None
        assert isinstance(retrieved, CommandWithMetadata)
        assert retrieved.id == command_id
        assert retrieved.command == "git status"
        assert retrieved.description == "Show the working tree status"
        # Auto-detected tags from commands.json: git -> [git, vcs, version-control]
        # Plus user tags: [git, status]
        assert "git" in retrieved.tags
        assert "status" in retrieved.tags
        assert retrieved.os == "linux"
        assert retrieved.project_type == "python"
        assert retrieved.category == "git"
        assert retrieved.execution_count == 0  # Not incremented by retrieval

    def test_search_commands_by_query(self, db_client: Neo4jClient) -> None:
        """Test searching commands by text query."""
        # Add multiple commands
        commands = [
            Command(
                command="docker ps",
                description="List running containers",
                tags=["docker"],
                category="docker",
            ),
            Command(
                command="docker images",
                description="List docker images",
                tags=["docker"],
                category="docker",
            ),
            Command(
                command="git log", description="Show commit logs", tags=["git"], category="git"
            ),
        ]

        for cmd in commands:
            db_client.add_command(cmd)

        # Search for docker commands
        results = db_client.search_commands(query="docker", limit=10)
        assert len(results) == 2
        assert all(
            "docker" in r.command.lower() or "docker" in r.description.lower() for r in results
        )  # Search for git commands
        results = db_client.search_commands(query="git", limit=10)
        assert len(results) == 1
        assert "git" in results[0].command.lower()

    def test_search_commands_by_filters(self, db_client: Neo4jClient) -> None:
        """Test searching commands with various filters."""
        # Add commands with different attributes
        commands = [
            Command(
                command="ls -la",
                description="List files",
                tags=["filesystem"],
                os="linux",
                project_type="general",
                category="filesystem",
            ),
            Command(
                command="dir",
                description="List files",
                tags=["filesystem"],
                os="windows",
                project_type="general",
                category="filesystem",
            ),
            Command(
                command="poetry install",
                description="Install dependencies",
                tags=["python", "poetry"],
                os="linux",
                project_type="python",
                category="package-management",
            ),
        ]

        for cmd in commands:
            db_client.add_command(cmd)

        # Filter by OS
        linux_results = db_client.search_commands(os="linux", limit=10)
        assert len(linux_results) >= 2
        assert all(r.os == "linux" for r in linux_results)

        # Filter by project type
        python_results = db_client.search_commands(project_type="python", limit=10)
        assert len(python_results) >= 1
        assert all(r.project_type == "python" for r in python_results)

        # Filter by category
        fs_results = db_client.search_commands(category="filesystem", limit=10)
        assert len(fs_results) == 2

        # Filter by tags
        python_tag_results = db_client.search_commands(tags=["python"], limit=10)
        assert len(python_tag_results) >= 1
        assert all("python" in r.tags for r in python_tag_results)

    def test_delete_command(self, db_client: Neo4jClient) -> None:
        """Test deleting a command."""
        cmd = Command(command="test command", description="A test command to delete", tags=["test"])

        command_id = db_client.add_command(cmd)
        assert command_id is not None

        # Verify command exists
        retrieved = db_client.get_command(command_id)
        assert retrieved is not None

        # Delete the command
        success = db_client.delete_command(command_id)
        assert success is True

        # Verify command is gone
        retrieved = db_client.get_command(command_id)
        assert retrieved is None

        # Try deleting non-existent command
        success = db_client.delete_command(str(uuid.uuid4()))
        assert success is False

    def test_search_with_query_only(self, db_client: Neo4jClient) -> None:
        """Test search with query parameter only (no tags, os, category, project_type)."""
        # Add some test commands
        cmd1 = Command(command="echo 'hello'", description="Print hello")
        cmd2 = Command(command="echo 'world'", description="Print world")
        cmd3 = Command(command="ls -la", description="List files")

        db_client.add_command(cmd1)
        db_client.add_command(cmd2)
        db_client.add_command(cmd3)

        # Search with ONLY query parameter (triggers line 353: WHERE without WITH c)
        results = db_client.search_commands(query="echo")

        assert len(results) == 2
        commands = [r.command for r in results]
        assert "echo 'hello'" in commands
        assert "echo 'world'" in commands
        assert "ls -la" not in commands

    def test_search_with_query_and_tag(self, db_client: Neo4jClient) -> None:
        """Test search with query AND tag filter (triggers line 353: WITH c WHERE)."""
        # Add test commands
        cmd1 = Command(command="echo 'hello'", description="Print hello", tags=["test"])
        cmd2 = Command(command="echo 'world'", description="Print world", tags=["prod"])
        cmd3 = Command(command="ls -la", description="List files", tags=["test"])

        db_client.add_command(cmd1)
        db_client.add_command(cmd2)
        db_client.add_command(cmd3)

        # Search with query AND tags (triggers line 353: WITH c\nWHERE because tag_match is set)
        results = db_client.search_commands(query="echo", tags=["test"])

        assert len(results) == 1
        assert results[0].command == "echo 'hello'"

    def test_get_all_tags(self, db_client: Neo4jClient) -> None:
        """Test retrieving all unique tags."""
        commands = [
            Command(command="cmd1", description="Command 1", tags=["tag1", "tag2"]),
            Command(command="cmd2", description="Command 2", tags=["tag2", "tag3"]),
            Command(command="cmd3", description="Command 3", tags=["tag3", "tag4"]),
        ]

        for cmd in commands:
            db_client.add_command(cmd)

        tags = db_client.get_all_tags()
        assert len(tags) >= 4
        assert {"tag1", "tag2", "tag3", "tag4"}.issubset(set(tags))

    def test_get_all_categories(self, db_client: Neo4jClient) -> None:
        """Test retrieving all unique categories."""
        # Use unique command texts to avoid deduplication
        commands = [
            Command(command="unique_cmd1", description="Command 1", category="cat1"),
            Command(command="unique_cmd2", description="Command 2", category="cat2"),
            Command(command="unique_cmd3", description="Command 3", category="cat2"),
        ]

        for cmd in commands:
            db_client.add_command(cmd)

        categories = db_client.get_all_categories()
        assert len(categories) >= 2
        assert {"cat1", "cat2"}.issubset(set(categories))

    def test_execution_count_not_incremented_by_retrieval(self, db_client: Neo4jClient) -> None:
        """Test that execution count is NOT incremented when retrieving commands."""
        cmd = Command(command="test command", description="Test execution count", tags=["test"])

        command_id = db_client.add_command(cmd)

        # Retrieve multiple times - execution count should stay 0
        for _ in range(1, 4):
            retrieved = db_client.get_command(command_id)
            assert retrieved is not None
            assert retrieved.execution_count == 0  # Not incremented by retrieval

    def test_last_used_timestamp(self, db_client: Neo4jClient) -> None:
        """Test that last_used timestamp is None initially (not updated by retrieval)."""
        cmd = Command(command="test command", description="Test timestamp", tags=["test"])

        command_id = db_client.add_command(cmd)

        # Retrieval should NOT set last_used (that's for execution tracking)
        retrieved = db_client.get_command(command_id)
        assert retrieved is not None
        assert retrieved.last_used is None  # Not set by retrieval anymore

    def test_search_with_limit(self, db_client: Neo4jClient) -> None:
        """Test that search respects limit parameter."""
        # Add many commands
        for i in range(10):
            cmd = Command(
                command=f"test command {i}",
                description=f"Test command number {i}",
                tags=["test"],
                category="test",
            )
            db_client.add_command(cmd)

        # Search with limit
        results = db_client.search_commands(category="test", limit=5)
        assert len(results) <= 5

    def test_command_with_context(self, db_client: Neo4jClient) -> None:
        """Test adding and retrieving command with context."""
        cmd = Command(
            command="kubectl apply -f deployment.yaml",
            description="Deploy application",
            tags=["kubernetes", "deployment"],
            context="Use when deploying to production cluster",
            category="kubernetes",
        )

        command_id = db_client.add_command(cmd)
        retrieved = db_client.get_command(command_id)

        assert retrieved is not None
        assert retrieved.context == "Use when deploying to production cluster"

        # Search by context
        results = db_client.search_commands(query="production", limit=10)
        assert len(results) >= 1
        assert any("production" in r.context for r in results if r.context)

    def test_created_at_timestamp(self, db_client: Neo4jClient) -> None:
        """Test that created_at timestamp is set correctly."""
        before = datetime.now(tz=UTC)

        cmd = Command(command="test timestamp", description="Test timestamp", tags=["test"])

        command_id = db_client.add_command(cmd)
        retrieved = db_client.get_command(command_id)

        after = datetime.now(tz=UTC)

        assert retrieved is not None
        assert retrieved.created_at is not None
        assert before <= retrieved.created_at <= after

    def test_command_execution_tracking(self, db_client: Neo4jClient) -> None:
        """Test execution count tracking."""
        # Add a command and execute it multiple times
        cmd = Command(
            command="echo 'Hello World'",
            description="Print hello world",
            tags=["test"],
        )

        cmd_id = db_client.add_command(cmd)
        retrieved = db_client.get_command(cmd_id)

        assert retrieved is not None
        # Initial execution count should be 0 since we don't track status anymore
        assert retrieved.execution_count == 0
        assert retrieved.success_count == 0
        assert retrieved.failure_count == 0

        # Execute the same command again (simulated by adding again)
        cmd2 = Command(
            command="echo 'Hello World'",  # Same command text
            description="Print hello world",
            tags=["test"],
        )

        cmd_id2 = db_client.add_command(cmd2)
        assert cmd_id == cmd_id2  # Should be same ID (deduplication)

        retrieved2 = db_client.get_command(cmd_id)
        assert retrieved2 is not None
        assert retrieved2.execution_count == 1  # Incremented
        assert retrieved2.success_count == 0  # Not tracked
        assert retrieved2.failure_count == 0  # Not tracked

    def test_invalid_category_validation(self, db_client: Neo4jClient) -> None:
        """Test that invalid categories in commands.json are filtered out."""
        # Save original
        original_command_map = lib.config.COMMAND_MAP.copy()
        original_categories_map = lib.config.CATEGORIES_MAP.copy()

        try:
            # Add a command with a category that doesn't exist in CATEGORIES_MAP
            lib.config.COMMAND_MAP["invalidcmd"] = {
                "category": "nonexistent_category",
                "tags": ["test"],
            }

            # Add command - should trigger line 35 (category validation)
            cmd = Command(command="invalidcmd test", description="Test invalid category")
            cmd_id = db_client.add_command(cmd)

            # Category should have been filtered to None
            retrieved = db_client.get_command(cmd_id)
            assert retrieved is not None
            # Since category was invalid, it should be None
            assert retrieved.category is None

        finally:
            # Restore original maps
            lib.config.COMMAND_MAP = original_command_map
            lib.config.CATEGORIES_MAP = original_categories_map
