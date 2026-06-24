"""Security primitives: principals, roles, and access decisions.

This module is intentionally minimal today. It defines the contracts that the
rest of the platform uses so that a real auth system (OIDC + RBAC) can be wired
in later without touching service or repository code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from packages.core.types import TenantId


class Role(StrEnum):
    """Role granted to a principal. Add new roles here as needed."""

    GUEST = "guest"
    STAFF = "staff"          # front-desk, ops domain
    CLINICIAN = "clinician"  # may read PHI
    ADMIN = "admin"          # full access
    SYSTEM = "system"        # internal jobs / agent runtime


# Roles allowed to read PHI. Codified once, used everywhere.
PHI_READ_ROLES: frozenset[Role] = frozenset({Role.CLINICIAN, Role.ADMIN, Role.SYSTEM})


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated caller. The audit layer logs this on every PHI access.

    ``tenant_id`` carries the resolved tenant for this request. In Phase 1
    (single-tenant) it is set by a FastAPI dependency that looks up
    ``Settings.tenant_default_slug`` once per request and attaches the
    ``tenant.tenant.id`` to the principal. ``None`` is allowed for
    pre-bootstrap callers (health checks, the bootstrap migration, anonymous
    requests in tests); per-tenant repository methods raise on ``None``.
    """

    id: UUID | None
    email: str | None
    tenant_id: TenantId | None = None
    roles: frozenset[Role] = field(default_factory=frozenset)
    # Free-form context: request_id, agent name, source IP, etc.
    context: dict[str, str] = field(default_factory=dict)

    def has_role(self, role: Role) -> bool:
        return role in self.roles

    def can_read_phi(self) -> bool:
        return bool(self.roles & PHI_READ_ROLES)

    def require_tenant(self) -> TenantId:
        """Return ``tenant_id`` or raise — defensive helper for service layers
        that must operate in a tenant context.

        Raises ``ValueError`` rather than a domain error so this stays a
        cheap, dependency-free check; the API boundary catches and translates
        into a 401/403 if it ever propagates that far (it should not — the
        FastAPI dependency populates ``tenant_id`` for every authenticated
        request).
        """
        if self.tenant_id is None:
            raise ValueError("Principal has no tenant_id")
        return self.tenant_id


# Default unauthenticated principal — used by health checks and tests.
ANONYMOUS = Principal(id=None, email=None, roles=frozenset({Role.GUEST}))
