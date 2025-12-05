"""Tests for data models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from lib.models import Command, CommandWithMetadata


class TestCommand:
    """Tests for Command model."""

    def test_command_creation_minimal(self) -> None:
        """Test creating a command with minimal required fields."""
        cmd = Command(command="git status", description="Show the working tree status")
        assert cmd.command == "git status"
        assert cmd.description == "Show the working tree status"
        assert cmd.tags == []
        assert cmd.os is None
        assert cmd.project_type is None
        assert cmd.context is None
        assert cmd.category is None
        assert cmd.status is None

    def test_command_creation_complete(self) -> None:
        """Test creating a command with all fields."""
        cmd = Command(
            command="poetry install",
            description="Install project dependencies",
            tags=["python", "dependencies"],
            os="linux",
            project_type="python",
            context="Use when setting up a new Python project",
            category="package-management",
            status="success",
        )
        assert cmd.command == "poetry install"
        assert cmd.description == "Install project dependencies"
        assert cmd.tags == ["python", "dependencies"]
        assert cmd.os == "linux"
        assert cmd.project_type == "python"
        assert cmd.context == "Use when setting up a new Python project"
        assert cmd.category == "package-management"
        assert cmd.status == "success"

    def test_command_missing_required_fields(self) -> None:
        """Test that creating a command without required fields raises error."""
        with pytest.raises(ValidationError):
            Command()  # type: ignore[call-arg]

    def test_command_missing_command_field(self) -> None:
        """Test that creating a command without command field raises error."""
        with pytest.raises(ValidationError):
            Command(description="Test description")  # type: ignore[call-arg]

    def test_command_missing_description_field(self) -> None:
        """Test that creating a command without description field raises error."""
        with pytest.raises(ValidationError):
            Command(command="test command")  # type: ignore[call-arg]

    def test_command_serialization(self) -> None:
        """Test that command can be serialized to dict."""
        cmd = Command(
            command="npm install", description="Install Node.js dependencies", tags=["node", "npm"]
        )
        data = cmd.model_dump()
        assert data["command"] == "npm install"
        assert data["description"] == "Install Node.js dependencies"
        assert data["tags"] == ["node", "npm"]


class TestCommandWithMetadata:
    """Tests for CommandWithMetadata model."""

    def test_command_with_metadata_creation(self) -> None:
        """Test creating a command with metadata."""
        now = datetime.now().astimezone()
        cmd = CommandWithMetadata(
            id="test-id-123",
            command="docker ps",
            description="List running containers",
            tags=["docker"],
            created_at=now,
            use_count=5,
        )
        assert cmd.id == "test-id-123"
        assert cmd.command == "docker ps"
        assert cmd.description == "List running containers"
        assert cmd.tags == ["docker"]
        assert cmd.created_at == now
        assert cmd.last_used is None
        assert cmd.use_count == 5

    def test_command_with_metadata_complete(self) -> None:
        """Test creating a command with all metadata fields."""
        created = datetime.now().astimezone()
        last_used = datetime.now().astimezone()
        cmd = CommandWithMetadata(
            id="test-id-456",
            command="kubectl get pods",
            description="List Kubernetes pods",
            tags=["kubernetes", "k8s"],
            os="linux",
            project_type="kubernetes",
            context="Use to check pod status",
            category="kubernetes",
            created_at=created,
            last_used=last_used,
            use_count=10,
        )
        assert cmd.id == "test-id-456"
        assert cmd.last_used == last_used
        assert cmd.use_count == 10

    def test_command_with_metadata_inherits_from_command(self) -> None:
        """Test that CommandWithMetadata inherits from Command."""
        assert issubclass(CommandWithMetadata, Command)

    def test_command_with_metadata_missing_required_fields(self) -> None:
        """Test that missing required metadata fields raises error."""
        with pytest.raises(ValidationError):
            CommandWithMetadata(  # type: ignore[call-arg]
                command="test", description="test"
            )

    def test_command_with_metadata_serialization(self) -> None:
        """Test that command with metadata can be serialized."""
        now = datetime.now().astimezone()
        cmd = CommandWithMetadata(
            id="test-789",
            command="cargo build",
            description="Build Rust project",
            created_at=now,
            use_count=3,
        )
        data = cmd.model_dump()
        assert data["id"] == "test-789"
        assert data["command"] == "cargo build"
        assert data["use_count"] == 3
