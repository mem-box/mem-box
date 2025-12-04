"""Data models for Memory Box."""

from datetime import datetime

from pydantic import BaseModel, Field


class Command(BaseModel):
    """A command stored in the memory box."""

    command: str = Field(..., description="The actual command or code snippet")
    description: str = Field(..., description="What this command does")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    os: str | None = Field(None, description="Operating system (linux, macos, windows)")
    project_type: str | None = Field(None, description="Project type (python, node, rust, etc.)")
    context: str | None = Field(None, description="Additional context about when to use this")
    category: str | None = Field(None, description="Category (git, docker, kubernetes, etc.)")


class CommandWithMetadata(Command):
    """A command with additional metadata from the database."""

    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="When this command was added")
    last_used: datetime | None = Field(None, description="Last time this command was accessed")
    use_count: int = Field(0, description="Number of times this command has been accessed")
