"""Tests for Stack model and stack-based command organization."""

from unittest.mock import MagicMock, patch

from lib.config import Settings
from lib.database import Neo4jClient
from lib.models import Stack


def create_mock_settings() -> Settings:
    """Create mock settings for testing."""
    return Settings(
        neo4j_uri="bolt://test:7687",
        neo4j_user="test_user",
        neo4j_password="test_password",
        neo4j_database="test_db",
    )


class TestStackModel:
    """Test Stack data model."""

    def test_stack_creation(self) -> None:
        """Test creating a Stack with all properties."""
        stack = Stack(
            name="Docker",
            type="tool",
            description="Container platform for building and running applications",
        )

        assert stack.name == "Docker"
        assert stack.type == "tool"
        assert stack.description == "Container platform for building and running applications"

    def test_stack_minimal(self) -> None:
        """Test creating a Stack with minimal required fields."""
        stack = Stack(name="Python", type="language")

        assert stack.name == "Python"
        assert stack.type == "language"
        assert stack.description == ""


class TestStackDatabase:
    """Test stack operations in database."""

    @patch("lib.database.GraphDatabase")
    def test_create_stack(self, mock_graph_db: MagicMock) -> None:
        """Test creating a stack node in database."""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        db = Neo4jClient(create_mock_settings())
        stack = Stack(name="Docker", type="tool", description="Container platform")

        db.create_stack(stack)

        # Verify Cypher query was called (skip initialization calls)
        call_args = mock_session.run.call_args
        query = call_args[0][0]

        assert "CREATE" in query or "MERGE" in query
        assert "Stack" in query
        assert call_args[1]["name"] == "Docker"
        assert call_args[1]["type"] == "tool"

    @patch("lib.database.GraphDatabase")
    def test_get_stack_by_name(self, mock_graph_db: MagicMock) -> None:
        """Test retrieving a stack by name."""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock return data - use dict instead of MagicMock to support .get()
        mock_node = {
            "name": "Docker",
            "type": "tool",
            "description": "Container platform",
        }
        mock_session.run.return_value.single.return_value = {"s": mock_node}

        db = Neo4jClient(create_mock_settings())
        stack = db.get_stack("Docker")

        assert stack is not None
        assert stack.name == "Docker"
        assert stack.type == "tool"

    @patch("lib.database.GraphDatabase")
    def test_link_command_to_stack(self, mock_graph_db: MagicMock) -> None:
        """Test creating a relationship between command and stack."""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        db = Neo4jClient(create_mock_settings())

        # Link command to stack with BUILD relationship
        db.link_command_to_stack(
            command_id="cmd-123", stack_name="Docker", relationship_type="BUILD"
        )

        # Verify relationship query (skip initialization calls)
        call_args = mock_session.run.call_args
        query = call_args[0][0]

        assert "MATCH" in query
        assert "CREATE" in query or "MERGE" in query
        assert ":BUILD" in query or "BUILD" in query
        assert call_args[1]["command_id"] == "cmd-123"
        assert call_args[1]["stack_name"] == "Docker"

    @patch("lib.database.GraphDatabase")
    def test_get_commands_by_stack(self, mock_graph_db: MagicMock) -> None:
        """Test retrieving all commands for a specific stack."""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock return data - use a dict-like object that supports .get()
        mock_node = {
            "id": "cmd-123",
            "command": "docker build -t myapp .",
            "description": "Build Docker image",
            "created_at": "2024-01-01T00:00:00",
            "tags": ["docker"],
            "os": None,
            "project_type": None,
            "context": None,
            "category": None,
            "last_used": None,
            "use_count": 5,
        }
        mock_record = {"c": mock_node, "tags": ["docker"], "rel_type": "BUILD"}
        mock_session.run.return_value = [mock_record]

        db = Neo4jClient(create_mock_settings())
        commands = db.get_commands_by_stack("Docker")

        assert len(commands) == 1
        assert commands[0].command == "docker build -t myapp ."

    @patch("lib.database.GraphDatabase")
    def test_get_commands_by_stack_and_category(self, mock_graph_db: MagicMock) -> None:
        """Test retrieving commands filtered by stack and relationship type."""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock return data - use a dict-like object that supports .get()
        mock_node = {
            "id": "cmd-123",
            "command": "docker build -t myapp .",
            "description": "Build Docker image",
            "created_at": "2024-01-01T00:00:00",
            "tags": ["docker"],
            "os": None,
            "project_type": None,
            "context": None,
            "category": None,
            "last_used": None,
            "use_count": 5,
        }
        mock_record = {"c": mock_node, "tags": ["docker"]}
        mock_session.run.return_value = [mock_record]

        db = Neo4jClient(create_mock_settings())
        commands = db.get_commands_by_stack("Docker", relationship_type="BUILD")

        assert len(commands) == 1
        # Verify query includes relationship type filter
        call_args = mock_session.run.call_args
        query = call_args[0][0]
        assert "BUILD" in query

    @patch("lib.database.GraphDatabase")
    def test_list_all_stacks(self, mock_graph_db: MagicMock) -> None:
        """Test listing all stacks in database."""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Mock multiple stacks - use dicts that support .get()
        mock_records = [
            {"s": {"name": "Docker", "type": "tool", "description": ""}},
            {"s": {"name": "Python", "type": "language", "description": ""}},
            {"s": {"name": "Git", "type": "tool", "description": ""}},
        ]
        mock_session.run.return_value = mock_records

        db = Neo4jClient(create_mock_settings())
        stacks = db.list_stacks()

        assert len(stacks) == 3
        assert any(s.name == "Docker" for s in stacks)
        assert any(s.name == "Python" for s in stacks)
