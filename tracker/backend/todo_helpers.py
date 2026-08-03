"""Helper functions for automatic TODO creation by the agent.

These write directly to the database (no HTTP round-trip needed).
"""

import json
from datetime import datetime

from database import SessionLocal
from models import Todo, TodoPriority


def _create_todo(
    title: str,
    category: str,
    priority: TodoPriority = TodoPriority.medium,
    description: str | None = None,
    job_id: str | None = None,
    job_title: str | None = None,
    company: str | None = None,
    action_url: str | None = None,
    metadata_json: str | None = None,
) -> Todo:
    """Internal helper — creates a Todo record in the database."""
    db = SessionLocal()
    try:
        todo = Todo(
            title=title,
            description=description,
            category=category,
            priority=priority,
            job_id=job_id,
            job_title=job_title,
            company=company,
            action_url=action_url,
            metadata_json=metadata_json,
        )
        db.add(todo)
        db.commit()
        db.refresh(todo)
        return todo
    finally:
        db.close()


def create_external_apply_todo(
    job_title: str, company: str, url: str, score: float
) -> Todo:
    """Creates a TODO when an external job with a high score is found.

    The user needs to apply manually via the external link.
    """
    priority = TodoPriority.high if score >= 0.85 else TodoPriority.medium
    return _create_todo(
        title=f"Apply externally: {job_title} at {company}",
        description=(
            f"This job scored {score:.0%} but requires external application. "
            f"Click the link to apply on the company's website."
        ),
        category="external_apply",
        priority=priority,
        job_title=job_title,
        company=company,
        action_url=url,
        metadata_json=json.dumps({"score": score}),
    )


def create_inmail_review_todo(
    job_title: str, company: str, recruiter: str
) -> Todo:
    """Creates a TODO to review an AI-generated InMail draft before sending."""
    return _create_todo(
        title=f"Review InMail to {recruiter} ({company})",
        description=(
            f"An InMail draft for '{job_title}' at {company} has been generated. "
            f"Please review it in the InMail section before sending."
        ),
        category="review_inmail",
        priority=TodoPriority.medium,
        job_title=job_title,
        company=company,
        metadata_json=json.dumps({"recruiter": recruiter}),
    )


def create_skill_gap_todo(skill_name: str, demanded_count: int) -> Todo:
    """Creates a TODO suggesting the user add a skill to their profile.

    Triggered when multiple high-scoring jobs require a skill not on the resume.
    """
    return _create_todo(
        title=f"Add skill: {skill_name}",
        description=(
            f"'{skill_name}' appeared in {demanded_count} high-scoring jobs "
            f"but isn't listed on your resume. Consider adding it if applicable."
        ),
        category="skill_gap",
        priority=TodoPriority.low,
        metadata_json=json.dumps(
            {"skill": skill_name, "demanded_count": demanded_count}
        ),
    )


def create_session_refresh_todo() -> Todo:
    """Creates a TODO when the LinkedIn session is expiring or has expired.

    The user needs to log in manually to refresh the session cookie.
    """
    return _create_todo(
        title="Refresh LinkedIn session",
        description=(
            "Your LinkedIn session has expired or is about to expire. "
            "Please log in manually in the browser to refresh the cookie."
        ),
        category="session_refresh",
        priority=TodoPriority.high,
    )
