"""Context detection utilities for Memory Box."""

import platform
from pathlib import Path

from lib.config import INDICATOR_MAP


def detect_os() -> str:
    """Detect the current operating system."""
    system = platform.system().lower()

    if system == "darwin":
        return "macos"
    if system in ("linux", "windows"):
        return system
    return "unknown"


def detect_project_type(directory: str | None = None) -> str | None:
    """
    Detect the project type based on files in the directory.

    Args:
        directory: Directory to check. Defaults to current working directory.

    Returns:
        Project type or None if not detected.
    """
    if directory is None:
        directory = str(Path.cwd())

    path = Path(directory)

    # Check each indicator file
    for indicator, project_type in INDICATOR_MAP.items():
        if (path / indicator).exists():
            return str(project_type)

    return None


def get_current_context() -> dict[str, str | None]:
    """Get the current system and project context."""
    return {"os": detect_os(), "project_type": detect_project_type(), "cwd": str(Path.cwd())}


def format_context_info(context: dict[str, str | None]) -> str:
    """Format context information for display."""
    parts = []

    if context.get("os"):
        parts.append(f"OS: {context['os']}")

    if context.get("project_type"):
        parts.append(f"Project: {context['project_type']}")

    if context.get("cwd"):
        parts.append(f"Directory: {context['cwd']}")

    return " | ".join(parts) if parts else "No context detected"
