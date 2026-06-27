"""AuthService — passwords, sessions, API keys.

Plaintext NEVER persists. Boundary commits; service does not.

Runtime permission denial is OUT of scope for M1 — every method here is
about issuance / lookup / lifecycle, not authorisation. The runtime gate
(``Principal.can_read_phi`` consulting ``auth.permission_grant``) lands in M8.

Every public method takes ``tenant_id: TenantId`` as the first positional
argument (ENG-128). Sessions and API keys live in a tenant scope —
issuing one for tenant A and resolving it under tenant B is rejected
even if the token bytes happen to collide.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import TenantId

from .models import ApiKey, Credential, Session
from .repository import AuthRepository

# Single process-wide hasher with default OWASP-style parameters.
_PASSWORD_HASHER = PasswordHasher()

# Token namespace prefixes — easy for secret-scanners to flag, easy for
# operators to recognise the bearer source.
_SESSION_TOKEN_PREFIX = "fcrm_sess_"  # noqa: S105 — namespace prefix, not a credential
_API_KEY_TOKEN_PREFIX = "fcrm_"  # noqa: S105 — namespace prefix, not a credential

# Random suffix length (urlsafe base64). 32 bytes ≈ 256 bits of entropy
# before base64 encoding; the encoded suffix is ~43 chars.
_TOKEN_RANDOM_BYTES = 32


def _hash_token(raw: str) -> str:
    """sha256 hex of a bearer token. Bearer tokens are high-entropy random
    so a fast hash is sufficient — slow hashing is for low-entropy passwords.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _generate_session_token() -> tuple[str, str]:
    """Return ``(raw, token_hash)`` for a new session bearer token."""
    suffix = secrets.token_urlsafe(_TOKEN_RANDOM_BYTES)
    raw = f"{_SESSION_TOKEN_PREFIX}{suffix}"
    return raw, _hash_token(raw)


def _generate_api_key_token() -> tuple[str, str, str]:
    """Return ``(raw, token_hash, token_prefix)`` for a new API key.

    ``token_prefix`` is the first 12 chars of the plaintext (covers the
    namespace prefix + a hint of the random suffix) — safe to display.
    """
    suffix = secrets.token_urlsafe(_TOKEN_RANDOM_BYTES)
    raw = f"{_API_KEY_TOKEN_PREFIX}{suffix}"
    return raw, _hash_token(raw), raw[:12]


def hash_password(plaintext: str) -> str:
    """Argon2 hash a plaintext password. Empty input is rejected."""
    if not plaintext:
        raise ValidationError("password must not be empty")
    return _PASSWORD_HASHER.hash(plaintext)


def verify_password_hash(stored_hash: str, plaintext: str) -> bool:
    """Verify a plaintext against a stored argon2 hash. Returns ``False`` on
    mismatch (does not raise) — same shape as Django/Flask conventions and
    avoids leaking the difference between "no such credential" and "wrong
    password" up the call stack.
    """
    if not stored_hash or not plaintext:
        return False
    try:
        return _PASSWORD_HASHER.verify(stored_hash, plaintext)
    except VerifyMismatchError:
        return False


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AuthRepository(session)

    # --- Passwords ---

    async def set_password(
        self,
        tenant_id: TenantId,
        subject_type: str,
        subject_id: UUID,
        plaintext: str,
    ) -> Credential:
        """Set / rotate the password for a subject.

        Any prior active password row is flipped to ``revoked``; the new
        row is created with ``status='active'``. The partial unique index
        on ``(subject_type, subject_id, credential_kind)`` WHERE
        ``status='active'`` enforces "one active password" at the DB level.
        """
        if subject_type not in ("actor", "portal_account"):
            raise ValidationError(
                "subject_type must be 'actor' or 'portal_account'",
                details={"got": subject_type},
            )

        existing = await self._repo.find_active_credential(
            tenant_id,
            subject_type,
            subject_id,
            "password",
        )
        if existing is not None:
            existing.status = "revoked"

        new_credential = Credential(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
            credential_kind="password",
            secret_hash=hash_password(plaintext),
            status="active",
        )
        return await self._repo.add_credential(new_credential)

    async def verify_password(
        self,
        tenant_id: TenantId,
        subject_type: str,
        subject_id: UUID,
        plaintext: str,
    ) -> bool:
        """Verify a plaintext password for a subject.

        Returns ``False`` for "no active password" / "wrong password" /
        "empty input" — does not differentiate (avoid timing / response
        side-channels). On success, updates ``last_used_at``.
        """
        credential = await self._repo.find_active_credential(
            tenant_id,
            subject_type,
            subject_id,
            "password",
        )
        if credential is None or credential.secret_hash is None:
            return False
        if not verify_password_hash(credential.secret_hash, plaintext):
            return False
        credential.last_used_at = datetime.now(tz=UTC)
        return True

    # --- Sessions ---

    async def issue_session(
        self,
        tenant_id: TenantId,
        subject_type: str,
        subject_id: UUID,
        ttl_seconds: int,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, Session]:
        """Issue a new bearer-token session. Returns ``(raw_token, Session)``.

        The raw token is shown ONCE; the row stores only the sha256 hash.
        Caller (the API router) sets the cookie/header from ``raw_token``.
        """
        if ttl_seconds <= 0:
            raise ValidationError("ttl_seconds must be positive")
        if subject_type not in ("actor", "portal_account"):
            raise ValidationError("subject_type must be 'actor' or 'portal_account'")

        raw_token, token_hash = _generate_session_token()
        now = datetime.now(tz=UTC)
        session_row = Session(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=now + timedelta(seconds=ttl_seconds),
            last_seen_at=now,
        )
        await self._repo.add_session(session_row)
        return raw_token, session_row

    async def revoke_session(
        self, tenant_id: TenantId, session_id: UUID
    ) -> Session:
        """Mark a session as revoked. Idempotent — already-revoked rows
        return without raising.
        """
        row = await self._repo.get_session(tenant_id, session_id)
        if row is None:
            raise NotFoundError("session not found", details={"id": str(session_id)})
        if row.revoked_at is None:
            row.revoked_at = datetime.now(tz=UTC)
        return row

    async def find_session_by_token(
        self, tenant_id: TenantId, raw_token: str
    ) -> Session | None:
        """Resolve a raw bearer token to its Session row (if active).

        Returns ``None`` if the token is unknown, expired, or revoked.
        Updates ``last_seen_at`` on a hit.
        """
        if not raw_token:
            return None
        row = await self._repo.find_session_by_token_hash(
            tenant_id, _hash_token(raw_token)
        )
        if row is None:
            return None
        if row.revoked_at is not None:
            return None
        if row.expires_at <= datetime.now(tz=UTC):
            return None
        row.last_seen_at = datetime.now(tz=UTC)
        return row

    # --- API keys ---

    async def issue_api_key(
        self,
        tenant_id: TenantId,
        actor_id: UUID,
        name: str,
        *,
        scopes: list[str] | None = None,
        ttl_days: int | None = None,
        created_by_actor_id: UUID | None = None,
        meta: dict[str, object] | None = None,
    ) -> tuple[str, ApiKey]:
        """Issue a new API key. Returns ``(raw_token, ApiKey)``.

        Plaintext shown ONCE; row stores ``token_hash`` and a 12-char
        ``token_prefix`` for display.
        """
        if not name or not name.strip():
            raise ValidationError("api key name required")

        raw_token, token_hash, token_prefix = _generate_api_key_token()
        expires_at: datetime | None = None
        if ttl_days is not None:
            if ttl_days <= 0:
                raise ValidationError("ttl_days must be positive")
            expires_at = datetime.now(tz=UTC) + timedelta(days=ttl_days)

        api_key = ApiKey(
            tenant_id=tenant_id,
            name=name.strip(),
            actor_id=actor_id,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=list(scopes or []),
            status="active",
            expires_at=expires_at,
            created_by_actor_id=created_by_actor_id,
            meta=dict(meta or {}),
        )
        await self._repo.add_api_key(api_key)
        return raw_token, api_key

    async def revoke_api_key(
        self, tenant_id: TenantId, api_key_id: UUID
    ) -> ApiKey:
        """Mark an API key as revoked. Idempotent."""
        row = await self._repo.get_api_key(tenant_id, api_key_id)
        if row is None:
            raise NotFoundError("api_key not found", details={"id": str(api_key_id)})
        if row.status != "revoked":
            row.status = "revoked"
            row.revoked_at = datetime.now(tz=UTC)
        return row

    async def find_api_key_by_token(
        self, tenant_id: TenantId, raw_token: str
    ) -> ApiKey | None:
        """Resolve a raw bearer token to its ApiKey row if active.

        Returns ``None`` for unknown / revoked / expired tokens. Updates
        ``last_used_at`` on a hit.
        """
        if not raw_token:
            return None
        row = await self._repo.find_api_key_by_token_hash(
            tenant_id, _hash_token(raw_token)
        )
        if row is None:
            return None
        if row.status != "active":
            return None
        if row.expires_at is not None and row.expires_at <= datetime.now(tz=UTC):
            return None
        row.last_used_at = datetime.now(tz=UTC)
        return row
