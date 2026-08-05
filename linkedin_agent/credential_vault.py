"""Credential vault — encrypts sensitive values at rest using Fernet.

Uses a master key derived from:
1. APPLYPILOT_MASTER_KEY environment variable (if set), or
2. Auto-generated key file at ~/.linkedin_agent/.vault_key

Encrypted values are prefixed with 'vault:' for identification.

Usage:
    from linkedin_agent.credential_vault import vault
    
    encrypted = vault.encrypt("my-secret-password")
    plaintext = vault.decrypt(encrypted)
    
    # Check if already encrypted
    if vault.is_encrypted(value):
        value = vault.decrypt(value)
"""

import base64
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_ENCRYPTED_PREFIX = "vault:"
_KEY_DIR = Path.home() / ".linkedin_agent"
_KEY_FILE = _KEY_DIR / ".vault_key"
_SALT = b"applypilot-vault-v1"  # Static salt (key is already high entropy)


class CredentialVault:
    """Encrypts and decrypts credential strings using Fernet symmetric encryption."""

    def __init__(self) -> None:
        self._fernet: Fernet | None = None

    def _get_fernet(self) -> Fernet:
        """Lazy-initialize the Fernet instance."""
        if self._fernet is not None:
            return self._fernet

        master_key = self._load_or_generate_key()
        # Derive a proper Fernet key from the master key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_SALT,
            iterations=100_000,
        )
        derived = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        self._fernet = Fernet(derived)
        return self._fernet

    def _load_or_generate_key(self) -> str:
        """Load master key from env or file, generating if needed."""
        # Priority 1: Environment variable
        env_key = os.environ.get("APPLYPILOT_MASTER_KEY", "").strip()
        if env_key:
            return env_key

        # Priority 2: Key file
        if _KEY_FILE.exists():
            return _KEY_FILE.read_text().strip()

        # Generate new key
        _KEY_DIR.mkdir(parents=True, exist_ok=True)
        new_key = Fernet.generate_key().decode()
        _KEY_FILE.write_text(new_key)
        # Restrict file permissions
        try:
            os.chmod(_KEY_FILE, 0o600)
            os.chmod(_KEY_DIR, 0o700)
        except OSError:
            pass  # Windows may not support this
        logger.info("Generated new vault key at %s", _KEY_FILE)
        return new_key

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string. Returns prefixed ciphertext.
        
        If the value is already encrypted (has vault: prefix), returns it unchanged.
        """
        if not plaintext or self.is_encrypted(plaintext):
            return plaintext
        fernet = self._get_fernet()
        token = fernet.encrypt(plaintext.encode())
        return f"{_ENCRYPTED_PREFIX}{token.decode()}"

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a vault-prefixed ciphertext. Returns plaintext.
        
        If the value is not encrypted (no vault: prefix), returns it unchanged.
        """
        if not ciphertext or not self.is_encrypted(ciphertext):
            return ciphertext
        fernet = self._get_fernet()
        token = ciphertext[len(_ENCRYPTED_PREFIX):]
        try:
            return fernet.decrypt(token.encode()).decode()
        except InvalidToken:
            logger.error("Failed to decrypt value (invalid token or wrong key)")
            return ciphertext  # Return as-is rather than crash

    def is_encrypted(self, value: str) -> bool:
        """Check if a value is vault-encrypted (has the prefix marker)."""
        return value.startswith(_ENCRYPTED_PREFIX) if value else False

    def rotate_key(self, new_master_key: str, values: list[str]) -> list[str]:
        """Re-encrypt a list of values with a new master key.
        
        Decrypts with current key, then encrypts with new key.
        """
        # Decrypt all with current key
        decrypted = [self.decrypt(v) for v in values]
        
        # Switch to new key
        self._fernet = None
        os.environ["APPLYPILOT_MASTER_KEY"] = new_master_key
        
        # Re-encrypt with new key
        return [self.encrypt(v) for v in decrypted]


# Module-level singleton
vault = CredentialVault()
