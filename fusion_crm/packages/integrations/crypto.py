"""Fernet helper + ``EncryptedString`` SQLAlchemy ``TypeDecorator``.

Encryption key is read from ``settings.encryption_key`` (a Fernet key —
url-safe base64 of 32 random bytes). Generate once with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

and store in ``.env`` as ``ENCRYPTION_KEY``.

Why this lives in ``packages/integrations``:
  Right now the only consumer is OAuth tokens on ``integration_account``.
  When other domains need encryption, promote ``crypto.py`` to
  ``packages/core/crypto.py`` and re-import.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import LargeBinary
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from packages.core.config import get_settings
from packages.core.exceptions import PlatformError


class EncryptionError(PlatformError):
    """Raised when encryption / decryption fails (bad key, tampered ciphertext)."""

    code = "encryption_error"
    http_status = 500


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Return the process-wide Fernet, lazily initialized from settings."""
    settings = get_settings()
    key = getattr(settings, "encryption_key", None)
    if not key:
        raise EncryptionError(
            "ENCRYPTION_KEY is not configured; cannot read or write encrypted columns",
        )
    # ``encryption_key`` is a SecretStr-like or str. Normalize to bytes.
    raw = key.get_secret_value() if hasattr(key, "get_secret_value") else key
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return Fernet(raw)


def encrypt_str(plaintext: str) -> bytes:
    """Encrypt a UTF-8 string; returns ciphertext bytes (base64 inside Fernet token)."""
    return _get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_str(ciphertext: bytes) -> str:
    """Decrypt Fernet-encrypted bytes back into the original UTF-8 string."""
    try:
        return _get_fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError("invalid or tampered ciphertext") from exc


class EncryptedString(TypeDecorator[str]):
    """SQLAlchemy column type that transparently encrypts string values.

    Stored as ``BYTEA`` (Postgres); Python sees ``str`` on read and write.
    NULL passes through unchanged so optional fields stay clean.
    """

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise EncryptionError(
                f"EncryptedString expected str, got {type(value).__name__}",
            )
        return encrypt_str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if isinstance(value, memoryview):
            value = value.tobytes()
        return decrypt_str(value)
