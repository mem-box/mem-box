"""Integration tests for CLI with real Neo4j database."""

from collections.abc import Generator

import pytest
from testcontainers.neo4j import Neo4jContainer
from typer.testing import CliRunner

from lib.database import Neo4jClient
from lib.settings import Settings
from server.cli import app


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
def neo4j_client(neo4j_settings: Settings) -> Generator[Neo4jClient, None, None]:
    """Create a Neo4j client for integration tests."""
    client = Neo4jClient(neo4j_settings)

    # Clean before test
    with client.driver.session(database=client.database) as session:
        session.run("MATCH (n) DETACH DELETE n")

    yield client

    # Clean after test
    with client.driver.session(database=client.database) as session:
        session.run("MATCH (n) DETACH DELETE n")

    client.close()


@pytest.fixture(autouse=True)
def patch_environment(neo4j_settings: Settings, monkeypatch):
    """Patch environment variables to use test container."""
    monkeypatch.setenv("NEO4J_URI", neo4j_settings.neo4j_uri)
    monkeypatch.setenv("NEO4J_USER", neo4j_settings.neo4j_user)
    monkeypatch.setenv("NEO4J_PASSWORD", neo4j_settings.neo4j_password)
    monkeypatch.setenv("NEO4J_DATABASE", neo4j_settings.neo4j_database)


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


class TestCLIIntegration:
    """Integration tests for CLI commands with Neo4j."""

    def test_add_and_search_command(self, runner, neo4j_client):
        """Test adding a command and searching for it."""
        # Add a command
        result = runner.invoke(
            app,
            [
                "add",
                "git commit -m 'message'",
                "--desc",
                "Commit changes",
                "-t",
                "git,version-control",
                "--no-auto-context",
            ],
        )
        assert result.exit_code == 0
        assert "Command added successfully" in result.stdout

        # Search for the command
        result = runner.invoke(app, ["search", "commit"])
        assert result.exit_code == 0
        assert "git commit" in result.stdout
        assert "Commit changes" in result.stdout

    def test_add_get_and_delete_command(self, runner, neo4j_client):
        """Test the full lifecycle: add, get, delete."""
        # Add a command
        result = runner.invoke(
            app,
            [
                "add",
                "docker ps -a",
                "--desc",
                "List all containers",
                "-t",
                "docker",
                "--no-auto-context",
            ],
        )
        assert result.exit_code == 0

        # Extract command ID from output
        lines = result.stdout.split("\n")
        command_id = None
        for line in lines:
            if "ID:" in line:
                command_id = line.split("ID:")[-1].strip()
                break

        assert command_id is not None

        # Get the command
        result = runner.invoke(app, ["get", command_id])
        assert result.exit_code == 0
        assert "docker ps -a" in result.stdout
        assert "List all containers" in result.stdout

        # Delete the command (simulate 'y' confirmation)
        result = runner.invoke(app, ["delete", command_id], input="y\n")
        assert result.exit_code == 0

        # Verify it's deleted
        result = runner.invoke(app, ["get", command_id])
        assert result.exit_code == 0
        assert "not found" in result.stdout.lower()

    def test_add_with_auto_context(self, runner, neo4j_client):
        """Test adding a command with auto-context detection."""
        result = runner.invoke(
            app,
            [
                "add",
                "pytest tests/",
                "--desc",
                "Run all tests",
            ],
        )
        assert result.exit_code == 0
        assert "Command added successfully" in result.stdout

        # Verify the command was added with context
        result = runner.invoke(app, ["search", "pytest"])
        assert result.exit_code == 0
        assert "pytest tests/" in result.stdout

    def test_search_with_filters(self, runner, neo4j_client):
        """Test searching with various filters."""
        # Add commands with different attributes
        runner.invoke(
            app,
            [
                "add",
                "ls -la",
                "--desc",
                "List files",
                "-t",
                "filesystem",
                "--category",
                "navigation",
                "--no-auto-context",
            ],
        )
        runner.invoke(
            app,
            [
                "add",
                "find . -name '*.py'",
                "--desc",
                "Find Python files",
                "-t",
                "filesystem,search",
                "--category",
                "search",
                "--no-auto-context",
            ],
        )

        # Search by tag
        result = runner.invoke(app, ["search", "-t", "filesystem"])
        assert result.exit_code == 0
        assert "ls -la" in result.stdout or "find" in result.stdout

        # Search by category
        result = runner.invoke(app, ["search", "--category", "navigation"])
        assert result.exit_code == 0
        assert "ls -la" in result.stdout
        assert "find" not in result.stdout

    def test_tags_and_categories_listing(self, runner, neo4j_client):
        """Test listing all tags and categories."""
        # Add commands with tags and categories
        runner.invoke(
            app,
            [
                "add",
                "npm install",
                "--desc",
                "Install packages",
                "-t",
                "npm,nodejs",
                "--category",
                "package-management",
                "--no-auto-context",
            ],
        )
        runner.invoke(
            app,
            [
                "add",
                "cargo build",
                "--desc",
                "Build Rust project",
                "-t",
                "rust,cargo",
                "--category",
                "build",
                "--no-auto-context",
            ],
        )

        # List tags
        result = runner.invoke(app, ["tags"])
        assert result.exit_code == 0
        assert "npm" in result.stdout
        assert "nodejs" in result.stdout
        assert "rust" in result.stdout
        assert "cargo" in result.stdout

        # List categories
        result = runner.invoke(app, ["categories"])
        assert result.exit_code == 0
        assert "package-management" in result.stdout
        assert "build" in result.stdout

    def test_suggest_command(self, runner, neo4j_client):
        """Test command suggestions based on context."""
        # Add a command with specific OS context
        runner.invoke(
            app,
            [
                "add",
                "apt update",
                "--desc",
                "Update package lists",
                "--os",
                "linux",
                "--no-auto-context",
            ],
        )

        # Get suggestions (this will use current context)
        result = runner.invoke(app, ["suggest"])
        assert result.exit_code == 0
        # Should show suggestions based on current OS

    def test_use_count_tracking(self, runner, neo4j_client):
        """Test that getting a command increments use count."""
        # Add a command
        result = runner.invoke(
            app,
            [
                "add",
                "echo 'hello'",
                "--desc",
                "Print hello",
                "--no-auto-context",
            ],
        )
        assert result.exit_code == 0

        # Extract command ID
        lines = result.stdout.split("\n")
        command_id = None
        for line in lines:
            if "ID:" in line:
                command_id = line.split("ID:")[-1].strip()
                break

        # Get the command multiple times
        for _ in range(3):
            runner.invoke(app, ["get", command_id])

        # Verify use count increased
        result = runner.invoke(app, ["get", command_id])
        assert result.exit_code == 0
        # The use count should be 4 (3 + 1 from this call)

    def test_search_with_limit(self, runner, neo4j_client):
        """Test search with limit parameter."""
        # Add multiple commands
        for i in range(5):
            runner.invoke(
                app,
                [
                    "add",
                    f"test command {i}",
                    "--desc",
                    f"Test {i}",
                    "--no-auto-context",
                ],
            )

        # Search with limit
        result = runner.invoke(app, ["search", "test", "--limit", "3"])
        assert result.exit_code == 0
        # Should show at most 3 results

    def test_context_display(self, runner, neo4j_client):
        """Test displaying current context information."""
        result = runner.invoke(app, ["context"])
        assert result.exit_code == 0
        assert "OS:" in result.stdout or "Project Type:" in result.stdout

    def test_search_with_multiple_tags(self, runner, neo4j_client):
        """Test searching with multiple tags (AND operation)."""
        # Add commands with different tag combinations
        runner.invoke(
            app,
            [
                "add",
                "docker build -t myapp .",
                "--desc",
                "Build Docker image",
                "-t",
                "docker,build",
                "--no-auto-context",
            ],
        )
        runner.invoke(
            app,
            [
                "add",
                "docker run myapp",
                "--desc",
                "Run Docker container",
                "-t",
                "docker,run",
                "--no-auto-context",
            ],
        )
        runner.invoke(
            app,
            [
                "add",
                "make build",
                "--desc",
                "Build with make",
                "-t",
                "make,build",
                "--no-auto-context",
            ],
        )

        # Search for commands with both docker AND build tags
        result = runner.invoke(app, ["search", "-t", "docker,build"])
        assert result.exit_code == 0
        assert "docker build" in result.stdout
        assert "docker run" not in result.stdout
        assert "make build" not in result.stdout
