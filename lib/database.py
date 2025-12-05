"""Neo4j database client for Memory Box."""

import contextlib
import re
import uuid
from datetime import datetime

from neo4j import Driver, GraphDatabase
from neo4j.time import DateTime as Neo4jDateTime
from rapidfuzz import fuzz

from lib.config import Settings
from lib.models import Command, CommandWithMetadata, Stack


def _convert_neo4j_datetime(value: datetime | Neo4jDateTime | None) -> datetime | None:
    """Convert Neo4j DateTime to Python datetime."""
    if isinstance(value, Neo4jDateTime):
        return value.to_native()
    return value


def _obfuscate_secrets(command: str) -> str:
    """Obfuscate passwords and secrets in commands."""
    # Pattern for common password/token flags and parameters
    # Supports quoted values (single or double quotes) and unquoted values
    patterns = [
        # Flags like -p, --password followed by quoted values (with any content inside)
        (r'''(-p|--password|--pass|--pwd)\s+"[^"]*"''', r"\1 ****"),
        (r"""(-p|--password|--pass|--pwd)\s+'[^']*'""", r"\1 ****"),
        # Flags followed by unquoted values
        (r"(-p|--password|--pass|--pwd)\s+\S+", r"\1 ****"),
        # Key=value with double quotes
        (r'''(password=|pwd=|pass=)"[^"]*"''', r"\1****"),
        (r'''(token=|api_key=|apikey=|secret=)"[^"]*"''', r"\1****"),
        (r'''(NEO4J_PASSWORD=|DB_PASSWORD=|POSTGRES_PASSWORD=)"[^"]*"''', r"\1****"),
        # Key=value with single quotes
        (r"""(password=|pwd=|pass=)'[^']*'""", r"\1****"),
        (r"""(token=|api_key=|apikey=|secret=)'[^']*'""", r"\1****"),
        (r"""(NEO4J_PASSWORD=|DB_PASSWORD=|POSTGRES_PASSWORD=)'[^']*'""", r"\1****"),
        # Key=value without quotes
        (r"(password=|pwd=|pass=)\S+", r"\1****"),
        (r"(token=|api_key=|apikey=|secret=)\S+", r"\1****"),
        (r"(NEO4J_PASSWORD=|DB_PASSWORD=|POSTGRES_PASSWORD=)\S+", r"\1****"),
        # Match passwords in URLs
        (r"(://[^:]+:)([^@]+)(@)", r"\1****\3"),
    ]

    obfuscated = command
    for pattern, replacement in patterns:
        obfuscated = re.sub(pattern, replacement, obfuscated, flags=re.IGNORECASE)

    return obfuscated.rstrip()


class Neo4jClient:
    """Client for interacting with Neo4j database."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the Neo4j client."""
        self.driver: Driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        self.database = settings.neo4j_database
        self._initialize_constraints()

    def close(self) -> None:
        """Close the database connection."""
        self.driver.close()

    def _initialize_constraints(self) -> None:
        """Create necessary constraints and indexes."""
        with self.driver.session(database=self.database) as session:
            # Ensure unique IDs for commands
            session.run(
                "CREATE CONSTRAINT command_id_unique IF NOT EXISTS "
                "FOR (c:Command) REQUIRE c.id IS UNIQUE"
            )
            # Index for faster text search
            session.run(
                "CREATE INDEX command_text_index IF NOT EXISTS "
                "FOR (c:Command) ON (c.command, c.description)"
            )
            # Full-text index for fuzzy search
            with contextlib.suppress(Exception):
                # Index might already exist or Neo4j version doesn't support it
                session.run(
                    "CREATE FULLTEXT INDEX command_fulltext IF NOT EXISTS "
                    "FOR (c:Command) ON EACH [c.command, c.description, c.context]"
                )

    def add_command(self, command: Command) -> str:
        """Add a new command to the database."""
        command_id = str(uuid.uuid4())

        # Always strip secrets from command before storing
        command_text = _obfuscate_secrets(command.command)

        with self.driver.session(database=self.database) as session:
            session.run(
                """
                CREATE (c:Command {
                    id: $id,
                    command: $command,
                    description: $description,
                    os: $os,
                    project_type: $project_type,
                    context: $context,
                    category: $category,
                    created_at: datetime($created_at),
                    last_used: NULL,
                    use_count: 0
                })
                WITH c
                UNWIND $tags AS tag
                MERGE (t:Tag {name: tag})
                MERGE (c)-[:TAGGED_WITH]->(t)
                """,
                id=command_id,
                command=command_text,
                description=command.description,
                os=command.os,
                project_type=command.project_type,
                context=command.context,
                category=command.category,
                tags=command.tags,
                created_at=datetime.now().astimezone().isoformat(),
            )

        # Auto-detect and link to stacks based on command content
        self._auto_link_stacks(command_id, command_text, command.tags, command.category)

        return command_id

    def _auto_link_stacks(
        self, command_id: str, command: str, tags: list[str], category: str | None
    ) -> None:
        """Automatically detect and link command to relevant stacks."""
        command_lower = command.lower()
        all_tags = [t.lower() for t in tags] + ([category.lower()] if category else [])

        # Check tags/category first for explicit stack hints
        self._link_from_tags(command_id, all_tags)

        # Check command text for specific patterns
        self._link_from_command_patterns(command_id, command_lower)

    def _link_from_tags(self, command_id: str, tags: list[str]) -> None:
        """Link command to stacks based on tags."""
        tag_stack_map = {
            "docker": ("Docker", "tool"),
            "container": ("Docker", "tool"),
            "python": ("Python", "language"),
            "py": ("Python", "language"),
            "node": ("Node", "language"),
            "npm": ("Node", "language"),
            "javascript": ("Node", "language"),
            "js": ("Node", "language"),
            "kubernetes": ("Kubernetes", "tool"),
            "k8s": ("Kubernetes", "tool"),
            "rust": ("Rust", "language"),
            "cargo": ("Rust", "language"),
            "git": ("Git", "tool"),
        }

        for tag in tags:
            if tag in tag_stack_map:
                stack_name, stack_type = tag_stack_map[tag]
                self._ensure_stack_link(command_id, stack_name, stack_type, "RUN")

    def _link_from_command_patterns(self, command_id: str, command_lower: str) -> None:
        """Link command to stacks based on command patterns."""
        # Stack detection patterns: (keywords, stack_name, stack_type, relationship_type)
        patterns = [
            # Docker
            (["docker build"], "Docker", "tool", "BUILD"),
            (["docker run", "docker start", "docker compose up"], "Docker", "tool", "RUN"),
            (["docker"], "Docker", "tool", "RUN"),  # fallback
            # Python
            (["pytest", "python -m pytest", "py.test"], "Python", "language", "TEST"),
            (["python -m", "python3 -m"], "Python", "language", "RUN"),
            (["pip install", "pip3 install"], "Python", "language", "BUILD"),
            (["python", "python3"], "Python", "language", "RUN"),  # fallback
            # Node/npm
            (["npm run build", "yarn build"], "Node", "language", "BUILD"),
            (["npm test", "yarn test"], "Node", "language", "TEST"),
            (["npm run", "yarn run"], "Node", "language", "RUN"),
            (["npm install", "yarn install"], "Node", "language", "BUILD"),
            # Git
            (["git push", "git pull"], "Git", "tool", "DEPLOY"),
            (["git commit"], "Git", "tool", "BUILD"),
            (["git"], "Git", "tool", "RUN"),  # fallback
            # Kubernetes
            (["kubectl apply"], "Kubernetes", "tool", "DEPLOY"),
            (["kubectl"], "Kubernetes", "tool", "RUN"),
            # Rust
            (["cargo build"], "Rust", "language", "BUILD"),
            (["cargo test"], "Rust", "language", "TEST"),
            (["cargo run"], "Rust", "language", "RUN"),
            # Make
            (["make build"], "Make", "tool", "BUILD"),
            (["make test"], "Make", "tool", "TEST"),
            (["make"], "Make", "tool", "BUILD"),  # fallback
        ]

        for keywords, stack_name, stack_type, rel_type in patterns:
            if self._matches_any_keyword(command_lower, keywords):
                self._ensure_stack_link(command_id, stack_name, stack_type, rel_type)
                break  # Only use first matching pattern for this stack

    def _matches_any_keyword(self, command: str, keywords: list[str]) -> bool:
        """Check if command contains any of the keywords."""
        return any(keyword in command for keyword in keywords)

    def _ensure_stack_link(
        self, command_id: str, stack_name: str, stack_type: str, relationship_type: str
    ) -> None:
        """Create stack if needed and link command to it."""
        with self.driver.session(database=self.database) as session:
            session.run(
                f"""
                MATCH (c:Command {{id: $command_id}})
                MERGE (s:Stack {{name: $stack_name}})
                ON CREATE SET s.type = $stack_type, s.description = ''
                MERGE (s)-[r:{relationship_type}]->(c)
                """,
                command_id=command_id,
                stack_name=stack_name,
                stack_type=stack_type,
            )

    def search_commands(
        self,
        query: str | None = None,
        os: str | None = None,
        project_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
        fuzzy: bool = False,
        fuzzy_threshold: int = 60,
    ) -> list[CommandWithMetadata]:
        """Search for commands matching the criteria.

        Args:
            query: Text to search for
            os: Filter by operating system
            project_type: Filter by project type
            category: Filter by category
            tags: Filter by tags (all must match)
            limit: Maximum number of results
            fuzzy: Enable fuzzy matching for query
            fuzzy_threshold: Minimum similarity score (0-100) for fuzzy matches
        """
        # Fetch candidates from database with structural filters only
        candidates = self._fetch_command_candidates(
            os=os,
            project_type=project_type,
            category=category,
            tags=tags,
            query=query if not fuzzy else None,  # Skip text filter for fuzzy
        )

        # Apply text matching (exact or fuzzy)
        if query:
            if fuzzy:
                return self._apply_fuzzy_matching(candidates, query, fuzzy_threshold, limit)
            # Exact match already filtered in query, just limit
            return candidates[:limit]

        return candidates[:limit]

    def _fetch_command_candidates(
        self,
        os: str | None = None,
        project_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        query: str | None = None,
    ) -> list[CommandWithMetadata]:
        """Fetch command candidates from database with structural filters.

        This method handles all database-level filtering (OS, project type,
        category, tags, and optional exact text matching). Text matching
        is only applied here for exact searches, not fuzzy searches.
        """
        where_clauses = []
        params: dict[str, str | list[str]] = {}

        # Text search (only for exact matching, not fuzzy)
        if query:
            where_clauses.append(
                "(c.command CONTAINS $query OR c.description CONTAINS $query OR "
                "c.context CONTAINS $query)"
            )
            params["query"] = query

        # Structural filters
        if os:
            where_clauses.append("c.os = $os")
            params["os"] = os

        if project_type:
            where_clauses.append("c.project_type = $project_type")
            params["project_type"] = project_type

        if category:
            where_clauses.append("c.category = $category")
            params["category"] = category

        # Tag matching
        tag_match = ""
        if tags:
            tag_match = """
            MATCH (c)-[:TAGGED_WITH]->(t:Tag)
            WHERE t.name IN $tags
            WITH c, count(t) as tag_count
            WHERE tag_count = size($tags)
            """
            params["tags"] = list(tags)

        # Build WHERE clause
        where_clause = ""
        if where_clauses:
            if tag_match:
                where_clause = "WITH c\nWHERE " + " AND ".join(where_clauses)
            else:
                where_clause = "WHERE " + " AND ".join(where_clauses)

        # Build and execute query
        cypher_query = f"""
        MATCH (c:Command)
        {tag_match}
        {where_clause}
        OPTIONAL MATCH (c)-[:TAGGED_WITH]->(t:Tag)
        WITH c, collect(t.name) as tags
        ORDER BY c.use_count DESC, c.created_at DESC
        RETURN c, tags
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(cypher_query, params)
            commands = []

            for record in result:
                node = record["c"]
                tags = record["tags"]

                created_at = _convert_neo4j_datetime(node["created_at"])
                if created_at is None:
                    continue  # Skip records with invalid timestamps

                commands.append(
                    CommandWithMetadata(
                        id=node["id"],
                        command=node["command"],
                        description=node["description"],
                        tags=tags,
                        os=node.get("os"),
                        project_type=node.get("project_type"),
                        context=node.get("context"),
                        category=node.get("category"),
                        created_at=created_at,
                        last_used=_convert_neo4j_datetime(node.get("last_used")),
                        use_count=node.get("use_count", 0),
                    )
                )

            return commands

    def _apply_fuzzy_matching(
        self, candidates: list[CommandWithMetadata], query: str, threshold: int, limit: int
    ) -> list[CommandWithMetadata]:
        """Apply fuzzy matching to candidates and return top matches.

        This method scores all candidates using fuzzy string matching,
        filters by threshold, and returns the top matches sorted by score.
        """
        scored_commands = []
        query_lower = query.lower()

        for cmd in candidates:
            # Score against command, description, and context
            cmd_score = fuzz.partial_ratio(query_lower, cmd.command.lower())
            desc_score = fuzz.partial_ratio(query_lower, cmd.description.lower())
            ctx_score = fuzz.partial_ratio(query_lower, (cmd.context or "").lower())
            max_score = max(cmd_score, desc_score, ctx_score)

            if max_score >= threshold:
                scored_commands.append((max_score, cmd))

        # Sort by score (highest first), then by use count
        scored_commands.sort(key=lambda x: (-x[0], -x[1].use_count))

        return [cmd for _, cmd in scored_commands[:limit]]

    def get_command(self, command_id: str) -> CommandWithMetadata | None:
        """Get a specific command by ID and increment its use count."""

        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (c:Command {id: $id})
                SET c.use_count = c.use_count + 1,
                    c.last_used = datetime($now)
                WITH c
                OPTIONAL MATCH (c)-[:TAGGED_WITH]->(t:Tag)
                WITH c, collect(t.name) as tags
                RETURN c, tags
                """,
                id=command_id,
                now=datetime.now().astimezone().isoformat(),
            )

            record = result.single()
            if not record:
                return None

            node = record["c"]
            tags = record["tags"]

            # Validate timestamp before creating command object
            created_at = _convert_neo4j_datetime(node["created_at"])
            if created_at is None:
                return None  # Invalid timestamp

            # Command is already obfuscated in DB, just return it
            return CommandWithMetadata(
                id=node["id"],
                command=node["command"],
                description=node["description"],
                tags=tags,
                os=node.get("os"),
                project_type=node.get("project_type"),
                context=node.get("context"),
                category=node.get("category"),
                created_at=created_at,
                last_used=_convert_neo4j_datetime(node.get("last_used")),
                use_count=node.get("use_count", 0),
            )

    def delete_command(self, command_id: str) -> bool:
        """Delete a command from the database."""

        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (c:Command {id: $id})
                DETACH DELETE c
                RETURN count(c) as deleted
                """,
                id=command_id,
            )

            record = result.single()
            return record["deleted"] > 0 if record else False

    def get_all_tags(self) -> list[str]:
        """Get all unique tags in the database."""

        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (t:Tag)
                RETURN t.name as tag
                ORDER BY tag
                """
            )

            return [record["tag"] for record in result]

    def get_all_categories(self) -> list[str]:
        """Get all unique categories in the database."""

        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (c:Command)
                WHERE c.category IS NOT NULL
                RETURN DISTINCT c.category as category
                ORDER BY category
                """
            )

            return [record["category"] for record in result]

    # Stack-related methods

    def create_stack(self, stack: "Stack") -> None:
        """Create or update a stack node."""

        with self.driver.session(database=self.database) as session:
            session.run(
                """
                MERGE (s:Stack {name: $name})
                SET s.type = $type,
                    s.description = $description
                """,
                name=stack.name,
                type=stack.type,
                description=stack.description,
            )

    def get_stack(self, name: str) -> "Stack | None":
        """Get a stack by name."""

        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (s:Stack {name: $name})
                RETURN s
                """,
                name=name,
            )
            record = result.single()
            if not record:
                return None

            node = record["s"]
            return Stack(
                name=node["name"], type=node["type"], description=node.get("description", "")
            )

    def link_command_to_stack(
        self, command_id: str, stack_name: str, relationship_type: str
    ) -> None:
        """Link a command to a stack with a specific relationship type (e.g., BUILD, RUN, TEST)."""
        with self.driver.session(database=self.database) as session:
            # Create stack if it doesn't exist, then create relationship
            session.run(
                f"""
                MATCH (c:Command {{id: $command_id}})
                MERGE (s:Stack {{name: $stack_name}})
                MERGE (s)-[r:{relationship_type}]->(c)
                """,
                command_id=command_id,
                stack_name=stack_name,
            )

    def get_commands_by_stack(
        self, stack_name: str, relationship_type: str | None = None
    ) -> list["CommandWithMetadata"]:
        """Get all commands for a specific stack, optionally filtered by relationship type."""

        with self.driver.session(database=self.database) as session:
            if relationship_type:
                query = f"""
                MATCH (s:Stack {{name: $stack_name}})-[r:{relationship_type}]->(c:Command)
                OPTIONAL MATCH (c)-[:TAGGED_WITH]->(t:Tag)
                WITH c, collect(t.name) as tags
                ORDER BY c.created_at DESC
                RETURN c, tags
                """
            else:
                query = """
                MATCH (s:Stack {name: $stack_name})-[r]->(c:Command)
                OPTIONAL MATCH (c)-[:TAGGED_WITH]->(t:Tag)
                WITH c, collect(t.name) as tags, type(r) as rel_type
                ORDER BY c.created_at DESC
                RETURN c, tags, rel_type
                """

            result = session.run(query, stack_name=stack_name)
            commands = []
            for record in result:
                node = record["c"]
                tags = record["tags"]

                created_at = _convert_neo4j_datetime(node["created_at"])
                if created_at is None:
                    continue  # Skip records with invalid timestamps

                commands.append(
                    CommandWithMetadata(
                        id=node["id"],
                        command=node["command"],
                        description=node.get("description", ""),
                        tags=tags,
                        os=node.get("os"),
                        project_type=node.get("project_type"),
                        context=node.get("context"),
                        category=node.get("category"),
                        created_at=created_at,
                        last_used=_convert_neo4j_datetime(node.get("last_used")),
                        use_count=node.get("use_count", 0),
                    )
                )
            return commands

    def list_stacks(self) -> list["Stack"]:
        """List all stacks in the database."""

        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (s:Stack)
                RETURN s
                ORDER BY s.name
                """
            )
            return [
                Stack(
                    name=record["s"]["name"],
                    type=record["s"]["type"],
                    description=record["s"].get("description", ""),
                )
                for record in result
            ]
