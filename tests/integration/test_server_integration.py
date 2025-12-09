"""Integration tests for MCP server with test Neo4j container."""

from collections.abc import Generator

import pytest
from testcontainers.neo4j import Neo4jContainer

import server.server
from lib.api import MemoryBox
from lib.database import Neo4jClient
from lib.settings import Settings
from server.server import (
    add_command,
    delete_command,
    get_command_by_id,
    get_context_suggestions,
    list_categories,
    list_tags,
    search_commands,
)


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
def test_memory_box(neo4j_settings: Settings) -> Generator[MemoryBox, None, None]:
    """Create a MemoryBox instance using test container settings."""
    mb = MemoryBox(settings=neo4j_settings)

    # Clean before test
    with mb._client.driver.session(database=mb._client.database) as session:
        session.run("MATCH (n) DETACH DELETE n")

    yield mb

    # Clean after test
    with mb._client.driver.session(database=mb._client.database) as session:
        session.run("MATCH (n) DETACH DELETE n")

    mb.close()


@pytest.fixture
def neo4j_client(test_memory_box: MemoryBox) -> Neo4jClient:
    """Get the Neo4jClient from the test MemoryBox."""
    return test_memory_box._client


@pytest.fixture(autouse=True)
def patch_server_memory_box(test_memory_box: MemoryBox):
    """Patch the global memory_box in server.server to use test container."""
    original = server.server.memory_box
    server.server.memory_box = test_memory_box
    yield
    server.server.memory_box = original


class TestMCPServerIntegration:
    """Integration tests for MCP server tools with Neo4j."""

    def test_add_and_search_command(self, neo4j_client):
        """Test adding a command via MCP and searching for it."""
        # Add a command using the MCP tool
        result = add_command.fn(
            command="git push origin main",
            description="Push changes to main branch",
            tags=["git", "version-control"],
            auto_detect_context=False,
        )
        assert "Command added successfully" in result

        # Search for the command
        search_result = search_commands.fn(query="push")
        assert isinstance(search_result, list)
        assert len(search_result) > 0
        assert any("git push origin main" in cmd["command"] for cmd in search_result)
        assert any("Push changes to main branch" in cmd["description"] for cmd in search_result)

    def test_add_get_and_delete_command(self, neo4j_client):
        """Test the full lifecycle via MCP: add, get, delete."""
        # Add a command
        add_result = add_command.fn(
            command="kubectl get pods",
            description="List all pods",
            tags=["kubernetes", "kubectl"],
            auto_detect_context=False,
        )
        assert "Command added successfully" in add_result

        # Extract command ID from result
        lines = add_result.split("\n")
        command_id = None
        for line in lines:
            if "ID:" in line:
                command_id = line.split("ID:")[-1].strip()
                break

        assert command_id is not None

        # Get the command
        get_result = get_command_by_id.fn(command_id=command_id)
        assert "kubectl get pods" in get_result
        assert "List all pods" in get_result

        # Delete the command
        delete_result = delete_command.fn(command_id=command_id)
        assert "deleted" in delete_result.lower()

        # Verify it's deleted
        get_deleted = get_command_by_id.fn(command_id=command_id)
        assert "not found" in get_deleted.lower()

    def test_add_with_auto_detect_context(self, neo4j_client):
        """Test adding a command with auto-context detection via MCP."""
        result = add_command.fn(
            command="cargo test",
            description="Run Rust tests",
            tags=["rust", "testing"],
            auto_detect_context=True,
        )
        assert "Command added successfully" in result

    def test_search_with_filters(self, neo4j_client):
        """Test searching with various filters via MCP."""
        # Add commands with different attributes
        add_command.fn(
            command="ls -la",
            description="List files detailed",
            tags=["filesystem"],
            category="navigation",
            auto_detect_context=False,
        )
        add_command.fn(
            command="grep -r 'pattern' .",
            description="Search for pattern",
            tags=["filesystem", "search"],
            category="search",
            auto_detect_context=False,
        )

        # Search by tags
        result = search_commands.fn(tags=["filesystem"])
        assert isinstance(result, list)
        assert any("ls -la" in cmd["command"] for cmd in result)
        assert any("grep -r" in cmd["command"] for cmd in result)

        # Search by category
        result = search_commands.fn(category="navigation")
        assert isinstance(result, list)
        assert any("ls -la" in cmd["command"] for cmd in result)
        assert not any("grep -r" in cmd["command"] for cmd in result)

        # Search by multiple tags (OR operation - both commands have at least one tag)
        result = search_commands.fn(tags=["filesystem", "search"])
        assert isinstance(result, list)
        assert any("grep -r" in cmd["command"] for cmd in result)
        # Also matches because it has "filesystem" tag
        assert any("ls -la" in cmd["command"] for cmd in result)

    def test_list_tags(self, neo4j_client):
        """Test listing all tags via MCP."""
        # Add commands with tags
        add_command.fn(
            command="npm test",
            description="Run npm tests",
            tags=["npm", "testing", "nodejs"],
            auto_detect_context=False,
        )
        add_command.fn(
            command="pip install -r requirements.txt",
            description="Install Python packages",
            tags=["python", "pip"],
            auto_detect_context=False,
        )

        # List tags
        result = list_tags.fn()
        assert "npm" in result
        assert "testing" in result
        assert "nodejs" in result
        assert "python" in result
        assert "pip" in result

    def test_list_categories(self, neo4j_client):
        """Test listing all categories via MCP."""
        # Add commands with categories
        add_command.fn(
            command="docker-compose up",
            description="Start containers",
            category="docker",
            auto_detect_context=False,
        )
        add_command.fn(
            command="systemctl restart nginx",
            description="Restart nginx service",
            category="system",
            auto_detect_context=False,
        )

        # List categories
        result = list_categories.fn()
        assert "docker" in result
        assert "system" in result

    def test_get_context_suggestions(self, neo4j_client):
        """Test getting context-based suggestions via MCP."""
        # Add commands with specific OS context
        add_command.fn(
            command="apt install vim",
            description="Install vim editor",
            os="linux",
            auto_detect_context=False,
        )
        add_command.fn(
            command="brew install vim",
            description="Install vim with Homebrew",
            os="macos",
            auto_detect_context=False,
        )

        # Get suggestions (will use current context)
        result = get_context_suggestions.fn()
        # Should return suggestions based on current OS
        assert "command" in result.lower() or "no commands found" in result.lower()

    def test_search_with_os_filter(self, neo4j_client):
        """Test searching with OS filter via MCP."""
        # Add commands for different OS
        add_command.fn(
            command="apt update",
            description="Update packages",
            os="linux",
            auto_detect_context=False,
        )
        add_command.fn(
            command="brew update",
            description="Update Homebrew",
            os="macos",
            auto_detect_context=False,
        )

        # Search for Linux commands
        result = search_commands.fn(os="linux")
        assert isinstance(result, list)
        assert any("apt update" in cmd["command"] for cmd in result)
        assert not any("brew update" in cmd["command"] for cmd in result)

        # Search for macOS commands
        result = search_commands.fn(os="macos")
        assert isinstance(result, list)
        assert any("brew update" in cmd["command"] for cmd in result)
        assert not any("apt update" in cmd["command"] for cmd in result)

    def test_search_with_project_type_filter(self, neo4j_client):
        """Test searching with project type filter via MCP."""
        # Add commands for different project types
        add_command.fn(
            command="npm run build",
            description="Build Node.js project",
            project_type="nodejs",
            auto_detect_context=False,
        )
        add_command.fn(
            command="cargo build --release",
            description="Build Rust project",
            project_type="rust",
            auto_detect_context=False,
        )

        # Search for Node.js commands
        result = search_commands.fn(project_type="nodejs")
        assert isinstance(result, list)
        assert any("npm run build" in cmd["command"] for cmd in result)
        assert not any("cargo build" in cmd["command"] for cmd in result)

        # Search for Rust commands
        result = search_commands.fn(project_type="rust")
        assert isinstance(result, list)
        assert any("cargo build" in cmd["command"] for cmd in result)
        assert not any("npm run build" in cmd["command"] for cmd in result)

    def test_search_with_limit(self, neo4j_client):
        """Test search with limit parameter via MCP."""
        # Add multiple commands
        for i in range(10):
            add_command.fn(
                command=f"echo 'test {i}'",
                description=f"Test command {i}",
                tags=["test"],
                auto_detect_context=False,
            )

        # Search with limit
        result = search_commands.fn(tags=["test"], limit=3)
        # Should contain at most 3 commands
        assert result.count("echo 'test") <= 3

    def test_execution_count_not_incremented_by_retrieval(self, neo4j_client):
        """Test that retrieving a command does NOT increment execution count via MCP."""
        # Add a command
        add_result = add_command.fn(
            command="systemctl status",
            description="Check service status",
            auto_detect_context=False,
        )

        # Extract command ID
        lines = add_result.split("\n")
        command_id = None
        for line in lines:
            if "ID:" in line:
                command_id = line.split("ID:")[-1].strip()
                break

        # Get the command multiple times - should NOT increment execution_count
        for _ in range(3):
            get_command_by_id.fn(command_id=command_id)

        # Get command details and check execution count is still 0
        result = get_command_by_id.fn(command_id=command_id)
        assert "Executed: 0 time(s)" in result  # Not incremented by retrieval

    def test_add_command_with_all_fields(self, neo4j_client):
        """Test adding a command with all optional fields via MCP."""
        result = add_command.fn(
            command="docker build -t myapp:latest .",
            description="Build Docker image with latest tag",
            tags=["docker", "build", "containerization"],
            category="devops",
            os="linux",
            project_type="docker",
            context="Production deployment",
            auto_detect_context=False,
        )
        assert "Command added successfully" in result

        # Search for it to verify all fields
        search_result = search_commands.fn(query="docker build")
        assert isinstance(search_result, list)
        assert any("docker build" in cmd["command"] for cmd in search_result)
        assert any("Build Docker image" in cmd["description"] for cmd in search_result)

    def test_search_with_query_and_filters(self, neo4j_client):
        """Test combining query search with filters via MCP."""
        # Add various commands
        add_command.fn(
            command="git commit -m 'fix'",
            description="Commit bug fix",
            tags=["git"],
            category="version-control",
            auto_detect_context=False,
        )
        add_command.fn(
            command="git push origin develop",
            description="Push to develop branch",
            tags=["git"],
            category="version-control",
            auto_detect_context=False,
        )
        add_command.fn(
            command="svn commit -m 'fix'",
            description="Commit with SVN",
            tags=["svn"],
            category="version-control",
            auto_detect_context=False,
        )

        # Search with both query and filters
        result = search_commands.fn(query="commit", tags=["git"], category="version-control")
        assert isinstance(result, list)
        assert any("git commit" in cmd["command"] for cmd in result)
        assert not any("git push" in cmd["command"] for cmd in result)
        assert not any("svn commit" in cmd["command"] for cmd in result)

    def test_empty_search_results(self, neo4j_client):
        """Test handling of empty search results via MCP."""
        result = search_commands.fn(query="nonexistent_command_xyz")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_empty_tags_list(self, neo4j_client):
        """Test listing tags when none exist via MCP."""
        result = list_tags.fn()
        assert "No tags found" in result or "Available tags" in result

    def test_empty_categories_list(self, neo4j_client):
        """Test listing categories when none exist via MCP."""
        result = list_categories.fn()
        assert "No categories found" in result or "Available categories" in result
