"""Tests for MCP server module."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from lib.models import CommandWithMetadata

# Import the functions - they're wrapped by FastMCP decorator, so we access the underlying function
from server import server
from server.server import main


@pytest.fixture
def mock_db() -> Mock:
    """Create a mock database client."""
    return Mock()


@pytest.fixture
def sample_command() -> CommandWithMetadata:
    """Create a sample command with metadata."""
    return CommandWithMetadata(
        id="test-123",
        command="git status",
        description="Show working tree status",
        tags=["git"],
        os="linux",
        project_type="python",
        context="Use to check git status",
        category="git",
        created_at=datetime.now(tz=UTC),
        use_count=5,
    )


class TestAddCommand:
    """Tests for add_command function."""

    @patch("server.server.get_memory_box")
    @patch("server.server.get_current_context")
    def test_add_command_minimal(
        self, mock_context: Mock, mock_get_db: Mock, mock_db: Mock
    ) -> None:
        """Test adding a command with minimal parameters."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": "python"}
        mock_db.add_command.return_value = "test-id-123"

        # Access the underlying function from the FunctionTool wrapper
        result = server.add_command.fn(command="git status", description="Show status")

        assert "test-id-123" in result
        assert "✓" in result
        mock_db.add_command.assert_called_once()

    @patch("server.server.get_memory_box")
    @patch("server.server.get_current_context")
    def test_add_command_with_tags(
        self, mock_context: Mock, mock_get_db: Mock, mock_db: Mock
    ) -> None:
        """Test adding a command with tags."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": "python"}
        mock_db.add_command.return_value = "test-id-456"

        result = server.add_command.fn(
            command="docker ps", description="List containers", tags=["docker", "containers"]
        )

        assert "test-id-456" in result
        cmd = mock_db.add_command.call_args[0][0]
        assert cmd.tags == ["docker", "containers"]

    @patch("server.server.get_memory_box")
    def test_add_command_no_auto_context(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test adding a command without auto-context detection."""
        mock_get_db.return_value = mock_db
        mock_db.add_command.return_value = "test-id-789"

        result = server.add_command.fn(
            command="ls -la", description="List files", auto_detect_context=False
        )

        assert "test-id-789" in result

    @patch("server.server.get_memory_box")
    @patch("server.server.get_current_context")
    def test_add_command_with_all_fields(
        self, mock_context: Mock, mock_get_db: Mock, mock_db: Mock
    ) -> None:
        """Test adding a command with all fields."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": "python"}
        mock_db.add_command.return_value = "full-cmd-id"

        result = server.add_command.fn(
            command="kubectl get pods",
            description="List pods",
            tags=["kubernetes", "k8s"],
            os="linux",
            project_type="kubernetes",
            context="Use in k8s cluster",
            category="kubernetes",
        )

        assert "full-cmd-id" in result


class TestSearchCommands:
    """Tests for search_commands function."""

    @patch("server.server.get_memory_box")
    def test_search_with_query(
        self, mock_get_db: Mock, mock_db: Mock, sample_command: CommandWithMetadata
    ) -> None:
        """Test searching with a query returns structured data."""
        mock_get_db.return_value = mock_db
        mock_db.search_commands.return_value = [sample_command]

        result = server.search_commands.fn(query="git")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["command"] == "git status"
        assert result[0]["id"] == "test-123"

    @patch("server.server.get_memory_box")
    def test_search_no_results(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test searching with no results returns empty list."""
        mock_get_db.return_value = mock_db
        mock_db.search_commands.return_value = []

        result = server.search_commands.fn(query="nonexistent")

        assert isinstance(result, list)
        assert len(result) == 0

    @patch("server.server.get_memory_box")
    @patch("server.server.get_current_context")
    def test_search_with_current_context(
        self,
        mock_context: Mock,
        mock_get_db: Mock,
        mock_db: Mock,
        sample_command: CommandWithMetadata,
    ) -> None:
        """Test searching with current context returns structured data."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": "python"}
        mock_db.search_commands.return_value = [sample_command]

        result = server.search_commands.fn(use_current_context=True)

        assert isinstance(result, list)
        assert len(result) == 1

    @patch("server.server.get_memory_box")
    def test_search_with_filters(
        self, mock_get_db: Mock, mock_db: Mock, sample_command: CommandWithMetadata
    ) -> None:
        """Test searching with multiple filters returns structured data."""
        mock_get_db.return_value = mock_db
        mock_db.search_commands.return_value = [sample_command]

        result = server.search_commands.fn(
            query="git", os="linux", project_type="python", category="git", tags=["git"], limit=5
        )

        assert isinstance(result, list)
        assert len(result) == 1
        mock_db.search_commands.assert_called_once_with(
            query="git", os="linux", project_type="python", category="git", tags=["git"], limit=5
        )


class TestGetCommandById:
    """Tests for get_command_by_id function."""

    @patch("server.server.get_memory_box")
    def test_get_existing_command(
        self, mock_get_db: Mock, mock_db: Mock, sample_command: CommandWithMetadata
    ) -> None:
        """Test getting an existing command returns formatted details."""
        mock_get_db.return_value = mock_db
        mock_db.get_command.return_value = sample_command

        result = server.get_command_by_id.fn("test-123")

        assert "git status" in result
        assert "test-123" in result
        assert "Executed" in result or "5" in result

    @patch("server.server.get_memory_box")
    def test_get_nonexistent_command(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test getting a nonexistent command."""
        mock_get_db.return_value = mock_db
        mock_db.get_command.return_value = None

        result = server.get_command_by_id.fn("nonexistent")

        assert "not found" in result


class TestDeleteCommand:
    """Tests for delete_command function."""

    @patch("server.server.get_memory_box")
    def test_delete_existing_command(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test deleting an existing command."""
        mock_get_db.return_value = mock_db
        mock_db.delete_command.return_value = True

        result = server.delete_command.fn("test-123")

        assert "✓" in result
        assert "deleted successfully" in result
        mock_db.delete_command.assert_called_once_with("test-123")

    @patch("server.server.get_memory_box")
    def test_delete_nonexistent_command(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test deleting a nonexistent command."""
        mock_get_db.return_value = mock_db
        mock_db.delete_command.return_value = False

        result = server.delete_command.fn("nonexistent")

        assert "✗" in result
        assert "not found" in result


class TestListTags:
    """Tests for list_tags function."""

    @patch("server.server.get_memory_box")
    def test_list_tags_with_results(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test listing tags with results."""
        mock_get_db.return_value = mock_db
        mock_db.get_all_tags.return_value = ["git", "docker", "kubernetes"]

        result = server.list_tags.fn()

        assert "Tags (3)" in result
        assert "git" in result
        assert "docker" in result
        assert "kubernetes" in result

    @patch("server.server.get_memory_box")
    def test_list_tags_empty(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test listing tags when there are none."""
        mock_get_db.return_value = mock_db
        mock_db.get_all_tags.return_value = []

        result = server.list_tags.fn()

        assert "No tags found" in result


class TestListCategories:
    """Tests for list_categories function."""

    @patch("server.server.get_memory_box")
    def test_list_categories_with_results(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test listing categories with results."""
        mock_get_db.return_value = mock_db
        mock_db.get_all_categories.return_value = ["git", "docker"]

        result = server.list_categories.fn()

        assert "Categories (2)" in result
        assert "git" in result
        assert "docker" in result

    @patch("server.server.get_memory_box")
    def test_list_categories_empty(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test listing categories when there are none."""
        mock_get_db.return_value = mock_db
        mock_db.get_all_categories.return_value = []

        result = server.list_categories.fn()

        assert "No categories found" in result


class TestGetContextSuggestions:
    """Tests for get_context_suggestions function."""

    @patch("server.server.get_memory_box")
    @patch("server.server.get_current_context")
    def test_suggestions_with_results(
        self,
        mock_context: Mock,
        mock_get_db: Mock,
        mock_db: Mock,
        sample_command: CommandWithMetadata,
    ) -> None:
        """Test getting suggestions with results."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": "python"}
        mock_db.search_commands.return_value = [sample_command]

        result = server.get_context_suggestions.fn()

        assert "Commands for your context" in result
        assert "linux" in result
        assert "python" in result
        assert "git status" in result

    @patch("server.server.get_memory_box")
    @patch("server.server.get_current_context")
    def test_suggestions_no_results(
        self, mock_context: Mock, mock_get_db: Mock, mock_db: Mock
    ) -> None:
        """Test getting suggestions with no results."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": None}
        mock_db.search_commands.return_value = []

        result = server.get_context_suggestions.fn()

        assert "No commands found" in result
        assert "linux" in result

    @patch("server.server.mcp.run")
    def test_main_function(self, mock_run: Mock) -> None:
        """Test that main() calls mcp.run()."""
        main()

        mock_run.assert_called_once()
