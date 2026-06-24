"""Generic tool-invocation endpoint.

This is the HTTP-facing equivalent of an agent runtime: pick a tool by name
from the registry and call it with a JSON ``args`` dict. Use this surface for
testing tools end-to-end; real agents will instantiate ``ToolContext``
themselves and call the tool functions directly.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db, get_principal_with_tenant
from packages.audit.service import AuditService
from packages.core.security import Principal
from packages.tools import ALL_TOOLS, get_tool
from packages.tools.base import ToolContext

router = APIRouter(prefix="/tools", tags=["tools"])

PrincipalDep = Annotated[Principal, Depends(get_principal_with_tenant)]


class ToolCallIn(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class ToolListOut(BaseModel):
    tools: list[dict[str, Any]]


@router.get("/", response_model=ToolListOut)
async def list_tools() -> ToolListOut:
    return ToolListOut(
        tools=[
            {"name": t.name, "description": t.description, "touches": sorted(t.touches)}
            for t in ALL_TOOLS.values()
        ]
    )


@router.post("/call")
async def call_tool(
    payload: ToolCallIn,
    principal: PrincipalDep,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        spec = get_tool(payload.name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit = AuditService(db)
    await audit.record(
        principal=principal,
        action=f"tool.invoke.{spec.name}",
        resource="tool",
        reason=payload.reason,
        extra={"args_keys": sorted(payload.args.keys())},
    )

    ctx = ToolContext(principal=principal, session=db)
    result = await spec.fn(ctx, **payload.args)
    return {"result": result}
