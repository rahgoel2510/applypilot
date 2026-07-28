"""Smart page parser — hybrid selector + LLM extraction.

Strategy:
1. Try CSS selectors first (fast, free, no API call)
2. If selectors fail → send page text to LLM for extraction
3. Rate-limit aware — tracks usage, backs off when approaching limits

Uses OpenRouter free models with automatic fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

EXTRACTION_PROMPT = """\
You are a data extraction bot. Given raw text from a LinkedIn job page, extract the following fields as JSON.
Return ONLY valid JSON, no explanation.

Fields to extract:
- title: job title (string)
- company: company name (string)
- location: job location (string or null)
- match_score_matched: number of matched qualifications (integer or null)
- match_score_total: total required qualifications (integer or null)
- is_easy_apply: whether "Easy Apply" button is mentioned (boolean)
- is_external: whether "Responses managed off LinkedIn" is mentioned (boolean)
- posted_date: when the job was posted (string like "2 days ago" or null)

If a field cannot be determined, use null. Never guess or hallucinate.
"""


@dataclass
class RateLimitState:
    """Tracks API usage to avoid hitting rate limits."""
    requests_made: int = 0
    requests_limit: int = 20  # Free tier: ~20 requests/min
    window_start: float = field(default_factory=time.time)
    window_seconds: int = 60
    last_error: Optional[str] = None
    consecutive_errors: int = 0

    def can_make_request(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()
        # Reset window
        if now - self.window_start > self.window_seconds:
            self.requests_made = 0
            self.window_start = now
            self.consecutive_errors = 0

        # Back off on consecutive errors
        if self.consecutive_errors >= 3:
            return False

        return self.requests_made < self.requests_limit

    def record_request(self, success: bool = True):
        self.requests_made += 1
        if success:
            self.consecutive_errors = 0
        else:
            self.consecutive_errors += 1

    @property
    def remaining(self) -> int:
        return max(0, self.requests_limit - self.requests_made)


class SmartPageParser:
    """Hybrid page parser — selectors first, LLM fallback.

    Usage:
        parser = SmartPageParser(api_key="sk-or-...")
        data = await parser.extract_job_data(page_text)
    """

    def __init__(self, api_key: str = "", model: str = ""):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model or os.environ.get("AI_MODEL", "openrouter/free")
        self._rate_limit = RateLimitState()
        self._cache: dict[str, dict] = {}  # Simple in-memory cache

    @property
    def rate_limit_info(self) -> dict:
        """Get current rate limit status."""
        return {
            "remaining": self._rate_limit.remaining,
            "used": self._rate_limit.requests_made,
            "limit": self._rate_limit.requests_limit,
            "can_request": self._rate_limit.can_make_request(),
            "errors": self._rate_limit.consecutive_errors,
        }

    def extract_with_selectors(self, page_text: str) -> dict[str, Any]:
        """Try regex/pattern extraction first (fast, no API call).

        Returns dict with extracted fields. None values mean "not found".
        """
        result = {
            "title": None,
            "company": None,
            "location": None,
            "match_score_matched": None,
            "match_score_total": None,
            "is_easy_apply": None,
            "is_external": None,
        }

        # Match score (from LinkedIn AI coach)
        score_patterns = [
            r"[Mm]atches?\s+(\d+)\s+of\s+(?:the\s+)?(\d+)\s+required\s+qualifications?",
            r"[Mm]atches?\s+(\d+)\s+of\s+(?:the\s+)?(\d+)\s+qualifications?",
            r"(\d+)\s+of\s+(?:the\s+)?(\d+)\s+required\s+qualifications?\s+match",
        ]
        for pattern in score_patterns:
            match = re.search(pattern, page_text)
            if match:
                result["match_score_matched"] = int(match.group(1))
                result["match_score_total"] = int(match.group(2))
                break

        # Easy Apply detection
        if "easy apply" in page_text.lower():
            result["is_easy_apply"] = True
        elif "responses managed off linkedin" in page_text.lower():
            result["is_external"] = True
            result["is_easy_apply"] = False

        return result

    async def extract_with_llm(self, page_text: str) -> dict[str, Any]:
        """Use LLM to extract job data from page text.

        Only called when selectors fail. Rate-limit aware.
        """
        if not self._api_key:
            logger.debug("No API key — skipping LLM extraction.")
            return {}

        if not self._rate_limit.can_make_request():
            logger.debug("Rate limit reached — skipping LLM extraction.")
            return {}

        # Truncate page text to fit model context
        # Most free models have 8k-32k context
        max_chars = 4000  # ~1000 tokens
        truncated = page_text[:max_chars]

        # Check cache
        cache_key = truncated[:200]
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": EXTRACTION_PROMPT},
                            {"role": "user", "content": f"Extract from this page:\n\n{truncated}"},
                        ],
                        "temperature": 0,
                        "max_tokens": 300,
                    },
                )

            self._rate_limit.record_request(response.status_code == 200)

            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                # Parse JSON from response
                clean = content.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                parsed = json.loads(clean)
                self._cache[cache_key] = parsed
                logger.info("LLM extracted: %s", {k: v for k, v in parsed.items() if v is not None})
                return parsed
            elif response.status_code == 429:
                self._rate_limit.record_request(False)
                logger.warning("Rate limited by OpenRouter. Backing off.")
                return {}
            else:
                self._rate_limit.record_request(False)
                logger.warning("LLM extraction failed: %d", response.status_code)
                return {}

        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON.")
            return {}
        except Exception as exc:
            self._rate_limit.record_request(False)
            logger.warning("LLM extraction error: %s", exc)
            return {}

    async def extract_job_data(self, page_text: str) -> dict[str, Any]:
        """Hybrid extraction: selectors first, LLM fallback.

        Returns:
            Dict with extracted fields. Values are None if not found.
        """
        # Step 1: Try selectors (fast, free)
        result = self.extract_with_selectors(page_text)

        # Step 2: If key fields missing, try LLM
        missing_critical = (
            result.get("match_score_matched") is None and
            result.get("is_easy_apply") is None
        )

        if missing_critical and self._rate_limit.can_make_request():
            logger.info("Selectors incomplete — using LLM fallback")
            llm_result = await self.extract_with_llm(page_text)

            # Merge: LLM fills gaps, selectors take priority
            for key, value in llm_result.items():
                if result.get(key) is None and value is not None:
                    result[key] = value

        return result


# Module-level singleton
_parser: Optional[SmartPageParser] = None


def get_parser() -> SmartPageParser:
    global _parser
    if _parser is None:
        _parser = SmartPageParser()
    return _parser
