"""Tool base types and the ``ToolContext``.

A ``ToolContext`` carries the per-invocation principal and DB session. Tools
ALWAYS receive a context; they never construct their own session.

The principal's ``tenant_id`` is the tenant scope for every tool call —
tools forward it to the services they call (ENG-128).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.security import Principal
from packages.core.types import TenantId


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Per-invocation execution context for a tool."""

    principal: Principal
    session: AsyncSession

    @property
    def tenant_id(self) -> TenantId:
        """Resolve the tenant for this invocation, raising if unset.

        Wrapper around ``Principal.require_tenant`` so tools have a short
        helper instead of reaching into ``ctx.principal`` every time.
        """
        return self.principal.require_tenant()


# A tool is an async callable: (ctx, **kwargs) -> Any
ToolFn = Callable[..., Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Static metadata about a tool — used for discovery and audit logs."""

    name: str
    description: str
    fn: ToolFn
    # Coarse classification for governance: which domains does this tool touch?
    touches: frozenset[str]  # e.g. {"identity"}, {"phi"}
