"""Catalog domain service (ENG-420).

Public surface: pull the CareStack procedure-code catalog (read-only)
and resolve ``procedureCodeId`` values into ``(code, description)``
tuples.

Service rules:

* Routes / jobs / scripts depend on this module — they do not import
  the repository directly.
* The service never commits, never rolls back, never swallows the
  upsert exception. The caller boundary owns the unit of work (Cloud
  Run Job entry point, operator backfill script, test). On failure the
  caller rolls back; on success it commits.
* Read-only against CareStack: never POST / PUT / DELETE.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from packages.catalog.repository import CatalogRepository
from packages.catalog.schemas import (
    ProcedureCodeByIdSyncOut,
    ProcedureCodeDriftOut,
    ProcedureCodeImportOut,
)
from packages.core.logging import get_logger

log = get_logger("catalog.procedure_code")

_DEFAULT_MAX_CODES = 20_000
_DEFAULT_BATCH_SIZE = 500

# By-id sync defaults (ENG-538). The by-id endpoint is the PRIMARY catalog
# source — the flat list pull is broken on the real account (returns junk
# "Other" codes, never the CDT codes treatment procedures reference). We
# resolve each needed id individually, so the run issues up to one GET per
# distinct code. ~248 codes in practice; the throttle keeps us well under
# CareStack's rate limit and the backoff rides out transient 429 / 5xx.
_DEFAULT_BY_ID_SLEEP_SECONDS = 0.1
_DEFAULT_BY_ID_MAX_RETRIES = 5
_DEFAULT_BY_ID_BACKOFF_BASE_SECONDS = 1.0

# HTTP status codes that justify exponential backoff + retry (mirrors the
# CareStack treatment pull). 429 is the rate-limit signal; the 5xx set covers
# transient upstream outages. If retries are exhausted the fetch RAISES (a
# transient outage that never cleared is a real failure, not a missing code) so
# the entry-point boundary rolls back and reports failure instead of committing
# an incomplete catalog.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# HTTP status codes that mean "this code is genuinely gone / never existed
# upstream" — the ONLY statuses converted to a non-fatal ``unresolved`` (return
# None). 404 = not found, 410 = gone/retired. Everything else that is not
# retryable (401 / 403 auth, 400 bad request, ...) is a config/auth failure and
# MUST propagate (ENG-538 Codex review): masking it as ``unresolved`` would let
# the backfill/job commit a partial catalog and report success.
_MISSING_STATUS_CODES: frozenset[int] = frozenset({404, 410})


def _carestack_error_status(exc: BaseException) -> int | None:
    """Read the HTTP status from a CareStack-shaped exception, if present.

    The ``catalog`` domain imports only ``core`` (packages/CLAUDE.md matrix),
    so we duck-type on the ``.details`` dict the integrations layer attaches
    to its typed exceptions rather than importing ``CareStackApiError``.
    Returns ``None`` when the exception is not CareStack-shaped — the caller
    treats that as non-retryable.
    """
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        status = details.get("status")
        if isinstance(status, int):
            return status
    return None


class CareStackProcedureCodesClientProtocol(Protocol):
    """Minimum CareStack client surface needed by the sync service.

    The catalog endpoint is a flat, unpaginated array — see
    ``docs/integrations/carestack/resources/procedure-codes.md``. Retained
    for the no-op list fallback; the by-id path uses
    :class:`CareStackProcedureCodeByIdClientProtocol`.
    """

    async def get(
        self,
        path: str,
        query: dict[str, str | int] | None = None,
    ) -> Any: ...


class CareStackProcedureCodeByIdClientProtocol(Protocol):
    """CareStack client surface for the PRIMARY by-id catalog sync (ENG-538)."""

    async def get_procedure_code(self, code_id: int | str) -> dict[str, Any]: ...


class CatalogService:
    """Public surface for ``catalog.*`` operations.

    Today: CareStack procedure-code sync + a resolver helper. As the
    catalog domain grows other reference tables can join this service
    or split into siblings; the resolver contract here is stable.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CatalogRepository(session)

    async def sync_procedure_codes_from_carestack(
        self,
        carestack_client: CareStackProcedureCodesClientProtocol,
        *,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        max_codes: int = _DEFAULT_MAX_CODES,
    ) -> ProcedureCodeImportOut:
        """Pull the flat CareStack procedure-code LIST and upsert it.

        DEPRECATED as the primary source (ENG-538): the flat
        ``GET /api/v1.0/procedure-codes`` endpoint is BROKEN on the real
        account — it returns only a handful of junk "Other" codes and never
        the CDT codes that treatment procedures reference. Use
        :meth:`sync_procedure_codes_by_id` (the by-id endpoint) as the primary
        catalog source. This method is retained only as a harmless fallback /
        for accounts where the list endpoint behaves; it is never relied on.

        Read-only CareStack call. Repeated runs are no-ops on unchanged
        data (the upsert is keyed on ``carestack_code_id``).

        The service does NOT commit and does NOT swallow upsert
        failures. The caller boundary (Cloud Run Job entry point /
        operator backfill script / test) owns the unit of work — it
        commits on success and rolls back on error. Any exception
        raised by the repository propagates so the caller can roll the
        transaction back atomically.

        Args:
            carestack_client: A client that implements
                ``await client.get("api/v1.0/procedure-codes")`` and
                returns a flat list of dicts.
            batch_size: Split the upsert into SQL statements of this
                size. Bounds the Postgres ``ON CONFLICT`` parameter
                payload (each row carries ~6 bound parameters, and
                Postgres caps a single statement at 65535). ``0`` or
                negative disables batching (one statement for the full
                response). The catalog is a few hundred rows in
                practice; the default keeps headroom against the
                ``max_codes`` cap.
            max_codes: Defensive cap on the number of rows we process in
                one invocation. The CareStack catalog is a few hundred
                rows in practice — the cap exists to bound a misbehaving
                response, not to limit a real catalog.
        """
        body = await carestack_client.get("api/v1.0/procedure-codes")
        if not isinstance(body, list):
            log.warning(
                "catalog.procedure_codes.non_array_body",
                body_type=type(body).__name__,
            )
            return ProcedureCodeImportOut(
                imported=0, total_seen=0, error_count=0
            )
        entries: list[dict[str, Any]] = body

        capped: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if len(capped) >= max_codes:
                break
            capped.append(entry)

        if not capped:
            return ProcedureCodeImportOut(
                imported=0, total_seen=0, error_count=0
            )

        chunk = max(1, batch_size) if batch_size > 0 else len(capped)
        imported_total = 0
        for start in range(0, len(capped), chunk):
            batch = capped[start : start + chunk]
            # Let exceptions propagate — the caller owns rollback.
            written = await self._repo.upsert_procedure_codes(batch)
            imported_total += written

        # Flush, do NOT commit. The caller boundary commits.
        await self._session.flush()

        log.info(
            "catalog.procedure_codes.imported",
            imported=imported_total,
            total_seen=len(capped),
        )
        return ProcedureCodeImportOut(
            imported=imported_total,
            total_seen=len(capped),
            error_count=0,
        )

    async def sync_procedure_codes_by_id(
        self,
        carestack_client: CareStackProcedureCodeByIdClientProtocol,
        code_ids: Sequence[int],
        *,
        refresh_existing: bool = True,
        sleep_seconds: float = _DEFAULT_BY_ID_SLEEP_SECONDS,
        max_retries: int = _DEFAULT_BY_ID_MAX_RETRIES,
        backoff_base_seconds: float = _DEFAULT_BY_ID_BACKOFF_BASE_SECONDS,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> ProcedureCodeByIdSyncOut:
        """PRIMARY catalog sync: resolve each id via the by-id endpoint (ENG-538).

        The flat list endpoint is broken on the real account, so the catalog
        is built by resolving each needed ``procedureCodeId`` through
        ``GET /api/v1.0/procedure-codes/{id}`` and upserting it (idempotent on
        ``carestack_code_id``).

        ``code_ids`` is the distinct set of ids to reconcile — typically the
        ids observed in ``ingest.raw_event`` treatment-procedure payloads,
        enumerated by the caller boundary (``ingest`` may import ``catalog``,
        not the other way round, so the service never reaches into ingest).

        Drift detection: each resolved entry is diffed against the catalog row
        that existed BEFORE this run. A NEW id (absent before) and a CHANGED
        code/description are both surfaced — in the returned DTO, in a
        structured ``drift`` log, and in a ``needs_review`` log line — and only
        NEW + CHANGED rows are upserted, so ``created_at`` marks first-seen and
        ``updated_at`` marks last-changed (an operator can query
        ``WHERE created_at > :since`` / ``WHERE updated_at > :since``).

        ``refresh_existing`` (default True): also re-fetch ids already in the
        catalog to catch upstream code/description edits. Set False for the
        cheap "fill only the gaps" path (see :meth:`ensure_procedure_codes`).

        Read-only CareStack (GET only). Throttled (``sleep_seconds`` between
        calls) with bounded exponential backoff on 429 / 5xx. The service does
        NOT commit and does NOT swallow upsert failures — the caller boundary
        owns the unit of work and rolls back on error. ``sleep`` is injected by
        tests so the throttle path completes instantly.
        """
        sleep_fn: Callable[[float], Awaitable[None]] = (
            sleep if sleep is not None else asyncio.sleep
        )

        wanted: list[int] = []
        seen: set[int] = set()
        for raw in code_ids:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                continue
            if value in seen:
                continue
            seen.add(value)
            wanted.append(value)

        if not wanted:
            return ProcedureCodeByIdSyncOut(
                requested=0, resolved=0, imported=0
            )

        # Snapshot the catalog BEFORE the run so drift is computed against the
        # prior state, not the freshly-upserted rows.
        known = await self._repo.resolve_procedure_codes(wanted)

        targets = wanted if refresh_existing else [i for i in wanted if i not in known]

        resolved_entries: list[dict[str, Any]] = []
        unresolved: list[int] = []
        for index, code_id in enumerate(targets):
            if index > 0 and sleep_seconds > 0:
                await sleep_fn(sleep_seconds)
            entry = await self._fetch_one_with_backoff(
                carestack_client,
                code_id,
                max_retries=max_retries,
                backoff_base_seconds=backoff_base_seconds,
                sleep_fn=sleep_fn,
            )
            if entry is None:
                unresolved.append(code_id)
                continue
            resolved_entries.append(entry)

        # Diff resolved entries against the pre-run catalog.
        new_codes: list[int] = []
        changed: list[ProcedureCodeDriftOut] = []
        to_write: list[dict[str, Any]] = []
        for entry in resolved_entries:
            entry_id = _entry_code_id(entry)
            new_code = _entry_str(entry.get("code"))
            if entry_id is None or new_code is None:
                # ``code`` is NOT NULL and the id is the business key — a row
                # missing either can't be upserted; skip it (counted via the
                # resolved/imported gap).
                continue
            # Mirror exactly what ``CatalogRepository.upsert_procedure_codes``
            # persists so the diff doesn't flag spurious drift on every run:
            # ``code`` is stripped, ``description`` is stored verbatim (only
            # None-checked, NOT stripped).
            desc_raw = entry.get("description")
            new_description = None if desc_raw is None else str(desc_raw)
            prior = known.get(entry_id)
            if prior is None:
                new_codes.append(entry_id)
                to_write.append(entry)
                continue
            old_code, old_description = prior
            if old_code != new_code or old_description != new_description:
                changed.append(
                    ProcedureCodeDriftOut(
                        carestack_code_id=entry_id,
                        old_code=old_code,
                        new_code=new_code,
                        old_description=old_description,
                        new_description=new_description,
                    )
                )
                to_write.append(entry)
            # else: unchanged — skip the write so ``updated_at`` stays put.

        imported_total = 0
        if to_write:
            imported_total = await self._repo.upsert_procedure_codes(to_write)
            await self._session.flush()

        if new_codes or changed:
            # Structured drift baseline (mirrors the ENG-425/426 schema-registry
            # drift line) PLUS a "needs review" surfacing so a new/changed
            # reference code is never silent. Codes are reference data — ids,
            # codes, and counts are safe to log.
            log.info(
                "catalog.procedure_codes.drift",
                new_codes=sorted(new_codes),
                changed_codes=sorted(c.carestack_code_id for c in changed),
            )
            log.warning(
                "catalog.procedure_codes.needs_review",
                new_count=len(new_codes),
                changed_count=len(changed),
                new_codes=sorted(new_codes),
                changed=[
                    {
                        "id": c.carestack_code_id,
                        "code": c.new_code,
                        "was": c.old_code,
                    }
                    for c in changed
                ],
            )

        log.info(
            "catalog.procedure_codes.by_id_sync_done",
            requested=len(wanted),
            resolved=len(resolved_entries),
            unresolved=len(unresolved),
            imported=imported_total,
            new=len(new_codes),
            changed=len(changed),
        )
        return ProcedureCodeByIdSyncOut(
            requested=len(wanted),
            resolved=len(resolved_entries),
            unresolved=sorted(unresolved),
            imported=imported_total,
            new_codes=sorted(new_codes),
            changed=changed,
        )

    async def ensure_procedure_codes(
        self,
        carestack_client: CareStackProcedureCodeByIdClientProtocol,
        ids: Sequence[int],
        *,
        max_retries: int = 0,
        sleep_seconds: float = 0.0,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> list[int]:
        """Lazy self-fill: resolve+upsert only the ids NOT already cached.

        Backs the treatment-procedure ingest self-fill (ENG-538) — when a
        ``procedureCodeId`` is seen that the catalog does not yet know, resolve
        it via the by-id endpoint and insert it so the ENG-511 implant-surgery
        gate (and every other resolver consumer) works on first encounter,
        with no manual backfill step. Already-known ids cost zero CareStack
        calls. Returns the list of newly-inserted ids.

        LOW-RETRY by design (ENG-538 Codex review): this runs inside the ingest
        hot path (per treatment row, inside the capture unit of work). The
        defaults are a single attempt (``max_retries=0``) with no inter-call
        throttle (``sleep_seconds=0``) so a flaky / rate-limited lookup never
        holds the ingest transaction for tens of seconds — unlike the standalone
        backfill / weekly job, which keep the full bounded backoff. A retryable
        failure with ``max_retries=0`` propagates (per
        :meth:`_fetch_one_with_backoff`); the ingest caller swallows it.
        """
        out = await self.sync_procedure_codes_by_id(
            carestack_client,
            ids,
            refresh_existing=False,
            max_retries=max_retries,
            sleep_seconds=sleep_seconds,
            sleep=sleep,
        )
        return out.new_codes

    async def _fetch_one_with_backoff(
        self,
        carestack_client: CareStackProcedureCodeByIdClientProtocol,
        code_id: int,
        *,
        max_retries: int,
        backoff_base_seconds: float,
        sleep_fn: Callable[[float], Awaitable[None]],
    ) -> dict[str, Any] | None:
        """Fetch one procedure code by id with bounded backoff on 429 / 5xx.

        Returns the entry dict on success. Returns ``None`` (→ counted as a
        non-fatal ``unresolved`` code) ONLY for a genuine missing-code status
        (404 / 410 — see :data:`_MISSING_STATUS_CODES`).

        RAISES (propagates) in every other failure mode so the caller boundary
        rolls back and fails loudly instead of committing an incomplete catalog
        (ENG-538 Codex review):

        * a non-CareStack-shaped error (no ``.details["status"]``) — a real bug,
          not a missing code;
        * an auth / config status (401 / 403 / 400 and any other non-retryable,
          non-missing status);
        * a retryable 429 / 5xx whose retries are EXHAUSTED — a transient outage
          that never cleared is a real failure, not an "unresolved" code.
        """
        attempt = 0
        while True:
            try:
                return await carestack_client.get_procedure_code(code_id)
            except Exception as exc:  # noqa: BLE001 — retry / classify funnel
                status = _carestack_error_status(exc)
                if status is None:
                    # Not a CareStack-shaped error — a real bug, not a missing
                    # code. Let it propagate so the caller rolls back.
                    raise
                if status in _MISSING_STATUS_CODES:
                    # 404 / 410 — code retired or never existed upstream. The
                    # ONLY non-fatal outcome: surfaced as ``unresolved``.
                    log.info(
                        "catalog.procedure_codes.unresolved",
                        code_id=code_id,
                        status=status,
                    )
                    return None
                if status not in _RETRYABLE_STATUS_CODES:
                    # 401 / 403 / 400 etc. — auth/config failure. Do NOT mask as
                    # unresolved; propagate so the boundary rolls back + fails.
                    log.error(
                        "catalog.procedure_codes.fatal_status",
                        code_id=code_id,
                        status=status,
                    )
                    raise
                if attempt >= max_retries:
                    # Transient outage that never cleared — fail loudly rather
                    # than silently report the code as ``unresolved``.
                    log.error(
                        "catalog.procedure_codes.retries_exhausted",
                        code_id=code_id,
                        status=status,
                        attempts=attempt,
                    )
                    raise
                attempt += 1
                wait_seconds = backoff_base_seconds * (2 ** (attempt - 1))
                log.warning(
                    "catalog.procedure_codes.retrying_after_backoff",
                    code_id=code_id,
                    attempt=attempt,
                    wait_seconds=wait_seconds,
                    status=status,
                )
                await sleep_fn(wait_seconds)

    async def resolve_procedure_codes(
        self,
        ids: Iterable[int],
    ) -> dict[int, tuple[str, str | None]]:
        """Resolve a batch of procedure code ids.

        ``{carestack_code_id: (code, description)}`` — missing ids are
        absent. Stable contract used by the person timeline, PM
        Payments, and funnel analytics (ENG-419).
        """
        return await self._repo.resolve_procedure_codes(ids)

    async def count_procedure_codes(self) -> int:
        """Return the total row count in ``catalog.procedure_code``."""
        return await self._repo.count()


def _entry_code_id(entry: dict[str, Any]) -> int | None:
    """Extract the CareStack procedure-code id from a by-id entry dict."""
    raw_id = entry.get("id")
    if raw_id is None or isinstance(raw_id, bool):
        return None
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


def _entry_str(value: Any) -> str | None:
    """Normalise a by-id entry string field; blank/whitespace -> ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
