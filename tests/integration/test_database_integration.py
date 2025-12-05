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
        session.run("MATCH (n:Stack) DELETE n")

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


@skip_if_no_neo4j
class TestStackAutoLinkingIntegration:
    """Integration tests for automatic stack detection and linking."""

    def test_docker_build_creates_docker_stack(self, db_client: Neo4jClient) -> None:
        """Test that 'docker build' command creates Docker stack with BUILD relationship."""
        cmd = Command(
            command="docker build -t myapp:latest .",
            description="Build Docker image for myapp",
            tags=["docker", "build"],
        )

        command_id = db_client.add_command(cmd)

        # Verify the stack was created
        docker_stack = db_client.get_stack("Docker")
        assert docker_stack is not None
        assert docker_stack.name == "Docker"
        assert docker_stack.type == "tool"

        # Verify the command is linked to the stack
        commands = db_client.get_commands_by_stack("Docker")
        assert len(commands) >= 1
        assert any(c.id == command_id for c in commands)

        # Verify BUILD relationship exists
        build_commands = db_client.get_commands_by_stack("Docker", relationship_type="BUILD")
        assert len(build_commands) >= 1
        assert any(c.id == command_id for c in build_commands)

    def test_pytest_creates_python_test_stack(self, db_client: Neo4jClient) -> None:
        """Test that 'pytest' command creates Python stack with TEST relationship."""
        cmd = Command(
            command="pytest tests/ -v --cov",
            description="Run Python tests with coverage",
            tags=["python", "testing"],
        )

        command_id = db_client.add_command(cmd)

        # Verify Python stack exists
        python_stack = db_client.get_stack("Python")
        assert python_stack is not None
        assert python_stack.name == "Python"
        assert python_stack.type == "language"

        # Verify TEST relationship
        test_commands = db_client.get_commands_by_stack("Python", relationship_type="TEST")
        assert len(test_commands) >= 1
        assert any(c.id == command_id for c in test_commands)

    def test_git_push_creates_git_deploy_stack(self, db_client: Neo4jClient) -> None:
        """Test that 'git push' command creates Git stack with DEPLOY relationship."""
        cmd = Command(
            command="git push origin main",
            description="Push changes to main branch",
            tags=["git"],
        )

        command_id = db_client.add_command(cmd)

        # Verify Git stack
        git_stack = db_client.get_stack("Git")
        assert git_stack is not None
        assert git_stack.name == "Git"
        assert git_stack.type == "tool"

        # Verify DEPLOY relationship
        deploy_commands = db_client.get_commands_by_stack("Git", relationship_type="DEPLOY")
        assert len(deploy_commands) >= 1
        assert any(c.id == command_id for c in deploy_commands)

    def test_npm_creates_node_stack(self, db_client: Neo4jClient) -> None:
        """Test that npm commands create Node stack with appropriate relationships."""
        # Test npm run build -> BUILD relationship
        build_cmd = Command(
            command="npm run build",
            description="Build Node.js application",
            tags=["node", "npm"],
        )
        build_id = db_client.add_command(build_cmd)

        # Test npm test -> TEST relationship
        test_cmd = Command(
            command="npm test",
            description="Run Node.js tests",
            tags=["node"],
        )
        test_id = db_client.add_command(test_cmd)

        # Verify Node stack
        node_stack = db_client.get_stack("Node")
        assert node_stack is not None
        assert node_stack.name == "Node"
        assert node_stack.type == "language"

        # Verify BUILD relationship
        build_commands = db_client.get_commands_by_stack("Node", relationship_type="BUILD")
        assert any(c.id == build_id for c in build_commands)

        # Verify TEST relationship
        test_commands = db_client.get_commands_by_stack("Node", relationship_type="TEST")
        assert any(c.id == test_id for c in test_commands)

    def test_multiple_stacks_for_single_command(self, db_client: Neo4jClient) -> None:
        """Test that a command can be linked to multiple stacks."""
        # A command that could relate to both Docker and Python
        cmd = Command(
            command="docker run python:3.11 python script.py",
            description="Run Python script in Docker container",
            tags=["docker", "python"],
        )

        command_id = db_client.add_command(cmd)

        # Should be linked to both Docker and Python stacks
        docker_commands = db_client.get_commands_by_stack("Docker")
        python_commands = db_client.get_commands_by_stack("Python")

        assert any(c.id == command_id for c in docker_commands)
        assert any(c.id == command_id for c in python_commands)

    def test_list_all_stacks(self, db_client: Neo4jClient) -> None:
        """Test listing all stacks after adding various commands."""
        # Add commands that create different stacks
        commands = [
            Command(command="docker build .", description="Build", tags=[]),
            Command(command="pytest tests/", description="Test", tags=[]),
            Command(command="git commit -m 'msg'", description="Commit", tags=[]),
            Command(command="cargo build", description="Build Rust", tags=[]),
        ]

        for cmd in commands:
            db_client.add_command(cmd)

        # List all stacks
        stacks = db_client.list_stacks()

        # Should have at least Docker, Python, Git, Rust
        stack_names = {s.name for s in stacks}
        assert "Docker" in stack_names
        assert "Python" in stack_names
        assert "Git" in stack_names
        assert "Rust" in stack_names

    def test_tag_based_stack_linking(self, db_client: Neo4jClient) -> None:
        """Test that tags alone can trigger stack linking."""
        cmd = Command(
            command="custom-script.sh",
            description="Custom script",
            tags=["kubernetes"],  # Tag should trigger Kubernetes stack
        )

        command_id = db_client.add_command(cmd)

        # Verify Kubernetes stack was created
        k8s_stack = db_client.get_stack("Kubernetes")
        assert k8s_stack is not None
        assert k8s_stack.name == "Kubernetes"

        # Verify command is linked
        k8s_commands = db_client.get_commands_by_stack("Kubernetes")
        assert any(c.id == command_id for c in k8s_commands)

    def test_stack_linking_with_category(self, db_client: Neo4jClient) -> None:
        """Test that category can influence stack linking."""
        cmd = Command(
            command="make build",
            description="Build using Make",
            tags=[],
            category="build",
        )

        command_id = db_client.add_command(cmd)

        # Should create Make stack
        make_stack = db_client.get_stack("Make")
        assert make_stack is not None

        # Verify BUILD relationship (from 'make build' pattern)
        build_commands = db_client.get_commands_by_stack("Make", relationship_type="BUILD")
        assert any(c.id == command_id for c in build_commands)
