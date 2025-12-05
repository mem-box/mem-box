"""Integration tests for secret obfuscation in database operations."""

from collections.abc import Generator

import pytest
from testcontainers.neo4j import Neo4jContainer

from lib.database import Neo4jClient
from lib.models import Command
from lib.settings import Settings


@pytest.fixture(scope="module")
def neo4j_container() -> Generator[Neo4jContainer, None, None]:
    """Start a Neo4j container for testing."""
    with Neo4jContainer("neo4j:5-community") as container:
        yield container


@pytest.fixture(scope="module")
def neo4j_settings(neo4j_container: Neo4jContainer) -> Settings:
    """Create settings for Neo4j test database."""
    return Settings(
        neo4j_uri=neo4j_container.get_connection_url(),
        neo4j_user=neo4j_container.username,
        neo4j_password=neo4j_container.password,
        neo4j_database="neo4j",
    )


@pytest.fixture
def db_client(neo4j_settings: Settings) -> Generator[Neo4jClient, None, None]:
    """Create a database client and clean up after tests."""
    client = Neo4jClient(neo4j_settings)
    yield client

    # Cleanup: Delete all test data
    with client.driver.session(database=client.database) as session:
        session.run("MATCH (n:Command) DETACH DELETE n")
        session.run("MATCH (n:Tag) DELETE n")

    client.close()


class TestSecretsIntegration:
    """Test that secrets are stripped before storage."""

    def test_add_command_strips_password_flag(self, db_client: Neo4jClient) -> None:
        """Test that -p passwords are stripped before storage."""
        command = Command(
            command="mysql -u root -p MySecretPassword",
            description="Connect to MySQL",
            tags=["database", "mysql"],
        )

        command_id = db_client.add_command(command)
        retrieved = db_client.get_command(command_id)

        assert retrieved.command == "mysql -u root -p ****"
        assert "MySecretPassword" not in retrieved.command

    def test_add_command_strips_url_password(self, db_client: Neo4jClient) -> None:
        """Test that URL passwords are stripped before storage."""
        command = Command(
            command="git clone https://user:secret123@github.com/repo.git",
            description="Clone private repo",
            tags=["git"],
        )

        command_id = db_client.add_command(command)
        retrieved = db_client.get_command(command_id)

        assert retrieved.command == "git clone https://user:****@github.com/repo.git"
        assert "secret123" not in retrieved.command

    def test_add_command_strips_env_var(self, db_client: Neo4jClient) -> None:
        """Test that environment variable passwords are stripped."""
        command = Command(
            command="export DB_PASSWORD=supersecret",
            description="Set database password",
            tags=["env"],
        )

        command_id = db_client.add_command(command)
        retrieved = db_client.get_command(command_id)

        assert retrieved.command == "export DB_PASSWORD=****"
        assert "supersecret" not in retrieved.command

    def test_search_returns_obfuscated_commands(self, db_client: Neo4jClient) -> None:
        """Test that retrieved commands have secrets stripped."""
        command = Command(
            command="psql --password MyPassword -d testdb",
            description="Connect to PostgreSQL database",
            tags=["database", "postgresql"],
        )

        command_id = db_client.add_command(command)

        # Test get_command returns obfuscated
        retrieved = db_client.get_command(command_id)
        assert retrieved.command == "psql --password **** -d testdb"
        assert "MyPassword" not in retrieved.command

    def test_multiple_secrets_all_stripped(self, db_client: Neo4jClient) -> None:
        """Test that multiple secrets in one command are all stripped."""
        command = Command(
            command="deploy -p secret1 token=secret2 api_key=secret3",
            description="Deploy with credentials",
            tags=["deploy"],
        )

        command_id = db_client.add_command(command)
        retrieved = db_client.get_command(command_id)

        assert retrieved.command == "deploy -p **** token=**** api_key=****"
        assert "secret1" not in retrieved.command
        assert "secret2" not in retrieved.command
        assert "secret3" not in retrieved.command

    def test_no_secrets_unchanged(self, db_client: Neo4jClient) -> None:
        """Test that commands without secrets are stored unchanged."""
        command = Command(
            command="ls -la /home/user", description="List files", tags=["filesystem"]
        )

        command_id = db_client.add_command(command)
        retrieved = db_client.get_command(command_id)

        assert retrieved.command == "ls -la /home/user"
