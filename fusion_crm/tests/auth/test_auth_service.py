"""Service-level tests for auth — pure-Python helpers (hash, token gen).

DB-dependent paths (set_password, issue_session, etc.) land with the alembic
migration in FUS-32, since they need a real Postgres session. Here we
exercise the crypto helpers that don't require DB.
"""

from __future__ import annotations

import hashlib

import pytest

from packages.auth.service import (
    _generate_api_key_token,
    _generate_session_token,
    _hash_token,
    hash_password,
    verify_password_hash,
)
from packages.core.exceptions import ValidationError

# --- password hashing ---


def test_hash_password_produces_argon2() -> None:
    """argon2 hashes start with $argon2id$."""
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2")
    # The hash should not contain the plaintext.
    assert "correct horse battery staple" not in hashed


def test_hash_password_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        hash_password("")


def test_verify_password_hash_roundtrip() -> None:
    plaintext = "correct horse battery staple"  # noqa: S105 — test fixture
    hashed = hash_password(plaintext)
    assert verify_password_hash(hashed, plaintext) is True


def test_verify_password_hash_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password_hash(hashed, "wrong-password") is False


def test_verify_password_hash_handles_empty_inputs() -> None:
    """Empty hash or empty plaintext returns False, never raises."""
    assert verify_password_hash("", "anything") is False
    assert verify_password_hash("$argon2id$v=19$m=65536,t=3,p=4$xxx$yyy", "") is False


def test_two_hashes_of_same_password_differ() -> None:
    """argon2 uses a per-hash salt — two hashes of the same plaintext differ."""
    p = "correct horse battery staple"  # noqa: S105 — test fixture
    assert hash_password(p) != hash_password(p)


# --- token generation ---


def test_session_token_format_and_hash() -> None:
    raw, token_hash = _generate_session_token()
    assert raw.startswith("fcrm_sess_")
    # Token hash is sha256 hex of the raw token.
    expected_hash = hashlib.sha256(raw.encode()).hexdigest()
    assert token_hash == expected_hash
    # 32 random bytes urlsafe-base64-encoded → ~43 chars after the prefix.
    assert len(raw) >= 30


def test_session_tokens_are_unique() -> None:
    seen = {_generate_session_token()[0] for _ in range(50)}
    assert len(seen) == 50  # all unique


def test_api_key_token_format_prefix_hash() -> None:
    raw, token_hash, token_prefix = _generate_api_key_token()
    assert raw.startswith("fcrm_")
    assert token_prefix == raw[:12]
    assert token_hash == hashlib.sha256(raw.encode()).hexdigest()


def test_api_key_tokens_are_unique() -> None:
    seen = {_generate_api_key_token()[0] for _ in range(50)}
    assert len(seen) == 50


def test_hash_token_helper_matches_sha256() -> None:
    raw = "fcrm_test_token_xyz"  # noqa: S105 — test fixture
    assert _hash_token(raw) == hashlib.sha256(raw.encode()).hexdigest()
