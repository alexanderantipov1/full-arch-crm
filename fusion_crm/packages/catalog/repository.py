"""Catalog repository — data access for ``catalog.*`` tables (ENG-420).

Repositories are data-only: they never commit, never rollback, never
mix business logic. The boundary (API dependency / worker job /
operator script / test) owns the unit of work.

The procedure-code catalog uses a UUID primary key (root ``CLAUDE.md``
invariant #8); the upsert and resolver key on
``catalog.procedure_code.carestack_code_id`` (``BIGINT NOT NULL UNIQUE``),
which is the CareStack-assigned natural / business key.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.catalog.models import ProcedureCode


class CatalogRepository:
    """Data access for ``catalog.procedure_code``.

    The catalog is workspace-wide; nothing here takes ``tenant_id``.
    See ``packages/catalog/models.py`` for the scoping decision.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_procedure_codes(
        self,
        rows: Sequence[dict[str, Any]],
    ) -> int:
        """Idempotent upsert of procedure-code rows.

        Keyed on ``carestack_code_id`` (the CareStack-assigned procedure
        code id, e.g. ``117408``). The local row ``id`` is a
        client-generated UUID (codebase invariant #8); the verbatim
        CareStack entry is preserved under ``payload`` so a future
        column extension does not require a re-pull.

        Empty input short-circuits without SQL.

        Returns the number of rows actually written (insert OR update).
        """
        if not rows:
            return 0

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        # Dedup by carestack_code_id so Postgres ``ON CONFLICT`` fires
        # at most once per key in a single statement (otherwise it
        # raises ``cardinality_violation``).
        seen: set[int] = set()
        normalised: list[dict[str, Any]] = []
        for entry in rows:
            raw_id = entry.get("id")
            if raw_id is None:
                continue
            try:
                code_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if code_id in seen:
                continue
            seen.add(code_id)

            code_value = entry.get("code")
            if code_value is None:
                # ``code`` is NOT NULL — skip rows the upstream returns
                # without a CDT/CPT code string. Counted by the caller.
                continue
            code_str = str(code_value).strip()
            if not code_str:
                continue

            description = entry.get("description")
            description_str: str | None
            if description is None:
                description_str = None
            else:
                description_str = str(description)

            def _int_or_none(value: Any) -> int | None:
                if value is None:
                    return None
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            normalised.append(
                {
                    "carestack_code_id": code_id,
                    "code": code_str,
                    "description": description_str,
                    "code_type_id": _int_or_none(entry.get("codeTypeId")),
                    "cdt_category_id": _int_or_none(entry.get("cdtCategoryId")),
                    "payload": dict(entry),
                }
            )

        if not normalised:
            return 0

        from sqlalchemy import func

        stmt = pg_insert(ProcedureCode).values(normalised)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ProcedureCode.carestack_code_id],
            set_={
                "code": stmt.excluded.code,
                "description": stmt.excluded.description,
                "code_type_id": stmt.excluded.code_type_id,
                "cdt_category_id": stmt.excluded.cdt_category_id,
                "payload": stmt.excluded.payload,
                # ``TimestampMixin.updated_at`` carries ``onupdate=func.now()``,
                # but ORM ``onupdate`` does NOT fire for a Core
                # ``ON CONFLICT DO UPDATE``. Set it explicitly so a re-written
                # row's ``updated_at`` advances — the by-id drift sweep
                # (ENG-538) only ever upserts NEW/CHANGED rows, so this stays a
                # truthful "code last changed at" signal an operator can query.
                "updated_at": func.now(),
            },
        )
        await self._session.execute(stmt)
        return len(normalised)

    async def resolve_procedure_codes(
        self,
        ids: Iterable[int],
    ) -> dict[int, tuple[str, str | None]]:
        """Return ``{carestack_code_id: (code, description)}``.

        Callers pass CareStack procedure-code ids (the integer values
        observed in raw_event payloads). Missing ids are absent from
        the returned dict — callers decide how to render the gap
        (display the raw id, show a placeholder, etc.).
        """
        wanted: list[int] = []
        seen: set[int] = set()
        for raw in ids:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if value in seen:
                continue
            seen.add(value)
            wanted.append(value)
        if not wanted:
            return {}

        stmt = select(
            ProcedureCode.carestack_code_id,
            ProcedureCode.code,
            ProcedureCode.description,
        ).where(ProcedureCode.carestack_code_id.in_(wanted))
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: (row[1], row[2]) for row in rows}

    async def count(self) -> int:
        """Return the total row count in ``catalog.procedure_code``.

        Used by tests + the operator backfill log line.
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(ProcedureCode)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
