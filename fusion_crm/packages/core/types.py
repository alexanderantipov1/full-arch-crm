"""Shared type aliases used across packages."""

from __future__ import annotations

from typing import NewType
from uuid import UUID

# Strongly typed alias for the global person identifier.
# Using NewType prevents accidental swapping with arbitrary UUIDs.
PersonUID = NewType("PersonUID", UUID)

# Strongly typed alias for the tenant identifier — the row id of
# `tenant.tenant`. Every per-tenant repository method takes this as
# its first argument so a stray UUID cannot slip into a tenant filter.
TenantId = NewType("TenantId", UUID)
