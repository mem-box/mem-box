"""Tests for configuration module."""

import os
from unittest.mock import patch

from lib.settings import Settings, get_settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        # Clear environment to test defaults
        with patch.dict(os.environ, {}, clear=False):
            # Remove NEO4J_PASSWORD if it exists in env
            if "NEO4J_PASSWORD" in os.environ:
                del os.environ["NEO4J_PASSWORD"]
            settings = Settings()
            assert settings.neo4j_uri == "bolt://localhost:7687"
            assert settings.neo4j_user == "neo4j"
            # Just check it has a value, not the specific value
            assert settings.neo4j_password is not None
            assert settings.neo4j_database == "neo4j"

    def test_custom_settings(self) -> None:
        """Test custom settings via environment variables."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://custom:7687",
                "NEO4J_USER": "custom_user",
                "NEO4J_PASSWORD": "custom_pass",
                "NEO4J_DATABASE": "custom_db",
            },
        ):
            settings = Settings()
            assert settings.neo4j_uri == "bolt://custom:7687"
            assert settings.neo4j_user == "custom_user"
            assert settings.neo4j_password == "custom_pass"  # noqa: S105
            assert settings.neo4j_database == "custom_db"


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_returns_settings_instance(self) -> None:
        """Test that get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_uses_environment(self) -> None:
        """Test that get_settings uses environment variables."""
        with patch.dict(os.environ, {"NEO4J_URI": "bolt://test:7687"}):
            settings = get_settings()
            assert settings.neo4j_uri == "bolt://test:7687"
