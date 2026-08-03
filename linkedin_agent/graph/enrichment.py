"""Graph enrichment functions — async LLM and embedding operations.

Provides utilities to extract skills from job descriptions, compute
semantic similarity between jobs, generate summaries, and produce
embedding vectors for graph-based search.

All functions are async and call external LLM/embedding APIs via
OpenRouter (compatible with OpenAI API format).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"

# Default models (can be overridden via env)
DEFAULT_CHAT_MODEL = os.environ.get("GRAPH_CHAT_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
DEFAULT_EMBEDDING_MODEL = os.environ.get("GRAPH_EMBEDDING_MODEL", "thenlper/gte-base")

# Timeout for API calls
API_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_api_key() -> str:
    """Get the OpenRouter/OpenAI API key from environment."""
    return os.environ.get("OPENAI_API_KEY", "")


def _get_headers() -> dict[str, str]:
    """Build request headers for OpenRouter API."""
    return {
        "Authorization": f"Bearer {_get_api_key()}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/rahgoel2510/applypilot",
        "X-Title": "ApplyPilot",
    }


def _hash_text(text: str) -> str:
    """Generate a consistent hash for text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Skill extraction
# ---------------------------------------------------------------------------

SKILL_EXTRACTION_PROMPT = """Extract technical and professional skills from this job description.
Return ONLY a JSON array of skill strings. No explanations, no markdown.

Example output: ["python", "kubernetes", "system design", "team leadership"]

Job description:
{text}"""


async def extract_skills_from_jd(text: str) -> list[str]:
    """Extract skills from a job description using an LLM.

    Args:
        text: Raw job description text.

    Returns:
        List of skill strings extracted from the JD.
        Returns empty list on failure.
    """
    if not text or not _get_api_key():
        return []

    # Truncate very long descriptions to stay within token limits
    truncated = text[:4000] if len(text) > 4000 else text

    payload = {
        "model": DEFAULT_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": "You extract skills from job descriptions. Respond only with a JSON array."},
            {"role": "user", "content": SKILL_EXTRACTION_PROMPT.format(text=truncated)},
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(OPENROUTER_URL, json=payload, headers=_get_headers())
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Parse JSON array from response
        # Handle cases where model wraps in markdown code block
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        skills = json.loads(content)
        if isinstance(skills, list):
            return [str(s).strip().lower() for s in skills if s]
        return []
    except json.JSONDecodeError as e:
        logger.debug("Failed to parse skills JSON: %s", e)
        return []
    except httpx.HTTPStatusError as e:
        logger.warning("Skill extraction API error (%d): %s", e.response.status_code, e)
        return []
    except Exception as e:
        logger.warning("Skill extraction failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Similarity computation
# ---------------------------------------------------------------------------


async def compute_similarity(job_a: dict[str, Any], job_b: dict[str, Any]) -> float:
    """Compute semantic similarity between two jobs.

    Uses embeddings if available, falls back to LLM-based comparison.

    Args:
        job_a: First job dict with 'title', 'description', 'location'.
        job_b: Second job dict with same keys.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    # If both have embeddings, use cosine similarity directly
    emb_a = job_a.get("embedding")
    emb_b = job_b.get("embedding")

    if emb_a and emb_b and len(emb_a) == len(emb_b):
        return _cosine_similarity(emb_a, emb_b)

    # Fall back to generating embeddings on the fly
    text_a = f"{job_a.get('title', '')} {job_a.get('description', '')[:500]}"
    text_b = f"{job_b.get('title', '')} {job_b.get('description', '')[:500]}"

    emb_a_new = await get_embedding(text_a)
    emb_b_new = await get_embedding(text_b)

    if emb_a_new and emb_b_new:
        return _cosine_similarity(emb_a_new, emb_b_new)

    # Final fallback: keyword overlap
    return _keyword_overlap_score(
        f"{job_a.get('title', '')} {job_a.get('description', '')}",
        f"{job_b.get('title', '')} {job_b.get('description', '')}",
    )


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = sum(a * a for a in vec_a) ** 0.5
    magnitude_b = sum(b * b for b in vec_b) ** 0.5
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)


def _keyword_overlap_score(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity based on keyword overlap."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# JD summary generation
# ---------------------------------------------------------------------------

SUMMARY_PROMPT = """Summarize this job description in 2-3 concise sentences.
Focus on: role level, key responsibilities, must-have skills, and team/product context.

Job description:
{text}"""


async def generate_jd_summary(text: str) -> str:
    """Generate a concise summary of a job description.

    Args:
        text: Raw job description text.

    Returns:
        2-3 sentence summary, or empty string on failure.
    """
    if not text or not _get_api_key():
        return ""

    truncated = text[:4000] if len(text) > 4000 else text

    payload = {
        "model": DEFAULT_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": "You summarize job descriptions concisely."},
            {"role": "user", "content": SUMMARY_PROMPT.format(text=truncated)},
        ],
        "temperature": 0.3,
        "max_tokens": 200,
    }

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(OPENROUTER_URL, json=payload, headers=_get_headers())
            response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        logger.warning("JD summary API error (%d): %s", e.response.status_code, e)
        return ""
    except Exception as e:
        logger.warning("JD summary generation failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------


async def get_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text.

    Uses the configured embedding model via OpenRouter/OpenAI-compatible API.

    Args:
        text: Input text to embed.

    Returns:
        List of floats representing the embedding vector.
        Returns empty list on failure.
    """
    if not text or not _get_api_key():
        return []

    # Truncate to reasonable length for embedding models
    truncated = text[:8000] if len(text) > 8000 else text

    payload = {
        "model": DEFAULT_EMBEDDING_MODEL,
        "input": truncated,
    }

    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.post(EMBEDDING_URL, json=payload, headers=_get_headers())
            response.raise_for_status()

        data = response.json()
        embedding = data["data"][0]["embedding"]
        if isinstance(embedding, list):
            return embedding
        return []
    except httpx.HTTPStatusError as e:
        logger.warning("Embedding API error (%d): %s", e.response.status_code, e)
        return []
    except (KeyError, IndexError) as e:
        logger.warning("Unexpected embedding response format: %s", e)
        return []
    except Exception as e:
        logger.warning("Embedding generation failed: %s", e)
        return []
