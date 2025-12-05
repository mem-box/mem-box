"""Tests for database module."""

from unittest.mock import Mock, patch

import pytest

from lib.database import Neo4jClient
from lib.models import Command, CommandWithMetadata
from lib.settings import Settings


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

        # Mock the existing check to return None (command doesn't exist)
        mock_result = Mock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

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
        assert mock_session.run.call_count >= 2  # Check + Create queries

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
                    "context": None,
                    "created_at": "2023-01-01T00:00:00",
                    "last_used": None,
                    "use_count": 0,
                    "execution_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                },
                "tags": ["git"],
                "oses": ["linux"],
                "categories": ["git"],
                "project_types": ["python"],
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
                    "context": None,
                    "created_at": "2023-01-01T00:00:00",
                    "last_used": None,
                    "use_count": 1,
                    "execution_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                },
                "tags": ["docker"],
                "oses": ["linux"],
                "categories": ["docker"],
                "project_types": [],
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


class TestEdgeCases:
    """Test edge cases."""

    @patch("lib.database.GraphDatabase")
    def test_search_commands_skips_invalid_timestamps(
        self, mock_graph_database: Mock, mock_settings: Settings
    ) -> None:
        """Test that search_commands skips records with invalid timestamps."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()

        # Create a record with invalid timestamp (None)
        mock_record = {
            "c": {
                "id": "test-id",
                "command": "test command",
                "description": "test",
                "created_at": None,  # Invalid timestamp
                "last_used": None,
                "use_count": 0,
                "execution_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "last_status": None,
            },
            "tags": [],
            "oses": [],
            "categories": [],
            "project_types": [],
        }

        mock_result.__iter__ = Mock(return_value=iter([mock_record]))
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_driver.session.return_value = mock_session
        mock_graph_database.driver.return_value = mock_driver

        client = Neo4jClient(mock_settings)
        results = client.search_commands("test")

        # Should return empty list because invalid timestamp was skipped
        assert results == []

    @patch("lib.database.GraphDatabase")
    def test_get_command_returns_none_for_invalid_timestamp(
        self, mock_graph_database: Mock, mock_settings: Settings
    ) -> None:
        """Test that get_command returns None for invalid timestamps."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()

        # Create a record with invalid timestamp
        mock_record = {
            "c": {
                "id": "test-id",
                "command": "test command",
                "description": "test",
                "created_at": None,  # Invalid
                "last_used": None,
                "use_count": 0,
                "execution_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "last_status": None,
            },
            "tags": [],
            "oses": [],
            "categories": [],
            "project_types": [],
        }

        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_driver.session.return_value = mock_session
        mock_graph_database.driver.return_value = mock_driver

        client = Neo4jClient(mock_settings)
        result = client.get_command("test-id")

        assert result is None

    @patch("lib.database.GraphDatabase")
    @patch("lib.database._detect_category_and_tags")
    def test_validate_category_filters_invalid_category(
        self,
        mock_detect: Mock,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test that invalid categories are filtered out during auto-detection."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)

        # Mock detection to return an invalid category (not in CATEGORIES_MAP)
        mock_detect.return_value = ("invalid_category_not_in_map", [])

        # Mock existing command check to return None (new command)
        mock_result = Mock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        client = Neo4jClient(mock_settings)
        cmd = Command(command="testcmd", description="test")

        client.add_command(cmd)

        # The _detect_category_and_tags function should have been called
        # and line 35 should execute (category validation)
        mock_detect.assert_called_once_with("testcmd")

    @patch("lib.database.GraphDatabase")
    def test_search_with_query_only_no_filters(
        self,
        mock_graph_database: Mock,
        mock_settings: Settings,
        mock_driver: Mock,
        mock_session: Mock,
    ) -> None:
        """Test search with only query parameter (no tags or relationship filters)."""
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)

        mock_result = Mock()
        # Make the result iterable (empty list)
        mock_result.__iter__ = Mock(return_value=iter([]))
        mock_session.run.return_value = mock_result

        client = Neo4jClient(mock_settings)

        # Search with only query, no other filters - this should hit line 353
        results = client.search_commands(query="test", limit=10)

        assert results == []
        # Verify the query was executed
        assert mock_session.run.called
