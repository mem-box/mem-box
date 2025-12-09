"""Neo4j database client for Memory Box."""

import contextlib
import re
import uuid
from datetime import datetime

from neo4j import Driver, GraphDatabase
from neo4j.time import DateTime as Neo4jDateTime
from rapidfuzz import fuzz

from lib.config import CATEGORIES_MAP, COMMAND_MAP, SECRETS_PATTERNS, TAGS_MAP
from lib.models import Command, CommandWithMetadata
from lib.settings import Settings


def _detect_category_and_tags(command: str) -> tuple[str | None, list[str]]:
    """Detect category and tags from command text.

    Args:
        command: The command text

    Returns:
        Tuple of (category, tags). Category and tags are validated against config.
    """
    first_word = command.strip().split()[0] if command.strip() else ""
    match = COMMAND_MAP.get(first_word)

    if match:
        category = match.get("category")
        tags = match.get("tags", [])

        # Validate category exists in categories.json
        if category and category not in CATEGORIES_MAP:
            category = None

        # Filter out invalid tags not in tags.json
        tags = [tag for tag in tags if tag in TAGS_MAP]

        return category, tags
    return None, []


def _convert_neo4j_datetime(value: datetime | Neo4jDateTime | None) -> datetime | None:
    """Convert Neo4j DateTime to Python datetime."""
    if isinstance(value, Neo4jDateTime):
        return value.to_native()
    return value


def _obfuscate_secrets(command: str) -> str:
    """Obfuscate passwords and secrets in commands."""
    obfuscated = command
    for pattern_config in SECRETS_PATTERNS:
        pattern = pattern_config["pattern"]
        replacement = pattern_config["replacement"]
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
        """Add a command or update execution stats if it already exists.

        If a command with the same text already exists, this will:
        - Increment execution_count
        - Update description/context if they've changed
        - Merge any new tags

        If the command is new, it creates a new Command node.
        """
        # Always strip secrets from command before storing
        command_text = _obfuscate_secrets(command.command)

        # Auto-detect category and tags if not provided
        detected_category, detected_tags = _detect_category_and_tags(command.command)

        # Use detected category if not explicitly provided
        category = command.category or detected_category

        # Merge user-provided tags with auto-detected tags
        all_tags = list(set(command.tags + detected_tags))

        with self.driver.session(database=self.database) as session:
            # Check if command already exists
            result = session.run(
                """
                MATCH (c:Command {command: $command})
                RETURN c.id as id
                """,
                command=command_text,
            )
            existing = result.single()

            if existing:
                # Update existing command's execution statistics
                command_id = existing["id"]
                session.run(
                    """
                    MATCH (c:Command {id: $id})
                    SET c.description = $description,
                        c.context = $context,
                        c.execution_count = c.execution_count + 1,
                        c.success_count = c.success_count +
                            CASE WHEN $status = 'success' THEN 1 ELSE 0 END,
                        c.failure_count = c.failure_count +
                            CASE WHEN $status = 'failed' THEN 1 ELSE 0 END
                    WITH c

                    // Merge new tags (don't remove existing ones)
                    UNWIND $tags AS tag
                    MERGE (t:Tag {name: tag})
                    MERGE (c)-[:TAGGED_WITH]->(t)

                    WITH c
                    // Merge category relationship (command may gain new category)
                    FOREACH (_ IN CASE WHEN $category IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (cat:Category {name: $category})
                        MERGE (c)-[:HAS_CATEGORY]->(cat)
                    )

                    WITH c
                    // Merge OS relationship (command may be run on multiple OSes)
                    FOREACH (_ IN CASE WHEN $os IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (o:OS {name: $os})
                        MERGE (c)-[:RUNS_ON]->(o)
                    )

                    WITH c
                    // Merge project type relationship
                    FOREACH (_ IN CASE WHEN $project_type IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (pt:ProjectType {name: $project_type})
                        MERGE (c)-[:FOR_PROJECT]->(pt)
                    )
                    """,
                    id=command_id,
                    description=command.description,
                    context=command.context,
                    status=command.status,
                    tags=all_tags,
                    category=category,
                    os=command.os,
                    project_type=command.project_type,
                )
            else:
                # Create new command
                command_id = str(uuid.uuid4())
                execution_count = 1 if command.status else 0
                success_count = 1 if command.status == "success" else 0
                failure_count = 1 if command.status == "failed" else 0

                session.run(
                    """
                    CREATE (c:Command {
                        id: $id,
                        command: $command,
                        description: $description,
                        context: $context,
                        created_at: datetime($created_at),
                        last_used: NULL,
                        use_count: 0,
                        execution_count: $execution_count,
                        success_count: $success_count,
                        failure_count: $failure_count
                    })
                    WITH c

                    // Create and link tags
                    WITH c, $tags AS tag_list
                    UNWIND CASE WHEN size(tag_list) > 0 THEN tag_list ELSE [null] END AS tag
                    FOREACH (_ IN CASE WHEN tag IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (t:Tag {name: tag})
                        MERGE (c)-[:TAGGED_WITH]->(t)
                    )

                    WITH c
                    // Create and link category
                    FOREACH (_ IN CASE WHEN $category IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (cat:Category {name: $category})
                        MERGE (c)-[:HAS_CATEGORY]->(cat)
                    )

                    WITH c
                    // Create and link OS
                    FOREACH (_ IN CASE WHEN $os IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (o:OS {name: $os})
                        MERGE (c)-[:RUNS_ON]->(o)
                    )

                    WITH c
                    // Create and link project type
                    FOREACH (_ IN CASE WHEN $project_type IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (pt:ProjectType {name: $project_type})
                        MERGE (c)-[:FOR_PROJECT]->(pt)
                    )
                    """,
                    id=command_id,
                    command=command_text,
                    description=command.description,
                    context=command.context,
                    tags=all_tags,
                    created_at=datetime.now().astimezone().isoformat(),
                    execution_count=execution_count,
                    success_count=success_count,
                    failure_count=failure_count,
                    category=category,
                    os=command.os,
                    project_type=command.project_type,
                )

        return str(command_id)

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

        # Build relationship filters
        relationship_filters = []

        if os:
            relationship_filters.append("MATCH (c)-[:RUNS_ON]->(os:OS {name: $os})")
            params["os"] = os

        if project_type:
            relationship_filters.append(
                "MATCH (c)-[:FOR_PROJECT]->(pt:ProjectType {name: $project_type})"
            )
            params["project_type"] = project_type

        if category:
            relationship_filters.append(
                "MATCH (c)-[:HAS_CATEGORY]->(cat:Category {name: $category})"
            )
            params["category"] = category

        # Tag matching (OR logic - match if command has ANY of the provided tags)
        tag_match = ""
        if tags:
            tag_match = """
            MATCH (c)-[:TAGGED_WITH]->(t:Tag)
            WHERE t.name IN $tags
            WITH DISTINCT c
            """
            params["tags"] = list(tags)

        # Build WHERE clause
        where_clause = ""
        if where_clauses:
            if tag_match or relationship_filters:
                where_clause = "WITH c\nWHERE " + " AND ".join(where_clauses)
            else:
                where_clause = "WHERE " + " AND ".join(where_clauses)

        # Build and execute query
        final_query = f"""
        MATCH (c:Command)
        {chr(10).join(relationship_filters)}
        {tag_match}
        {where_clause}
        OPTIONAL MATCH (c)-[:TAGGED_WITH]->(t:Tag)
        OPTIONAL MATCH (c)-[:RUNS_ON]->(os:OS)
        OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category)
        OPTIONAL MATCH (c)-[:FOR_PROJECT]->(pt:ProjectType)
        WITH c,
             collect(DISTINCT t.name) as tags,
             collect(DISTINCT os.name) as oses,
             collect(DISTINCT cat.name) as categories,
             collect(DISTINCT pt.name) as project_types
        ORDER BY c.execution_count DESC, c.created_at DESC
        RETURN c, tags, oses, categories, project_types
        """

        # Update query to also fetch OS, category, project_type from relationships
        final_query = f"""
        MATCH (c:Command)
        {chr(10).join(relationship_filters)}
        {tag_match}
        {where_clause}
        OPTIONAL MATCH (c)-[:TAGGED_WITH]->(t:Tag)
        OPTIONAL MATCH (c)-[:RUNS_ON]->(os:OS)
        OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category)
        OPTIONAL MATCH (c)-[:FOR_PROJECT]->(pt:ProjectType)
        WITH c,
             collect(DISTINCT t.name) as tags,
             collect(DISTINCT os.name) as oses,
             collect(DISTINCT cat.name) as categories,
             collect(DISTINCT pt.name) as project_types
        ORDER BY c.execution_count DESC, c.created_at DESC
        RETURN c, tags, oses, categories, project_types
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(final_query, params)
            commands = []

            for record in result:
                node = record["c"]
                tags = record["tags"]
                oses = record["oses"]
                categories = record["categories"]
                project_types = record["project_types"]

                created_at = _convert_neo4j_datetime(node["created_at"])
                if created_at is None:
                    continue  # Skip records with invalid timestamps

                # Use first OS/category/project_type for backwards compatibility
                # (CommandWithMetadata expects single values)
                commands.append(
                    CommandWithMetadata(
                        id=node["id"],
                        command=node["command"],
                        description=node["description"],
                        tags=tags,
                        os=oses[0] if oses else None,
                        project_type=project_types[0] if project_types else None,
                        context=node.get("context"),
                        category=categories[0] if categories else None,
                        status=node.get("status"),
                        created_at=created_at,
                        last_used=_convert_neo4j_datetime(node.get("last_used")),
                        use_count=node.get("use_count", 0),
                        execution_count=node.get("execution_count", 0),
                        success_count=node.get("success_count", 0),
                        failure_count=node.get("failure_count", 0),
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

        # Sort by score (highest first), then by execution count
        scored_commands.sort(key=lambda x: (-x[0], -x[1].execution_count))

        return [cmd for _, cmd in scored_commands[:limit]]

    def get_command(self, command_id: str) -> CommandWithMetadata | None:
        """Get a specific command by ID."""

        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (c:Command {id: $id})
                OPTIONAL MATCH (c)-[:TAGGED_WITH]->(t:Tag)
                OPTIONAL MATCH (c)-[:RUNS_ON]->(os:OS)
                OPTIONAL MATCH (c)-[:HAS_CATEGORY]->(cat:Category)
                OPTIONAL MATCH (c)-[:FOR_PROJECT]->(pt:ProjectType)
                WITH c,
                     collect(DISTINCT t.name) as tags,
                     collect(DISTINCT os.name) as oses,
                     collect(DISTINCT cat.name) as categories,
                     collect(DISTINCT pt.name) as project_types
                RETURN c, tags, oses, categories, project_types
                """,
                id=command_id,
                now=datetime.now().astimezone().isoformat(),
            )

            record = result.single()
            if not record:
                return None

            node = record["c"]
            tags = record["tags"]
            oses = record["oses"]
            categories = record["categories"]
            project_types = record["project_types"]

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
                os=oses[0] if oses else None,
                project_type=project_types[0] if project_types else None,
                context=node.get("context"),
                category=categories[0] if categories else None,
                status=node.get("status"),
                created_at=created_at,
                last_used=_convert_neo4j_datetime(node.get("last_used")),
                use_count=node.get("use_count", 0),
                execution_count=node.get("execution_count", 0),
                success_count=node.get("success_count", 0),
                failure_count=node.get("failure_count", 0),
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
                MATCH (cat:Category)
                RETURN cat.name as category
                ORDER BY category
                """
            )

            return [record["category"] for record in result]
