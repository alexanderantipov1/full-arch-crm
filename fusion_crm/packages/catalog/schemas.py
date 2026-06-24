"""Catalog domain DTOs (ENG-420)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProcedureCodeOut(BaseModel):
    """Read-side DTO for a single procedure code.

    ``id`` is the local UUID primary key (codebase invariant #8).
    ``carestack_code_id`` is the CareStack-assigned natural / business
    key — the integer value callers see in raw_event payloads and pass
    to ``CatalogService.resolve_procedure_codes``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    carestack_code_id: int
    code: str
    description: str | None = None
    code_type_id: int | None = None
    cdt_category_id: int | None = None


class ProcedureCodeImportOut(BaseModel):
    """Outcome of one ``catalog.procedure_code`` sync run."""

    imported: int
    total_seen: int
    error_count: int


class ProcedureCodeDriftOut(BaseModel):
    """A single code/description drift detected during a by-id sync (ENG-538).

    Carries the CareStack id plus the before/after code + description so an
    operator review surface can show exactly what moved. No PHI — procedure
    codes are reference data.
    """

    carestack_code_id: int
    old_code: str | None = None
    new_code: str
    old_description: str | None = None
    new_description: str | None = None


class ProcedureCodeByIdSyncOut(BaseModel):
    """Outcome of one by-id ``catalog.procedure_code`` sync run (ENG-538).

    ``requested`` — distinct ids the caller asked to reconcile.
    ``resolved`` — ids the by-id endpoint returned an entry for.
    ``unresolved`` — ids the by-id endpoint reported as missing (404 / 410 only;
        auth/config and exhausted-retry failures raise instead of counting here);
        surfaced so the operator can spot a code that disappeared upstream.
    ``imported`` — rows actually written (new + changed only; unchanged rows
        are skipped so ``updated_at`` stays a real "last changed" signal).
    ``new_codes`` — ids absent from the catalog before this run (drift: NEW).
    ``changed`` — codes whose ``code``/``description`` moved (drift: CHANGED).
    """

    requested: int
    resolved: int
    unresolved: list[int] = []
    imported: int
    new_codes: list[int] = []
    changed: list[ProcedureCodeDriftOut] = []
