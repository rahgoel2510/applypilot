"""PII redaction utilities for sanitizing data before sending to third-party AI services."""

import re

# Patterns for common PII
_EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_PHONE_PATTERN = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}')
_URL_PATTERN = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')


def redact_email(text: str) -> str:
    """Replace email addresses with placeholder."""
    return _EMAIL_PATTERN.sub('[email redacted]', text)


def redact_phone(text: str) -> str:
    """Replace phone numbers with placeholder."""
    return _PHONE_PATTERN.sub('[phone redacted]', text)


def redact_pii(text: str) -> str:
    """Remove common PII patterns from text before sending to AI."""
    text = redact_email(text)
    text = redact_phone(text)
    return text


def safe_candidate_context(
    name: str | None = None,
    skills: list[str] | None = None,
    notice_period: str | None = None,
    experience_years: str | None = None,
    willing_to_relocate: bool | None = None,
) -> str:
    """Build a privacy-safe candidate description for AI prompts.

    Includes only what the AI needs to generate contextual responses.
    Excludes: email, phone, address, DOB, salary details.
    """
    parts = []
    if name:
        parts.append(f"Candidate: {name}")
    if skills:
        parts.append(f"Key skills: {', '.join(skills[:10])}")
    if notice_period:
        parts.append(f"Notice period: {notice_period}")
    if experience_years:
        parts.append(f"Experience: {experience_years}")
    if willing_to_relocate is not None:
        parts.append(f"Willing to relocate: {'Yes' if willing_to_relocate else 'No'}")
    return " | ".join(parts) if parts else "Job applicant"
