"""Tests for context detection utilities."""

from pathlib import Path
from unittest.mock import Mock, patch

from server.context import (
    detect_os,
    detect_project_type,
    format_context_info,
    get_current_context,
)


class TestDetectOS:
    """Tests for detect_os function."""

    @patch("platform.system")
    def test_detect_macos(self, mock_system: Mock) -> None:
        """Test macOS detection."""
        mock_system.return_value = "Darwin"
        assert detect_os() == "macos"

    @patch("platform.system")
    def test_detect_linux(self, mock_system: Mock) -> None:
        """Test Linux detection."""
        mock_system.return_value = "Linux"
        assert detect_os() == "linux"

    @patch("platform.system")
    def test_detect_windows(self, mock_system: Mock) -> None:
        """Test Windows detection."""
        mock_system.return_value = "Windows"
        assert detect_os() == "windows"

    @patch("platform.system")
    def test_detect_unknown(self, mock_system: Mock) -> None:
        """Test unknown OS detection."""
        mock_system.return_value = "FreeBSD"
        assert detect_os() == "unknown"


class TestDetectProjectType:
    """Tests for detect_project_type function."""

    def test_node_project(self, tmp_path: Path) -> None:
        """Test Node.js project detection."""
        (tmp_path / "package.json").touch()
        assert detect_project_type(str(tmp_path)) == "node"

    def test_rust_project(self, tmp_path: Path) -> None:
        """Test Rust project detection."""
        (tmp_path / "Cargo.toml").touch()
        assert detect_project_type(str(tmp_path)) == "rust"

    def test_go_project(self, tmp_path: Path) -> None:
        """Test Go project detection."""
        (tmp_path / "go.mod").touch()
        assert detect_project_type(str(tmp_path)) == "go"

    def test_python_project_pyproject(self, tmp_path: Path) -> None:
        """Test Python project detection via pyproject.toml."""
        (tmp_path / "pyproject.toml").touch()
        assert detect_project_type(str(tmp_path)) == "python"

    def test_python_project_setup(self, tmp_path: Path) -> None:
        """Test Python project detection via setup.py."""
        (tmp_path / "setup.py").touch()
        assert detect_project_type(str(tmp_path)) == "python"

    def test_java_project_pom(self, tmp_path: Path) -> None:
        """Test Java project detection via pom.xml."""
        (tmp_path / "pom.xml").touch()
        assert detect_project_type(str(tmp_path)) == "java"

    def test_java_project_gradle(self, tmp_path: Path) -> None:
        """Test Java project detection via build.gradle."""
        (tmp_path / "build.gradle").touch()
        assert detect_project_type(str(tmp_path)) == "java"

    def test_ruby_project(self, tmp_path: Path) -> None:
        """Test Ruby project detection."""
        (tmp_path / "Gemfile").touch()
        assert detect_project_type(str(tmp_path)) == "ruby"

    def test_php_project(self, tmp_path: Path) -> None:
        """Test PHP project detection."""
        (tmp_path / "composer.json").touch()
        assert detect_project_type(str(tmp_path)) == "php"

    def test_dotnet_project_csproj(self, tmp_path: Path) -> None:
        """Test .NET project detection via .csproj."""
        (tmp_path / ".csproj").touch()
        assert detect_project_type(str(tmp_path)) == "dotnet"

    def test_dotnet_project_sln(self, tmp_path: Path) -> None:
        """Test .NET project detection via .sln."""
        (tmp_path / ".sln").touch()
        assert detect_project_type(str(tmp_path)) == "dotnet"

    def test_elixir_project(self, tmp_path: Path) -> None:
        """Test Elixir project detection."""
        (tmp_path / "mix.exs").touch()
        assert detect_project_type(str(tmp_path)) == "elixir"

    def test_makefile_project(self, tmp_path: Path) -> None:
        """Test Makefile project detection."""
        (tmp_path / "Makefile").touch()
        assert detect_project_type(str(tmp_path)) == "makefile"

    def test_no_project_detected(self, tmp_path: Path) -> None:
        """Test no project type detected."""
        assert detect_project_type(str(tmp_path)) is None

    def test_priority_node_over_makefile(self, tmp_path: Path) -> None:
        """Test that Node.js is detected before Makefile when both exist."""
        (tmp_path / "package.json").touch()
        (tmp_path / "Makefile").touch()
        assert detect_project_type(str(tmp_path)) == "node"

    @patch("server.context.Path.cwd")
    def test_default_directory(self, mock_cwd: Mock, tmp_path: Path) -> None:
        """Test using current working directory when no directory provided."""
        mock_cwd.return_value = tmp_path
        (tmp_path / "go.mod").touch()
        assert detect_project_type() == "go"


class TestGetCurrentContext:
    """Tests for get_current_context function."""

    @patch("server.context.detect_project_type")
    @patch("server.context.detect_os")
    @patch("server.context.Path.cwd")
    def test_get_current_context(
        self, mock_cwd: Mock, mock_detect_os: Mock, mock_detect_project_type: Mock
    ) -> None:
        """Test getting current context."""
        mock_cwd.return_value = Path("/home/user/project")
        mock_detect_os.return_value = "linux"
        mock_detect_project_type.return_value = "python"

        context = get_current_context()

        assert context == {"os": "linux", "project_type": "python", "cwd": "/home/user/project"}


class TestFormatContextInfo:
    """Tests for format_context_info function."""

    def test_format_complete_context(self) -> None:
        """Test formatting complete context information."""
        context = {"os": "linux", "project_type": "python", "cwd": "/home/user/project"}
        result = format_context_info(context)
        assert "OS: linux" in result
        assert "Project: python" in result
        assert "Directory: /home/user/project" in result

    def test_format_partial_context(self) -> None:
        """Test formatting partial context information."""
        context = {"os": "macos", "cwd": "/Users/user/project"}
        result = format_context_info(context)
        assert "OS: macos" in result
        assert "Directory: /Users/user/project" in result
        assert "Project" not in result

    def test_format_empty_context(self) -> None:
        """Test formatting empty context."""
        context = {}
        result = format_context_info(context)
        assert result == "No context detected"

    def test_format_none_values(self) -> None:
        """Test formatting context with None values."""
        context = {"os": None, "project_type": None, "cwd": None}
        result = format_context_info(context)
        assert result == "No context detected"
