"""Graph store — KùzuDB-backed knowledge graph for ApplyPilot.

Provides the GraphStore class (wraps KùzuDB) and NoOpGraphStore (no-op stub).
The factory function in __init__.py decides which to instantiate based on config.

Usage:
    from linkedin_agent.graph import get_graph_store
    store = get_graph_store()
    if store.is_seen("4441030628"):
        skip  # Already in graph
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    import kuzu
except ImportError:
    kuzu = None  # type: ignore[assignment]

from linkedin_agent.graph.queries import (
    ANALYTICS,
    DEDUP,
    DISCOVERY,
    INMAIL,
    PROMPTS,
    SCORING,
    SIMILARITY,
)
from linkedin_agent.graph.schema import initialize_schema

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_id() -> str:
    """Generate a unique ID for graph nodes."""
    return uuid.uuid4().hex[:16]


def _hash_text(text: str) -> str:
    """Create a deterministic hash of input text for prompt caching."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _normalize_company_id(name: str) -> str:
    """Create a stable company ID from its name."""
    return name.strip().lower().replace(" ", "_").replace(".", "")


# ---------------------------------------------------------------------------
# GraphStore — Full KùzuDB implementation
# ---------------------------------------------------------------------------


class GraphStore:
    """KùzuDB-backed graph store for job application intelligence.

    Manages nodes (jobs, companies, skills, prompts) and relationships,
    providing graph-powered dedup, scoring, similarity, and caching.

    Args:
        db_path: Path to the KùzuDB database directory.
    """

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db: Optional[kuzu.Database] = None
        self._conn: Optional[kuzu.Connection] = None
        self._connected = False

    @property
    def connected(self) -> bool:
        """Whether the graph store is connected and ready."""
        return self._connected

    def connect(self) -> None:
        """Open a connection to KùzuDB and initialize schema.

        Creates the database directory if it doesn't exist.

        Raises:
            RuntimeError: If connection or schema initialization fails.
        """
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = kuzu.Database(str(self._db_path))
            self._conn = kuzu.Connection(self._db)
            initialize_schema(self._conn)
            self._connected = True
            logger.info("GraphStore connected at %s", self._db_path)
        except Exception as e:
            self._connected = False
            logger.error("GraphStore connection failed: %s", e)
            raise RuntimeError(f"Failed to connect to KùzuDB at {self._db_path}: {e}") from e

    def close(self) -> None:
        """Close the database connection and release resources."""
        if self._conn is not None:
            try:
                del self._conn
            except Exception:
                pass
            self._conn = None
        if self._db is not None:
            try:
                del self._db
            except Exception:
                pass
            self._db = None
        self._connected = False
        logger.info("GraphStore closed.")

    def _execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a Cypher query with parameters.

        Args:
            query: Cypher query string.
            params: Query parameters dict.

        Returns:
            KùzuDB QueryResult.

        Raises:
            RuntimeError: If not connected or query fails.
        """
        if not self._connected or self._conn is None:
            raise RuntimeError("GraphStore is not connected. Call connect() first.")
        try:
            if params:
                return self._conn.execute(query, params)
            return self._conn.execute(query)
        except Exception as e:
            logger.error("Query failed: %s | Params: %s | Error: %s", query[:100], params, e)
            raise

    # -----------------------------------------------------------------------
    # DEDUP operations
    # -----------------------------------------------------------------------

    def is_seen(self, job_id: str) -> bool:
        """Check if a job has been recorded in the graph.

        Args:
            job_id: LinkedIn job ID.

        Returns:
            True if the job exists in the graph, False otherwise.
        """
        if not self._connected:
            return False
        try:
            result = self._execute(DEDUP.IS_SEEN, {"job_id": job_id})
            return result.has_next()
        except Exception as e:
            logger.debug("is_seen check failed for %s: %s", job_id, e)
            return False

    # -----------------------------------------------------------------------
    # DISCOVERY operations
    # -----------------------------------------------------------------------

    def mark_discovered(self, job: dict[str, Any], run_id: str) -> None:
        """Record a newly discovered job in the graph.

        Creates the Job node, Company node (if needed), AT_COMPANY edge,
        and links the job to the current Run.

        Args:
            job: Job data dict with keys: id, title, company, location,
                 posting_url, is_easy_apply, match_score, description.
            run_id: ID of the current agent run.
        """
        if not self._connected:
            return

        job_id = str(job.get("id", job.get("job_id", "")))
        company_name = job.get("company", "Unknown")
        company_id = _normalize_company_id(company_name)

        try:
            # Create job node
            self._execute(DISCOVERY.CREATE_JOB, {
                "job_id": job_id,
                "title": job.get("title", ""),
                "description": job.get("description", ""),
                "location": job.get("location", ""),
                "posting_url": job.get("posting_url", job.get("url", "")),
                "is_easy_apply": bool(job.get("is_easy_apply", False)),
                "match_score": float(job.get("match_score", 0.0)),
            })

            # Upsert company
            self._execute(DISCOVERY.UPSERT_COMPANY, {
                "company_id": company_id,
                "name": company_name,
                "industry": job.get("industry", ""),
            })

            # Link job → company
            self._execute(DISCOVERY.LINK_JOB_COMPANY, {
                "job_id": job_id,
                "company_id": company_id,
            })

            # Link run → job
            if run_id:
                self._execute(DISCOVERY.LINK_RUN_JOB, {
                    "run_id": run_id,
                    "job_id": job_id,
                })

            logger.debug("Marked discovered: %s at %s", job_id, company_name)
        except Exception as e:
            logger.warning("Failed to mark_discovered for job %s: %s", job_id, e)

    # -----------------------------------------------------------------------
    # APPLICATION operations
    # -----------------------------------------------------------------------

    def mark_applied(self, job_id: str, method: str = "easy_apply", resume: str = "") -> None:
        """Record that the candidate applied to a job.

        Updates the Job status and creates an Application node with
        APPLIED_TO relationship.

        Args:
            job_id: LinkedIn job ID.
            method: Application method (easy_apply, external, manual).
            resume: Filename of the resume used.
        """
        if not self._connected:
            return

        application_id = _generate_id()
        try:
            # Update job status
            self._execute(
                "MATCH (j:Job {id: $job_id}) SET j.status = 'applied' RETURN j.id",
                {"job_id": job_id},
            )

            # Create application node
            self._execute(
                """CREATE (a:Application {
                    id: $app_id, method: $method, resume_used: $resume,
                    applied_at: timestamp(), status: 'submitted'
                }) RETURN a.id""",
                {"app_id": application_id, "method": method, "resume": resume},
            )

            # Create APPLIED_TO edge (Candidate → Job)
            # Uses a default candidate node (created on first use)
            self._execute(
                """MATCH (c:Candidate), (j:Job {id: $job_id})
                   CREATE (c)-[:APPLIED_TO {
                       application_id: $app_id,
                       applied_at: timestamp(),
                       method: $method,
                       resume_used: $resume
                   }]->(j)""",
                {"job_id": job_id, "app_id": application_id, "method": method, "resume": resume},
            )

            logger.debug("Marked applied: %s via %s", job_id, method)
        except Exception as e:
            logger.warning("Failed to mark_applied for job %s: %s", job_id, e)

    # -----------------------------------------------------------------------
    # SCORING operations
    # -----------------------------------------------------------------------

    def get_company_context(self, company: str) -> dict[str, Any]:
        """Get intelligence about a company from the graph.

        Returns past jobs, recruiters, target/blocklist status, and
        score adjustment.

        Args:
            company: Company name.

        Returns:
            Dict with company context or empty dict if not found.
        """
        if not self._connected:
            return {}

        try:
            result = self._execute(SCORING.GET_COMPANY_CONTEXT, {"company_name": company})
            if result.has_next():
                row = result.get_next()
                return {
                    "name": row[0],
                    "industry": row[1],
                    "is_target": row[2],
                    "is_blocklisted": row[3],
                    "score_adjustment": row[4],
                    "past_jobs": row[5] or [],
                    "recruiters": row[6] or [],
                }
            return {}
        except Exception as e:
            logger.debug("get_company_context failed for %s: %s", company, e)
            return {}

    def compute_score_adjustment(self, company: str) -> float:
        """Compute the score adjustment for a company.

        Checks target/blocklist status and historical performance.

        Args:
            company: Company name.

        Returns:
            Score adjustment value (positive = boost, negative = penalty).
        """
        if not self._connected:
            return 0.0

        company_id = _normalize_company_id(company)
        try:
            result = self._execute(SCORING.GET_COMPANY_ADJUSTMENT, {"company_id": company_id})
            if result.has_next():
                row = result.get_next()
                adjustment = float(row[0] or 0.0)
                is_target = bool(row[1])
                is_blocklisted = bool(row[2])

                if is_target and adjustment == 0.0:
                    return 0.15  # Default target boost
                if is_blocklisted and adjustment == 0.0:
                    return -0.20  # Default blocklist penalty
                return adjustment
            return 0.0
        except Exception as e:
            logger.debug("compute_score_adjustment failed for %s: %s", company, e)
            return 0.0

    # -----------------------------------------------------------------------
    # SIMILARITY operations
    # -----------------------------------------------------------------------

    def get_similar_jobs(self, job_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Find jobs similar to the given job.

        Uses explicit SIMILAR_TO edges (precomputed) and shared skills.

        Args:
            job_id: LinkedIn job ID.
            limit: Maximum number of similar jobs to return.

        Returns:
            List of dicts with similar job info.
        """
        if not self._connected:
            return []

        try:
            result = self._execute(SIMILARITY.GET_SIMILAR_JOBS, {
                "job_id": job_id,
                "limit": limit,
            })
            similar = []
            while result.has_next():
                row = result.get_next()
                similar.append({
                    "id": row[0],
                    "title": row[1],
                    "location": row[2],
                    "similarity_score": row[3],
                })
            return similar
        except Exception as e:
            logger.debug("get_similar_jobs failed for %s: %s", job_id, e)
            return []

    # -----------------------------------------------------------------------
    # PROMPT operations
    # -----------------------------------------------------------------------

    def store_prompt(
        self,
        prompt_type: str,
        input_text: str,
        output_text: str,
        tokens_used: int = 0,
        model: str = "",
    ) -> str:
        """Store an LLM prompt/response pair in the graph.

        Enables caching, cost tracking, and audit trail for AI usage.

        Args:
            prompt_type: Category (cover_letter, answer, inmail, summary).
            input_text: The input/prompt sent to the LLM.
            output_text: The LLM response.
            tokens_used: Total tokens consumed.
            model: Model identifier used.

        Returns:
            The generated prompt node ID, or empty string on failure.
        """
        if not self._connected:
            return ""

        prompt_id = _generate_id()
        input_hash = _hash_text(input_text)

        try:
            self._execute(PROMPTS.STORE_PROMPT, {
                "prompt_id": prompt_id,
                "prompt_type": prompt_type,
                "input_text": input_text,
                "input_hash": input_hash,
                "output_text": output_text,
                "model": model,
                "tokens_used": tokens_used,
            })
            logger.debug("Stored prompt %s (type=%s, tokens=%d)", prompt_id, prompt_type, tokens_used)
            return prompt_id
        except Exception as e:
            logger.warning("Failed to store prompt: %s", e)
            return ""

    def get_cached_prompt(self, prompt_type: str, input_hash: str) -> Optional[str]:
        """Retrieve a cached LLM response by type and input hash.

        Args:
            prompt_type: Category of prompt.
            input_hash: SHA-256 hash of the input text (first 32 chars).

        Returns:
            Cached output text if found, None otherwise.
        """
        if not self._connected:
            return None

        try:
            result = self._execute(PROMPTS.GET_CACHED_PROMPT, {
                "prompt_type": prompt_type,
                "input_hash": input_hash,
            })
            if result.has_next():
                row = result.get_next()
                return row[0]
            return None
        except Exception as e:
            logger.debug("get_cached_prompt failed: %s", e)
            return None

    # -----------------------------------------------------------------------
    # EMBEDDING operations
    # -----------------------------------------------------------------------

    def store_embedding(
        self,
        node_type: str,
        node_id: str,
        embedding_vector: list[float],
    ) -> None:
        """Store an embedding vector on a Job or Skill node.

        Args:
            node_type: 'Job' or 'Skill'.
            node_id: The node's ID.
            embedding_vector: Float list representing the embedding.
        """
        if not self._connected:
            return

        if node_type not in ("Job", "Skill"):
            logger.warning("store_embedding: unsupported node_type %s", node_type)
            return

        query = SIMILARITY.STORE_EMBEDDING.format(node_type=node_type)
        try:
            self._execute(query, {"node_id": node_id, "embedding": embedding_vector})
            logger.debug("Stored embedding for %s:%s (%d dims)", node_type, node_id, len(embedding_vector))
        except Exception as e:
            logger.warning("Failed to store embedding for %s:%s: %s", node_type, node_id, e)

    def find_similar_by_embedding(
        self,
        embedding: list[float],
        node_type: str = "Job",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find nodes with similar embeddings via cosine similarity.

        Performs in-memory cosine similarity computation against all
        nodes of the given type that have embeddings. For large-scale
        usage, consider an external vector index.

        Args:
            embedding: Query embedding vector.
            node_type: 'Job' or 'Skill'.
            limit: Maximum results to return.

        Returns:
            List of dicts with node info and similarity scores, sorted desc.
        """
        if not self._connected:
            return []

        if node_type not in ("Job", "Skill"):
            return []

        try:
            # Fetch all embeddings for the given type
            query = f"MATCH (n:{node_type}) WHERE n.embedding IS NOT NULL RETURN n.id, n.embedding"
            if node_type == "Job":
                query = f"MATCH (n:{node_type}) WHERE n.embedding IS NOT NULL RETURN n.id, n.title, n.embedding"

            result = self._execute(query)
            candidates = []

            while result.has_next():
                row = result.get_next()
                if node_type == "Job":
                    node_id, title, node_emb = row[0], row[1], row[2]
                else:
                    node_id, node_emb = row[0], row[1]
                    title = ""

                if node_emb and len(node_emb) == len(embedding):
                    score = self._cosine_similarity(embedding, node_emb)
                    candidates.append({"id": node_id, "title": title, "similarity": score})

            # Sort by similarity descending
            candidates.sort(key=lambda x: x["similarity"], reverse=True)
            return candidates[:limit]
        except Exception as e:
            logger.debug("find_similar_by_embedding failed: %s", e)
            return []

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        magnitude_a = sum(a * a for a in vec_a) ** 0.5
        magnitude_b = sum(b * b for b in vec_b) ** 0.5
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        return dot_product / (magnitude_a * magnitude_b)


# ---------------------------------------------------------------------------
# NoOpGraphStore — Stub for when graph is disabled
# ---------------------------------------------------------------------------


class NoOpGraphStore:
    """No-op graph store stub used when the graph feature is disabled.

    All methods return safe defaults without performing any operations.
    This allows the rest of the application to call graph methods without
    checking if the graph is enabled.
    """

    @property
    def connected(self) -> bool:
        return False

    def connect(self) -> None:
        """No-op."""

    def close(self) -> None:
        """No-op."""

    def is_seen(self, job_id: str) -> bool:
        return False

    def mark_discovered(self, job: dict[str, Any], run_id: str) -> None:
        """No-op."""

    def mark_applied(self, job_id: str, method: str = "easy_apply", resume: str = "") -> None:
        """No-op."""

    def get_company_context(self, company: str) -> dict[str, Any]:
        return {}

    def get_similar_jobs(self, job_id: str, limit: int = 10) -> list[dict[str, Any]]:
        return []

    def compute_score_adjustment(self, company: str) -> float:
        return 0.0

    def store_prompt(
        self,
        prompt_type: str,
        input_text: str,
        output_text: str,
        tokens_used: int = 0,
        model: str = "",
    ) -> str:
        return ""

    def get_cached_prompt(self, prompt_type: str, input_hash: str) -> Optional[str]:
        return None

    def store_embedding(
        self,
        node_type: str,
        node_id: str,
        embedding_vector: list[float],
    ) -> None:
        """No-op."""

    def find_similar_by_embedding(
        self,
        embedding: list[float],
        node_type: str = "Job",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return []
