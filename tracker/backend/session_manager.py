"""Session management with token rotation and expiry cleanup."""

import secrets
import time
from typing import Optional


class SessionManager:
    """In-memory session store with configurable TTL and automatic rotation."""

    def __init__(self, ttl_seconds: int = 86400):
        """
        Args:
            ttl_seconds: Session time-to-live in seconds (default 24h).
        """
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, dict] = {}

    def create_session(self, user_id: str = "default") -> str:
        """Create a new session and return the token.

        Args:
            user_id: Identifier for the session owner.

        Returns:
            A secure random token string.
        """
        self.cleanup_expired()
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._sessions[token] = {
            "created_at": now,
            "last_active": now,
            "expires_at": now + self.ttl_seconds,
            "user_id": user_id,
        }
        return token

    def validate_session(self, token: str) -> bool:
        """Check if a token corresponds to a valid, non-expired session.

        Args:
            token: The session token to validate.

        Returns:
            True if the session exists and has not expired.
        """
        self.cleanup_expired()
        session = self._sessions.get(token)
        if session is None:
            return False
        if time.time() > session["expires_at"]:
            del self._sessions[token]
            return False
        session["last_active"] = time.time()
        return True

    def rotate_if_needed(self, token: str) -> Optional[str]:
        """Rotate the session token if more than 50% of the TTL has elapsed.

        Issues a new token, migrates session data, and invalidates the old one.

        Args:
            token: The current session token.

        Returns:
            A new token string if rotation occurred, otherwise None.
        """
        session = self._sessions.get(token)
        if session is None:
            return None

        now = time.time()
        elapsed = now - session["created_at"]

        if elapsed < (self.ttl_seconds * 0.5):
            return None

        # Issue new token with refreshed expiry
        new_token = secrets.token_urlsafe(32)
        self._sessions[new_token] = {
            "created_at": now,
            "last_active": now,
            "expires_at": now + self.ttl_seconds,
            "user_id": session["user_id"],
        }

        # Invalidate old token
        del self._sessions[token]
        return new_token

    def cleanup_expired(self) -> int:
        """Remove all expired sessions from the store.

        Returns:
            Number of sessions removed.
        """
        now = time.time()
        expired_tokens = [
            token
            for token, session in self._sessions.items()
            if now > session["expires_at"]
        ]
        for token in expired_tokens:
            del self._sessions[token]
        return len(expired_tokens)

    @property
    def active_count(self) -> int:
        """Return the number of currently active (non-expired) sessions."""
        self.cleanup_expired()
        return len(self._sessions)


# Module-level singleton for convenience
session_manager = SessionManager()
