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


class TestStackAutoLinking:
    """Tests for automatic stack detection and linking."""

    @patch("lib.database.GraphDatabase")
    @patch("lib.database.uuid.uuid4")
    def test_docker_build_creates_docker_stack_build_relationship(
        self,
        mock_uuid: Mock,
        mock_graph_database: Mock,
        mock_settings: Settings,
    ) -> None:
        """Test that 'docker build' command creates Docker stack with BUILD relationship."""
        mock_uuid.return_value = "test-uuid"
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        client = Neo4jClient(mock_settings)
        cmd = Command(
            command="docker build -t myapp .",
            description="Build Docker image",
            tags=[],
        )

        client.add_command(cmd)

        # Verify stack linking was called
        calls = mock_session.run.call_args_list
        # Should have: 1) constraint creation calls, 2) add command, 3) stack link
        stack_link_calls = [call for call in calls if "Stack" in str(call) and "MERGE" in str(call)]
        assert len(stack_link_calls) >= 1

        # Verify Docker stack with BUILD relationship
        last_stack_call = stack_link_calls[-1]
        query = last_stack_call[0][0]
        assert "Docker" in str(last_stack_call)
        assert "BUILD" in query

    @patch("lib.database.GraphDatabase")
    @patch("lib.database.uuid.uuid4")
    def test_pytest_creates_python_stack_test_relationship(
        self,
        mock_uuid: Mock,
        mock_graph_database: Mock,
        mock_settings: Settings,
    ) -> None:
        """Test that 'pytest' command creates Python stack with TEST relationship."""
        mock_uuid.return_value = "test-uuid"
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        client = Neo4jClient(mock_settings)
        cmd = Command(
            command="pytest tests/",
            description="Run Python tests",
            tags=[],
        )

        client.add_command(cmd)

        # Verify stack linking
        calls = mock_session.run.call_args_list
        stack_link_calls = [call for call in calls if "Stack" in str(call) and "MERGE" in str(call)]
        assert len(stack_link_calls) >= 1

        # Verify Python stack with TEST relationship
        last_stack_call = stack_link_calls[-1]
        query = last_stack_call[0][0]
        assert "Python" in str(last_stack_call)
        assert "TEST" in query

    @patch("lib.database.GraphDatabase")
    @patch("lib.database.uuid.uuid4")
    def test_tag_based_stack_linking(
        self,
        mock_uuid: Mock,
        mock_graph_database: Mock,
        mock_settings: Settings,
    ) -> None:
        """Test that tags can trigger stack linking."""
        mock_uuid.return_value = "test-uuid"
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        client = Neo4jClient(mock_settings)
        cmd = Command(
            command="some custom command",
            description="Custom command",
            tags=["docker"],  # Tag should trigger Docker stack linking
        )

        client.add_command(cmd)

        # Verify stack linking
        calls = mock_session.run.call_args_list
        stack_link_calls = [call for call in calls if "Stack" in str(call) and "MERGE" in str(call)]
        assert len(stack_link_calls) >= 1
        assert "Docker" in str(stack_link_calls[-1])

    @patch("lib.database.GraphDatabase")
    @patch("lib.database.uuid.uuid4")
    def test_git_push_creates_git_stack_deploy_relationship(
        self,
        mock_uuid: Mock,
        mock_graph_database: Mock,
        mock_settings: Settings,
    ) -> None:
        """Test that 'git push' command creates Git stack with DEPLOY relationship."""
        mock_uuid.return_value = "test-uuid"
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        client = Neo4jClient(mock_settings)
        cmd = Command(
            command="git push origin main",
            description="Push changes to remote",
            tags=["git"],
        )

        client.add_command(cmd)

        # Verify stack linking
        calls = mock_session.run.call_args_list
        stack_link_calls = [call for call in calls if "Stack" in str(call) and "MERGE" in str(call)]
        assert len(stack_link_calls) >= 1

        # Should create Git stack with DEPLOY relationship
        last_stack_call = stack_link_calls[-1]
        query = last_stack_call[0][0]
        assert "Git" in str(last_stack_call)
        assert "DEPLOY" in query

    @patch("lib.database.GraphDatabase")
    @patch("lib.database.uuid.uuid4")
    def test_npm_run_build_creates_node_stack_build_relationship(
        self,
        mock_uuid: Mock,
        mock_graph_database: Mock,
        mock_settings: Settings,
    ) -> None:
        """Test that 'npm run build' creates Node stack with BUILD relationship."""
        mock_uuid.return_value = "test-uuid"
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_graph_database.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        client = Neo4jClient(mock_settings)
        cmd = Command(
            command="npm run build",
            description="Build Node.js application",
            tags=[],
        )

        client.add_command(cmd)

        # Verify stack linking
        calls = mock_session.run.call_args_list
        stack_link_calls = [call for call in calls if "Stack" in str(call) and "MERGE" in str(call)]
        assert len(stack_link_calls) >= 1

        # Should create Node stack with BUILD relationship
        last_stack_call = stack_link_calls[-1]
        query = last_stack_call[0][0]
        assert "Node" in str(last_stack_call)
        assert "BUILD" in query


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
                "category": None,
                "os_context": None,
                "project_type": None,
            },
            "tags": [],
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
                "category": None,
                "os_context": None,
                "project_type": None,
            },
            "tags": [],
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
    def test_get_stack_returns_none_when_not_found(
        self, mock_graph_database: Mock, mock_settings: Settings
    ) -> None:
        """Test that get_stack returns None when stack doesn't exist."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()

        mock_result.single.return_value = None  # No stack found
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_driver.session.return_value = mock_session
        mock_graph_database.driver.return_value = mock_driver

        client = Neo4jClient(mock_settings)
        result = client.get_stack("NonexistentStack")

        assert result is None

    @patch("lib.database.GraphDatabase")
    def test_get_commands_by_stack_skips_invalid_timestamps(
        self, mock_graph_database: Mock, mock_settings: Settings
    ) -> None:
        """Test that get_commands_by_stack skips records with invalid timestamps."""
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
                "category": None,
                "os_context": None,
                "project_type": None,
            },
            "tags": [],
        }

        mock_result.__iter__ = Mock(return_value=iter([mock_record]))
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=False)
        mock_driver.session.return_value = mock_session
        mock_graph_database.driver.return_value = mock_driver

        client = Neo4jClient(mock_settings)
        results = client.get_commands_by_stack("Docker")

        # Should return empty list because invalid timestamp was skipped
        assert results == []
