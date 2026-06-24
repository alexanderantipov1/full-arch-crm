"""Service-level tests for TenantService — validation + happy paths.

Repo is mocked in these tests; integration coverage with a real
PostgreSQL session lands when the test-DB harness expands beyond the
existing per-domain coverage. Per
`packages/CLAUDE.md` and root `CLAUDE.md`, integration tests must use
real Postgres, not mocks — the unit layer here only asserts validation
and audit-emission rules.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.exceptions import ConflictError, NotFoundError, ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.tenant.models import IntegrationCredential, Tenant
from packages.tenant.repository import TenantRepository
from packages.tenant.schemas import (
    IntegrationCredentialIn,
    LocationIn,
    SettingIn,
    TenantIn,
)
from packages.tenant.service import LocationService, TenantService


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="ops@example.com",
        roles=frozenset({Role.ADMIN}),
    )


def _make_tenant_service() -> tuple[TenantService, MagicMock, MagicMock]:
    session = MagicMock()
    service = TenantService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._audit = MagicMock()  # type: ignore[attr-defined]
    service._audit.record = AsyncMock()
    return service, service._repo, service._audit  # type: ignore[attr-defined]


def _make_location_service() -> tuple[LocationService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    service = LocationService(session)
    service._repo = MagicMock()  # type: ignore[attr-defined]
    service._tenant_repo = MagicMock()  # type: ignore[attr-defined]
    service._audit = MagicMock()  # type: ignore[attr-defined]
    service._audit.record = AsyncMock()
    return (
        service,
        service._repo,  # type: ignore[attr-defined]
        service._tenant_repo,  # type: ignore[attr-defined]
        service._audit,  # type: ignore[attr-defined]
    )


def _scalar_one_or_none_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


# --- create_tenant ---


@pytest.mark.asyncio
async def test_create_tenant_rejects_duplicate_slug() -> None:
    service, repo, _audit = _make_tenant_service()
    existing = Tenant(slug="existing", name="Existing")
    existing.id = uuid.uuid4()
    repo.get_by_slug = AsyncMock(return_value=existing)

    with pytest.raises(ConflictError):
        await service.create_tenant(
            TenantIn(slug="existing", name="Other"),
            principal=_principal(),
        )


@pytest.mark.asyncio
async def test_create_tenant_emits_audit() -> None:
    service, repo, audit = _make_tenant_service()
    repo.get_by_slug = AsyncMock(return_value=None)

    captured: dict[str, Tenant] = {}

    async def _capture(tenant: Tenant) -> Tenant:
        captured["tenant"] = tenant
        return tenant

    repo.add = AsyncMock(side_effect=_capture)

    await service.create_tenant(
        TenantIn(slug="acme", name="Acme Dental"),
        principal=_principal(),
    )

    assert captured["tenant"].slug == "acme"
    audit.record.assert_awaited_once()
    kwargs = audit.record.await_args.kwargs
    assert kwargs["action"] == "tenant.create"
    assert kwargs["resource"] == "tenant"


# --- resolve_default ---


@pytest.mark.asyncio
async def test_resolve_default_raises_when_missing() -> None:
    service, repo, _ = _make_tenant_service()
    repo.get_by_slug = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.resolve_default("nope")


# --- upsert_setting ---


@pytest.mark.asyncio
async def test_upsert_setting_inserts_when_absent() -> None:
    service, repo, audit = _make_tenant_service()
    tenant_id = TenantId(uuid.uuid4())
    repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    repo.get_setting = AsyncMock(return_value=None)
    repo.add_setting = AsyncMock(side_effect=lambda s: s)

    result = await service.upsert_setting(
        tenant_id,
        SettingIn(key="business_hours", value={"mon": "9-18"}),
        principal=_principal(),
    )

    assert result.key == "business_hours"
    audit.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_setting_updates_existing() -> None:
    """Second call with the same key replaces value, no insert."""
    service, repo, audit = _make_tenant_service()
    tenant_id = TenantId(uuid.uuid4())

    from packages.tenant.models import Setting

    existing = Setting(tenant_id=tenant_id, key="business_hours", value={"mon": "old"})
    repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    repo.get_setting = AsyncMock(return_value=existing)
    repo.add_setting = AsyncMock()

    result = await service.upsert_setting(
        tenant_id,
        SettingIn(key="business_hours", value={"mon": "new"}),
        principal=_principal(),
    )

    assert result is existing
    assert existing.value == {"mon": "new"}
    repo.add_setting.assert_not_called()


# --- record_credential ---


@pytest.mark.asyncio
async def test_record_credential_happy_path_emits_audit() -> None:
    service, repo, audit = _make_tenant_service()
    tenant_id = TenantId(uuid.uuid4())
    repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))

    captured: dict[str, IntegrationCredential] = {}

    async def _capture(cred: IntegrationCredential) -> IntegrationCredential:
        captured["cred"] = cred
        return cred

    repo.add_credential = AsyncMock(side_effect=_capture)

    await service.record_credential(
        tenant_id,
        IntegrationCredentialIn(
            provider_kind="salesforce",
            credential_kind="oauth_token",
            payload={"access_token": "ciphertext-base64"},
            display_name="Salesforce production org",
        ),
        principal=_principal(),
    )

    assert captured["cred"].provider_kind == "salesforce"
    audit.record.assert_awaited_once()
    assert audit.record.await_args.kwargs["action"] == "tenant.credential.record"


@pytest.mark.asyncio
async def test_record_credential_unknown_provider_via_model_construct() -> None:
    """Service-side check fires when payload bypasses Pydantic literal guard.

    The Pydantic schema's ``Literal`` type catches obvious typos at the API
    boundary; the service-layer check is defence-in-depth for callers that
    construct an ``IntegrationCredentialIn`` via ``model_construct`` (e.g.
    a worker reading provider rows from a database). Use ``model_construct``
    here so the test exercises the service's guard, not Pydantic's.
    """
    service, repo, _ = _make_tenant_service()
    repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))

    payload = IntegrationCredentialIn.model_construct(
        provider_kind="unsupported",  # type: ignore[arg-type]
        credential_kind="api_key",
        payload={"secret": "ciphertext"},
        display_name=None,
        status="active",
        expires_at=None,
        last_refreshed_at=None,
    )

    with pytest.raises(ValidationError) as excinfo:
        await service.record_credential(
            TenantId(uuid.uuid4()),
            payload,
            principal=_principal(),
        )
    assert "unknown provider_kind" in str(excinfo.value)


@pytest.mark.asyncio
async def test_list_credentials_hides_revoked_by_default() -> None:
    """The default operator-UI projection excludes revoked rows.

    Without this default, every soft-revoked credential from a past
    reconnect surfaces in Settings → Integrations as a live mailbox.
    See ENG-175 follow-up after the SF reconnect-loop fix.
    """
    service, repo, _audit = _make_tenant_service()
    repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    repo.list_credentials = AsyncMock(return_value=[])

    await service.list_credentials(TenantId(uuid.uuid4()))

    repo.list_credentials.assert_awaited_once()
    kwargs = repo.list_credentials.await_args.kwargs
    assert kwargs.get("include_revoked") is False, (
        "service must default include_revoked=False so revoked rows "
        "do not leak into the staff Settings → Integrations UI"
    )


@pytest.mark.asyncio
async def test_list_credentials_opt_in_includes_revoked() -> None:
    """Admin / history views can opt in via include_revoked=True."""
    service, repo, _audit = _make_tenant_service()
    repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    repo.list_credentials = AsyncMock(return_value=[])

    await service.list_credentials(TenantId(uuid.uuid4()), include_revoked=True)

    kwargs = repo.list_credentials.await_args.kwargs
    assert kwargs.get("include_revoked") is True


# --- revoke_credential ---


@pytest.mark.asyncio
async def test_revoke_credential_uses_tenant_scoped_lookup() -> None:
    service, repo, audit = _make_tenant_service()
    tenant_id = TenantId(uuid.uuid4())
    credential_id = uuid.uuid4()
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="oauth_token",
        payload={"access_token": "ciphertext-base64"},
        status="active",
    )
    cred.id = credential_id
    repo.get_credential = AsyncMock(return_value=cred)

    result = await service.revoke_credential(
        tenant_id,
        credential_id,
        principal=_principal(),
    )

    assert result is cred
    assert cred.status == "revoked"
    repo.get_credential.assert_awaited_once_with(tenant_id, credential_id)
    audit.record.assert_awaited_once()
    assert audit.record.await_args.kwargs["action"] == "tenant.credential.revoke"


@pytest.mark.asyncio
async def test_revoke_credential_raises_when_scoped_lookup_misses() -> None:
    service, repo, audit = _make_tenant_service()
    tenant_id = TenantId(uuid.uuid4())
    credential_id = uuid.uuid4()
    repo.get_credential = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.revoke_credential(
            tenant_id,
            credential_id,
            principal=_principal(),
        )

    repo.get_credential.assert_awaited_once_with(tenant_id, credential_id)
    audit.record.assert_not_called()


@pytest.mark.asyncio
async def test_repository_get_credential_filters_by_tenant_and_credential_id() -> None:
    tenant_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="oauth_token",
        payload={"access_token": "ciphertext-base64"},
        status="active",
    )
    cred.id = credential_id
    session = MagicMock()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))
    repo = TenantRepository(session)

    result = await repo.get_credential(tenant_id, credential_id)

    assert result is cred
    stmt = session.execute.await_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "integration_credential.tenant_id" in compiled
    assert "integration_credential.id" in compiled


# --- LocationService ---


@pytest.mark.asyncio
async def test_upsert_location_creates_when_absent() -> None:
    service, repo, tenant_repo, audit = _make_location_service()
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    repo.find_by_name = AsyncMock(return_value=None)
    repo.add = AsyncMock(side_effect=lambda loc: loc)

    result = await service.upsert_location(
        TenantId(uuid.uuid4()),
        LocationIn(name="Main", short_name="MAIN"),
        principal=_principal(),
    )

    assert result.name == "Main"
    audit.record.assert_awaited_once()
    assert audit.record.await_args.kwargs["action"] == "tenant.location.create"


@pytest.mark.asyncio
async def test_upsert_location_updates_existing() -> None:
    service, repo, tenant_repo, audit = _make_location_service()
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))

    from packages.tenant.models import Location

    existing = Location(
        tenant_id=uuid.uuid4(),
        name="Main",
        short_name="OLD",
        external_ref={},
    )
    existing.id = uuid.uuid4()
    repo.find_by_name = AsyncMock(return_value=existing)

    result = await service.upsert_location(
        TenantId(existing.tenant_id),
        LocationIn(name="Main", short_name="NEW"),
        principal=_principal(),
    )

    assert result is existing
    assert existing.short_name == "NEW"
    assert audit.record.await_args.kwargs["action"] == "tenant.location.update"


@pytest.mark.asyncio
async def test_list_locations_raises_when_tenant_missing() -> None:
    service, _, tenant_repo, _ = _make_location_service()
    tenant_repo.get = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.list_locations(TenantId(uuid.uuid4()))


@pytest.mark.asyncio
async def test_find_by_carestack_id_resolves_location() -> None:
    service, repo, tenant_repo, _ = _make_location_service()
    tenant_id = TenantId(uuid.uuid4())
    tenant_repo.get = AsyncMock(return_value=Tenant(slug="x", name="X"))
    location = object()
    repo.find_by_carestack_id = AsyncMock(return_value=location)

    result = await service.find_by_carestack_id(tenant_id, 10029)

    assert result is location
    repo.find_by_carestack_id.assert_awaited_once_with(tenant_id, 10029)
