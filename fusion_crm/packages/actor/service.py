"""ActorService — the only entry point for actor-domain logic.

Responsibilities:
  * upsert an Actor (idempotent on ``(actor_type, name)``)
  * attach an external identifier (idempotent on ``(kind, value)``)
  * resolve an Actor by external identifier

Every public method takes ``tenant_id: TenantId`` as the first positional
argument (ENG-128).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import NotFoundError, ValidationError
from packages.core.types import TenantId
from packages.identity.service import normalise_email, normalise_phone

from .models import Actor, ActorIdentifier
from .repository import ActorRepository
from .schemas import (
    ActorIdentifierIn,
    ActorIn,
    ProviderMessengerMappingOut,
)

# --- ENG-415 source-mapping constants --------------------------------------

# SF Id prefixes used to discriminate Users from Groups/Queues.
# Reference: Salesforce stable 3-char object prefixes.
_SF_USER_PREFIX = "005"
_SF_GROUP_PREFIX = "00G"

# Sofia AI uses a SINGLE actor across all tenants — the resolver treats
# any ``source_provider="sofia"`` call as the same actor.
_SOFIA_ACTOR_NAME = "Sofia AI"
_SOFIA_EXTERNAL_ID = "sofia_ai"


# Identifier kinds emitted by ``resolve_actor_from_source``. Mirrored in
# ``packages/actor/CLAUDE.md`` — keep them in sync.
ACTOR_KIND_SF_USER = "salesforce_user_id"
ACTOR_KIND_SF_GROUP = "salesforce_group_id"
ACTOR_KIND_CS_PROVIDER = "carestack_provider_id"
ACTOR_KIND_CS_USER_DETAIL = "carestack_user_detail_id"
ACTOR_KIND_SOFIA = "sofia_ai"

# Messenger mapping (ENG-543/ENG-546): a doctor's Mattermost @handle, stored on
# the same ``carestack_provider_id`` actor and resolved at reminder time.
ACTOR_KIND_MATTERMOST_USERNAME = "mattermost_username"


def _normalise_email_or_none(value: str | None) -> str | None:
    """Lowercase + validate email; pass through None.

    Reuses the identity domain's normaliser so actor emails are stored in the
    same canonical form as ``identity.person_identifier.value`` for kind=email
    — otherwise resolve-by-identifier lookups across the two domains diverge.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return normalise_email(stripped)


def _normalise_phone_or_none(value: str | None) -> str | None:
    """E.164-ish normalise (digits-only via identity service); pass through None."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return normalise_phone(stripped)


def _classify_source(
    source_provider: str, external_id: str
) -> tuple[str, str, str, str]:
    """Map a provider-shaped key to ``(actor_type, kind, value, default_name)``.

    See ``packages/actor/CLAUDE.md`` and the ENG-415 contract.
    """
    provider = source_provider.strip().lower()
    raw = external_id.strip()
    if provider == "salesforce":
        if raw.startswith(_SF_USER_PREFIX):
            return "human", ACTOR_KIND_SF_USER, raw, f"SF User {raw}"
        if raw.startswith(_SF_GROUP_PREFIX):
            return "system", ACTOR_KIND_SF_GROUP, raw, f"SF Group {raw}"
        raise ValidationError(
            "unrecognised Salesforce id prefix",
            details={"external_id": raw, "expected_prefixes": ["005", "00G"]},
        )
    if provider == "carestack":
        # CareStack provider ids are integers; userDetailId is the join key
        # to the users resource. Discriminate via a hint in the external_id
        # by allowing callers to prefix ``userdetail:`` for the user side.
        if raw.startswith("userdetail:"):
            value = raw.removeprefix("userdetail:").strip()
            if not value:
                raise ValidationError("empty carestack userdetail id")
            return (
                "human",
                ACTOR_KIND_CS_USER_DETAIL,
                value,
                f"CareStack User {value}",
            )
        return "human", ACTOR_KIND_CS_PROVIDER, raw, f"CareStack Provider {raw}"
    if provider == "sofia":
        if raw not in (_SOFIA_EXTERNAL_ID, _SOFIA_ACTOR_NAME):
            raise ValidationError(
                "sofia source_provider must use the canonical external_id",
                details={
                    "external_id": raw,
                    "expected": _SOFIA_EXTERNAL_ID,
                },
            )
        return "ai", ACTOR_KIND_SOFIA, _SOFIA_EXTERNAL_ID, _SOFIA_ACTOR_NAME
    raise ValidationError(
        "unknown source_provider",
        details={
            "source_provider": source_provider,
            "allowed": ["salesforce", "carestack", "sofia"],
        },
    )


def _ensure_source_instance(actor: Actor, source_instance: str | None) -> None:
    """Track which provider instances have referenced this actor.

    Idempotent: appends ``source_instance`` to ``actor.meta["sources"]``
    only if it is not already present. Source-instance provenance helps
    operators disambiguate multi-tenant SF orgs without altering the
    actor identity.
    """
    if not source_instance:
        return
    meta = dict(actor.meta or {})
    sources_raw = meta.get("sources")
    sources: list[str]
    if isinstance(sources_raw, list):
        sources = [str(s) for s in sources_raw if isinstance(s, str)]
    else:
        sources = []
    if source_instance in sources:
        return
    sources.append(source_instance)
    meta["sources"] = sources
    actor.meta = meta


def _normalise_identifier_value(kind: str, value: str) -> str:
    """Apply per-kind normalisation rules consistent with identity domain."""
    if kind == "email":
        return normalise_email(value)
    if kind == "phone":
        return normalise_phone(value)
    return value


class ActorService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ActorRepository(session)

    async def get_actor(self, tenant_id: TenantId, actor_id: UUID) -> Actor:
        actor = await self._repo.get_actor(tenant_id, actor_id)
        if actor is None:
            raise NotFoundError("actor not found", details={"actor_id": str(actor_id)})
        return actor

    async def find_by_identifier(
        self, tenant_id: TenantId, kind: str, value: str
    ) -> Actor | None:
        # Normalise the lookup value so callers passing "Anna@Example.com" or
        # "(415) 555-1234" still hit the same row that attach_identifier
        # canonicalised on insert. Without this, asymmetric normalisation
        # silently misses matches.
        normalised_value = _normalise_identifier_value(kind, value)
        identifier = await self._repo.find_identifier(
            tenant_id, kind, normalised_value
        )
        return identifier.actor if identifier else None

    async def resolve_linked_identifier(
        self,
        tenant_id: TenantId,
        source_kind: str,
        source_value: str,
        target_kind: str,
    ) -> str | None:
        """Return an actor's ``target_kind`` identifier value, found via another.

        Resolves the actor by ``(source_kind, source_value)`` then returns its
        identifier of ``target_kind`` (or ``None`` if no actor / no such
        identifier). ENG-543 uses it to map a consultation's
        ``carestack_provider_id`` → the doctor's ``mattermost_username`` for the
        reminder @mention. Never raises on a miss.
        """
        actor = await self.find_by_identifier(tenant_id, source_kind, source_value)
        if actor is None:
            return None
        for ident in await self._repo.list_identifiers(tenant_id, actor.id):
            if ident.kind == target_kind:
                return ident.value
        return None

    async def list_provider_messenger_mappings(
        self, tenant_id: TenantId
    ) -> list[ProviderMessengerMappingOut]:
        """List every CareStack provider (doctor) + its Mattermost username.

        Backs the Messenger-settings card (ENG-546). One row per
        ``carestack_provider_id`` actor; ``mattermost_username`` is ``None``
        when the doctor has not been mapped yet. Mirrors the directory the
        interim ``set_provider_mattermost.py --list`` script prints.
        """
        rows = await self._repo.list_actors_with_identifier(
            tenant_id, ACTOR_KIND_CS_PROVIDER
        )
        out: list[ProviderMessengerMappingOut] = []
        for actor, provider_id in rows:
            username = await self.resolve_linked_identifier(
                tenant_id,
                ACTOR_KIND_CS_PROVIDER,
                provider_id,
                ACTOR_KIND_MATTERMOST_USERNAME,
            )
            out.append(
                ProviderMessengerMappingOut(
                    actor_id=actor.id,
                    actor_name=actor.name,
                    carestack_provider_id=provider_id,
                    mattermost_username=username,
                )
            )
        return out

    async def set_provider_messenger_username(
        self,
        tenant_id: TenantId,
        carestack_provider_id: str,
        mattermost_username: str,
    ) -> ProviderMessengerMappingOut:
        """Map a CareStack provider (doctor) to a Mattermost username (ENG-546).

        Resolves the doctor's actor by its ``carestack_provider_id`` then sets
        its ``mattermost_username`` so the T-15m consult-reminder can @mention
        them. Strips a leading ``@`` so callers may paste either form.

        CORRECTNESS INVARIANT: ``attach_identifier`` is ADDITIVE. We therefore
        DELETE any existing ``mattermost_username`` rows on the actor BEFORE
        attaching the new one, leaving exactly one — otherwise a re-map keeps
        the stale handle too and ``resolve_linked_identifier`` returns an
        arbitrary one, producing a wrong @mention in production.

        Raises ``NotFoundError`` when no actor carries that
        ``carestack_provider_id``, and ``ValidationError`` when the username is
        blank after normalisation or is already attached to a different actor
        (surfaced by ``attach_identifier``).
        """
        actor = await self.find_by_identifier(
            tenant_id, ACTOR_KIND_CS_PROVIDER, carestack_provider_id
        )
        if actor is None:
            raise NotFoundError(
                "no provider actor for carestack_provider_id",
                details={"carestack_provider_id": carestack_provider_id},
            )

        username = mattermost_username.strip().lstrip("@").strip()
        if not username:
            raise ValidationError(
                "mattermost_username required",
                details={"mattermost_username": mattermost_username},
            )

        # Purge stale mappings first — see invariant in the docstring.
        await self._repo.delete_identifiers(
            tenant_id, actor.id, ACTOR_KIND_MATTERMOST_USERNAME
        )
        await self.attach_identifier(
            tenant_id, actor.id, ACTOR_KIND_MATTERMOST_USERNAME, username
        )
        return ProviderMessengerMappingOut(
            actor_id=actor.id,
            actor_name=actor.name,
            carestack_provider_id=carestack_provider_id,
            mattermost_username=username,
        )

    async def upsert_actor(
        self, tenant_id: TenantId, payload: ActorIn
    ) -> Actor:
        """Find or create an Actor by ``(actor_type, name)``.

        On a hit, refreshes the mutable demographic / status fields. Does NOT
        replace identifiers — use ``attach_identifier`` for that, idempotent.
        """
        existing = await self._repo.find_by_type_and_name(
            tenant_id, payload.actor_type, payload.name
        )

        # Normalise demographic fields BEFORE persistence — required by
        # CLAUDE.md ("Anna@Example.com and anna@example.com must not diverge").
        normalised_email = _normalise_email_or_none(payload.email)
        normalised_phone = _normalise_phone_or_none(payload.phone)

        if existing is None:
            actor = Actor(
                tenant_id=tenant_id,
                actor_type=payload.actor_type,
                name=payload.name,
                role=payload.role,
                status=payload.status,
                email=normalised_email,
                phone=normalised_phone,
                person_uid=payload.person_uid,
                availability_status=payload.availability_status,
                meta=dict(payload.meta),
            )
            await self._repo.add_actor(actor)
        else:
            # Refresh mutable fields. ``actor_type`` + ``name`` are the identity.
            existing.role = payload.role if payload.role is not None else existing.role
            existing.status = payload.status
            existing.email = normalised_email if normalised_email is not None else existing.email
            existing.phone = normalised_phone if normalised_phone is not None else existing.phone
            if payload.person_uid is not None:
                existing.person_uid = payload.person_uid
            existing.availability_status = payload.availability_status
            # Merge meta rather than replace.
            merged_meta = dict(existing.meta or {})
            merged_meta.update(payload.meta)
            existing.meta = merged_meta
            actor = existing

        for ident in payload.identifiers:
            await self.attach_identifier(tenant_id, actor.id, ident.kind, ident.value)

        return actor

    async def resolve_actor_from_source(
        self,
        tenant_id: TenantId,
        *,
        source_provider: str,
        source_instance: str,
        external_id: str,
        name_hint: str | None = None,
        role_hint: str | None = None,
    ) -> Actor:
        """Map an external party id to an ``actor.actor`` idempotently (ENG-415).

        See ``packages/actor/CLAUDE.md`` for the full mapping table. The
        method:

        1. Resolves ``(source_provider, external_id)`` to a canonical
           ``(actor_type, kind, identifier_value)`` triple.
        2. If an identifier row already exists for ``(kind, value)``,
           returns the attached actor.
        3. Otherwise: upserts the actor by ``(actor_type, name)`` and
           attaches the identifier.

        ``name_hint`` is used only when a new actor must be created —
        existing actors keep the name they were originally created with
        (no surprise renames on re-pull).

        ``source_instance`` is stored under ``actor.meta["sources"]`` so
        callers can later disambiguate cross-instance lookups without
        DDL — the actor still resolves to a single row per ``(kind,
        value)`` because ``actor_identifier`` is workspace-wide unique.
        """
        if not source_provider or not external_id:
            raise ValidationError(
                "source_provider and external_id are required",
                details={
                    "source_provider": source_provider,
                    "external_id": external_id,
                },
            )

        actor_type, kind, identifier_value, default_name = _classify_source(
            source_provider, external_id
        )

        existing = await self.find_by_identifier(tenant_id, kind, identifier_value)
        if existing is not None:
            # Track source-instance provenance without altering identity.
            _ensure_source_instance(existing, source_instance)
            return existing

        actor_name = (name_hint or default_name).strip() or default_name
        payload = ActorIn(
            actor_type=actor_type,  # type: ignore[arg-type]
            name=actor_name,
            role=role_hint,
            meta={"sources": [source_instance]} if source_instance else {},
            identifiers=[
                ActorIdentifierIn(kind=kind, value=identifier_value),
            ],
        )
        return await self.upsert_actor(tenant_id, payload)

    async def resolve_actor_ids_from_source(
        self,
        tenant_id: TenantId,
        *,
        source_provider: str,
        source_instance: str,
        external_ids: Iterable[str],
        name_hints: Mapping[str, str] | None = None,
    ) -> dict[str, UUID]:
        """Batch idempotent backfill: ``external_id → actor_id`` (ENG-509/510).

        Resolves each distinct ``external_id`` to an ``actor.actor`` via
        :meth:`resolve_actor_from_source` (create-or-lookup), returning the id
        map. Used by the analytics fact builder to fill caller / coordinator /
        doctor dimensions from a small set of distinct SF user / CareStack
        provider ids without per-person round-trips.

        Tolerant of unmappable ids: an ``external_id`` that
        ``resolve_actor_from_source`` rejects (e.g. a malformed SF prefix) is
        skipped — it stays absent from the map and the dimension ships NULL
        (method=unresolved) rather than failing the whole build. ``name_hints``
        (optional ``external_id → display name``) seed the name only when a new
        actor row is created.
        """
        hints = name_hints or {}
        out: dict[str, UUID] = {}
        for external_id in {e.strip() for e in external_ids if e and e.strip()}:
            try:
                actor = await self.resolve_actor_from_source(
                    tenant_id,
                    source_provider=source_provider,
                    source_instance=source_instance,
                    external_id=external_id,
                    name_hint=hints.get(external_id),
                )
            except ValidationError:
                # Unmappable id — leave the dimension unresolved rather than
                # aborting the backfill for one bad value.
                continue
            out[external_id] = actor.id
        return out

    async def attach_identifier(
        self,
        tenant_id: TenantId,
        actor_id: UUID,
        kind: str,
        value: str,
    ) -> ActorIdentifier:
        """Attach an external identifier to an Actor; idempotent on ``(kind, value)``.

        Raises ``ValidationError`` if the identifier already exists but points
        at a different actor — that's a real conflict and should be surfaced.
        """
        if not kind or not value:
            raise ValidationError("kind and value required")

        # Normalise so cross-domain lookup (e.g. resolve_by_email in identity)
        # finds the same canonical form. Per CLAUDE.md.
        normalised_value = _normalise_identifier_value(kind, value)

        existing = await self._repo.find_identifier(
            tenant_id, kind, normalised_value
        )
        if existing is not None:
            if existing.actor_id != actor_id:
                raise ValidationError(
                    "identifier already attached to a different actor",
                    details={
                        "kind": kind,
                        "value": normalised_value,
                        "existing_actor_id": str(existing.actor_id),
                        "requested_actor_id": str(actor_id),
                    },
                )
            return existing

        identifier = ActorIdentifier(
            tenant_id=tenant_id,
            actor_id=actor_id,
            kind=kind,
            value=normalised_value,
        )
        return await self._repo.add_identifier(identifier)
