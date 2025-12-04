"""Tests for shell integration functionality."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from server.cli import app


class TestShellCapture:
    """Test shell integration command capture."""

    @patch("server.cli.MemoryBox")
    def test_capture_command_basic(self, mock_memory_box: MagicMock) -> None:
        """Test capturing a basic command from shell."""
        # Setup
        mock_mb_instance = MagicMock()
        mock_memory_box.return_value = mock_mb_instance
        mock_mb_instance.add_command.return_value = "cmd-123"

        # Execute - simulate shell calling: memory-box capture "ls -la" 0 "/home/user"
        runner = CliRunner()
        result = runner.invoke(
            app, ["capture", "ls -la", "--exit-code", "0", "--cwd", "/home/user"]
        )

        # Verify
        assert result.exit_code == 0
        mock_mb_instance.add_command.assert_called_once()
        call_args = mock_mb_instance.add_command.call_args
        assert call_args[0][0] == "ls -la"  # command
        assert call_args[1]["context"] == "/home/user"

    @patch("server.cli.MemoryBox")
    def test_capture_command_with_failure(self, mock_memory_box: MagicMock) -> None:
        """Test capturing a failed command (non-zero exit code)."""
        mock_mb_instance = MagicMock()
        mock_memory_box.return_value = mock_mb_instance
        mock_mb_instance.add_command.return_value = "cmd-124"

        runner = CliRunner()
        result = runner.invoke(
            app, ["capture", "git push", "--exit-code", "1", "--cwd", "/home/user/project"]
        )

        # Should still capture but with category 'failed'
        assert result.exit_code == 0
        call_args = mock_mb_instance.add_command.call_args
        assert call_args[0][0] == "git push"
        assert call_args[1].get("category") == "failed"

    @patch("server.cli.MemoryBox")
    def test_capture_command_success_only_mode(self, mock_memory_box: MagicMock) -> None:
        """Test success-only mode skips failed commands."""
        mock_mb_instance = MagicMock()
        mock_memory_box.return_value = mock_mb_instance

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "capture",
                "git push",
                "--exit-code",
                "1",
                "--cwd",
                "/home/user",
                "--success-only",
            ],
        )

        # Should skip without error
        assert result.exit_code == 0
        mock_mb_instance.add_command.assert_not_called()

    @patch("server.cli.MemoryBox")
    def test_capture_empty_command_is_skipped(self, mock_memory_box: MagicMock) -> None:
        """Test that empty commands are not captured."""
        mock_mb_instance = MagicMock()
        mock_memory_box.return_value = mock_mb_instance

        runner = CliRunner()
        result = runner.invoke(app, ["capture", "", "--exit-code", "0", "--cwd", "/home/user"])

        # Should skip without error
        assert result.exit_code == 0
        mock_mb_instance.add_command.assert_not_called()

    @patch("server.cli.MemoryBox")
    def test_capture_command_silent_mode(self, mock_memory_box: MagicMock) -> None:
        """Test capture command runs silently (no output)."""
        mock_mb_instance = MagicMock()
        mock_memory_box.return_value = mock_mb_instance
        mock_mb_instance.add_command.return_value = "cmd-125"

        runner = CliRunner()
        result = runner.invoke(
            app, ["capture", "echo test", "--exit-code", "0", "--cwd", "/home/user"]
        )

        # Should have no output (silent)
        assert result.exit_code == 0
        assert result.stdout.strip() == ""
