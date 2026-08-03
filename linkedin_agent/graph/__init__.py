"""Graph module — KùzuDB-backed knowledge graph for ApplyPilot.

Provides graph-powered intelligence: deduplication, company context,
job similarity, LLM prompt caching, and embedding-based search.

Usage:
    from linkedin_agent.graph import get_graph_store
    store = get_graph_store()
    store.mark_discovered(job, run_id)

If the graph feature is disabled (via config or missing kuzu), a
NoOpGraphStore is returned that safely no-ops all calls.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)

# Type alias for the store (either real or no-op)
GraphStoreType = Union["GraphStore", "NoOpGraphStore"]

# Singleton instance
_graph_store: GraphStoreType | None = None


def get_graph_store(*, force_reload: bool = False) -> GraphStoreType:
    """Factory function to get the graph store singleton.

    Returns a GraphStore if:
    - kuzu is installed
    - GRAPH_ENABLED env var is not explicitly "false" / "0"
    - Connection succeeds

    Otherwise returns a NoOpGraphStore that safely no-ops all calls.

    Args:
        force_reload: If True, discards existing instance and reconnects.

    Returns:
        GraphStore or NoOpGraphStore instance.
    """
    global _graph_store  # noqa: PLW0603

    if _graph_store is not None and not force_reload:
        return _graph_store

    # Check if graph is explicitly disabled
    graph_enabled = os.environ.get("GRAPH_ENABLED", "true").lower()
    if graph_enabled in ("false", "0", "no", "off"):
        logger.info("Graph store disabled via GRAPH_ENABLED=%s", graph_enabled)
        from linkedin_agent.graph.store import NoOpGraphStore
        _graph_store = NoOpGraphStore()
        return _graph_store

    # Attempt to import kuzu and connect
    try:
        import kuzu  # noqa: F401
    except ImportError:
        logger.warning(
            "kuzu not installed. Graph features disabled. "
            "Install with: pip install kuzu"
        )
        from linkedin_agent.graph.store import NoOpGraphStore
        _graph_store = NoOpGraphStore()
        return _graph_store

    # Determine database path
    from linkedin_agent.config import PROJECT_ROOT
    db_path = Path(os.environ.get(
        "GRAPH_DB_PATH",
        str(PROJECT_ROOT / "data" / "graph_db"),
    ))

    # Try to connect
    try:
        from linkedin_agent.graph.store import GraphStore
        store = GraphStore(db_path)
        store.connect()
        _graph_store = store
        logger.info("Graph store initialized at %s", db_path)
        return _graph_store
    except Exception as e:
        logger.warning(
            "Graph store initialization failed: %s. "
            "Falling back to NoOpGraphStore.",
            e,
        )
        from linkedin_agent.graph.store import NoOpGraphStore
        _graph_store = NoOpGraphStore()
        return _graph_store


def reset_graph_store() -> None:
    """Reset the graph store singleton (primarily for testing)."""
    global _graph_store  # noqa: PLW0603
    if _graph_store is not None:
        try:
            _graph_store.close()
        except Exception:
            pass
    _graph_store = None


# Lazy re-exports to avoid importing kuzu at module load time
def __getattr__(name: str):
    if name == "GraphStore":
        from linkedin_agent.graph.store import GraphStore
        return GraphStore
    if name == "NoOpGraphStore":
        from linkedin_agent.graph.store import NoOpGraphStore
        return NoOpGraphStore
    raise AttributeError(f"module 'linkedin_agent.graph' has no attribute {name!r}")


__all__ = ["get_graph_store", "reset_graph_store", "GraphStore", "NoOpGraphStore"]
