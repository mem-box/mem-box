"""Tests for CLI module."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from lib.models import CommandWithMetadata, Stack
from server.cli import app

runner = CliRunner()


@pytest.fixture
def mock_db() -> Mock:
    """Create a mock database client."""
    db = Mock()
    db.close = Mock()
    return db


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
    """Tests for add command."""

    @patch("server.cli.get_memory_box")
    @patch("server.cli.get_current_context")
    def test_add_command_minimal(
        self, mock_context: Mock, mock_get_db: Mock, mock_db: Mock
    ) -> None:
        """Test adding a command with minimal arguments."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": "python"}
        mock_db.add_command.return_value = "test-id-123"

        result = runner.invoke(app, ["add", "git status", "--desc", "Show status"])

        assert result.exit_code == 0
        assert "Command added successfully" in result.stdout
        assert "test-id-123" in result.stdout
        mock_db.add_command.assert_called_once()
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    @patch("server.cli.get_current_context")
    def test_add_command_with_tags(
        self, mock_context: Mock, mock_get_db: Mock, mock_db: Mock
    ) -> None:
        """Test adding a command with tags."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": "python"}
        mock_db.add_command.return_value = "test-id-456"

        result = runner.invoke(
            app,
            [
                "add",
                "docker ps",
                "--desc",
                "List containers",
                "--tag",
                "docker",
                "--tag",
                "containers",
            ],
        )

        assert result.exit_code == 0
        mock_db.add_command.assert_called_once()
        cmd = mock_db.add_command.call_args[0][0]
        assert cmd.tags == ["docker", "containers"]

    @patch("server.cli.get_memory_box")
    def test_add_command_no_auto_context(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test adding a command without auto-context detection."""
        mock_get_db.return_value = mock_db
        mock_db.add_command.return_value = "test-id-789"

        result = runner.invoke(app, ["add", "ls -la", "--desc", "List files", "--no-auto-context"])

        assert result.exit_code == 0


class TestSearchCommand:
    """Tests for search command."""

    @patch("server.cli.get_memory_box")
    def test_search_with_query(
        self, mock_get_db: Mock, mock_db: Mock, sample_command: CommandWithMetadata
    ) -> None:
        """Test searching with a query."""
        mock_get_db.return_value = mock_db
        mock_db.search_commands.return_value = [sample_command]

        result = runner.invoke(app, ["search", "git"])

        assert result.exit_code == 0
        assert "Found 1 command(s)" in result.stdout
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    def test_search_no_results(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test searching with no results."""
        mock_get_db.return_value = mock_db
        mock_db.search_commands.return_value = []

        result = runner.invoke(app, ["search", "nonexistent"])

        assert result.exit_code == 0
        assert "No commands found" in result.stdout

    @patch("server.cli.get_memory_box")
    @patch("server.cli.get_current_context")
    def test_search_with_current_context(
        self,
        mock_context: Mock,
        mock_get_db: Mock,
        mock_db: Mock,
        sample_command: CommandWithMetadata,
    ) -> None:
        """Test searching with current context."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": "python"}
        mock_db.search_commands.return_value = [sample_command]

        result = runner.invoke(app, ["search", "--current"])

        assert result.exit_code == 0


class TestGetCommand:
    """Tests for get command."""

    @patch("server.cli.get_memory_box")
    def test_get_existing_command(
        self, mock_get_db: Mock, mock_db: Mock, sample_command: CommandWithMetadata
    ) -> None:
        """Test getting an existing command."""
        mock_get_db.return_value = mock_db
        mock_db.get_command.return_value = sample_command

        result = runner.invoke(app, ["get", "test-123"])

        assert result.exit_code == 0
        assert "git status" in result.stdout
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    def test_get_nonexistent_command(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test getting a nonexistent command."""
        mock_get_db.return_value = mock_db
        mock_db.get_command.return_value = None

        result = runner.invoke(app, ["get", "nonexistent"])

        assert result.exit_code == 0
        assert "not found" in result.stdout


class TestDeleteCommand:
    """Tests for delete command."""

    @patch("server.cli.get_memory_box")
    def test_delete_existing_command(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test deleting an existing command."""
        mock_get_db.return_value = mock_db
        mock_db.delete_command.return_value = True

        result = runner.invoke(app, ["delete", "test-123"], input="y\n")

        assert result.exit_code == 0
        assert "deleted" in result.stdout
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    def test_delete_cancelled(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test cancelling a delete operation."""
        mock_get_db.return_value = mock_db

        result = runner.invoke(app, ["delete", "test-123"], input="n\n")

        assert result.exit_code == 0
        assert "cancel" in result.stdout.lower()
        mock_db.delete_command.assert_not_called()


class TestTagsCommand:
    """Tests for tags command."""

    @patch("server.cli.get_memory_box")
    def test_list_tags(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test listing all tags."""
        mock_get_db.return_value = mock_db
        mock_db.get_all_tags.return_value = ["git", "docker", "kubernetes"]

        result = runner.invoke(app, ["tags"])

        assert result.exit_code == 0
        assert "git" in result.stdout
        assert "docker" in result.stdout
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    def test_list_tags_empty(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test listing tags when there are none."""
        mock_get_db.return_value = mock_db
        mock_db.get_all_tags.return_value = []

        result = runner.invoke(app, ["tags"])

        assert result.exit_code == 0
        assert "No tags found" in result.stdout


class TestCategoriesCommand:
    """Tests for categories command."""

    @patch("server.cli.get_memory_box")
    def test_list_categories(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test listing all categories."""
        mock_get_db.return_value = mock_db
        mock_db.get_all_categories.return_value = ["git", "docker"]

        result = runner.invoke(app, ["categories"])

        assert result.exit_code == 0
        assert "git" in result.stdout
        mock_db.close.assert_called_once()


class TestContextCommand:
    """Tests for context command."""

    @patch("server.cli.get_current_context")
    def test_show_context(self, mock_context: Mock) -> None:
        """Test showing current context."""
        mock_context.return_value = {
            "os": "linux",
            "project_type": "python",
            "cwd": "/home/user/project",
        }

        result = runner.invoke(app, ["context"])

        assert result.exit_code == 0
        assert "linux" in result.stdout
        assert "python" in result.stdout


class TestSuggestCommand:
    """Tests for suggest command."""

    @patch("server.cli.get_memory_box")
    @patch("server.cli.get_current_context")
    def test_suggest_with_results(
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

        result = runner.invoke(app, ["suggest"])

        assert result.exit_code == 0
        assert "git status" in result.stdout
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    @patch("server.cli.get_current_context")
    def test_suggest_no_results(self, mock_context: Mock, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test getting suggestions with no results."""
        mock_get_db.return_value = mock_db
        mock_context.return_value = {"os": "linux", "project_type": "python"}
        mock_db.search_commands.return_value = []

        result = runner.invoke(app, ["suggest"])

        assert result.exit_code == 0
        assert "No commands found" in result.stdout


class TestStackCommands:
    """Tests for stack-related commands."""

    @patch("server.cli.get_memory_box")
    def test_list_stacks_with_results(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test listing stacks with results."""

        mock_get_db.return_value = mock_db
        mock_stacks = [
            Stack(name="Docker", type="tool", description="Container platform"),
            Stack(name="Python", type="language", description="Programming language"),
            Stack(name="Git", type="tool", description="Version control"),
        ]
        mock_db.list_stacks.return_value = mock_stacks

        result = runner.invoke(app, ["list-stacks"])

        assert result.exit_code == 0
        assert "Docker" in result.stdout
        assert "Python" in result.stdout
        assert "Git" in result.stdout
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    def test_list_stacks_empty(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test listing stacks with no results."""
        mock_get_db.return_value = mock_db
        mock_db.list_stacks.return_value = []

        result = runner.invoke(app, ["list-stacks"])

        assert result.exit_code == 0
        assert "No stacks found" in result.stdout
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    def test_get_stack_commands_with_results(
        self, mock_get_db: Mock, mock_db: Mock, sample_command: CommandWithMetadata
    ) -> None:
        """Test getting commands for a stack with results."""
        mock_get_db.return_value = mock_db
        mock_db.get_commands_by_stack.return_value = [sample_command]

        result = runner.invoke(app, ["stack", "Docker"])

        assert result.exit_code == 0
        assert "Docker" in result.stdout
        assert "git status" in result.stdout
        mock_db.get_commands_by_stack.assert_called_once_with("Docker", None)
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    def test_get_stack_commands_with_relationship_type(
        self, mock_get_db: Mock, mock_db: Mock, sample_command: CommandWithMetadata
    ) -> None:
        """Test getting commands for a stack filtered by relationship type."""
        mock_get_db.return_value = mock_db
        mock_db.get_commands_by_stack.return_value = [sample_command]

        result = runner.invoke(app, ["stack", "Docker", "--type", "BUILD"])

        assert result.exit_code == 0
        assert "Docker" in result.stdout
        assert "BUILD" in result.stdout
        mock_db.get_commands_by_stack.assert_called_once_with("Docker", "BUILD")
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    def test_get_stack_commands_no_results(self, mock_get_db: Mock, mock_db: Mock) -> None:
        """Test getting commands for a stack with no results."""
        mock_get_db.return_value = mock_db
        mock_db.get_commands_by_stack.return_value = []

        result = runner.invoke(app, ["stack", "Docker"])

        assert result.exit_code == 0
        assert "No commands found for Docker" in result.stdout
        mock_db.close.assert_called_once()


class TestEdgeCases:
    """Test edge cases."""

    @patch("server.cli.get_memory_box")
    def test_delete_command_not_found(self, mock_get_db: Mock) -> None:
        """Test deleting a command that doesn't exist."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_db.delete_command.return_value = False  # Command not found

        result = runner.invoke(app, ["delete", "nonexistent-id"], input="y\n")

        assert result.exit_code == 0
        assert "not found" in result.stdout.lower()
        mock_db.close.assert_called_once()

    @patch("server.cli.get_memory_box")
    def test_categories_command_empty_list(self, mock_get_db: Mock) -> None:
        """Test categories command when no categories exist."""
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        mock_db.get_all_categories.return_value = []

        result = runner.invoke(app, ["categories"])

        assert result.exit_code == 0
        assert "No categories found" in result.stdout
        mock_db.close.assert_called_once()
