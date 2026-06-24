"""Service-level tests for IntegrationCredentialService (ENG-125).

Covers the encryption envelope round-trip, upsert idempotency, the
``is_default`` atomic flip, multi-mailbox isolation, the no-credential
error path, and the audit-no-leak invariant.

The session and the executed SQL are stubbed — these are unit tests for
the service contract, not integration tests. A separate integration
test (when the test-DB harness lands) will exercise the real partial
unique index + GIN tag index behaviour.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

from packages.core.exceptions import ValidationError
from packages.core.security import Principal, Role
from packages.core.types import TenantId
from packages.integrations import crypto
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
    _unwrap_envelope,
    _wrap_envelope,
)
from packages.tenant.models import IntegrationCredential, Location
from packages.tenant.schemas import (
    IntegrationCredentialBootstrapIn,
    IntegrationCredentialUpdate,
)


@pytest.fixture(autouse=True)
def _isolate_fernet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a real Fernet without going through ``Settings``.

    Mirrors the pattern in ``tests/integrations/test_crypto.py`` —
    avoids the requirement that ``SECRET_KEY`` / ``DATABASE_URL`` be
    set in the test environment (Settings would raise at construction).
    """
    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(crypto, "_get_fernet", lambda: fernet)


def _principal() -> Principal:
    return Principal(
        id=uuid.uuid4(),
        email="ops@example.com",
        roles=frozenset({Role.ADMIN}),
    )


def _make_service() -> tuple[IntegrationCredentialService, MagicMock, MagicMock]:
    """Construct a service with the session + audit replaced by mocks."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.delete = AsyncMock()

    async def _refresh(row: IntegrationCredential) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        if row.id is None:
            row.id = uuid.uuid4()
        if row.created_at is None:
            row.created_at = now
        if row.updated_at is None:
            row.updated_at = now
        if row.tags is None:
            row.tags = []

    session.refresh = AsyncMock(side_effect=_refresh)
    service = IntegrationCredentialService(session)
    service._audit = MagicMock()  # type: ignore[attr-defined]
    service._audit.record = AsyncMock()
    return service, session, service._audit  # type: ignore[attr-defined]


def _mark_persisted(row: IntegrationCredential) -> IntegrationCredential:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    row.created_at = now
    row.updated_at = now
    if row.tags is None:
        row.tags = []
    return row


# --- Envelope round-trip ---


def test_envelope_round_trip() -> None:
    payload = {"access_token": "abc.def.ghi", "instance_url": "https://x.my.salesforce.com"}
    envelope = _wrap_envelope(payload)
    assert envelope["alg"] == "fernet"
    assert isinstance(envelope["ciphertext"], str) and len(envelope["ciphertext"]) > 0
    decoded = _unwrap_envelope(envelope)
    assert decoded == payload


def test_envelope_rejects_tampered_alg() -> None:
    payload = {"x": "y"}
    envelope = _wrap_envelope(payload)
    envelope["alg"] = "rot13"
    with pytest.raises(ValidationError):
        _unwrap_envelope(envelope)


def test_envelope_rejects_missing_ciphertext() -> None:
    with pytest.raises(ValidationError):
        _unwrap_envelope({"alg": "fernet"})


# --- read_for ---


def _scalar_one_or_none_result(value: Any) -> MagicMock:
    """Build the chain that ``await session.execute(stmt)`` returns."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    return result


def _scalars_all_result(values: list[Any]) -> MagicMock:
    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=values)
    result.scalars = MagicMock(return_value=scalars)
    return result


def _assert_statement_filters_tenant_and_credential(stmt: Any) -> None:
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "integration_credential.tenant_id" in compiled
    assert "integration_credential.id" in compiled


@pytest.mark.asyncio
async def test_read_for_unknown_provider_raises() -> None:
    service, _session, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.read_for(TenantId(uuid.uuid4()), "nope-provider")


@pytest.mark.asyncio
async def test_read_for_returns_decrypted_payload() -> None:
    service, session, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    payload = {"access_token": "abc", "instance_url": "https://x"}
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="oauth_token",
        payload=_wrap_envelope(payload),
        status="active",
    )
    cred.id = uuid.uuid4()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))

    result = await service.read_for(tenant_id, "salesforce", "oauth_token")
    assert result == payload


@pytest.mark.asyncio
async def test_read_for_raises_when_missing() -> None:
    service, session, _ = _make_service()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))

    with pytest.raises(NoCredentialError):
        await service.read_for(TenantId(uuid.uuid4()), "salesforce", "oauth_token")


# --- read_by_id ---


@pytest.mark.asyncio
async def test_read_by_id_uses_tenant_scoped_lookup() -> None:
    service, session, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    credential_id = uuid.uuid4()
    payload = {"access_token": "abc"}
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="oauth_token",
        payload=_wrap_envelope(payload),
        status="active",
    )
    cred.id = credential_id
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))

    result = await service.read_by_id(credential_id, tenant_id=tenant_id)

    assert result == payload
    _assert_statement_filters_tenant_and_credential(session.execute.await_args.args[0])
    assert not hasattr(session, "get") or not session.get.called


@pytest.mark.asyncio
async def test_read_by_id_raises_when_scoped_lookup_misses() -> None:
    service, session, _ = _make_service()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))

    with pytest.raises(NoCredentialError):
        await service.read_by_id(uuid.uuid4(), tenant_id=TenantId(uuid.uuid4()))


# --- upsert idempotency ---


@pytest.mark.asyncio
async def test_upsert_inserts_when_no_existing_row() -> None:
    service, session, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    # First call to find existing → none. The default-flip path is NOT
    # triggered since is_default=False.
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))

    captured: dict[str, IntegrationCredential] = {}

    def _add(row: IntegrationCredential) -> None:
        row.id = uuid.uuid4()
        captured["row"] = row

    session.add.side_effect = _add

    out = await service.upsert(
        tenant_id,
        "salesforce",
        "oauth_token",
        {
            "access_token": "super-secret-access-token",
            "instance_url": "https://x",
        },
        principal=_principal(),
    )
    assert out.provider_kind == "salesforce"
    assert "row" in captured
    # Audit fires with the insert action and no payload bytes.
    audit.record.assert_awaited_once()
    extra = audit.record.await_args.kwargs["extra"]
    assert "credential_id" in extra
    assert "tenant_id" in extra
    # Make absolutely sure the secret is not on the audit row.
    serialised = json.dumps(extra)
    assert "super-secret-access-token" not in serialised


@pytest.mark.asyncio
async def test_upsert_updates_existing_row_payload_only() -> None:
    service, session, _audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    existing = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="oauth_token",
        payload=_wrap_envelope({"access_token": "old"}),
        display_name="old-name",
        status="active",
    )
    existing.id = uuid.uuid4()
    existing.is_default = False
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(existing))

    out = await service.upsert(
        tenant_id,
        "salesforce",
        "oauth_token",
        {"access_token": "new"},
        principal=_principal(),
    )
    # Same row id — no insert.
    assert out.id == existing.id
    # Display name unchanged when not provided.
    assert existing.display_name == "old-name"
    # Payload re-wrapped to the new value.
    assert _unwrap_envelope(dict(existing.payload)) == {"access_token": "new"}


# --- is_default atomic flip ---


@pytest.mark.asyncio
async def test_set_default_clears_others_atomically() -> None:
    service, session, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    target = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="google_workspace",
        credential_kind="oauth_token",
        payload=_wrap_envelope({"access_token": "x"}),
        status="active",
    )
    target.id = uuid.uuid4()
    target.is_default = False
    _mark_persisted(target)
    # session.execute is called for scoped credential lookup, then for the
    # UPDATE clearing defaults.
    session.execute = AsyncMock(side_effect=[_scalar_one_or_none_result(target), MagicMock()])

    out = await service.set_default(
        target.id,
        tenant_id=tenant_id,
        provider_kind="google_workspace",
        principal=_principal(),
    )
    assert target.is_default is True
    assert out.id == target.id
    # The scoped lookup and clear-others UPDATE both ran.
    assert session.execute.await_count == 2
    _assert_statement_filters_tenant_and_credential(session.execute.await_args_list[0].args[0])
    audit.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_default_rejects_inactive_credential() -> None:
    service, session, _ = _make_service()
    cred = IntegrationCredential(
        tenant_id=uuid.uuid4(),
        provider_kind="google_workspace",
        credential_kind="oauth_token",
        payload=_wrap_envelope({}),
        status="revoked",
    )
    cred.id = uuid.uuid4()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))
    with pytest.raises(ValidationError):
        await service.set_default(
            cred.id,
            tenant_id=TenantId(cred.tenant_id),
            provider_kind="google_workspace",
            principal=_principal(),
        )


# --- metadata update ---


@pytest.mark.asyncio
async def test_update_metadata_updates_metadata_without_touching_payload() -> None:
    service, session, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    location_id = uuid.uuid4()
    stored_payload = _wrap_envelope({"access_token": "old-secret-token"})
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="google_workspace",
        credential_kind="oauth_token",
        payload=stored_payload,
        status="active",
        display_name="Old",
        tags=["old"],
    )
    cred.id = uuid.uuid4()
    cred.is_default = False
    _mark_persisted(cred)
    location = Location(tenant_id=tenant_id, name="Main")
    location.id = location_id
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))
    session.get = AsyncMock(return_value=location)

    out = await service.update_metadata(
        cred.id,
        tenant_id=tenant_id,
        payload=IntegrationCredentialUpdate(
            display_name="Main mailbox",
            location_id=location_id,
            tags=["marketing"],
            status="expired",
        ),
        principal=_principal(),
    )

    assert out.id == cred.id
    assert cred.display_name == "Main mailbox"
    assert cred.location_id == location_id
    assert cred.tags == ["marketing"]
    assert cred.status == "expired"
    assert dict(cred.payload) == stored_payload
    audit.record.assert_awaited_once()
    extra = audit.record.await_args.kwargs["extra"]
    serialised = json.dumps(extra)
    assert "old-secret-token" not in serialised
    assert "access_token" not in serialised


@pytest.mark.asyncio
async def test_update_metadata_raises_when_tenant_mismatch() -> None:
    service, session, _ = _make_service()
    credential_id = uuid.uuid4()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))

    with pytest.raises(NoCredentialError):
        await service.update_metadata(
            credential_id,
            tenant_id=TenantId(uuid.uuid4()),
            payload=IntegrationCredentialUpdate(display_name="Nope"),
            principal=_principal(),
        )


@pytest.mark.asyncio
async def test_update_metadata_rejects_location_from_other_tenant() -> None:
    service, session, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    location_id = uuid.uuid4()
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="google_workspace",
        credential_kind="oauth_token",
        payload=_wrap_envelope({}),
        status="active",
    )
    cred.id = uuid.uuid4()
    location = Location(tenant_id=uuid.uuid4(), name="Other")
    location.id = location_id
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))
    session.get = AsyncMock(return_value=location)

    with pytest.raises(ValidationError):
        await service.update_metadata(
            cred.id,
            tenant_id=tenant_id,
            payload=IntegrationCredentialUpdate(location_id=location_id),
            principal=_principal(),
        )


@pytest.mark.asyncio
async def test_update_metadata_clears_default_when_status_becomes_inactive() -> None:
    """An active default credential updated to ``status='expired'`` without
    an explicit ``is_default=False`` must end with ``is_default = False``.

    Otherwise the operator UI would keep showing an expired row as the
    provider default — confusing metadata even though runtime reads still
    filter on ``status='active'``.
    """
    service, session, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="oauth_token",
        payload=_wrap_envelope({"access_token": "x"}),
        status="active",
    )
    cred.id = uuid.uuid4()
    cred.is_default = True
    _mark_persisted(cred)
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))

    out = await service.update_metadata(
        cred.id,
        tenant_id=tenant_id,
        payload=IntegrationCredentialUpdate(status="expired"),
        principal=_principal(),
    )

    assert cred.status == "expired"
    assert cred.is_default is False
    assert out.is_default is False
    audit.record.assert_awaited_once()
    extra = audit.record.await_args.kwargs["extra"]
    assert extra["is_default"] is False


@pytest.mark.asyncio
async def test_update_metadata_rejects_revoke_status() -> None:
    service, session, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="oauth_token",
        payload=_wrap_envelope({}),
        status="active",
    )
    cred.id = uuid.uuid4()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))

    with pytest.raises(ValidationError):
        await service.update_metadata(
            cred.id,
            tenant_id=tenant_id,
            payload=IntegrationCredentialUpdate(status="revoked"),
            principal=_principal(),
        )


@pytest.mark.asyncio
async def test_expire_active_for_marks_matching_rows_expired() -> None:
    service, session, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    active = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="oauth_token",
        payload=_wrap_envelope({"access_token": "stale-token"}),
        status="active",
    )
    active.id = uuid.uuid4()
    active.is_default = True
    other = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="api_key",
        payload=_wrap_envelope({"client_id": "client"}),
        status="active",
    )
    other.id = uuid.uuid4()
    other.is_default = True
    session.execute = AsyncMock(return_value=_scalars_all_result([active]))

    count = await service.expire_active_for(
        tenant_id,
        "salesforce",
        "oauth_token",
        principal=_principal(),
    )

    assert count == 1
    assert active.status == "expired"
    assert active.is_default is False
    assert other.status == "active"
    assert other.is_default is True
    session.flush.assert_awaited_once()
    audit.record.assert_awaited_once()
    extra = audit.record.await_args.kwargs["extra"]
    assert extra["expired_count"] == 1
    assert "stale-token" not in json.dumps(extra)


# --- bootstrap credential upsert ---


@pytest.mark.asyncio
async def test_upsert_bootstrap_salesforce_uses_encrypted_api_key_row() -> None:
    service, session, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())

    class _Result:
        def scalar_one_or_none(self) -> None:
            return None

    session.execute = AsyncMock(return_value=_Result())

    out = await service.upsert_bootstrap_credentials(
        tenant_id,
        IntegrationCredentialBootstrapIn(
            provider_kind="salesforce",
            client_id="sf-client-id",
            client_secret="sf-client-secret",
            callback_url="https://fusioncrm.app/api/integrations/salesforce/callback",
            domain="login.salesforce.com",
        ),
        principal=_principal(),
    )

    assert out.provider_kind == "salesforce"
    assert out.credential_kind == "api_key"
    stored = session.add.call_args.args[0]
    assert stored.is_default is False
    assert stored.payload["alg"] == "fernet"
    assert "sf-client-secret" not in json.dumps(stored.payload)
    assert _unwrap_envelope(dict(stored.payload)) == {
        "callback_url": "https://fusioncrm.app/api/integrations/salesforce/callback",
        "client_id": "sf-client-id",
        "client_secret": "sf-client-secret",
        "domain": "login.salesforce.com",
    }
    serialised_audit = json.dumps(audit.record.await_args.kwargs["extra"])
    assert "sf-client-secret" not in serialised_audit
    assert "client_secret" not in serialised_audit


@pytest.mark.asyncio
async def test_upsert_bootstrap_carestack_uses_password_grant_default() -> None:
    service, session, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())

    class _Result:
        def scalar_one_or_none(self) -> None:
            return None

    session.execute = AsyncMock(return_value=_Result())

    out = await service.upsert_bootstrap_credentials(
        tenant_id,
        IntegrationCredentialBootstrapIn(
            provider_kind="carestack",
            client_id="cs-client-id",
            client_secret="cs-client-secret",
            vendor_key="vendor",
            account_key="account-key",
            account_id="account-id",
            idp_base_url="https://identity.carestack.com",
            api_base_url="https://api.carestack.com",
            api_version="v1.0",
        ),
        principal=_principal(),
    )

    assert out.provider_kind == "carestack"
    assert out.credential_kind == "password_grant"
    stored = session.add.call_args.args[0]
    assert stored.is_default is True
    payload = _unwrap_envelope(dict(stored.payload))
    assert payload["account_key"] == "account-key"
    assert payload["api_base_url"] == "https://api.carestack.com"


@pytest.mark.asyncio
async def test_upsert_bootstrap_openai_uses_encrypted_api_key_default() -> None:
    service, session, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())

    class _Result:
        def scalar_one_or_none(self) -> None:
            return None

    session.execute = AsyncMock(return_value=_Result())

    out = await service.upsert_bootstrap_credentials(
        tenant_id,
        IntegrationCredentialBootstrapIn(
            provider_kind="openai",
            api_key="sk-test-openai-secret",
        ),
        principal=_principal(),
    )

    assert out.provider_kind == "openai"
    assert out.credential_kind == "api_key"
    stored = session.add.call_args.args[0]
    assert stored.is_default is True
    assert stored.payload["alg"] == "fernet"
    assert "sk-test-openai-secret" not in json.dumps(stored.payload)
    assert _unwrap_envelope(dict(stored.payload)) == {
        "api_key": "sk-test-openai-secret"
    }
    serialised_audit = json.dumps(audit.record.await_args.kwargs["extra"])
    assert "sk-test-openai-secret" not in serialised_audit


# --- multi-mailbox isolation ---


@pytest.mark.asyncio
async def test_upsert_rejects_mailbox_for_non_email_provider() -> None:
    service, _session, _ = _make_service()
    with pytest.raises(ValidationError):
        await service.upsert(
            TenantId(uuid.uuid4()),
            "salesforce",
            "oauth_token",
            {"access_token": "x"},
            mailbox_email="me@example.com",
            principal=_principal(),
        )


@pytest.mark.asyncio
async def test_read_for_location_falls_back_to_default() -> None:
    service, session, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    location_id = uuid.uuid4()
    default_payload = {"access_token": "default-tok"}
    default_row = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="google_workspace",
        credential_kind="oauth_token",
        payload=_wrap_envelope(default_payload),
        status="active",
    )
    default_row.is_default = True
    default_row.id = uuid.uuid4()

    # First call (location-pinned) returns None; second call (default)
    # returns the default row.
    session.execute = AsyncMock(
        side_effect=[
            _scalar_one_or_none_result(None),
            _scalar_one_or_none_result(default_row),
        ]
    )
    out = await service.read_for_location(tenant_id, "google_workspace", location_id)
    assert out == default_payload


@pytest.mark.asyncio
async def test_read_for_location_returns_pinned_when_match() -> None:
    service, session, _ = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    location_id = uuid.uuid4()
    pinned_payload = {"access_token": "loc-A-tok"}
    pinned_row = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="google_workspace",
        credential_kind="oauth_token",
        payload=_wrap_envelope(pinned_payload),
        status="active",
    )
    pinned_row.id = uuid.uuid4()
    pinned_row.location_id = location_id

    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(pinned_row))
    out = await service.read_for_location(tenant_id, "google_workspace", location_id)
    assert out == pinned_payload


# --- delete soft-revoke ---


@pytest.mark.asyncio
async def test_delete_soft_revokes_active_row() -> None:
    service, session, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    cred = IntegrationCredential(
        tenant_id=tenant_id,
        provider_kind="salesforce",
        credential_kind="oauth_token",
        payload=_wrap_envelope({}),
        status="active",
    )
    cred.id = uuid.uuid4()
    cred.is_default = True
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(cred))

    await service.delete(cred.id, tenant_id=tenant_id, principal=_principal())
    assert cred.status == "revoked"
    assert cred.is_default is False
    audit.record.assert_awaited_once()
    assert audit.record.await_args.kwargs["action"] == "tenant.credential.revoke"


@pytest.mark.asyncio
async def test_delete_raises_when_tenant_mismatch() -> None:
    service, session, _ = _make_service()
    credential_id = uuid.uuid4()
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))
    with pytest.raises(NoCredentialError):
        await service.delete(
            credential_id,
            tenant_id=TenantId(uuid.uuid4()),  # different tenant
            principal=_principal(),
        )


# --- audit-no-leak invariant ---


@pytest.mark.asyncio
async def test_upsert_audit_does_not_carry_payload_keys() -> None:
    """Sanitiser invariant: the audit ``extra`` payload contains only
    structural identifiers — never plaintext payload keys or values."""
    service, session, audit = _make_service()
    tenant_id = TenantId(uuid.uuid4())
    session.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))
    session.add.side_effect = lambda row: setattr(row, "id", uuid.uuid4())
    secret = "super-secret-access-token-DO-NOT-LEAK"
    secret_key = "client_secret_value_DO_NOT_LEAK"
    await service.upsert(
        tenant_id,
        "salesforce",
        "api_key",
        {"client_id": "abc", "client_secret": secret_key, "token": secret},
        principal=_principal(),
        display_name="primary",
    )
    audit.record.assert_awaited_once()
    extra = audit.record.await_args.kwargs["extra"]
    serialised = json.dumps(extra)
    assert secret not in serialised
    assert secret_key not in serialised
    # Allowed structural fields ARE present.
    assert "tenant_id" in extra
    assert "credential_id" in extra
    assert "provider_kind" in extra
