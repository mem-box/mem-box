"""Unit tests for the JSON bridge."""

import contextlib
import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from lib.models import Command
from server.bridge import handle_request, main, write_response


@pytest.fixture
def mock_memory_box():
    """Create a mock MemoryBox instance."""
    return MagicMock()


class TestHandleRequest:
    """Tests for handle_request function."""

    def test_ping(self, mock_memory_box):
        """Test ping method returns pong."""
        request = {"method": "ping", "params": {}}
        result = handle_request(mock_memory_box, request)
        assert result["result"] == "pong"
        assert result["error"] is None

    def test_add_command(self, mock_memory_box):
        """Test add_command method."""
        mock_memory_box.add_command.return_value = "test-id-123"

        request = {
            "method": "add_command",
            "params": {
                "command": "docker ps",
                "description": "List containers",
                "tags": ["docker"],
            },
        }
        result = handle_request(mock_memory_box, request)

        assert result["result"] == "test-id-123"
        assert result["error"] is None
        mock_memory_box.add_command.assert_called_once_with(
            command="docker ps",
            description="List containers",
            tags=["docker"],
        )

    def test_search_commands(self, mock_memory_box):
        """Test search_commands method."""
        mock_command = Command(
            id="test-id",
            command="docker ps",
            description="List containers",
        )
        mock_memory_box.search_commands.return_value = [mock_command]

        request = {"method": "search_commands", "params": {"query": "docker"}}
        result = handle_request(mock_memory_box, request)

        assert len(result["result"]) == 1
        assert result["result"][0]["command"] == "docker ps"
        assert result["error"] is None
        mock_memory_box.search_commands.assert_called_once_with(query="docker")

    def test_get_command(self, mock_memory_box):
        """Test get_command method."""
        mock_command = Command(
            id="test-id",
            command="docker ps",
            description="List containers",
        )
        mock_memory_box.get_command.return_value = mock_command

        request = {"method": "get_command", "params": {"command_id": "test-id"}}
        result = handle_request(mock_memory_box, request)

        assert result["result"]["command"] == "docker ps"
        assert result["error"] is None
        mock_memory_box.get_command.assert_called_once_with(command_id="test-id")

    def test_get_command_not_found(self, mock_memory_box):
        """Test get_command when command not found."""
        mock_memory_box.get_command.return_value = None

        request = {"method": "get_command", "params": {"command_id": "missing"}}
        result = handle_request(mock_memory_box, request)

        assert result["result"] is None
        assert result["error"] is None

    def test_list_commands(self, mock_memory_box):
        """Test list_commands method."""
        mock_command = Command(
            id="test-id",
            command="docker ps",
            description="List containers",
        )
        mock_memory_box.list_commands.return_value = [mock_command]

        request = {
            "method": "list_commands",
            "params": {"limit": 10, "tags": ["docker"]},
        }
        result = handle_request(mock_memory_box, request)

        assert len(result["result"]) == 1
        assert result["result"][0]["command"] == "docker ps"
        assert result["error"] is None
        mock_memory_box.list_commands.assert_called_once_with(limit=10, tags=["docker"])

    def test_delete_command(self, mock_memory_box):
        """Test delete_command method."""
        mock_memory_box.delete_command.return_value = True

        request = {"method": "delete_command", "params": {"command_id": "test-id"}}
        result = handle_request(mock_memory_box, request)

        assert result["result"] is True
        assert result["error"] is None
        mock_memory_box.delete_command.assert_called_once_with(command_id="test-id")

    def test_get_all_tags(self, mock_memory_box):
        """Test get_all_tags method."""
        mock_memory_box.get_all_tags.return_value = ["docker", "git"]

        request = {"method": "get_all_tags", "params": {}}
        result = handle_request(mock_memory_box, request)

        assert result["result"] == ["docker", "git"]
        assert result["error"] is None
        mock_memory_box.get_all_tags.assert_called_once()

    def test_get_all_categories(self, mock_memory_box):
        """Test get_all_categories method."""
        mock_memory_box.get_all_categories.return_value = ["dev", "ops"]

        request = {"method": "get_all_categories", "params": {}}
        result = handle_request(mock_memory_box, request)

        assert result["result"] == ["dev", "ops"]
        assert result["error"] is None
        mock_memory_box.get_all_categories.assert_called_once()

    def test_unknown_method(self, mock_memory_box):
        """Test unknown method returns error."""
        request = {"method": "invalid_method", "params": {}}
        result = handle_request(mock_memory_box, request)

        assert result["result"] is None
        assert "Unknown method" in result["error"]


class TestWriteResponse:
    """Tests for write_response function."""

    @patch("sys.stdout", new_callable=StringIO)
    def test_write_success_response(self, mock_stdout):
        """Test writing success response."""
        write_response({"result": "test-result", "error": None})

        output = mock_stdout.getvalue()
        data = json.loads(output.strip())

        assert data["result"] == "test-result"
        assert data["error"] is None

    @patch("sys.stdout", new_callable=StringIO)
    def test_write_error_response(self, mock_stdout):
        """Test writing error response."""
        write_response({"result": None, "error": "Something went wrong"})

        output = mock_stdout.getvalue()
        data = json.loads(output.strip())

        assert data["result"] is None
        assert data["error"] == "Something went wrong"


class TestMain:
    """Tests for main function."""

    @patch("sys.argv", ["bridge.py"])
    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch("server.bridge.MemoryBox")
    def test_main_ping(self, mock_mb_class, mock_stdout, mock_stdin):
        """Test main function with ping request."""
        mock_mb = MagicMock()
        mock_mb_class.return_value = mock_mb

        # Simulate single request
        mock_stdin.write('{"method": "ping", "params": {}}\n')
        mock_stdin.seek(0)

        # Run main (will exit on EOF)
        with contextlib.suppress(StopIteration):
            main()

        # Check output
        output = mock_stdout.getvalue()
        lines = [line for line in output.split("\n") if line.strip()]

        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["result"] == "pong"
        assert data["error"] is None
        mock_mb.close.assert_called_once()

    @patch("sys.argv", ["bridge.py"])
    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch("server.bridge.MemoryBox")
    def test_main_multiple_requests(self, mock_mb_class, mock_stdout, mock_stdin):
        """Test main function with multiple requests."""
        mock_mb = MagicMock()
        mock_mb_class.return_value = mock_mb
        mock_mb.get_all_tags.return_value = ["tag1", "tag2"]

        # Simulate multiple requests
        mock_stdin.write('{"method": "ping", "params": {}}\n')
        mock_stdin.write('{"method": "get_all_tags", "params": {}}\n')
        mock_stdin.seek(0)

        # Run main
        with contextlib.suppress(StopIteration):
            main()

        # Check output
        output = mock_stdout.getvalue()
        lines = [line for line in output.split("\n") if line.strip()]

        assert len(lines) == 2

        # First response: ping
        data1 = json.loads(lines[0])
        assert data1["result"] == "pong"

        # Second response: get_all_tags
        data2 = json.loads(lines[1])
        assert data2["result"] == ["tag1", "tag2"]

    @patch("sys.argv", ["bridge.py"])
    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch("server.bridge.MemoryBox")
    def test_main_invalid_json(self, mock_mb_class, mock_stdout, mock_stdin):
        """Test main function with invalid JSON."""
        mock_mb = MagicMock()
        mock_mb_class.return_value = mock_mb

        # Simulate invalid JSON
        mock_stdin.write("not valid json\n")
        mock_stdin.seek(0)

        # Run main
        with contextlib.suppress(StopIteration):
            main()

        # Check error response
        output = mock_stdout.getvalue()
        lines = [line for line in output.split("\n") if line.strip()]

        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["result"] is None
        assert "Invalid JSON" in data["error"]

    @patch("sys.argv", ["bridge.py"])
    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch("server.bridge.MemoryBox")
    def test_main_method_error(self, mock_mb_class, mock_stdout, mock_stdin):
        """Test main function when method raises error."""
        mock_mb = MagicMock()
        mock_mb_class.return_value = mock_mb
        mock_mb.search_commands.side_effect = RuntimeError("Database error")

        # Simulate request that will fail
        mock_stdin.write('{"method": "search_commands", "params": {"query": "test"}}\n')
        mock_stdin.seek(0)

        # Run main
        with contextlib.suppress(StopIteration):
            main()

        # Check error response
        output = mock_stdout.getvalue()
        lines = [line for line in output.split("\n") if line.strip()]

        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["result"] is None
        assert "Database error" in data["error"]

    @patch("sys.argv", ["bridge.py"])
    @patch("sys.stdin", new_callable=StringIO)
    @patch("sys.stdout", new_callable=StringIO)
    @patch("server.bridge.MemoryBox")
    def test_main_empty_lines(self, mock_mb_class, mock_stdout, mock_stdin):
        """Test main function handles empty lines gracefully."""
        mock_mb = MagicMock()
        mock_mb_class.return_value = mock_mb

        # Simulate input with empty lines
        mock_stdin.write("\n")
        mock_stdin.write("  \n")
        mock_stdin.write('{"method": "ping", "params": {}}\n')
        mock_stdin.write("\n")
        mock_stdin.seek(0)

        # Run main
        with contextlib.suppress(StopIteration):
            main()

        # Should only get one response (empty lines ignored)
        output = mock_stdout.getvalue()
        lines = [line for line in output.split("\n") if line.strip()]

        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["result"] == "pong"

    @patch("sys.argv", ["bridge.py"])
    @patch("sys.stdin")
    @patch("sys.stdout", new_callable=StringIO)
    @patch("server.bridge.sys.stderr")
    @patch("server.bridge.MemoryBox")
    def test_main_keyboard_interrupt(self, mock_mb_class, mock_stderr, mock_stdout, mock_stdin):
        """Test main function handles KeyboardInterrupt gracefully."""
        mock_mb = MagicMock()
        mock_mb_class.return_value = mock_mb

        # Create a custom stdin that yields one line then raises KeyboardInterrupt
        def stdin_generator(self):
            yield '{"method": "ping", "params": {}}\n'
            raise KeyboardInterrupt

        mock_stdin.__iter__ = stdin_generator

        # Should not raise exception, just exit cleanly
        main()

        # Memory box should be closed
        mock_mb.close.assert_called_once()

        # Should have processed the ping request before interrupt
        output = mock_stdout.getvalue()
        lines = [line for line in output.split("\n") if line.strip()]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["result"] == "pong"

        # Should have written graceful shutdown message to stderr
        mock_stderr.write.assert_called()
        stderr_calls = "".join(str(call) for call in mock_stderr.write.call_args_list)
        assert "interrupt signal" in stderr_calls.lower()
        assert "shutting down gracefully" in stderr_calls.lower()
