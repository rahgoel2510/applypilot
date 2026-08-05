"""File security and cleanup utilities for ApplyPilot.

Handles:
- Screenshot auto-deletion after configurable TTL (default 24h)
- File permission hardening on sensitive directories
- Startup cleanup of expired temporary files
"""

import logging
import os
import stat
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCREENSHOT_TTL_HOURS = int(os.environ.get("SCREENSHOT_TTL_HOURS", "24"))

# Directories that should have restricted permissions
_SENSITIVE_DIRS = [
    Path.home() / "Library" / "Application Support" / "linkedin_agent" / "browser_data",
    Path.home() / ".local" / "share" / "linkedin_agent" / "browser_data",
    Path.home() / ".linkedin_agent",
]


# ---------------------------------------------------------------------------
# Screenshot Cleanup
# ---------------------------------------------------------------------------


def cleanup_expired_screenshots(screenshots_dir: Path, ttl_hours: int = SCREENSHOT_TTL_HOURS) -> int:
    """Delete screenshot files older than TTL.
    
    Args:
        screenshots_dir: Path to the screenshots directory.
        ttl_hours: Maximum age in hours before deletion.
    
    Returns:
        Number of files deleted.
    """
    if not screenshots_dir.exists():
        return 0

    cutoff = time.time() - (ttl_hours * 3600)
    deleted = 0

    for file_path in screenshots_dir.iterdir():
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        try:
            if file_path.stat().st_mtime < cutoff:
                file_path.unlink()
                deleted += 1
                logger.info("Deleted expired screenshot: %s", file_path.name)
        except OSError as e:
            logger.warning("Failed to delete screenshot %s: %s", file_path.name, e)

    if deleted:
        logger.info("Screenshot cleanup: removed %d expired file(s)", deleted)
    return deleted


# ---------------------------------------------------------------------------
# File Permission Hardening
# ---------------------------------------------------------------------------


def harden_directory_permissions(directory: Path, mode: int = 0o700) -> bool:
    """Set restrictive permissions on a directory.
    
    Args:
        directory: Path to the directory to harden.
        mode: Unix permission mode (default 0700 = owner only).
    
    Returns:
        True if permissions were set successfully.
    """
    if not directory.exists():
        return False

    try:
        os.chmod(directory, mode)
        logger.debug("Set permissions %o on %s", mode, directory)
        return True
    except OSError as e:
        logger.warning("Failed to set permissions on %s: %s", directory, e)
        return False


def harden_file_permissions(file_path: Path, mode: int = 0o600) -> bool:
    """Set restrictive permissions on a file (owner read/write only).
    
    Args:
        file_path: Path to the file.
        mode: Unix permission mode (default 0600 = owner read/write only).
    
    Returns:
        True if permissions were set successfully.
    """
    if not file_path.exists():
        return False

    try:
        os.chmod(file_path, mode)
        return True
    except OSError as e:
        logger.warning("Failed to set permissions on %s: %s", file_path, e)
        return False


def harden_sensitive_directories() -> int:
    """Apply restrictive permissions to all known sensitive directories.
    
    Returns:
        Number of directories successfully hardened.
    """
    hardened = 0
    for dir_path in _SENSITIVE_DIRS:
        if dir_path.exists():
            if harden_directory_permissions(dir_path):
                hardened += 1
    
    # Also harden .env file if it exists
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        harden_file_permissions(env_file, 0o600)
        hardened += 1

    if hardened:
        logger.info("File security: hardened %d sensitive path(s)", hardened)
    return hardened


# ---------------------------------------------------------------------------
# Startup Routine
# ---------------------------------------------------------------------------


def run_startup_security() -> None:
    """Run all file security measures on application startup.
    
    Call this during agent initialization.
    """
    project_root = Path(__file__).resolve().parent.parent
    screenshots_dir = project_root / "screenshots"
    
    # Clean up old screenshots
    cleanup_expired_screenshots(screenshots_dir)
    
    # Harden sensitive directories
    harden_sensitive_directories()
    
    logger.info("File security startup checks complete")
