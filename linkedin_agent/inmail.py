"""InMail drafting module for LinkedIn Job Agent.

Uses OpenAI API to generate personalized InMail messages to recruiters
and job posters. Caches drafts to avoid re-generation and falls back
to templates if the API is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError

from linkedin_agent.config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DRAFTS_DIR = Path.home() / ".linkedin_agent"
DRAFTS_FILE = DRAFTS_DIR / "inmail_drafts.json"

SYSTEM_PROMPT_INMAIL = """\
You draft brief, personalized LinkedIn InMail messages on behalf of a job seeker.

Tone: Professional, enthusiastic but not overly eager. Human and conversational.

Structure:
1. Hook — one sentence explaining why you're reaching out (mention the specific role).
2. Brief value prop — 2-3 sentences on what makes the candidate a strong fit (use specifics from the job description and candidate background).
3. Soft CTA — a low-pressure ask (e.g., "Would you be open to a quick chat?" or "Happy to share more details if helpful").

Constraints:
- Do NOT use "I hope this message finds you well" or any generic openers.
- Do NOT use filler phrases or corporate buzzwords.
- Be specific — reference the job title, company, and concrete skills.
- Keep it concise — every sentence must earn its place.
- Write in first person as the candidate.
- Do NOT include a subject line — just the message body.
- End with the candidate's first name only.
"""

SYSTEM_PROMPT_CONNECTION = """\
You write ultra-short LinkedIn connection request notes (max 300 characters).

Rules:
- Mention the specific job title and company.
- One sentence: why you're connecting.
- Friendly but professional.
- No generic "I'd love to connect" — be specific.
- Do NOT exceed 300 characters total.
"""

# ---------------------------------------------------------------------------
# Fallback templates (used when OpenAI API is unavailable)
# ---------------------------------------------------------------------------

FALLBACK_INMAIL_TEMPLATE = """\
Hi {recruiter_name},

I came across the {job_title} role at {company} and it immediately stood out — \
the work aligns closely with my background in this space.

{value_prop}

Would you be open to a brief conversation about the role? I'd love to learn more \
about the team's priorities and share how my experience could contribute.

Best,
{candidate_first_name}"""

FALLBACK_CONNECTION_TEMPLATE = (
    "Hi {recruiter_name} — saw the {job_title} opening at {company} and "
    "would love to connect. My background seems like a strong fit!"
)


# ---------------------------------------------------------------------------
# InMailDrafter class
# ---------------------------------------------------------------------------


class InMailDrafter:
    """Generates personalized InMail messages using OpenAI."""

    def __init__(self, config: Settings) -> None:
        """Initialize with application settings.

        Args:
            config: The application Settings instance (from get_config()).
        """
        self._config = config
        self._client = AsyncOpenAI(api_key=config.openai_api_key)
        self._model = "gpt-4o-mini"
        self._max_length = config.inmail.max_length  # word limit
        self._tone = config.inmail.tone
        self._cache: dict[str, dict[str, Any]] = {}
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def draft_inmail(
        self,
        job_title: str,
        company: str,
        recruiter_name: str,
        job_description: str,
        candidate_summary: str,
    ) -> str:
        """Generate a personalized InMail message.

        Args:
            job_title: The role being applied to.
            company: The hiring company.
            recruiter_name: Name of the recruiter/poster.
            job_description: Full or summarized JD text.
            candidate_summary: Brief summary of the candidate's background.

        Returns:
            A ready-to-send InMail message string.
        """
        cache_key = self._cache_key(job_title, company, recruiter_name)

        # Return cached draft if available
        if cache_key in self._cache:
            logger.info("Using cached InMail draft for %s at %s", job_title, company)
            return self._cache[cache_key]["draft"]

        # Build the user prompt
        user_prompt = self._build_inmail_prompt(
            job_title, company, recruiter_name, job_description, candidate_summary
        )

        draft = await self._generate(
            system_prompt=SYSTEM_PROMPT_INMAIL,
            user_prompt=user_prompt,
            fallback=self._fallback_inmail(job_title, company, recruiter_name, candidate_summary),
        )

        # Cache and persist
        self._cache[cache_key] = {
            "draft": draft,
            "job_title": job_title,
            "company": company,
            "recruiter_name": recruiter_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "inmail",
        }
        self._save_cache()

        return draft

    async def draft_connection_note(
        self,
        recruiter_name: str,
        job_title: str,
        company: str,
    ) -> str:
        """Generate a short connection request note (max 300 chars).

        Args:
            recruiter_name: Name of the person to connect with.
            job_title: The role of interest.
            company: The hiring company.

        Returns:
            A connection note string, guaranteed ≤ 300 characters.
        """
        cache_key = self._cache_key(f"conn_{job_title}", company, recruiter_name)

        if cache_key in self._cache:
            logger.info("Using cached connection note for %s at %s", job_title, company)
            return self._cache[cache_key]["draft"]

        candidate_name = self._config.candidate.name.split()[0] if self._config.candidate.name else ""

        user_prompt = (
            f"Write a connection request note to {recruiter_name} about the "
            f"{job_title} role at {company}. "
            f"The candidate's first name is {candidate_name}. "
            f"Must be under 300 characters total."
        )

        fallback = FALLBACK_CONNECTION_TEMPLATE.format(
            recruiter_name=recruiter_name.split()[0],
            job_title=job_title,
            company=company,
        )

        draft = await self._generate(
            system_prompt=SYSTEM_PROMPT_CONNECTION,
            user_prompt=user_prompt,
            fallback=fallback,
        )

        # Enforce 300-char hard limit
        if len(draft) > 300:
            draft = draft[:297] + "..."

        self._cache[cache_key] = {
            "draft": draft,
            "job_title": job_title,
            "company": company,
            "recruiter_name": recruiter_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "type": "connection_note",
        }
        self._save_cache()

        return draft

    def get_candidate_summary(self) -> str:
        """Build a brief candidate summary from config profile.

        Returns:
            A concise string summarizing the candidate's background.
        """
        c = self._config.candidate
        parts: list[str] = []

        if c.name:
            parts.append(f"Name: {c.name}")
        if c.email:
            parts.append(f"Email: {c.email}")
        if c.phone:
            parts.append(f"Phone: {c.phone}")
        if c.notice_period:
            parts.append(f"Notice period: {c.notice_period}")
        if c.work_authorization:
            parts.append(f"Work authorization: {c.work_authorization}")
        if c.preferred_cities:
            parts.append(f"Preferred locations: {', '.join(c.preferred_cities)}")
        if c.willing_to_relocate:
            parts.append("Open to relocation")

        return " | ".join(parts) if parts else "Experienced professional seeking new opportunities."

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_inmail_prompt(
        self,
        job_title: str,
        company: str,
        recruiter_name: str,
        job_description: str,
        candidate_summary: str,
    ) -> str:
        """Build the user prompt for InMail generation."""
        candidate_first = self._config.candidate.name.split()[0] if self._config.candidate.name else "the candidate"

        return (
            f"Draft an InMail to {recruiter_name} about the {job_title} position at {company}.\n\n"
            f"Job description:\n{job_description[:2000]}\n\n"
            f"Candidate background:\n{candidate_summary}\n\n"
            f"Sign off with just the first name: {candidate_first}\n"
            f"Keep it under {self._max_length} words. Tone: {self._tone}."
        )

    async def _generate(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback: str,
    ) -> str:
        """Call OpenAI API with fallback on failure.

        Args:
            system_prompt: The system message for GPT.
            user_prompt: The user message with specific instructions.
            fallback: Template string to use if API call fails.

        Returns:
            Generated or fallback text.
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=600,
            )
            content = response.choices[0].message.content
            if content:
                logger.info("Successfully generated draft via OpenAI")
                return content.strip()
            else:
                logger.warning("OpenAI returned empty content, using fallback")
                return fallback

        except (APIError, RateLimitError, APIConnectionError) as exc:
            logger.warning("OpenAI API error (%s), using fallback template", exc)
            return fallback
        except Exception as exc:
            logger.error("Unexpected error during OpenAI call: %s", exc)
            return fallback

    def _fallback_inmail(
        self,
        job_title: str,
        company: str,
        recruiter_name: str,
        candidate_summary: str,
    ) -> str:
        """Generate a fallback InMail from template."""
        candidate_first = (
            self._config.candidate.name.split()[0]
            if self._config.candidate.name
            else "Best regards"
        )

        # Extract a brief value prop from candidate summary
        value_prop = candidate_summary[:200] if candidate_summary else (
            "I bring relevant experience and am eager to contribute to your team's goals."
        )

        return FALLBACK_INMAIL_TEMPLATE.format(
            recruiter_name=recruiter_name.split()[0],
            job_title=job_title,
            company=company,
            value_prop=value_prop,
            candidate_first_name=candidate_first,
        )

    @staticmethod
    def _cache_key(job_title: str, company: str, recruiter_name: str) -> str:
        """Generate a deterministic cache key."""
        raw = f"{job_title.lower().strip()}|{company.lower().strip()}|{recruiter_name.lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _load_cache(self) -> None:
        """Load cached drafts from disk."""
        if DRAFTS_FILE.exists():
            try:
                data = json.loads(DRAFTS_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._cache = data
                    logger.info("Loaded %d cached InMail drafts", len(self._cache))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load drafts cache: %s", exc)
                self._cache = {}
        else:
            self._cache = {}

    def _save_cache(self) -> None:
        """Persist drafts cache to disk."""
        try:
            DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
            DRAFTS_FILE.write_text(
                json.dumps(self._cache, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("Saved drafts cache to %s", DRAFTS_FILE)
        except OSError as exc:
            logger.error("Failed to save drafts cache: %s", exc)
