"""Identity repository — data access only. NO business logic.

Repositories take an ``AsyncSession`` and return ORM entities. They do not
commit (that is the unit-of-work caller's responsibility).

Every per-tenant read filters by ``tenant_id`` via :func:`for_tenant`
(ENG-128). The first positional argument after ``self`` on every method
that touches a tenant-scoped table is ``tenant_id: TenantId`` so a stray
UUID cannot slip past type checking into a tenant filter.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.core.types import TenantId
from packages.db.tenant_scope import for_tenant

from .canonical import identifier_match_key
from .models import (
    REUSE_MATCH_RULES,
    MatchCandidate,
    MergeEvent,
    Person,
    PersonIdentifier,
    SourceLink,
)


def _value_or_match_key(value: str, match_key: str) -> Any:
    """Match an identifier by canonical key, falling back to the raw value.

    The match-key clause is only added when ``match_key`` is non-empty, so a
    junk value whose key is ``""`` never collides with every other empty-key
    row. The raw-value equality keeps lookups correct for rows whose
    ``value_match_key`` has not been backfilled yet.
    """
    if match_key:
        return or_(
            PersonIdentifier.value_match_key == match_key,
            PersonIdentifier.value == value,
        )
    return PersonIdentifier.value == value


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Person ---
    async def get_person(self, tenant_id: TenantId, person_id: UUID) -> Person | None:
        stmt = for_tenant(select(Person), tenant_id, Person).where(Person.id == person_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_person(self, person: Person) -> Person:
        self._session.add(person)
        await self._session.flush()
        return person

    async def list_recent(self, tenant_id: TenantId, limit: int) -> list[Person]:
        stmt = (
            for_tenant(select(Person), tenant_id, Person)
            .options(selectinload(Person.identifiers))
            .order_by(Person.updated_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_by_ids(self, tenant_id: TenantId, person_uids: list[UUID]) -> list[Person]:
        """Return tenant-scoped persons by ids with identifiers loaded."""
        if not person_uids:
            return []
        stmt = (
            for_tenant(select(Person), tenant_id, Person)
            .where(Person.id.in_(person_uids))
            .options(selectinload(Person.identifiers))
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_for_tenant(self, tenant_id: TenantId) -> int:
        stmt = for_tenant(select(func.count(Person.id)), tenant_id, Person)
        return int((await self._session.execute(stmt)).scalar_one())

    async def list_source_providers_for(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> dict[UUID, list[str]]:
        if not person_uids:
            return {}
        stmt = for_tenant(
            select(SourceLink.person_uid, SourceLink.source_system).distinct(),
            tenant_id,
            SourceLink,
        ).where(SourceLink.person_uid.in_(person_uids))
        rows = (await self._session.execute(stmt)).all()
        out: dict[UUID, list[str]] = {uid: [] for uid in person_uids}
        for person_uid, source_system in rows:
            out.setdefault(person_uid, []).append(source_system)
        return out

    async def list_source_links_for_persons(
        self, tenant_id: TenantId, person_uids: list[UUID]
    ) -> list[SourceLink]:
        if not person_uids:
            return []
        stmt = (
            for_tenant(select(SourceLink), tenant_id, SourceLink)
            .where(SourceLink.person_uid.in_(person_uids))
            .order_by(
                SourceLink.source_system.asc(),
                SourceLink.source_instance.asc(),
                SourceLink.source_kind.asc(),
                SourceLink.source_id.asc().nullslast(),
            )
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_source_links_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        source_system: str | None = None,
        source_kind: str | None = None,
        first_seen_from: Any | None = None,
        first_seen_to: Any | None = None,
        limit: int = 200,
    ) -> list[SourceLink]:
        """List source links for dashboard source-record rows."""
        stmt = for_tenant(select(SourceLink), tenant_id, SourceLink)
        if source_system is not None:
            stmt = stmt.where(SourceLink.source_system == source_system)
        if source_kind is not None:
            stmt = stmt.where(SourceLink.source_kind == source_kind)
        if first_seen_from is not None:
            stmt = stmt.where(SourceLink.first_seen_at >= first_seen_from)
        if first_seen_to is not None:
            stmt = stmt.where(SourceLink.first_seen_at < first_seen_to)
        stmt = stmt.order_by(SourceLink.first_seen_at.desc(), SourceLink.id.desc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_source_links_for_dashboard(
        self,
        tenant_id: TenantId,
        *,
        source_system: str | None = None,
        source_kind: str | None = None,
        first_seen_from: Any | None = None,
        first_seen_to: Any | None = None,
    ) -> int:
        """Count source links for dashboard source-record rows."""
        stmt = for_tenant(select(func.count()).select_from(SourceLink), tenant_id, SourceLink)
        if source_system is not None:
            stmt = stmt.where(SourceLink.source_system == source_system)
        if source_kind is not None:
            stmt = stmt.where(SourceLink.source_kind == source_kind)
        if first_seen_from is not None:
            stmt = stmt.where(SourceLink.first_seen_at >= first_seen_from)
        if first_seen_to is not None:
            stmt = stmt.where(SourceLink.first_seen_at < first_seen_to)
        return int((await self._session.execute(stmt)).scalar_one())

    async def full_funnel_carestack_patient_person_uids(
        self, tenant_id: TenantId
    ) -> list[UUID]:
        """DISTINCT person_uids with a ``carestack/patient`` source link.

        All-time, NOT windowed: the CareStack patient object has no creation
        date, so ``first_seen_at`` (a bulk-import artifact) is meaningless for
        funnel timing (ENG-481 dating fix). The composition layer subtracts
        the persons that have any ``ops.lead`` and dates the remainder by their
        earliest real activity instead.
        """
        stmt = (
            for_tenant(
                select(SourceLink.person_uid).select_from(SourceLink).distinct(),
                tenant_id,
                SourceLink,
            )
            .where(SourceLink.source_system == "carestack")
            .where(SourceLink.source_kind == "patient")
        )
        rows = (await self._session.execute(stmt)).all()
        return [person_uid for (person_uid,) in rows]

    async def source_linkage_coverage(self, tenant_id: TenantId) -> dict[str, int]:
        """Return Salesforce/CareStack source-linkage aggregate counts."""
        total_persons = await self.count_for_tenant(tenant_id)
        provider_flags = (
            for_tenant(
                select(
                    SourceLink.person_uid.label("person_uid"),
                    func.bool_or(SourceLink.source_system == "salesforce").label(
                        "has_salesforce"
                    ),
                    func.bool_or(SourceLink.source_system == "carestack").label(
                        "has_carestack"
                    ),
                ).select_from(SourceLink),
                tenant_id,
                SourceLink,
            )
            .where(SourceLink.source_system.in_(("salesforce", "carestack")))
            .group_by(SourceLink.person_uid)
            .subquery()
        )
        stmt = select(
            func.count()
            .filter(provider_flags.c.has_salesforce.is_(True))
            .label("salesforce_person_count"),
            func.count()
            .filter(provider_flags.c.has_carestack.is_(True))
            .label("carestack_person_count"),
            func.count()
            .filter(
                provider_flags.c.has_salesforce.is_(True),
                provider_flags.c.has_carestack.is_(True),
            )
            .label("linked_salesforce_carestack_count"),
            func.count()
            .filter(
                provider_flags.c.has_salesforce.is_(True),
                provider_flags.c.has_carestack.is_(False),
            )
            .label("salesforce_only_count"),
            func.count()
            .filter(
                provider_flags.c.has_salesforce.is_(False),
                provider_flags.c.has_carestack.is_(True),
            )
            .label("carestack_only_count"),
        ).select_from(provider_flags)
        row = (await self._session.execute(stmt)).one()
        return {
            "total_persons": total_persons,
            "salesforce_person_count": int(row.salesforce_person_count),
            "carestack_person_count": int(row.carestack_person_count),
            "linked_salesforce_carestack_count": int(row.linked_salesforce_carestack_count),
            "salesforce_only_count": int(row.salesforce_only_count),
            "carestack_only_count": int(row.carestack_only_count),
        }

    async def list_source_linkage_examples(
        self,
        tenant_id: TenantId,
        *,
        limit: int,
    ) -> list[dict[str, object]]:
        """Return bounded provider-linkage examples without person demographics."""
        salesforce_id = func.min(SourceLink.source_id).filter(
            SourceLink.source_system == "salesforce"
        )
        carestack_id = func.min(SourceLink.source_id).filter(
            SourceLink.source_system == "carestack"
        )
        has_salesforce = func.bool_or(SourceLink.source_system == "salesforce")
        has_carestack = func.bool_or(SourceLink.source_system == "carestack")
        stmt = (
            for_tenant(
                select(
                    SourceLink.person_uid,
                    has_salesforce.label("has_salesforce"),
                    has_carestack.label("has_carestack"),
                    salesforce_id.label("salesforce_source_id"),
                    carestack_id.label("carestack_source_id"),
                ).select_from(SourceLink),
                tenant_id,
                SourceLink,
            )
            .where(SourceLink.source_system.in_(("salesforce", "carestack")))
            .group_by(SourceLink.person_uid)
            .order_by(SourceLink.person_uid.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "person_uid": person_uid,
                "has_salesforce": bool(has_salesforce_value),
                "has_carestack": bool(has_carestack_value),
                "salesforce_source_id": salesforce_source_id,
                "carestack_source_id": carestack_source_id,
            }
            for (
                person_uid,
                has_salesforce_value,
                has_carestack_value,
                salesforce_source_id,
                carestack_source_id,
            ) in rows
        ]

    async def list_source_links_by_external_records(
        self,
        tenant_id: TenantId,
        keys: list[tuple[str, str, str, str]],
    ) -> list[SourceLink]:
        if not keys:
            return []
        stmt = for_tenant(select(SourceLink), tenant_id, SourceLink).where(
            tuple_(
                SourceLink.source_system,
                SourceLink.source_instance,
                SourceLink.source_kind,
                SourceLink.source_id,
            ).in_(keys)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_candidate_persons_by_identifiers(
        self,
        tenant_id: TenantId,
        email_normalized: str | None,
        phone_normalized: str | None,
    ) -> list[Person]:
        """Return distinct persons whose identifiers match the given email or
        phone (ENG-185).

        Used by :meth:`IdentityService.resolve_or_create_from_hint` to find
        the candidate persons evaluated by the match policy. Both filters are
        tenant-scoped: each subquery filters ``PersonIdentifier.tenant_id``
        AND ``Person.tenant_id`` so no cross-tenant person ever surfaces,
        even if a foreign identifier value happens to collide.

        Returns an empty list if neither identifier is given.
        """
        if not email_normalized and not phone_normalized:
            return []

        # Match on the canonical key (E.164 phone / lower-cased email) with a
        # raw-value OR fallback, so candidates are found across stored formats.
        clauses: list[Any] = []
        if email_normalized:
            clauses.append(
                and_(
                    PersonIdentifier.kind == "email",
                    _value_or_match_key(
                        email_normalized,
                        identifier_match_key("email", email_normalized),
                    ),
                )
            )
        if phone_normalized:
            clauses.append(
                and_(
                    PersonIdentifier.kind == "phone",
                    _value_or_match_key(
                        phone_normalized,
                        identifier_match_key("phone", phone_normalized),
                    ),
                )
            )

        stmt = (
            for_tenant(select(Person), tenant_id, Person)
            .join(PersonIdentifier, PersonIdentifier.person_id == Person.id)
            .where(PersonIdentifier.tenant_id == tenant_id)
            .where(or_(*clauses))
            .options(selectinload(Person.identifiers))
            .distinct()
            .order_by(Person.created_at.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    # --- Identifiers ---
    async def find_identifier(
        self, tenant_id: TenantId, kind: str, value: str
    ) -> PersonIdentifier | None:
        """Return one identifier row for ``(kind, value)`` in the tenant.

        ENG-341: a SHARED kind (``phone`` / ``email``) may now be held by
        multiple persons, so this can match more than one row. We return the
        EARLIEST holder deterministically (``created_at``, then ``id`` as a
        stable tiebreaker) rather than an arbitrary row, so point lookups
        (``resolve_by_phone`` / ``resolve_by_email`` / ``upsert_by_identifier``)
        are stable. Household-aware enumeration of ALL holders goes through
        :meth:`list_candidate_persons_by_identifiers` (the hint resolver path),
        not this method.

        ENG-341 ACCEPTED TRADE-OFF: the API ``resolve_person``, the agent
        ``person_tools.resolve_person``, and outreach recipient preview present
        this single earliest holder as "the" person for a shared phone/email.
        That preserves pre-A behaviour (the 2nd holder previously had no row)
        and matches the layer-C intent (one shared contact = one outreach
        target). Making those consumers household-aware is the follow-up
        ENG-558.
        """
        # Compare on the canonical match key so a phone stored in one format
        # (``2015550123``) is found by an incoming value in another
        # (``+12015550123``). Raw-value equality is kept as an OR fallback so
        # there is no correctness gap while legacy rows are being backfilled.
        match_key = identifier_match_key(kind, value)
        stmt = (
            for_tenant(select(PersonIdentifier), tenant_id, PersonIdentifier)
            .where(
                PersonIdentifier.kind == kind,
                _value_or_match_key(value, match_key),
            )
            .order_by(PersonIdentifier.created_at.asc(), PersonIdentifier.id.asc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_identifier(self, identifier: PersonIdentifier) -> PersonIdentifier:
        # Single choke point for identifier inserts: always derive the canonical
        # match key from (kind, value) so matching/dedup compares on it. The
        # service has already normalised ``value``; ``identifier_match_key`` is
        # idempotent on a normalised value and total (never raises).
        identifier.value_match_key = identifier_match_key(
            identifier.kind, identifier.value
        )
        self._session.add(identifier)
        await self._session.flush()
        return identifier

    # --- Source links ---
    async def find_source_link(
        self,
        tenant_id: TenantId,
        source_system: str,
        source_instance: str,
        source_kind: str,
        source_id: str,
    ) -> SourceLink | None:
        """Look up a source link by its external triple.

        ``source_id`` is required for lookup — links with NULL ``source_id``
        are not addressable through this method (they are seed/manual rows
        without a stable provider identifier).
        """
        stmt = (
            for_tenant(select(SourceLink), tenant_id, SourceLink)
            .where(
                SourceLink.source_system == source_system,
                SourceLink.source_instance == source_instance,
                SourceLink.source_kind == source_kind,
                SourceLink.source_id == source_id,
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def add_source_link(self, link: SourceLink) -> SourceLink:
        self._session.add(link)
        await self._session.flush()
        return link

    async def touch_source_link(self, tenant_id: TenantId, link_id: UUID) -> None:
        """Bump ``last_seen_at`` to ``now()`` without rewriting other columns.

        Called every time a re-pull observes the same external record. The
        update is in-place (single row, single column) so re-pull volume
        does not bloat row history.
        """
        await self._session.execute(
            update(SourceLink)
            .where(SourceLink.id == link_id)
            .where(SourceLink.tenant_id == tenant_id)
            .values(last_seen_at=func.now())
        )

    # --- Merge events ---
    async def add_merge_event(self, event: MergeEvent) -> MergeEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def is_person_retired(self, tenant_id: TenantId, person_uid: UUID) -> bool:
        """True if ``person_uid`` was already retired by an append-only merge
        (it appears as a ``merge_event.merged_person_uid``).

        Used by the ENG-544 replay live pass to stay idempotent: a tombstone
        source that a prior merge already collapsed must never be re-merged
        into a second survivor (a double-merge). Because ``add_merge_event``
        flushes, a merge recorded earlier in the SAME transaction is visible
        here too, so this also dedupes multiple open candidates that share one
        source person within a single replay pass.
        """
        stmt = select(
            exists().where(
                MergeEvent.tenant_id == tenant_id,
                MergeEvent.merged_person_uid == person_uid,
            )
        )
        return bool((await self._session.execute(stmt)).scalar())

    # --- Match candidates (ENG-182) ---
    async def add_match_candidate(self, candidate: MatchCandidate) -> MatchCandidate:
        self._session.add(candidate)
        await self._session.flush()
        return candidate

    async def get_match_candidate(
        self, tenant_id: TenantId, candidate_id: UUID
    ) -> MatchCandidate | None:
        stmt = for_tenant(select(MatchCandidate), tenant_id, MatchCandidate).where(
            MatchCandidate.id == candidate_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_open_match_for_pair(
        self, tenant_id: TenantId, person_pair_key: str
    ) -> MatchCandidate | None:
        """Return the open candidate for ``person_pair_key`` if one exists.

        Mirrors the partial-unique index
        ``uq_match_candidate_open_pair`` — at most one row matches.
        """
        stmt = (
            for_tenant(select(MatchCandidate), tenant_id, MatchCandidate)
            .where(
                MatchCandidate.person_pair_key == person_pair_key,
                MatchCandidate.status == "open",
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_active_hint_candidate(
        self,
        tenant_id: TenantId,
        hint_id: UUID,
        candidate_person_uid: UUID,
    ) -> MatchCandidate | None:
        """Return the active (``open``/``auto_accepted``/``accepted``) row.

        Mirrors the partial-unique
        ``uq_match_candidate_hint_candidate_active`` guard.
        """
        stmt = (
            for_tenant(select(MatchCandidate), tenant_id, MatchCandidate)
            .where(
                MatchCandidate.hint_id == hint_id,
                MatchCandidate.candidate_person_uid == candidate_person_uid,
                MatchCandidate.status.in_(("open", "auto_accepted", "accepted")),
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_persons_sharing_identifier(
        self,
        tenant_id: TenantId,
        kind: str,
        value: str,
        exclude_person_uid: UUID,
    ) -> list[Person]:
        """Return tenant-scoped persons whose ``(kind, value)`` identifier
        matches but whose ``id`` is not ``exclude_person_uid``.

        Used by the re-merge sweep to walk identifier overlaps without
        N+1 round-tripping through ``find_identifier``. Identifiers are
        loaded eagerly so the caller can score the pair without another
        SELECT per person.
        """
        stmt = (
            for_tenant(select(Person), tenant_id, Person)
            .join(PersonIdentifier, PersonIdentifier.person_id == Person.id)
            .where(
                PersonIdentifier.kind == kind,
                _value_or_match_key(value, identifier_match_key(kind, value)),
                Person.id != exclude_person_uid,
            )
            .options(selectinload(Person.identifiers))
            .distinct()
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def find_decided_match_for_pair(
        self,
        tenant_id: TenantId,
        person_pair_key: str,
    ) -> MatchCandidate | None:
        """Return any decided (accepted / auto_accepted / rejected) candidate
        for the pair, if one exists. Used by the sweep to skip pairs that
        have already been ruled on (positively or negatively)."""
        stmt = (
            for_tenant(select(MatchCandidate), tenant_id, MatchCandidate)
            .where(
                MatchCandidate.person_pair_key == person_pair_key,
                MatchCandidate.status.in_(("accepted", "auto_accepted", "rejected")),
            )
            .order_by(MatchCandidate.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_open_candidates_for_person(
        self,
        tenant_id: TenantId,
        person_uid: UUID,
    ) -> list[MatchCandidate]:
        """All open MatchCandidate rows where ``person_uid`` is the source OR
        the candidate side. Newest first."""
        stmt = (
            for_tenant(select(MatchCandidate), tenant_id, MatchCandidate)
            .where(
                MatchCandidate.status == "open",
                or_(
                    MatchCandidate.source_person_uid == person_uid,
                    MatchCandidate.candidate_person_uid == person_uid,
                ),
            )
            .order_by(MatchCandidate.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_open_reuse_candidates_created_after(
        self,
        tenant_id: TenantId,
        after: datetime,
        *,
        after_created_at: datetime | None = None,
        after_id: UUID | None = None,
        limit: int = 500,
    ) -> list[MatchCandidate]:
        """Open shared-contact-reuse candidates created at/after ``after``.

        The signal source for the ENG-555 Messenger alert: an OPEN
        ``match_candidate`` whose ``match_rule`` is one of
        :data:`REUSE_MATCH_RULES` (``phone_only_ambiguous`` /
        ``email_only_ambiguous``) — i.e. an incoming record reused a shared
        contact already held by an existing person. ``after`` is the no-retro
        cutoff (the caller passes ``Settings.notifications_cutoff_at``), so the
        pre-existing open backlog is never scanned.

        Ordered oldest-first on the stable keyset ``(created_at, id)``. Pass the
        last row's ``(created_at, id)`` as ``after_created_at`` / ``after_id`` to
        page forward: the caller loops until a short page so EVERY post-cutoff
        open candidate is visited each tick (the ``limit`` cap alone would
        starve rows beyond the first page once the head rows are emitted —
        ENG-555 Codex review). ``emit``'s ledger dedupe makes re-visiting an
        already-alerted candidate a cheap no-op.
        """
        stmt = for_tenant(select(MatchCandidate), tenant_id, MatchCandidate).where(
            MatchCandidate.status == "open",
            MatchCandidate.match_rule.in_(REUSE_MATCH_RULES),
            MatchCandidate.created_at >= after,
        )
        if after_created_at is not None and after_id is not None:
            # Keyset compare: tuple of columns vs a plain Python value tuple
            # (SQLAlchemy renders a row-value comparison; the RHS must be literal
            # values, not another tuple_() of columns).
            stmt = stmt.where(
                tuple_(MatchCandidate.created_at, MatchCandidate.id)
                > (after_created_at, after_id)
            )
        stmt = stmt.order_by(
            MatchCandidate.created_at.asc(), MatchCandidate.id.asc()
        ).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def update_match_candidate_status(
        self,
        tenant_id: TenantId,
        candidate_id: UUID,
        *,
        status: str,
        accepted_person_uid: UUID | None,
        decided_at: Any,
        decided_by_actor_id: UUID | None,
        merge_event_id: UUID | None = None,
    ) -> None:
        """Mutate a MatchCandidate's decision columns in place.

        The service layer enforces transition legality; this method just
        writes the row.
        """
        await self._session.execute(
            update(MatchCandidate)
            .where(MatchCandidate.id == candidate_id)
            .where(MatchCandidate.tenant_id == tenant_id)
            .values(
                status=status,
                accepted_person_uid=accepted_person_uid,
                decided_at=decided_at,
                decided_by_actor_id=decided_by_actor_id,
                merge_event_id=merge_event_id,
            )
        )

    async def list_persons_for_sweep(
        self,
        tenant_id: TenantId,
        *,
        updated_since: Any | None,
        limit: int,
    ) -> list[Person]:
        """Persons to consider in a sweep tick.

        ``updated_since=None`` means full sweep (all persons, ordered by
        ``id``). When set, return persons with ``updated_at >= updated_since``.
        Identifiers are loaded eagerly so the sweep does not N+1 per person.
        """
        stmt = for_tenant(select(Person), tenant_id, Person).options(
            selectinload(Person.identifiers)
        )
        if updated_since is not None:
            stmt = stmt.where(Person.updated_at >= updated_since)
        stmt = stmt.order_by(Person.id).limit(limit)
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_match_candidates_by_status(
        self,
        tenant_id: TenantId,
        statuses: tuple[str, ...],
        limit: int,
    ) -> list[MatchCandidate]:
        """List rows whose ``status`` is in ``statuses``, newest first.

        Used by the operator review UI / reconciliation worker; defaults
        to the indexed ``(tenant_id, status, created_at)`` access pattern.
        """
        if not statuses:
            return []
        stmt = (
            for_tenant(select(MatchCandidate), tenant_id, MatchCandidate)
            .where(MatchCandidate.status.in_(statuses))
            .order_by(MatchCandidate.created_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_open_match_candidates_after(
        self,
        tenant_id: TenantId,
        *,
        after_id: UUID | None,
        limit: int,
    ) -> list[MatchCandidate]:
        """Return a page of ``status='open'`` candidates ordered by ``id``.

        Cursor-based (``id > after_id``) so a full backfill/replay pass can
        page through every open row deterministically without OFFSET drift,
        even while earlier rows are being decided in a live pass (a decided
        row simply drops out of the ``status='open'`` filter on the next
        page). ``after_id=None`` starts from the first row.
        """
        stmt = (
            for_tenant(select(MatchCandidate), tenant_id, MatchCandidate)
            .where(MatchCandidate.status == "open")
            .order_by(MatchCandidate.id)
            .limit(limit)
        )
        if after_id is not None:
            stmt = stmt.where(MatchCandidate.id > after_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_open_match_candidates(self, tenant_id: TenantId) -> int:
        """Return the total number of ``status='open'`` candidates."""
        stmt = for_tenant(
            select(func.count(MatchCandidate.id)), tenant_id, MatchCandidate
        ).where(MatchCandidate.status == "open")
        return int((await self._session.execute(stmt)).scalar_one())

    async def reassign_source_links(
        self,
        tenant_id: TenantId,
        from_person_uid: UUID,
        to_person_uid: UUID,
    ) -> int:
        """Re-point every ``source_link`` of ``from_person_uid`` at
        ``to_person_uid`` (the surviving canonical person of a merge).

        Data-only: the service decides WHEN a merge happens and records the
        append-only ``merge_event``; this method just moves the provenance
        rows so the surviving person inherits the merged person's external
        origins. Returns the number of links moved. The merged person row is
        never deleted (append-only merge model) — it is left as a tombstone
        with zero source links.
        """
        result = await self._session.execute(
            update(SourceLink)
            .where(SourceLink.tenant_id == tenant_id)
            .where(SourceLink.person_uid == from_person_uid)
            .values(person_uid=to_person_uid)
        )
        return int(getattr(result, "rowcount", 0) or 0)
