"""Integration tests for Neo4j database."""

import os
import time
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest

from lib.config import Settings
from lib.database import Neo4jClient
from lib.models import Command, CommandWithMetadata

# Check if Neo4j is available for integration tests
SKIP_INTEGRATION = os.getenv("SKIP_INTEGRATION_TESTS", "false").lower() == "true"
skip_if_no_neo4j = pytest.mark.skipif(
    SKIP_INTEGRATION,
    reason="Integration tests disabled (set SKIP_INTEGRATION_TESTS=false to enable)",
)


@pytest.fixture(scope="module")
def neo4j_settings() -> Settings:
    """Create settings for Neo4j test database."""
    # Use environment variables if set, otherwise use defaults
    return Settings(
        neo4j_uri=os.getenv("NEO4J_TEST_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_TEST_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "devpassword"),
        neo4j_database=os.getenv("NEO4J_TEST_DATABASE", "neo4j"),
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

    client.close()


@skip_if_no_neo4j
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
        assert set(retrieved.tags) == {"git", "status"}
        assert retrieved.os == "linux"
        assert retrieved.project_type == "python"
        assert retrieved.category == "git"
        assert retrieved.use_count == 1  # Incremented when retrieved

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
        commands = [
            Command(command="cmd1", description="Command 1", category="cat1"),
            Command(command="cmd2", description="Command 2", category="cat2"),
            Command(command="cmd3", description="Command 3", category="cat2"),
        ]

        for cmd in commands:
            db_client.add_command(cmd)

        categories = db_client.get_all_categories()
        assert len(categories) >= 2
        assert {"cat1", "cat2"}.issubset(set(categories))

    def test_use_count_increment(self, db_client: Neo4jClient) -> None:
        """Test that use count increments when retrieving commands."""
        cmd = Command(command="test command", description="Test use count", tags=["test"])

        command_id = db_client.add_command(cmd)

        # Retrieve multiple times
        for i in range(1, 4):
            retrieved = db_client.get_command(command_id)
            assert retrieved is not None
            assert retrieved.use_count == i

    def test_last_used_timestamp(self, db_client: Neo4jClient) -> None:
        """Test that last_used timestamp is updated."""
        cmd = Command(command="test command", description="Test timestamp", tags=["test"])

        command_id = db_client.add_command(cmd)

        # First retrieval should set last_used
        retrieved = db_client.get_command(command_id)
        assert retrieved is not None
        assert retrieved.last_used is not None
        first_used = retrieved.last_used

        # Second retrieval should update last_used
        time.sleep(0.1)  # Small delay to ensure different timestamp
        retrieved = db_client.get_command(command_id)
        assert retrieved is not None
        assert retrieved.last_used is not None
        assert retrieved.last_used >= first_used

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
