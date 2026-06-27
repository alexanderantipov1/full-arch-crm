"""Crypto roundtrip tests — encrypt → store → read → decrypt."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from packages.integrations import crypto


@pytest.fixture(autouse=True)
def _isolate_fernet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a fresh Fernet per test instead of relying on ENCRYPTION_KEY env."""
    key = Fernet.generate_key()
    fernet = Fernet(key)
    monkeypatch.setattr(crypto, "_get_fernet", lambda: fernet)


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "fcrm_test_super_secret_token_123"  # noqa: S105 — not a real credential
    cipher = crypto.encrypt_str(plaintext)
    assert isinstance(cipher, bytes)
    assert plaintext.encode() not in cipher  # plaintext not in ciphertext
    assert crypto.decrypt_str(cipher) == plaintext


def test_encrypt_unicode() -> None:
    plaintext = "пароль_с_unicode_символами_🔒"  # noqa: S105 — not a real credential
    cipher = crypto.encrypt_str(plaintext)
    assert crypto.decrypt_str(cipher) == plaintext


def test_encrypt_empty_string() -> None:
    cipher = crypto.encrypt_str("")
    assert crypto.decrypt_str(cipher) == ""


def test_decrypt_invalid_token_raises() -> None:
    with pytest.raises(crypto.EncryptionError):
        crypto.decrypt_str(b"not-a-real-fernet-token")


def test_encrypted_string_type_decorator_handles_none() -> None:
    column_type = crypto.EncryptedString()
    assert column_type.process_bind_param(None, None) is None  # type: ignore[arg-type]
    assert column_type.process_result_value(None, None) is None  # type: ignore[arg-type]


def test_encrypted_string_type_decorator_roundtrip() -> None:
    column_type = crypto.EncryptedString()
    plaintext = "salesforce_access_token_xyz"
    cipher = column_type.process_bind_param(plaintext, None)  # type: ignore[arg-type]
    assert isinstance(cipher, bytes)
    decrypted = column_type.process_result_value(cipher, None)  # type: ignore[arg-type]
    assert decrypted == plaintext


def test_encrypted_string_rejects_non_string() -> None:
    column_type = crypto.EncryptedString()
    with pytest.raises(crypto.EncryptionError):
        column_type.process_bind_param(12345, None)  # type: ignore[arg-type]
