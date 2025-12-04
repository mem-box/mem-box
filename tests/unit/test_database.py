"""Tests for database module."""

from unittest.mock import Mock, patch

import pytest

from lib.config import Settings
from lib.database import Neo4jClient
from lib.models import Command, CommandWithMetadata


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    return Settings(
        neo4j_uri="bolt://test:7687",
        neo4j_user="test_user",
        neo4j_password="test_password",
        neo4j_database="test_db",
    )


@pytest.fixture
def mock_driver() -> Mock:
    """Create a mock Neo4j driver."""
    return Mock()


@pytest.fixture
def mock_session() -> Mock:
    """Create a mock Neo4j session."""
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    return session


class TestNeo4jClient:
    """Tests for Neo4jClient class."""

    @patch("lib.database.GraphDatabase")
    def test_client_initialization(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test Neo4j client initialization."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        client = Neo4jClient(mock_settings)

        mock_graph_database.driver.assert_called_once_with(
            "bolt://test:7687", auth=("test_user", "test_password")
        )
        assert client.database == "test_db"

    @patch("lib.database.GraphDatabase")
    def test_client_close(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test closing Neo4j client connection."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        client = Neo4jClient(mock_settings)
        client.close()

        mock_driver.close.assert_called_once()

    @patch("lib.database.GraphDatabase")
    @patch("lib.database.uuid.uuid4")
    def test_add_command(
        self,
        mock_uuid: Mock,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test adding a command to the database."""
        mock_uuid.return_value = "test-uuid-123"
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        client = Neo4jClient(mock_settings)

        cmd = Command(
            command="git status",
            description="Show working tree status",
            tags=["git"],
            os="linux",
            project_type="python",
        )

        command_id = client.add_command(cmd)

        assert command_id == "test-uuid-123"
        mock_session.run.assert_called()

    @patch("lib.database.GraphDatabase")
    def test_search_commands_with_query(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test searching commands with a query string."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        # Mock the query result
        mock_record = Mock()
        mock_record.__getitem__ = Mock(
            side_effect=lambda key: {
                "c": {
                    "id": "test-id",
                    "command": "git status",
                    "description": "Show status",
                    "os": "linux",
                    "project_type": "python",
                    "context": None,
                    "category": "git",
                    "created_at": "2023-01-01T00:00:00",
                    "last_used": None,
                    "use_count": 0,
                },
                "tags": ["git"],
            }[key]
        )

        mock_session.run.return_value = [mock_record]

        client = Neo4jClient(mock_settings)
        commands = client.search_commands(query="status", limit=10)

        assert len(commands) == 1
        assert isinstance(commands[0], CommandWithMetadata)
        assert commands[0].command == "git status"

    @patch("lib.database.GraphDatabase")
    def test_search_commands_no_results(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test searching commands with no results."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session
        mock_session.run.return_value = []

        client = Neo4jClient(mock_settings)
        commands = client.search_commands(query="nonexistent")

        assert commands == []

    @patch("lib.database.GraphDatabase")
    def test_get_command_found(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test getting a command by ID when it exists."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        mock_record = Mock()
        mock_record.__getitem__ = Mock(
            side_effect=lambda key: {
                "c": {
                    "id": "test-id",
                    "command": "docker ps",
                    "description": "List containers",
                    "os": "linux",
                    "project_type": None,
                    "context": None,
                    "category": "docker",
                    "created_at": "2023-01-01T00:00:00",
                    "last_used": None,
                    "use_count": 1,
                },
                "tags": ["docker"],
            }[key]
        )

        mock_session.run.return_value.single.return_value = mock_record

        client = Neo4jClient(mock_settings)
        cmd = client.get_command("test-id")

        assert cmd is not None
        assert isinstance(cmd, CommandWithMetadata)
        assert cmd.id == "test-id"
        assert cmd.command == "docker ps"

    @patch("lib.database.GraphDatabase")
    def test_get_command_not_found(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test getting a command by ID when it doesn't exist."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session
        mock_session.run.return_value.single.return_value = None

        client = Neo4jClient(mock_settings)
        cmd = client.get_command("nonexistent-id")

        assert cmd is None

    @patch("lib.database.GraphDatabase")
    def test_delete_command_success(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test deleting a command successfully."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        mock_record = Mock()
        mock_record.__getitem__ = Mock(return_value=1)
        mock_session.run.return_value.single.return_value = mock_record

        client = Neo4jClient(mock_settings)
        result = client.delete_command("test-id")

        assert result is True

    @patch("lib.database.GraphDatabase")
    def test_delete_command_not_found(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test deleting a command that doesn't exist."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        mock_record = Mock()
        mock_record.__getitem__ = Mock(return_value=0)
        mock_session.run.return_value.single.return_value = mock_record

        client = Neo4jClient(mock_settings)
        result = client.delete_command("nonexistent-id")

        assert result is False

    @patch("lib.database.GraphDatabase")
    def test_get_all_tags(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test getting all tags."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        mock_records = [{"tag": "git"}, {"tag": "docker"}, {"tag": "python"}]
        mock_session.run.return_value = mock_records

        client = Neo4jClient(mock_settings)
        tags = client.get_all_tags()

        assert tags == ["git", "docker", "python"]

    @patch("lib.database.GraphDatabase")
    def test_get_all_categories(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test getting all categories."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        mock_records = [{"category": "git"}, {"category": "docker"}, {"category": "kubernetes"}]
        mock_session.run.return_value = mock_records

        client = Neo4jClient(mock_settings)
        categories = client.get_all_categories()

        assert categories == ["git", "docker", "kubernetes"]
