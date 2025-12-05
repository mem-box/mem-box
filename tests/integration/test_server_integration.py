"""Integration tests for MCP server with real Neo4j database."""

import pytest

from lib.config import get_settings
from lib.database import Neo4jClient
from server.server import (
    add_command,
    delete_command,
    get_command_by_id,
    get_commands_by_stack,
    get_context_suggestions,
    list_categories,
    list_stacks,
    list_tags,
    search_commands,
)


@pytest.fixture(scope="module")
def neo4j_client():
    """Create a Neo4j client for integration tests."""
    settings = get_settings()
    client = Neo4jClient(settings)
    yield client
    client.close()


@pytest.fixture(autouse=True)
def clean_database(neo4j_client):
    """Clean the database before each test."""
    with neo4j_client.driver.session(database=neo4j_client.database) as session:
        session.run("MATCH (n) DETACH DELETE n")


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
        assert "git push origin main" in search_result
        assert "Push changes to main branch" in search_result

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
        assert "ls -la" in result
        assert "grep -r" in result

        # Search by category
        result = search_commands.fn(category="navigation")
        assert "ls -la" in result
        assert "grep -r" not in result

        # Search by multiple tags (AND operation)
        result = search_commands.fn(tags=["filesystem", "search"])
        assert "grep -r" in result
        assert "ls -la" not in result

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
        assert "apt update" in result
        assert "brew update" not in result

        # Search for macOS commands
        result = search_commands.fn(os="macos")
        assert "brew update" in result
        assert "apt update" not in result

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
        assert "npm run build" in result
        assert "cargo build" not in result

        # Search for Rust commands
        result = search_commands.fn(project_type="rust")
        assert "cargo build" in result
        assert "npm run build" not in result

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

    def test_use_count_tracking(self, neo4j_client):
        """Test that retrieving a command increments use count via MCP."""
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

        # Get the command multiple times
        for _ in range(3):
            get_command_by_id.fn(command_id=command_id)

        # Get command details and check use count
        result = get_command_by_id.fn(command_id=command_id)
        assert "Used: 4 time(s)" in result  # 3 previous calls + this one

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
        assert "docker build" in search_result
        assert "Build Docker image" in search_result

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
        assert "git commit" in result
        assert "git push" not in result
        assert "svn commit" not in result

    def test_empty_search_results(self, neo4j_client):
        """Test handling of empty search results via MCP."""
        result = search_commands.fn(query="nonexistent_command_xyz")
        assert "No commands found" in result

    def test_empty_tags_list(self, neo4j_client):
        """Test listing tags when none exist via MCP."""
        result = list_tags.fn()
        assert "No tags found" in result or "Available tags" in result

    def test_empty_categories_list(self, neo4j_client):
        """Test listing categories when none exist via MCP."""
        result = list_categories.fn()
        assert "No categories found" in result or "Available categories" in result

    def test_list_stacks_via_mcp(self, neo4j_client):
        """Test listing stacks via MCP server."""
        # Add commands that create stacks
        add_command.fn(
            command="docker build -t app .",
            description="Build Docker image",
            tags=["docker"],
            auto_detect_context=False,
        )
        add_command.fn(
            command="pytest tests/",
            description="Run Python tests",
            tags=["python"],
            auto_detect_context=False,
        )
        add_command.fn(
            command="git push origin main",
            description="Push to remote",
            tags=["git"],
            auto_detect_context=False,
        )

        # List stacks
        result = list_stacks.fn()
        assert "Technology Stacks" in result
        assert "Docker" in result
        assert "Python" in result
        assert "Git" in result

    def test_get_commands_by_stack_via_mcp(self, neo4j_client):
        """Test getting commands for a specific stack via MCP."""
        # Add Docker commands
        add_command.fn(
            command="docker build -t myapp .",
            description="Build Docker image",
            tags=["docker"],
            auto_detect_context=False,
        )
        add_command.fn(
            command="docker run -p 8080:80 myapp",
            description="Run Docker container",
            tags=["docker"],
            auto_detect_context=False,
        )
        add_command.fn(
            command="pytest tests/",
            description="Run tests",
            tags=["python"],
            auto_detect_context=False,
        )

        # Get all Docker commands
        result = get_commands_by_stack.fn(stack_name="Docker")
        assert "Commands for Docker" in result
        assert "docker build" in result
        assert "docker run" in result
        assert "pytest" not in result

    def test_get_commands_by_stack_with_relationship_type_via_mcp(self, neo4j_client):
        """Test filtering commands by stack and relationship type via MCP."""
        # Add Docker commands
        add_command.fn(
            command="docker build -t myapp .",
            description="Build Docker image",
            tags=["docker"],
            auto_detect_context=False,
        )
        add_command.fn(
            command="docker run -p 8080:80 myapp",
            description="Run Docker container",
            tags=["docker"],
            auto_detect_context=False,
        )

        # Get only Docker BUILD commands
        result = get_commands_by_stack.fn(stack_name="Docker", relationship_type="BUILD")
        assert "Commands for Docker (BUILD)" in result
        assert "docker build" in result
        assert "docker run" not in result

    def test_empty_stack_list_via_mcp(self, neo4j_client):
        """Test listing stacks when none exist via MCP."""
        result = list_stacks.fn()
        assert "No stacks found" in result

    def test_add_command_auto_creates_stack(self, neo4j_client):
        """Test that adding a command automatically creates the stack."""
        # Verify no stacks exist initially
        result = list_stacks.fn()
        assert "No stacks found" in result

        # Add a Docker command
        add_command.fn(
            command="docker build -t myapp .",
            description="Build Docker image",
            auto_detect_context=False,
        )

        # Verify Docker stack was created
        result = list_stacks.fn()
        assert "Docker" in result
        assert "tool" in result.lower()

        # Verify command is linked to stack
        result = get_commands_by_stack.fn(stack_name="Docker")
        assert "docker build" in result

    def test_add_command_creates_multiple_stacks(self, neo4j_client):
        """Test that adding commands creates multiple stacks."""
        # Add commands for different technologies
        commands = [
            ("docker build .", "Build with Docker", ["docker"]),
            ("pytest tests/", "Run Python tests", ["python"]),
            ("git push origin main", "Push to Git", ["git"]),
            ("npm run build", "Build Node app", ["node"]),
        ]

        for cmd, desc, tags in commands:
            add_command.fn(
                command=cmd,
                description=desc,
                tags=tags,
                auto_detect_context=False,
            )

        # Verify all stacks were created
        result = list_stacks.fn()
        assert "Docker" in result
        assert "Python" in result
        assert "Git" in result
        assert "Node" in result

    def test_add_command_with_tag_creates_stack(self, neo4j_client):
        """Test that tags also trigger stack creation."""
        # Add a command with kubernetes tag
        add_command.fn(
            command="kubectl get pods",
            description="List Kubernetes pods",
            tags=["kubernetes"],
            auto_detect_context=False,
        )

        # Verify Kubernetes stack was created
        result = list_stacks.fn()
        assert "Kubernetes" in result

        # Verify command is linked
        result = get_commands_by_stack.fn(stack_name="Kubernetes")
        assert "kubectl get pods" in result
