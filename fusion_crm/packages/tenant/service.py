"""Tenant + Location services — public surface for the tenant domain.

Anything outside ``packages.tenant`` that wants to read or write tenant
configuration goes through these services. Models and repositories are
private to the package.

Audit policy (per `packages/tenant/CLAUDE.md`): every state-change
method writes an ``audit.access_log`` row at the service layer so
multiple call sites do not need to remember to audit.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.exceptions import ConflictError, NotFoundError, ValidationError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId

from ._windows_iana_tz import to_iana
from .models import (
    CREDENTIAL_KINDS,
    CREDENTIAL_STATUSES,
    PROVIDER_KINDS,
    TENANT_STATUSES,
    IntegrationCredential,
    Location,
    Setting,
    Tenant,
)
from .repository import LocationRepository, TenantRepository
from .schemas import (
    ImportSummary,
    IntegrationCredentialIn,
    LocationIn,
    SettingIn,
    TenantIn,
)

log = get_logger("tenant.service")


class CareStackLocationsClientProtocol(Protocol):
    """Minimum CareStack client surface used by ``import_locations_from_carestack``.

    The concrete implementation lives in
    ``packages.integrations.carestack`` and matches by duck-typing —
    we do not import it here to respect the
    ``tenant → integrations`` cross-package import rule (per
    ``packages/CLAUDE.md`` matrix). The wiring layer
    (``apps/api/dependencies.py``) constructs a real
    ``CareStackClient`` and passes it in.
    """

    async def list_locations(self) -> list[dict[str, Any]]: ...


class TenantService:
    """Public surface for tenant root + settings + credentials."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = TenantRepository(session)
        self._audit = AuditService(session)

    # --- Reads ---

    async def get_tenant(self, tenant_id: TenantId) -> Tenant:
        tenant = await self._repo.get(tenant_id)
        if tenant is None:
            raise NotFoundError("tenant not found", details={"tenant_id": str(tenant_id)})
        return tenant

    async def get_by_slug(self, slug: str) -> Tenant:
        tenant = await self._repo.get_by_slug(slug)
        if tenant is None:
            raise NotFoundError("tenant not found", details={"slug": slug})
        return tenant

    async def resolve_default(self, slug: str) -> Tenant:
        """Resolve the bootstrap tenant by slug.

        Used by the API dependency that builds ``Principal.tenant_id``
        from ``Settings.tenant_default_slug`` at request time. Raises
        ``NotFoundError`` if the slug is unknown — the bootstrap
        migration must have run before the app boots.
        """
        return await self.get_by_slug(slug)

    async def list_tenants(self) -> list[Tenant]:
        return await self._repo.list_all()

    # --- Writes (each writes audit) ---

    async def create_tenant(self, payload: TenantIn, *, principal: Principal) -> Tenant:
        if payload.status not in TENANT_STATUSES:
            raise ValidationError(
                "unknown tenant status",
                details={"status": payload.status, "allowed": list(TENANT_STATUSES)},
            )
        existing = await self._repo.get_by_slug(payload.slug)
        if existing is not None:
            raise ConflictError(
                "tenant slug already in use",
                details={"slug": payload.slug, "tenant_id": str(existing.id)},
            )
        tenant = Tenant(
            slug=payload.slug,
            name=payload.name,
            primary_email=payload.primary_email,
            timezone=payload.timezone,
            locale=payload.locale,
            status=payload.status,
        )
        await self._repo.add(tenant)
        await self._audit.record(
            principal=principal,
            action="tenant.create",
            resource="tenant",
            extra={"tenant_id": str(tenant.id), "slug": tenant.slug},
        )
        return tenant

    async def upsert_setting(
        self,
        tenant_id: TenantId,
        payload: SettingIn,
        *,
        principal: Principal,
    ) -> Setting:
        await self.get_tenant(tenant_id)
        existing = await self._repo.get_setting(tenant_id, payload.key)
        if existing is None:
            setting = Setting(
                tenant_id=tenant_id,
                key=payload.key,
                value=dict(payload.value),
            )
            await self._repo.add_setting(setting)
        else:
            existing.value = dict(payload.value)
            setting = existing
        await self._audit.record(
            principal=principal,
            action="tenant.setting.upsert",
            resource="tenant.setting",
            extra={"tenant_id": str(tenant_id), "key": payload.key},
        )
        return setting

    async def list_settings(self, tenant_id: TenantId) -> list[Setting]:
        await self.get_tenant(tenant_id)
        return await self._repo.list_settings(tenant_id)

    async def list_credentials(
        self,
        tenant_id: TenantId,
        provider_kind: str | None = None,
        *,
        include_revoked: bool = False,
    ) -> list[IntegrationCredential]:
        """List credential rows visible to operator UI.

        ``include_revoked`` defaults to ``False`` so the staff
        Settings → Integrations page only sees rows that are still
        operationally usable (``active`` / ``expired``). Revoked
        rows remain in the DB for audit and are accessible by
        explicit opt-in (future "Disconnected mailboxes" history
        view). Without this filter every revoked row from a past
        reconnect surfaces as a live mailbox in the UI.
        """
        await self.get_tenant(tenant_id)
        if provider_kind is not None and provider_kind not in PROVIDER_KINDS:
            raise ValidationError(
                "unknown provider_kind",
                details={
                    "provider_kind": provider_kind,
                    "allowed": list(PROVIDER_KINDS),
                },
            )
        return await self._repo.list_credentials(
            tenant_id, provider_kind, include_revoked=include_revoked
        )

    async def record_credential(
        self,
        tenant_id: TenantId,
        payload: IntegrationCredentialIn,
        *,
        principal: Principal,
    ) -> IntegrationCredential:
        """Insert a new credential row.

        ``payload.payload`` MUST already contain ciphertext values
        (encrypted at the application layer). The service performs no
        encryption — callers wrap secrets with
        ``packages.integrations.crypto.encrypt_str`` before calling.
        """
        await self.get_tenant(tenant_id)
        if payload.provider_kind not in PROVIDER_KINDS:
            raise ValidationError(
                "unknown provider_kind",
                details={
                    "provider_kind": payload.provider_kind,
                    "allowed": list(PROVIDER_KINDS),
                },
            )
        if payload.credential_kind not in CREDENTIAL_KINDS:
            raise ValidationError(
                "unknown credential_kind",
                details={
                    "credential_kind": payload.credential_kind,
                    "allowed": list(CREDENTIAL_KINDS),
                },
            )
        if payload.status not in CREDENTIAL_STATUSES:
            raise ValidationError(
                "unknown credential status",
                details={
                    "status": payload.status,
                    "allowed": list(CREDENTIAL_STATUSES),
                },
            )

        cred = IntegrationCredential(
            tenant_id=tenant_id,
            provider_kind=payload.provider_kind,
            credential_kind=payload.credential_kind,
            payload=dict(payload.payload),
            display_name=payload.display_name,
            status=payload.status,
            expires_at=payload.expires_at,
            last_refreshed_at=payload.last_refreshed_at,
        )
        await self._repo.add_credential(cred)
        await self._audit.record(
            principal=principal,
            action="tenant.credential.record",
            resource="tenant.integration_credential",
            extra={
                "tenant_id": str(tenant_id),
                "credential_id": str(cred.id),
                "provider_kind": cred.provider_kind,
                "credential_kind": cred.credential_kind,
            },
        )
        return cred

    async def revoke_credential(
        self,
        tenant_id: TenantId,
        credential_id: UUID,
        *,
        principal: Principal,
    ) -> IntegrationCredential:
        cred = await self._repo.get_credential(tenant_id, credential_id)
        if cred is None:
            raise NotFoundError(
                "credential not found",
                details={
                    "tenant_id": str(tenant_id),
                    "credential_id": str(credential_id),
                },
            )
        cred.status = "revoked"
        await self._audit.record(
            principal=principal,
            action="tenant.credential.revoke",
            resource="tenant.integration_credential",
            extra={
                "tenant_id": str(tenant_id),
                "credential_id": str(credential_id),
            },
        )
        return cred


class LocationService:
    """Public surface for tenant locations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = LocationRepository(session)
        self._tenant_repo = TenantRepository(session)
        self._audit = AuditService(session)

    async def get_location(self, tenant_id: TenantId, location_id: UUID) -> Location:
        location = await self._repo.get(location_id)
        if location is None or location.tenant_id != tenant_id:
            raise NotFoundError(
                "location not found",
                details={
                    "tenant_id": str(tenant_id),
                    "location_id": str(location_id),
                },
            )
        return location

    async def list_locations(
        self, tenant_id: TenantId, *, only_active: bool = False
    ) -> list[Location]:
        # Validate tenant exists; cleaner error than empty list.
        if (await self._tenant_repo.get(tenant_id)) is None:
            raise NotFoundError("tenant not found", details={"tenant_id": str(tenant_id)})
        return await self._repo.list_for_tenant(tenant_id, only_active=only_active)

    async def find_by_carestack_id(
        self, tenant_id: TenantId, carestack_location_id: int
    ) -> Location | None:
        """Resolve a CareStack location id to a local tenant location."""
        if (await self._tenant_repo.get(tenant_id)) is None:
            raise NotFoundError("tenant not found", details={"tenant_id": str(tenant_id)})
        return await self._repo.find_by_carestack_id(tenant_id, carestack_location_id)

    async def upsert_location(
        self,
        tenant_id: TenantId,
        payload: LocationIn,
        *,
        principal: Principal,
    ) -> Location:
        if (await self._tenant_repo.get(tenant_id)) is None:
            raise NotFoundError("tenant not found", details={"tenant_id": str(tenant_id)})
        existing = await self._repo.find_by_name(tenant_id, payload.name)
        if existing is None:
            location = Location(
                tenant_id=tenant_id,
                name=payload.name,
                short_name=payload.short_name,
                external_ref=dict(payload.external_ref),
                address_line1=payload.address_line1,
                address_line2=payload.address_line2,
                city=payload.city,
                state=payload.state,
                zip=payload.zip,
                country=payload.country,
                phone=payload.phone,
                timezone_override=payload.timezone_override,
                latitude=payload.latitude,
                longitude=payload.longitude,
                is_active=payload.is_active,
            )
            await self._repo.add(location)
            action = "tenant.location.create"
        else:
            existing.short_name = payload.short_name
            existing.external_ref = dict(payload.external_ref)
            existing.address_line1 = payload.address_line1
            existing.address_line2 = payload.address_line2
            existing.city = payload.city
            existing.state = payload.state
            existing.zip = payload.zip
            existing.country = payload.country
            existing.phone = payload.phone
            existing.timezone_override = payload.timezone_override
            existing.latitude = payload.latitude
            existing.longitude = payload.longitude
            existing.is_active = payload.is_active
            location = existing
            action = "tenant.location.update"

        await self._audit.record(
            principal=principal,
            action=action,
            resource="tenant.location",
            extra={
                "tenant_id": str(tenant_id),
                "location_id": str(location.id),
                "name": location.name,
            },
        )
        return location

    # ------------------------------------------------------------------ CareStack import

    async def import_locations_from_carestack(
        self,
        tenant_id: TenantId,
        cs_client: CareStackLocationsClientProtocol,
        *,
        principal: Principal,
    ) -> ImportSummary:
        """Pull ``GET /api/v1.0/locations`` from CareStack and upsert
        into ``tenant.location``.

        Idempotent: re-running updates only changed fields. Locations
        present locally that no longer appear upstream are marked
        ``is_active = false`` (history preserved, never deleted).

        Audit: one ``tenant.location.upsert_from_carestack`` row per
        upserted location with ``op ∈ {create, update, deactivate}``.
        No PHI lands in audit ``extra`` — only non-PHI structural
        identifiers (``tenant_id``, ``carestack_location_id``).

        Concurrency: this method only mutates rows it owns
        (``tenant.location`` for the supplied ``tenant_id``) and
        does not commit — the caller's unit of work commits.
        Re-running concurrently is safe: a duplicate insert hits the
        ``(tenant_id, name)`` unique index; the caller's transaction
        rolls back and the user retries. The append-only audit row
        is created in the same UoW so partial state is impossible.
        """
        if (await self._tenant_repo.get(tenant_id)) is None:
            raise NotFoundError("tenant not found", details={"tenant_id": str(tenant_id)})

        upstream = await cs_client.list_locations()
        if not isinstance(upstream, list):
            raise ValidationError(
                "carestack /locations returned non-list",
                details={"type": type(upstream).__name__},
            )

        summary = ImportSummary(total_seen=len(upstream))
        seen_cs_ids: set[int] = set()

        for raw in upstream:
            cs_id_value = raw.get("id")
            if not isinstance(cs_id_value, int):
                # Skip malformed rows — CareStack guarantees integer ids,
                # but we'd rather drop one than corrupt the whole sync.
                log.warning(
                    "tenant.location.cs_import.skip_bad_id",
                    type=type(cs_id_value).__name__,
                )
                continue
            seen_cs_ids.add(cs_id_value)

            mapped = _map_carestack_location(raw)
            existing = await self._repo.find_by_carestack_id(tenant_id, cs_id_value)

            if existing is None:
                created = Location(
                    tenant_id=tenant_id,
                    external_ref={"carestack_location_id": cs_id_value},
                    name=mapped["name"],
                    short_name=mapped["short_name"],
                    address_line1=mapped["address_line1"],
                    address_line2=mapped["address_line2"],
                    city=mapped["city"],
                    state=mapped["state"],
                    zip=mapped["zip"],
                    phone=mapped["phone"],
                    timezone_override=mapped["timezone_override"],
                    latitude=mapped["latitude"],
                    longitude=mapped["longitude"],
                    is_active=mapped["is_active"],
                )
                await self._repo.add(created)
                summary = summary.model_copy(update={"created": summary.created + 1})
                await self._audit.record(
                    principal=principal,
                    action="tenant.location.upsert_from_carestack",
                    resource="tenant.location",
                    extra={
                        "tenant_id": str(tenant_id),
                        "carestack_location_id": cs_id_value,
                        "op": "create",
                    },
                )
            else:
                changed = _apply_changes(existing, mapped)
                # Always make sure the external_ref carries the CS id —
                # rows imported via a different code path may have a
                # different shape.
                desired_ref = {"carestack_location_id": cs_id_value}
                if dict(existing.external_ref) != desired_ref:
                    existing.external_ref = desired_ref
                    changed = True
                if changed:
                    summary = summary.model_copy(update={"updated": summary.updated + 1})
                    await self._audit.record(
                        principal=principal,
                        action="tenant.location.upsert_from_carestack",
                        resource="tenant.location",
                        extra={
                            "tenant_id": str(tenant_id),
                            "carestack_location_id": cs_id_value,
                            "op": "update",
                        },
                    )

        # Deactivate any local CS-linked rows missing from the upstream
        # response. Rows without a ``carestack_location_id`` are left
        # alone — they may have been created by a different provider
        # or by the operator.
        local_rows = await self._repo.list_for_tenant(tenant_id)
        for row in local_rows:
            ref = row.external_ref or {}
            local_cs_id = ref.get("carestack_location_id")
            if not isinstance(local_cs_id, int):
                continue
            if local_cs_id in seen_cs_ids:
                continue
            if not row.is_active:
                continue
            row.is_active = False
            summary = summary.model_copy(update={"deactivated": summary.deactivated + 1})
            await self._audit.record(
                principal=principal,
                action="tenant.location.upsert_from_carestack",
                resource="tenant.location",
                extra={
                    "tenant_id": str(tenant_id),
                    "carestack_location_id": local_cs_id,
                    "op": "deactivate",
                },
            )

        log.info(
            "tenant.location.cs_import.complete",
            tenant_id=str(tenant_id),
            created=summary.created,
            updated=summary.updated,
            deactivated=summary.deactivated,
            total_seen=summary.total_seen,
        )
        return summary


# ------------------------------------------------------------------ helpers


def _str_or_none(value: object) -> str | None:
    """Coerce the CareStack value into ``str | None``.

    CareStack returns empty strings rather than nulls for missing
    optional fields. Treat ``""`` as ``None`` so we don't store
    whitespace where ``NULL`` is more accurate.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    stripped = value.strip()
    return stripped or None


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None  # JSON has no bool/float ambiguity, but be defensive.
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _map_carestack_location(raw: dict[str, Any]) -> dict[str, Any]:
    """Translate a CareStack location payload into our column layout.

    CareStack shape (per ``docs/integrations/carestack/resources/locations.md``):

      { id, name, shortName, email, timeZone, phone1, phone2, fax,
        address: { addressLine1, addressLine2, city, state, zipCode },
        latitude, longitude, isActive }

    The CareStack spec does not document ``latitude``, ``longitude``,
    or ``isActive`` on the response, but the live API empirically
    returns them — when absent we fall back to ``None`` /  ``True``
    so the import stays robust.
    """
    address_raw = raw.get("address") or {}
    address: dict[str, Any] = address_raw if isinstance(address_raw, dict) else {}

    is_active_value = raw.get("isActive")
    is_active = bool(is_active_value) if isinstance(is_active_value, bool) else True

    return {
        "name": _str_or_none(raw.get("name")) or "",
        "short_name": _str_or_none(raw.get("shortName")),
        "address_line1": _str_or_none(address.get("addressLine1")),
        "address_line2": _str_or_none(address.get("addressLine2")),
        "city": _str_or_none(address.get("city")),
        "state": _str_or_none(address.get("state")),
        "zip": _str_or_none(address.get("zipCode")),
        "phone": _str_or_none(raw.get("phone1")),
        "timezone_override": to_iana(_str_or_none(raw.get("timeZone"))),
        "latitude": _float_or_none(raw.get("latitude")),
        "longitude": _float_or_none(raw.get("longitude")),
        "is_active": is_active,
    }


_TRACKED_COLUMNS: tuple[str, ...] = (
    "name",
    "short_name",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "zip",
    "phone",
    "timezone_override",
    "latitude",
    "longitude",
    "is_active",
)


def _apply_changes(existing: Location, mapped: dict[str, Any]) -> bool:
    """Mutate ``existing`` in place with values from ``mapped``.

    Only the columns in ``_TRACKED_COLUMNS`` are touched — everything
    else (``tenant_id``, ``country``, ``external_ref``, …) is owned
    by other code paths and must not be overwritten by a sync.
    Returns ``True`` if at least one column actually changed; ``False``
    means the upstream payload matches local state and no audit row
    is needed.
    """
    changed = False
    for column in _TRACKED_COLUMNS:
        new_value = mapped.get(column)
        if getattr(existing, column) != new_value:
            setattr(existing, column, new_value)
            changed = True
    return changed
