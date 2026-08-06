"""Centralized settings service — single source of truth for all configuration.

Reads from DB first (AppSetting table), falls back to os.environ.
Encrypts sensitive values on write, decrypts on read.

Usage:
    from settings_service import get_setting, get_credential, set_setting
    
    # Get any setting (DB first, env fallback)
    email = get_setting('LINKEDIN_EMAIL')
    
    # Get sensitive credential (auto-decrypts)
    password = get_credential('LINKEDIN_PASSWORD')
    
    # Set a setting (auto-encrypts sensitive fields)
    set_setting('LINKEDIN_PASSWORD', 'new-password')
"""

import os
import sys
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Keys that should be encrypted at rest in the DB
SENSITIVE_KEYS = {
    'LINKEDIN_PASSWORD',
    'TELEGRAM_BOT_TOKEN',
    'OPENAI_API_KEY',
}


def _get_db_session():
    """Get a database session. Returns None if DB is not available."""
    try:
        from database import SessionLocal
        return SessionLocal()
    except Exception:
        return None


def _get_vault():
    """Get the credential vault for encrypt/decrypt. Returns None if unavailable."""
    try:
        # Add the linkedin_agent path if needed
        project_root = Path(__file__).resolve().parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from linkedin_agent.credential_vault import vault
        return vault
    except Exception:
        return None


def get_setting(key: str, default: str = '') -> str:
    """Get a setting value. Checks DB first, then os.environ.
    
    For sensitive keys, auto-decrypts the stored value.
    """
    # Try DB first
    db = _get_db_session()
    if db:
        try:
            from models import AppSetting
            row = db.query(AppSetting).filter(AppSetting.key == key).first()
            if row and row.value:
                value = row.value
                # Decrypt if encrypted
                if key in SENSITIVE_KEYS:
                    vault = _get_vault()
                    if vault and vault.is_encrypted(value):
                        value = vault.decrypt(value)
                return value
        except Exception as e:
            logger.debug(f'DB read failed for {key}: {e}')
        finally:
            db.close()
    
    # Fallback to environment
    return os.environ.get(key, default)


def get_credential(key: str, default: str = '') -> str:
    """Get a sensitive credential. Same as get_setting but explicit about intent."""
    return get_setting(key, default)


def set_setting(key: str, value: str) -> bool:
    """Set a setting in the DB. Encrypts sensitive keys automatically.
    
    Returns True on success, False on failure.
    """
    if not value:
        return False
    
    # Encrypt sensitive values
    store_value = value
    if key in SENSITIVE_KEYS:
        vault = _get_vault()
        if vault:
            store_value = vault.encrypt(value)
    
    db = _get_db_session()
    if not db:
        return False
    
    try:
        from models import AppSetting
        existing = db.query(AppSetting).filter(AppSetting.key == key).first()
        if existing:
            existing.value = store_value
        else:
            db.add(AppSetting(key=key, value=store_value))
        db.commit()
        return True
    except Exception as e:
        logger.error(f'Failed to save setting {key}: {e}')
        db.rollback()
        return False
    finally:
        db.close()


def get_all_settings_as_env() -> dict[str, str]:
    """Get all settings as a flat dict (for passing to subprocess env).
    
    Decrypts all sensitive values.
    """
    result = {}
    db = _get_db_session()
    if not db:
        return result
    
    try:
        from models import AppSetting
        rows = db.query(AppSetting).all()
        vault = _get_vault()
        for row in rows:
            value = row.value or ''
            if row.key in SENSITIVE_KEYS and vault and vault.is_encrypted(value):
                value = vault.decrypt(value)
            result[row.key] = value
    except Exception as e:
        logger.error(f'Failed to read all settings: {e}')
    finally:
        db.close()
    
    return result


def is_configured(key: str) -> bool:
    """Check if a setting has a real (non-placeholder) value."""
    value = get_setting(key)
    if not value:
        return False
    placeholders = {'your', 'placeholder', 'example', 'your-email', 'your-password', 'sk-or-v1-your'}
    return not any(p in value.lower() for p in placeholders)
