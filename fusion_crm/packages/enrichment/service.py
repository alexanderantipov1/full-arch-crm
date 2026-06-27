"""Enrichment domain service (ENG-439, Block F).

Public surface for ``enrichment.*``: record one of *our own* fields on a
canonical entity and read them back. The UI write path uses it now; the chat
action path (Block G) and the AI-agent tools layer write through the SAME
method later, so the audit + validation rules live in exactly one place.

Service rules (``packages/CLAUDE.md``):

* Routes / jobs / tools depend on this module — never on the repository.
* The service NEVER commits and NEVER rolls back. The caller boundary owns
  the unit of work (the API ``get_db`` dependency, a worker job, or a test).
* Every annotation write also writes an ``audit.access_log`` row in the same
  unit of work — the audit row and the annotation commit or roll back
  together.
"""

from __future__ import annotations

from collections import OrderedDict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.security import Principal
from packages.core.types import PersonUID, TenantId

from .models import ANNOTATION_SOURCES, RecordAnnotation
from .repository import RecordAnnotationRepository
from .schemas import AnnotationIn

_PERSON_SUBJECT_TYPE = "person"


class EnrichmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = RecordAnnotationRepository(session)
        self._audit = AuditService(session)

    async def add_annotation(
        self,
        tenant_id: TenantId,
        data: AnnotationIn,
        *,
        principal: Principal,
    ) -> RecordAnnotation:
        """Persist one annotation and write its audit row.

        The ``source`` value is validated here as well as by the DB CHECK
        constraint so callers that bypass the Pydantic DTO (none today, but
        Block G's action mapper might) still fail closed at the service
        boundary rather than at flush time.

        The audit ``extra`` carries keys/ids only — ``subject_type``,
        ``subject_id``, ``key``, ``source``. The annotation ``value`` (which
        may contain free text / PII) is deliberately NOT placed in ``extra``.
        """
        if data.source not in ANNOTATION_SOURCES:
            raise ValueError(
                f"invalid annotation source {data.source!r}; "
                f"expected one of {ANNOTATION_SOURCES}"
            )

        annotation = RecordAnnotation(
            tenant_id=tenant_id,
            subject_type=data.subject_type,
            subject_id=data.subject_id,
            key=data.key,
            value=data.value,
            source=data.source,
            note=data.note,
            author_actor_id=data.author_actor_id,
        )
        await self._repo.add(annotation)

        person_uid: PersonUID | None = None
        if data.subject_type == _PERSON_SUBJECT_TYPE:
            person_uid = PersonUID(data.subject_id)

        await self._audit.record(
            principal=principal,
            action="enrichment.annotation.add",
            resource="enrichment.record_annotation",
            person_uid=person_uid,
            extra={
                "subject_type": data.subject_type,
                "subject_id": str(data.subject_id),
                "key": data.key,
                "source": data.source,
            },
        )
        return annotation

    async def list_for_subject(
        self,
        tenant_id: TenantId,
        subject_type: str,
        subject_id: UUID,
    ) -> list[RecordAnnotation]:
        """Return all annotations for one subject, newest first."""
        return await self._repo.list_for_subject(tenant_id, subject_type, subject_id)

    async def latest_per_key(
        self,
        tenant_id: TenantId,
        subject_type: str,
        subject_id: UUID,
    ) -> list[RecordAnnotation]:
        """Return the newest annotation per ``key`` for a subject.

        Built on top of :meth:`list_for_subject` (which orders newest-first),
        so the first row seen for each key wins. Order of the result follows
        first-seen order of the keys (i.e. newest-overall first).
        """
        rows = await self._repo.list_for_subject(tenant_id, subject_type, subject_id)
        latest: OrderedDict[str, RecordAnnotation] = OrderedDict()
        for row in rows:
            if row.key not in latest:
                latest[row.key] = row
        return list(latest.values())
