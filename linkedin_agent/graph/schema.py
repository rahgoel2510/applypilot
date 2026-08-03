"""KùzuDB schema definitions for the ApplyPilot knowledge graph.

Defines node tables, relationship tables, and helper functions to
initialize or migrate the schema on a KùzuDB database instance.

Node tables:
    Candidate, Job, Company, Recruiter, Skill, Run, InMail, Application, Prompt

Relationship tables:
    HAS_SKILL, APPLIED_TO, AT_COMPANY, REQUIRES_SKILL, SIMILAR_TO,
    WORKS_AT, CONTACTED, DISCOVERED, SENT_TO, ABOUT_JOB, USED_PROMPT, GENERATED_BY
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

try:
    import kuzu
except ImportError:
    kuzu = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema version (bump when adding/altering tables)
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Node table definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NodeTable:
    """Represents a KùzuDB node table definition."""

    name: str
    columns: list[str]
    primary_key: str


NODE_TABLES: list[NodeTable] = [
    NodeTable(
        name="Candidate",
        columns=[
            "id STRING",
            "name STRING",
            "email STRING",
            "phone STRING",
            "skills STRING[]",
            "notice_period STRING",
            "created_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
        ],
        primary_key="id",
    ),
    NodeTable(
        name="Job",
        columns=[
            "id STRING",
            "title STRING",
            "description STRING",
            "location STRING",
            "posting_url STRING",
            "is_easy_apply BOOLEAN DEFAULT false",
            "match_score DOUBLE DEFAULT 0.0",
            "posted_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
            "discovered_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
            "status STRING DEFAULT 'discovered'",
            "embedding DOUBLE[]",
        ],
        primary_key="id",
    ),
    NodeTable(
        name="Company",
        columns=[
            "id STRING",
            "name STRING",
            "industry STRING DEFAULT ''",
            "size STRING DEFAULT ''",
            "is_target BOOLEAN DEFAULT false",
            "is_blocklisted BOOLEAN DEFAULT false",
            "score_adjustment DOUBLE DEFAULT 0.0",
        ],
        primary_key="id",
    ),
    NodeTable(
        name="Recruiter",
        columns=[
            "id STRING",
            "name STRING",
            "linkedin_url STRING DEFAULT ''",
            "title STRING DEFAULT ''",
        ],
        primary_key="id",
    ),
    NodeTable(
        name="Skill",
        columns=[
            "id STRING",
            "name STRING",
            "category STRING DEFAULT ''",
            "embedding DOUBLE[]",
        ],
        primary_key="id",
    ),
    NodeTable(
        name="Run",
        columns=[
            "id STRING",
            "started_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
            "ended_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
            "mode STRING DEFAULT 'single'",
            "jobs_discovered INT64 DEFAULT 0",
            "jobs_applied INT64 DEFAULT 0",
            "jobs_skipped INT64 DEFAULT 0",
            "dry_run BOOLEAN DEFAULT true",
        ],
        primary_key="id",
    ),
    NodeTable(
        name="InMail",
        columns=[
            "id STRING",
            "subject STRING DEFAULT ''",
            "body STRING",
            "tone STRING DEFAULT 'professional'",
            "sent_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
            "status STRING DEFAULT 'drafted'",
        ],
        primary_key="id",
    ),
    NodeTable(
        name="Application",
        columns=[
            "id STRING",
            "method STRING DEFAULT 'easy_apply'",
            "resume_used STRING DEFAULT ''",
            "applied_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
            "status STRING DEFAULT 'submitted'",
            "answers_json STRING DEFAULT '{}'",
        ],
        primary_key="id",
    ),
    NodeTable(
        name="Prompt",
        columns=[
            "id STRING",
            "prompt_type STRING",
            "input_text STRING",
            "input_hash STRING",
            "output_text STRING",
            "model STRING DEFAULT ''",
            "tokens_used INT64 DEFAULT 0",
            "latency_ms INT64 DEFAULT 0",
            "created_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
        ],
        primary_key="id",
    ),
]


# ---------------------------------------------------------------------------
# Relationship table definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RelTable:
    """Represents a KùzuDB relationship table definition."""

    name: str
    from_table: str
    to_table: str
    columns: list[str] = field(default_factory=list)


REL_TABLES: list[RelTable] = [
    RelTable(
        name="HAS_SKILL",
        from_table="Candidate",
        to_table="Skill",
        columns=["proficiency STRING DEFAULT 'intermediate'"],
    ),
    RelTable(
        name="APPLIED_TO",
        from_table="Candidate",
        to_table="Job",
        columns=[
            "application_id STRING",
            "applied_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
            "method STRING DEFAULT 'easy_apply'",
            "resume_used STRING DEFAULT ''",
        ],
    ),
    RelTable(
        name="AT_COMPANY",
        from_table="Job",
        to_table="Company",
    ),
    RelTable(
        name="REQUIRES_SKILL",
        from_table="Job",
        to_table="Skill",
        columns=["importance STRING DEFAULT 'preferred'"],
    ),
    RelTable(
        name="SIMILAR_TO",
        from_table="Job",
        to_table="Job",
        columns=["similarity_score DOUBLE DEFAULT 0.0"],
    ),
    RelTable(
        name="WORKS_AT",
        from_table="Recruiter",
        to_table="Company",
        columns=["since STRING DEFAULT ''"],
    ),
    RelTable(
        name="CONTACTED",
        from_table="Candidate",
        to_table="Recruiter",
        columns=[
            "contacted_at TIMESTAMP DEFAULT timestamp('1970-01-01')",
            "channel STRING DEFAULT 'inmail'",
        ],
    ),
    RelTable(
        name="DISCOVERED",
        from_table="Run",
        to_table="Job",
        columns=["discovered_at TIMESTAMP DEFAULT timestamp('1970-01-01')"],
    ),
    RelTable(
        name="SENT_TO",
        from_table="InMail",
        to_table="Recruiter",
    ),
    RelTable(
        name="ABOUT_JOB",
        from_table="InMail",
        to_table="Job",
    ),
    RelTable(
        name="USED_PROMPT",
        from_table="Application",
        to_table="Prompt",
    ),
    RelTable(
        name="GENERATED_BY",
        from_table="InMail",
        to_table="Prompt",
    ),
]


# ---------------------------------------------------------------------------
# Schema initialization
# ---------------------------------------------------------------------------


def _build_create_node_query(table: NodeTable) -> str:
    """Build a CREATE NODE TABLE statement for KùzuDB."""
    cols = ", ".join(table.columns)
    return f"CREATE NODE TABLE IF NOT EXISTS {table.name} ({cols}, PRIMARY KEY ({table.primary_key}))"


def _build_create_rel_query(rel: RelTable) -> str:
    """Build a CREATE REL TABLE statement for KùzuDB."""
    col_str = ", ".join(rel.columns) if rel.columns else ""
    if col_str:
        return (
            f"CREATE REL TABLE IF NOT EXISTS {rel.name} "
            f"(FROM {rel.from_table} TO {rel.to_table}, {col_str})"
        )
    return (
        f"CREATE REL TABLE IF NOT EXISTS {rel.name} "
        f"(FROM {rel.from_table} TO {rel.to_table})"
    )


def initialize_schema(conn: Any) -> None:
    """Create all node and relationship tables if they don't exist.

    Args:
        conn: An active KùzuDB connection.

    Raises:
        RuntimeError: If schema creation fails irrecoverably.
    """
    logger.info("Initializing KùzuDB schema (version %d)...", SCHEMA_VERSION)

    # Create node tables first (relationships depend on them)
    for table in NODE_TABLES:
        query = _build_create_node_query(table)
        try:
            conn.execute(query)
            logger.debug("Created/verified node table: %s", table.name)
        except Exception as e:
            # Table already exists with different schema — log and continue
            if "already exists" in str(e).lower():
                logger.debug("Node table %s already exists, skipping.", table.name)
            else:
                logger.error("Failed to create node table %s: %s", table.name, e)
                raise RuntimeError(f"Schema init failed on {table.name}: {e}") from e

    # Create relationship tables
    for rel in REL_TABLES:
        query = _build_create_rel_query(rel)
        try:
            conn.execute(query)
            logger.debug("Created/verified rel table: %s", rel.name)
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.debug("Rel table %s already exists, skipping.", rel.name)
            else:
                logger.error("Failed to create rel table %s: %s", rel.name, e)
                raise RuntimeError(f"Schema init failed on {rel.name}: {e}") from e

    logger.info("KùzuDB schema initialized successfully (%d nodes, %d rels).",
                len(NODE_TABLES), len(REL_TABLES))
