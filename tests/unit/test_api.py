"""Tests for the public Memory Box API."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from lib.api import MemoryBox
from lib.models import Command, CommandWithMetadata, Stack


@pytest.fixture
def mock_client():
    """Create a mock Neo4jClient."""
    with patch("lib.api.Neo4jClient") as mock:
        yield mock


@pytest.fixture
def sample_datetime():
    """Sample datetime for tests."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_memory_box_initialization_with_defaults(mock_client):
    """Test MemoryBox initializes with default settings."""
    mb = MemoryBox()
    mock_client.assert_called_once()
    mb.close()


def test_memory_box_initialization_with_custom_params(mock_client):
    """Test MemoryBox accepts custom connection parameters."""
    mb = MemoryBox(
        neo4j_uri="bolt://custom:7687",
        neo4j_user="custom_user",
        neo4j_password="custom_pass",
        neo4j_database="custom_db",
    )
    mock_client.assert_called_once()
    mb.close()


def test_add_command_with_string():
    """Test adding a command with simple string input."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.add_command.return_value = "test-id-123"
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        command_id = mb.add_command("docker ps", description="List containers", tags=["docker"])

        assert command_id == "test-id-123"
        mock_instance.add_command.assert_called_once()

        # Verify it created a Command object
        call_args = mock_instance.add_command.call_args[0][0]
        assert isinstance(call_args, Command)
        assert call_args.command == "docker ps"
        assert call_args.description == "List containers"
        assert call_args.tags == ["docker"]


def test_add_command_with_command_object():
    """Test adding a command with Command model object."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.add_command.return_value = "test-id-456"
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        cmd = Command(command="git status", description="Check status", tags=["git"])
        command_id = mb.add_command(cmd)

        assert command_id == "test-id-456"
        mock_instance.add_command.assert_called_once_with(cmd)


def test_add_command_with_all_parameters():
    """Test adding a command with all optional parameters."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.add_command.return_value = "test-id-789"
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        command_id = mb.add_command(
            "npm install",
            description="Install dependencies",
            tags=["npm", "node"],
            os="linux",
            project_type="node",
            context="/workspace/project",
            category="package-management",
        )

        assert command_id == "test-id-789"
        call_args = mock_instance.add_command.call_args[0][0]
        assert call_args.command == "npm install"
        assert call_args.os == "linux"
        assert call_args.project_type == "node"
        assert call_args.context == "/workspace/project"
        assert call_args.category == "package-management"


def test_search_commands_default_fuzzy(sample_datetime):
    """Test search with default fuzzy matching enabled."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_result = CommandWithMetadata(
            id="1",
            command="docker ps",
            description="",
            tags=[],
            created_at=sample_datetime,
            use_count=0,
        )
        mock_instance.search_commands.return_value = [mock_result]
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        results = mb.search_commands("doker")  # typo

        assert len(results) == 1
        assert results[0].command == "docker ps"
        mock_instance.search_commands.assert_called_once_with(
            query="doker",
            fuzzy=True,
            os=None,
            project_type=None,
            category=None,
            tags=None,
            limit=10,
        )


def test_search_commands_with_filters():
    """Test search with all filter parameters."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.search_commands.return_value = []
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        mb.search_commands(
            query="docker",
            fuzzy=False,
            os="linux",
            project_type="python",
            category="containers",
            tags=["docker", "dev"],
            limit=20,
        )

        mock_instance.search_commands.assert_called_once_with(
            query="docker",
            fuzzy=False,
            os="linux",
            project_type="python",
            category="containers",
            tags=["docker", "dev"],
            limit=20,
        )


def test_get_command(sample_datetime):
    """Test retrieving a specific command by ID."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_result = CommandWithMetadata(
            id="test-123",
            command="docker ps",
            description="List containers",
            tags=["docker"],
            created_at=sample_datetime,
            use_count=5,
        )
        mock_instance.get_command.return_value = mock_result
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        cmd = mb.get_command("test-123")

        assert cmd is not None
        assert cmd.id == "test-123"
        assert cmd.command == "docker ps"
        assert cmd.use_count == 5
        mock_instance.get_command.assert_called_once_with("test-123")


def test_get_command_not_found():
    """Test get_command returns None when command not found."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get_command.return_value = None
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        cmd = mb.get_command("nonexistent")

        assert cmd is None


def test_list_commands_no_filters():
    """Test listing all commands without filters."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.search_commands.return_value = []
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        mb.list_commands()

        mock_instance.search_commands.assert_called_once_with(
            query="",
            fuzzy=False,
            os=None,
            project_type=None,
            category=None,
            tags=None,
            limit=100,
        )


def test_list_commands_with_filters():
    """Test listing commands with filters."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.search_commands.return_value = []
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        mb.list_commands(os="linux", project_type="python", category="git", tags=["git"], limit=50)

        mock_instance.search_commands.assert_called_once_with(
            query="",
            fuzzy=False,
            os="linux",
            project_type="python",
            category="git",
            tags=["git"],
            limit=50,
        )


def test_delete_command_success():
    """Test deleting a command successfully."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.delete_command.return_value = True
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        result = mb.delete_command("test-123")

        assert result is True
        mock_instance.delete_command.assert_called_once_with("test-123")


def test_delete_command_not_found():
    """Test delete_command returns False when command not found."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.delete_command.return_value = False
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        result = mb.delete_command("nonexistent")

        assert result is False


def test_context_manager():
    """Test MemoryBox works as a context manager."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance

        with MemoryBox() as mb:
            assert mb is not None

        mock_instance.close.assert_called_once()


def test_increment_use_count(sample_datetime):
    """Test incrementing use count for a command."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get_command.return_value = CommandWithMetadata(
            id="test-123",
            command="docker ps",
            description="",
            tags=[],
            created_at=sample_datetime,
            use_count=1,
        )
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        result = mb.increment_use_count("test-123")

        assert result is True
        mock_instance.get_command.assert_called_once_with("test-123")


def test_increment_use_count_not_found():
    """Test increment_use_count returns False when command not found."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get_command.return_value = None
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        result = mb.increment_use_count("nonexistent")

        assert result is False


def test_list_stacks():
    """Test listing all stacks."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_stacks = [
            Stack(name="Docker", type="tool", description="Container platform"),
            Stack(name="Python", type="language", description="Programming language"),
            Stack(name="Git", type="tool", description="Version control"),
        ]
        mock_instance.list_stacks.return_value = mock_stacks
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        stacks = mb.list_stacks()

        assert len(stacks) == 3
        assert stacks[0].name == "Docker"
        assert stacks[1].name == "Python"
        assert stacks[2].name == "Git"
        mock_instance.list_stacks.assert_called_once()


def test_get_commands_by_stack():
    """Test getting commands for a specific stack."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_commands = [
            CommandWithMetadata(
                id="cmd-1",
                command="docker build -t app .",
                description="Build Docker image",
                tags=["docker"],
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
                use_count=5,
            ),
            CommandWithMetadata(
                id="cmd-2",
                command="docker run -p 8080:80 app",
                description="Run Docker container",
                tags=["docker"],
                created_at=datetime(2024, 1, 2, tzinfo=UTC),
                use_count=3,
            ),
        ]
        mock_instance.get_commands_by_stack.return_value = mock_commands
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        commands = mb.get_commands_by_stack("Docker")

        assert len(commands) == 2
        assert commands[0].command == "docker build -t app ."
        assert commands[1].command == "docker run -p 8080:80 app"
        mock_instance.get_commands_by_stack.assert_called_once_with("Docker", None)


def test_get_commands_by_stack_with_relationship_type():
    """Test getting commands for a stack filtered by relationship type."""
    with patch("lib.api.Neo4jClient") as mock_client:
        mock_instance = MagicMock()
        mock_commands = [
            CommandWithMetadata(
                id="cmd-1",
                command="docker build -t app .",
                description="Build Docker image",
                tags=["docker"],
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
                use_count=5,
            ),
        ]
        mock_instance.get_commands_by_stack.return_value = mock_commands
        mock_client.return_value = mock_instance

        mb = MemoryBox()
        commands = mb.get_commands_by_stack("Docker", relationship_type="BUILD")

        assert len(commands) == 1
        assert commands[0].command == "docker build -t app ."
        mock_instance.get_commands_by_stack.assert_called_once_with("Docker", "BUILD")
