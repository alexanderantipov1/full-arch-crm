"""IntegrationCredentialService — encrypted credential payloads per tenant.

Public surface for reading and writing credential payloads stored in
``tenant.integration_credential``. Composes ``TenantService.record_credential``
with the encryption envelope layer + multi-mailbox routing rules.

What this service does (ENG-125):

  1. Encrypts a plaintext payload (``dict[str, Any]``) into a single-field
     envelope ``{"ciphertext": "...", "alg": "fernet"}`` using the platform
     Fernet key (``packages.integrations.crypto``).
  2. Performs an UPSERT keyed on:
        - ``(tenant_id, provider_kind, credential_kind, mailbox_email)``
          for email-OAuth providers (``google_workspace``,
          ``microsoft_365``) where ``mailbox_email`` is non-null;
        - ``(tenant_id, provider_kind, credential_kind)`` otherwise.
     A refresh / rotation flow does not pile up rows.
  3. Decrypts on read and returns the plaintext payload to in-process
     callers — never logged, never serialised by ``IntegrationCredentialOut``.
  4. Manages ``is_default`` atomically: ``set_default`` flips one row to
     default and clears every other row in the same tenant+provider. The
     partial unique index would reject a multi-default state regardless;
     this method makes the flip a single transactional step.

Hard rules (enforced by code review + the test suite):

- Payload values are **never logged**. Audit messages name the
  ``provider_kind`` + ``credential_kind`` only.
- The plaintext payload **never crosses the service boundary in a DTO** —
  it is returned as ``dict[str, Any]`` to in-process callers (e.g. an SF
  client about to make an HTTP request) and the FastAPI route layer is
  responsible for refusing to serialise it.
- Tenants are isolated: ``read_for(tenant_a, ...)`` cannot return a row
  belonging to ``tenant_b`` even when both have the same provider tuple.
- Multi-mailbox isolation: ``read_for_location(tenant, provider, loc_a)``
  cannot return a credential pinned to ``loc_b``.

See ENG-125 + ``packages/tenant/CLAUDE.md``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.service import AuditService
from packages.core.exceptions import PlatformError, ValidationError
from packages.core.logging import get_logger
from packages.core.security import Principal
from packages.core.types import TenantId
from packages.integrations.crypto import decrypt_str, encrypt_str

from .models import (
    CREDENTIAL_KINDS,
    CREDENTIAL_STATUSES,
    MAILBOX_PROVIDER_KINDS,
    PROVIDER_KINDS,
    IntegrationCredential,
    Location,
)
from .schemas import (
    GoogleAdsCredentialPayload,
    GoogleAnalyticsCredentialPayload,
    GoogleSearchConsoleCredentialPayload,
    IntegrationCredentialBootstrapIn,
    IntegrationCredentialOut,
    IntegrationCredentialUpdate,
    MetaAdsCredentialPayload,
)

log = get_logger("tenant.credential_service")


# Envelope constant. Future migrations can swap the ``alg`` field to
# rotate to a new encryption scheme; readers branch on ``alg``.
_ALG_FERNET = "fernet"

# Marketing / SEO bootstrap providers (ENG-491). All persist as ``api_key``
# credentials with a payload shaped by the ENG-489 typed models.
_MARKETING_BOOTSTRAP_PROVIDERS = frozenset(
    {"google_ads", "meta_ads", "google_analytics", "google_search_console"}
)
_MARKETING_DISPLAY_NAMES = {
    "google_ads": "Google Ads",
    "meta_ads": "Meta Ads",
    "google_analytics": "Google Analytics (GA4)",
    "google_search_console": "Google Search Console",
}


def _build_marketing_payload(
    payload: IntegrationCredentialBootstrapIn,
) -> dict[str, Any]:
    """Map a validated bootstrap input to the ENG-489 payload dict.

    Routes the typed bootstrap fields through the matching ENG-489 payload
    model so the encrypted-at-rest envelope is exactly the shape the ENG-490
    ``from_credential`` factories read. Pydantic re-validation here is a
    second guard on top of ``IntegrationCredentialBootstrapIn.validate_provider_shape``.
    """
    provider = payload.provider_kind
    if provider == "google_ads":
        return GoogleAdsCredentialPayload(
            client_id=payload.client_id or "",
            client_secret=payload.client_secret or "",
            developer_token=payload.developer_token or "",
            refresh_token=payload.refresh_token or "",
            login_customer_id=payload.login_customer_id,
            customer_ids=payload.customer_ids or [],
        ).model_dump(mode="json")
    if provider == "meta_ads":
        return MetaAdsCredentialPayload(
            access_token=payload.access_token or "",
            ad_account_ids=payload.ad_account_ids or [],
            app_id=payload.app_id,
            app_secret=payload.app_secret,
        ).model_dump(mode="json")
    if provider == "google_analytics":
        return GoogleAnalyticsCredentialPayload(
            client_id=payload.client_id or "",
            client_secret=payload.client_secret or "",
            refresh_token=payload.refresh_token or "",
            property_id=payload.property_id or "",
        ).model_dump(mode="json")
    if provider == "google_search_console":
        return GoogleSearchConsoleCredentialPayload(
            client_id=payload.client_id or "",
            client_secret=payload.client_secret or "",
            refresh_token=payload.refresh_token or "",
            site_url=payload.site_url,
        ).model_dump(mode="json")
    raise ValidationError(  # pragma: no cover - guarded by caller
        "unsupported marketing bootstrap provider",
        details={"provider_kind": provider},
    )


class NoCredentialError(PlatformError):
    """Raised when no active credential exists for the given tuple.

    The caller (e.g. a Salesforce client builder) translates this to an
    env-fallback or a 404 ``not_connected`` error; this exception itself is
    deliberately distinct from ``NotFoundError`` so the resolver can
    differentiate "row missing" from "tenant missing".
    """

    code = "no_credential"
    http_status = 404


def _wrap_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Encrypt ``payload`` (JSON-serialised) and wrap in the alg envelope.

    The wire format on disk is::

        {"ciphertext": "<fernet-base64>", "alg": "fernet"}

    The whole envelope sits inside the JSONB column. Future algos can be
    introduced by branching on ``alg`` in :func:`_unwrap_envelope`.
    """
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    ciphertext = encrypt_str(plaintext)
    # Fernet ciphertext is already URL-safe base64 ASCII; decode for JSONB.
    return {"ciphertext": ciphertext.decode("ascii"), "alg": _ALG_FERNET}


def _unwrap_envelope(stored: dict[str, Any]) -> dict[str, Any]:
    """Decrypt a stored envelope back to plaintext payload.

    Raises ``ValidationError`` when the envelope is malformed (missing
    fields, unsupported algo) — never log the payload itself.
    """
    if not isinstance(stored, dict):
        raise ValidationError("credential payload is not an envelope dict")
    alg = stored.get("alg")
    ciphertext = stored.get("ciphertext")
    if alg != _ALG_FERNET:
        raise ValidationError(
            "unsupported credential alg",
            details={"alg": str(alg) if alg is not None else None},
        )
    if not isinstance(ciphertext, str) or not ciphertext:
        raise ValidationError("credential envelope missing ciphertext")
    plaintext = decrypt_str(ciphertext.encode("ascii"))
    decoded = json.loads(plaintext)
    if not isinstance(decoded, dict):
        raise ValidationError("decrypted credential payload is not an object")
    return decoded


class IntegrationCredentialService:
    """High-level read/write surface for encrypted tenant credentials.

    Composes direct queries (read by tuple / id / location) with the
    encryption envelope and audit emission. Repositories themselves stay
    data-only; this service holds the encryption + UPSERT + default-flip
    logic.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._audit = AuditService(session)

    # --- Reads ----------------------------------------------------

    async def read_for(
        self,
        tenant_id: TenantId,
        provider_kind: str,
        credential_kind: str | None = None,
    ) -> dict[str, Any]:
        """Decrypt and return the active credential payload for ``tenant``.

        Filters on ``status = 'active'``. When multiple active rows match,
        the row with ``is_default = true`` wins; ties (none default) fall
        back to the most-recently-created row.

        Most callers should pass ``credential_kind`` explicitly (e.g.
        ``oauth_token`` vs ``api_key``).

        Raises:
            ValidationError: input enum is unknown.
            NoCredentialError: no matching active row.
        """
        self._validate_enums(provider_kind, credential_kind)

        stmt = (
            select(IntegrationCredential)
            .where(IntegrationCredential.tenant_id == tenant_id)
            .where(IntegrationCredential.provider_kind == provider_kind)
            .where(IntegrationCredential.status == "active")
        )
        if credential_kind is not None:
            stmt = stmt.where(IntegrationCredential.credential_kind == credential_kind)
        # Default first, then newest. ``is_default DESC`` puts true (1) ahead.
        stmt = stmt.order_by(
            IntegrationCredential.is_default.desc(),
            IntegrationCredential.created_at.desc(),
        ).limit(1)

        cred = (await self._session.execute(stmt)).scalar_one_or_none()
        if cred is None:
            raise NoCredentialError(
                "no active credential for tenant+provider+kind",
                details={
                    "tenant_id": str(tenant_id),
                    "provider_kind": provider_kind,
                    "credential_kind": credential_kind,
                },
            )
        log.debug(
            "tenant.credential.read",
            tenant_id=str(tenant_id),
            provider_kind=provider_kind,
            credential_kind=cred.credential_kind,
            credential_id=str(cred.id),
        )
        return _unwrap_envelope(dict(cred.payload))

    async def list_active_payloads_across_tenants(
        self,
        provider_kind: str,
        credential_kind: str,
    ) -> list[tuple[TenantId, dict[str, Any]]]:
        """Decrypt every active credential for a provider tuple, all tenants.

        Inbound webhook authentication (ENG-438) needs to resolve which
        tenant a presented shared token belongs to, but the external system
        (Mattermost) does not send our ``tenant_id``. This method returns
        ``(tenant_id, plaintext_payload)`` for every ACTIVE row matching the
        ``(provider_kind, credential_kind)`` tuple across all tenants so the
        caller can constant-time-compare the presented token against each.

        This is a deliberate cross-tenant read — the ONLY sanctioned one in
        this service. It is gated to the narrow inbound-webhook use case and
        must only ever be used to resolve a tenant from a secret the caller
        already holds. Plaintext payloads are returned in-process only and
        are NEVER logged.

        Rows whose stored envelope fails to decrypt are skipped (a corrupt
        row must not break inbound resolution for healthy tenants); no
        payload content is logged on skip.
        """
        self._validate_enums(provider_kind, credential_kind)

        stmt = (
            select(IntegrationCredential)
            .where(IntegrationCredential.provider_kind == provider_kind)
            .where(IntegrationCredential.credential_kind == credential_kind)
            .where(IntegrationCredential.status == "active")
            .order_by(IntegrationCredential.created_at.desc())
        )
        rows = list((await self._session.execute(stmt)).scalars().all())

        out: list[tuple[TenantId, dict[str, Any]]] = []
        for cred in rows:
            try:
                payload = _unwrap_envelope(dict(cred.payload))
            except ValidationError:
                # Corrupt / unreadable envelope — skip without logging the
                # payload. Healthy tenants must still resolve.
                continue
            out.append((TenantId(cred.tenant_id), payload))
        return out

    async def read_default(
        self,
        tenant_id: TenantId,
        provider_kind: str,
    ) -> dict[str, Any] | None:
        """Return the explicit default credential for the provider, or None.

        Unlike :meth:`read_for`, this does NOT fall back to "newest" when
        no default is set — the caller must decide whether absent-default
        is an error or a "use env fallback" signal.
        """
        self._validate_enums(provider_kind, None)

        stmt = (
            select(IntegrationCredential)
            .where(IntegrationCredential.tenant_id == tenant_id)
            .where(IntegrationCredential.provider_kind == provider_kind)
            .where(IntegrationCredential.status == "active")
            .where(IntegrationCredential.is_default.is_(True))
            .limit(1)
        )
        cred = (await self._session.execute(stmt)).scalar_one_or_none()
        if cred is None:
            return None
        return _unwrap_envelope(dict(cred.payload))

    async def read_by_id(
        self,
        credential_id: UUID,
        *,
        tenant_id: TenantId,
    ) -> dict[str, Any]:
        """Decrypt one specific row by id.

        Mailbox-routing callers know which credential to use (the routing
        rule resolved a UUID). The read is still tenant-scoped in SQL so a
        raw credential UUID cannot cross tenant boundaries before the service
        has checked ownership.

        Raises ``NoCredentialError`` if the row does not exist for the tenant.
        """
        cred = await self._get_credential_for_tenant(tenant_id, credential_id)
        if cred is None:
            raise NoCredentialError(
                "credential not found",
                details={
                    "credential_id": str(credential_id),
                    "tenant_id": str(tenant_id),
                },
            )
        log.debug(
            "tenant.credential.read_by_id",
            tenant_id=str(cred.tenant_id),
            provider_kind=cred.provider_kind,
            credential_id=str(cred.id),
        )
        return _unwrap_envelope(dict(cred.payload))

    async def read_for_location(
        self,
        tenant_id: TenantId,
        provider_kind: str,
        location_id: UUID,
    ) -> dict[str, Any] | None:
        """Return the credential pinned to ``location_id`` for the provider.

        Falls back to the tenant default when no location-pinned row exists.
        Returns ``None`` if there is no location-specific row AND no
        default — the caller decides whether that is an error.

        Resolution order:
          1. Active row with ``location_id == location_id`` (newest first).
          2. Active row with ``is_default = true``.
          3. None.
        """
        self._validate_enums(provider_kind, None)

        # Step 1: location-pinned row.
        loc_stmt = (
            select(IntegrationCredential)
            .where(IntegrationCredential.tenant_id == tenant_id)
            .where(IntegrationCredential.provider_kind == provider_kind)
            .where(IntegrationCredential.status == "active")
            .where(IntegrationCredential.location_id == location_id)
            .order_by(IntegrationCredential.created_at.desc())
            .limit(1)
        )
        cred = (await self._session.execute(loc_stmt)).scalar_one_or_none()
        if cred is not None:
            return _unwrap_envelope(dict(cred.payload))

        # Step 2: tenant default.
        return await self.read_default(tenant_id, provider_kind)

    async def list_for_tenant(
        self,
        tenant_id: TenantId,
        provider_kind: str | None = None,
        *,
        include_revoked: bool = False,
    ) -> list[IntegrationCredentialOut]:
        """Admin view: every credential row for the tenant, no payload.

        Used by the operator UI (Settings → Integrations → list mailboxes)
        and by tests that assert insert/update side-effects without
        decrypting.
        """
        if provider_kind is not None:
            self._validate_enums(provider_kind, None)

        stmt = select(IntegrationCredential).where(IntegrationCredential.tenant_id == tenant_id)
        if provider_kind is not None:
            stmt = stmt.where(IntegrationCredential.provider_kind == provider_kind)
        if not include_revoked:
            stmt = stmt.where(IntegrationCredential.status != "revoked")
        stmt = stmt.order_by(
            IntegrationCredential.provider_kind,
            IntegrationCredential.created_at.desc(),
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return [IntegrationCredentialOut.model_validate(r) for r in rows]

    # --- Writes ---------------------------------------------------

    async def upsert(
        self,
        tenant_id: TenantId,
        provider_kind: str,
        credential_kind: str,
        payload: dict[str, Any],
        *,
        principal: Principal,
        mailbox_email: str | None = None,
        location_id: UUID | None = None,
        is_default: bool = False,
        tags: list[str] | None = None,
        display_name: str | None = None,
        expires_at: datetime | None = None,
        last_refreshed_at: datetime | None = None,
    ) -> IntegrationCredentialOut:
        """Encrypt ``payload`` and write a new (or update existing) row.

        Upsert key:

          - ``(tenant_id, provider_kind, credential_kind, mailbox_email)``
            when ``mailbox_email`` is set (multi-mailbox providers);
          - ``(tenant_id, provider_kind, credential_kind)`` otherwise
            (and only the most-recently-created active row is updated).

        ``is_default = true`` triggers an atomic flip: every other row in
        the same ``(tenant_id, provider_kind)`` has ``is_default`` cleared
        BEFORE the target row is written. This is the same pattern as
        :meth:`set_default`; we run it here so a single ``upsert`` call
        suffices for the common "this is now my primary mailbox" flow.

        Audit row is written via ``AuditService.record`` with action
        ``tenant.credential.upsert.{insert|update}``. Plaintext values
        NEVER appear in audit ``extra``.
        """
        if provider_kind not in PROVIDER_KINDS:
            raise ValidationError(
                "unknown provider_kind",
                details={
                    "provider_kind": provider_kind,
                    "allowed": list(PROVIDER_KINDS),
                },
            )
        if credential_kind not in CREDENTIAL_KINDS:
            raise ValidationError(
                "unknown credential_kind",
                details={
                    "credential_kind": credential_kind,
                    "allowed": list(CREDENTIAL_KINDS),
                },
            )
        if not isinstance(payload, dict):
            raise ValidationError("credential payload must be a dict")
        # Defensive: mailbox_email is only meaningful for email-OAuth
        # providers. Reject silently-misuse so rows do not pile up under
        # surprise upsert keys.
        if mailbox_email is not None and provider_kind not in MAILBOX_PROVIDER_KINDS:
            raise ValidationError(
                "mailbox_email is only valid for email-OAuth providers",
                details={
                    "provider_kind": provider_kind,
                    "allowed_for_mailbox": sorted(MAILBOX_PROVIDER_KINDS),
                },
            )

        envelope = _wrap_envelope(payload)

        # Find the existing active row (if any) for the upsert key.
        find_stmt = (
            select(IntegrationCredential)
            .where(IntegrationCredential.tenant_id == tenant_id)
            .where(IntegrationCredential.provider_kind == provider_kind)
            .where(IntegrationCredential.credential_kind == credential_kind)
            .where(IntegrationCredential.status == "active")
        )
        if mailbox_email is not None:
            find_stmt = find_stmt.where(IntegrationCredential.mailbox_email == mailbox_email)
        else:
            # Non-mailbox providers: ignore mailbox_email column entirely.
            # We do NOT filter ``mailbox_email IS NULL`` because that would
            # exclude legacy rows from the bootstrap migration.
            pass
        find_stmt = find_stmt.order_by(IntegrationCredential.created_at.desc()).limit(1)
        existing = (await self._session.execute(find_stmt)).scalar_one_or_none()

        # If is_default is being set, clear every other row in the same
        # (tenant, provider) BEFORE we write the target — otherwise the
        # partial unique index would reject the second row.
        if is_default:
            await self._clear_defaults(
                tenant_id=tenant_id,
                provider_kind=provider_kind,
                except_id=existing.id if existing is not None else None,
            )

        if existing is None:
            cred = IntegrationCredential(
                tenant_id=tenant_id,
                provider_kind=provider_kind,
                credential_kind=credential_kind,
                payload=envelope,
                display_name=display_name,
                status="active",
                expires_at=expires_at,
                last_refreshed_at=last_refreshed_at,
                mailbox_email=mailbox_email,
                location_id=location_id,
                is_default=is_default,
                tags=list(tags) if tags is not None else [],
            )
            self._session.add(cred)
            await self._session.flush()
            action = "tenant.credential.upsert.insert"
        else:
            existing.payload = envelope
            if display_name is not None:
                existing.display_name = display_name
            if expires_at is not None:
                existing.expires_at = expires_at
            if last_refreshed_at is not None:
                existing.last_refreshed_at = last_refreshed_at
            if location_id is not None:
                existing.location_id = location_id
            if tags is not None:
                existing.tags = list(tags)
            if mailbox_email is not None:
                existing.mailbox_email = mailbox_email
            # is_default is intentionally NOT advanced unless True — we
            # do not auto-clear default here. Use ``set_default`` to flip
            # the default back to a different row.
            if is_default:
                existing.is_default = True
            cred = existing
            action = "tenant.credential.upsert.update"
            await self._session.flush()

        # ``created_at`` / ``updated_at`` are server-defaulted. Without an
        # explicit refresh the attributes are expired on the ORM object,
        # and Pydantic's ``model_validate(cred)`` triggers a lazy SELECT
        # on attribute access — which fails under the async session
        # (``MissingGreenlet``). Refresh now while we're awaitable.
        await self._session.refresh(cred)

        await self._audit.record(
            principal=principal,
            action=action,
            resource="tenant.integration_credential",
            extra={
                "tenant_id": str(tenant_id),
                "credential_id": str(cred.id),
                "provider_kind": cred.provider_kind,
                "credential_kind": cred.credential_kind,
                "is_default": cred.is_default,
                "has_mailbox": cred.mailbox_email is not None,
                "has_location": cred.location_id is not None,
                # Intentionally no payload bytes / keys here.
            },
        )
        return IntegrationCredentialOut.model_validate(cred)

    async def upsert_bootstrap_credentials(
        self,
        tenant_id: TenantId,
        payload: IntegrationCredentialBootstrapIn,
        *,
        principal: Principal,
    ) -> IntegrationCredentialOut:
        """Store operator-entered bootstrap credentials for supported providers.

        The public UI sends typed fields; this method maps them to the
        provider payload shape expected by runtime resolvers and persists
        through ``upsert`` so encryption, tenant scoping and audit behavior
        stay in one place.
        """
        if payload.provider_kind == "salesforce":
            credential_kind = "api_key"
            credential_payload: dict[str, Any] = {
                "client_id": payload.client_id,
                "client_secret": payload.client_secret,
                "callback_url": payload.callback_url,
                "domain": payload.domain or "login.salesforce.com",
            }
            display_name = payload.display_name or "Salesforce app credentials"
            is_default = payload.is_default if payload.is_default is not None else False
        elif payload.provider_kind == "carestack":
            credential_kind = "password_grant"
            credential_payload = {
                "client_id": payload.client_id,
                "client_secret": payload.client_secret,
                "vendor_key": payload.vendor_key,
                "account_key": payload.account_key,
                "account_id": payload.account_id,
                "idp_base_url": payload.idp_base_url,
                "api_base_url": payload.api_base_url,
            }
            if payload.api_version is not None:
                credential_payload["api_version"] = payload.api_version
            display_name = payload.display_name or "CareStack password grant"
            is_default = payload.is_default if payload.is_default is not None else True
        elif payload.provider_kind == "openai":
            credential_kind = "api_key"
            credential_payload = {"api_key": payload.api_key}
            display_name = payload.display_name or "OpenAI API key"
            is_default = payload.is_default if payload.is_default is not None else True
        elif payload.provider_kind in _MARKETING_BOOTSTRAP_PROVIDERS:
            # Marketing / SEO providers (ENG-491). Build the payload through
            # the ENG-489 typed models so the stored envelope is exactly the
            # shape the per-tenant pull (ENG-490) ``from_credential`` factories
            # expect — never a hand-rolled dict that can drift from them.
            credential_kind = "api_key"
            credential_payload = _build_marketing_payload(payload)
            display_name = payload.display_name or _MARKETING_DISPLAY_NAMES[
                payload.provider_kind
            ]
            is_default = payload.is_default if payload.is_default is not None else True
        else:
            raise ValidationError(
                "unsupported bootstrap credential provider",
                details={"provider_kind": payload.provider_kind},
            )

        return await self.upsert(
            tenant_id,
            payload.provider_kind,
            credential_kind,
            credential_payload,
            principal=principal,
            display_name=display_name,
            is_default=is_default,
        )

    async def set_default(
        self,
        credential_id: UUID,
        *,
        tenant_id: TenantId,
        provider_kind: str,
        principal: Principal,
    ) -> IntegrationCredentialOut:
        """Atomically flip ``is_default`` to the given credential.

        Clears every other row in ``(tenant_id, provider_kind)`` first
        (single ``UPDATE``) then sets the target. The partial unique
        index would reject a multi-default state regardless; this is the
        operator-friendly entry point that holds the write inside one
        transaction.
        """
        self._validate_enums(provider_kind, None)

        cred = await self._get_credential_for_tenant(tenant_id, credential_id)
        if cred is None or cred.provider_kind != provider_kind:
            raise NoCredentialError(
                "credential not found",
                details={
                    "credential_id": str(credential_id),
                    "tenant_id": str(tenant_id),
                    "provider_kind": provider_kind,
                },
            )
        if cred.status != "active":
            raise ValidationError(
                "cannot set a non-active credential as default",
                details={"credential_id": str(credential_id), "status": cred.status},
            )

        await self._clear_defaults(
            tenant_id=tenant_id,
            provider_kind=provider_kind,
            except_id=credential_id,
        )
        cred.is_default = True
        await self._session.flush()

        await self._audit.record(
            principal=principal,
            action="tenant.credential.set_default",
            resource="tenant.integration_credential",
            extra={
                "tenant_id": str(tenant_id),
                "credential_id": str(credential_id),
                "provider_kind": provider_kind,
            },
        )
        return IntegrationCredentialOut.model_validate(cred)

    async def update_metadata(
        self,
        credential_id: UUID,
        *,
        tenant_id: TenantId,
        payload: IntegrationCredentialUpdate,
        principal: Principal,
    ) -> IntegrationCredentialOut:
        """Update operator-editable credential metadata without payload IO.

        This method intentionally never decrypts or re-encrypts
        ``IntegrationCredential.payload``. Payload rotation belongs to
        ``upsert`` / a future rotate endpoint.
        """
        cred = await self._get_credential_for_tenant(tenant_id, credential_id)
        if cred is None:
            raise NoCredentialError(
                "credential not found",
                details={
                    "credential_id": str(credential_id),
                    "tenant_id": str(tenant_id),
                },
            )

        updates = payload.model_dump(exclude_unset=True)

        if "status" in updates:
            status = updates["status"]
            if status not in CREDENTIAL_STATUSES:
                raise ValidationError(
                    "unknown credential status",
                    details={
                        "status": status,
                        "allowed": list(CREDENTIAL_STATUSES),
                    },
                )
            if status == "revoked":
                raise ValidationError(
                    "cannot revoke a credential via metadata update",
                    details={"credential_id": str(credential_id)},
                )
            cred.status = status

        if "location_id" in updates:
            location_id = updates["location_id"]
            if location_id is not None:
                location = await self._session.get(Location, location_id)
                if location is None or location.tenant_id != tenant_id:
                    raise ValidationError(
                        "location does not belong to tenant",
                        details={
                            "tenant_id": str(tenant_id),
                            "location_id": str(location_id),
                        },
                    )
            cred.location_id = location_id

        if "display_name" in updates:
            cred.display_name = updates["display_name"]
        if "tags" in updates:
            tags = updates["tags"]
            cred.tags = list(tags) if tags is not None else []
        if "expires_at" in updates:
            cred.expires_at = updates["expires_at"]
        if "last_refreshed_at" in updates:
            cred.last_refreshed_at = updates["last_refreshed_at"]

        if updates.get("is_default") is True:
            if cred.status != "active":
                raise ValidationError(
                    "cannot set a non-active credential as default",
                    details={
                        "credential_id": str(credential_id),
                        "status": cred.status,
                    },
                )
            await self._clear_defaults(
                tenant_id=tenant_id,
                provider_kind=cred.provider_kind,
                except_id=credential_id,
            )
            cred.is_default = True
        elif updates.get("is_default") is False:
            cred.is_default = False

        # An expired / revoked credential must never remain marked as
        # default. A common operator flow is "mark this row expired"
        # without re-sending is_default=False; without this guard the row
        # would keep is_default=True and the UI would surface a non-active
        # row as the provider default.
        if cred.status != "active" and cred.is_default:
            cred.is_default = False

        await self._session.flush()

        await self._audit.record(
            principal=principal,
            action="tenant.credential.update_metadata",
            resource="tenant.integration_credential",
            extra={
                "tenant_id": str(tenant_id),
                "credential_id": str(credential_id),
                "provider_kind": cred.provider_kind,
                "credential_kind": cred.credential_kind,
                "is_default": cred.is_default,
                "has_mailbox": cred.mailbox_email is not None,
                "has_location": cred.location_id is not None,
                "updated_fields": sorted(updates.keys()),
            },
        )
        return IntegrationCredentialOut.model_validate(cred)

    async def expire_active_for(
        self,
        tenant_id: TenantId,
        provider_kind: str,
        credential_kind: str,
        *,
        principal: Principal,
    ) -> int:
        """Mark all active credentials for a provider tuple as expired.

        Used when a provider proves the stored OAuth refresh token is dead.
        The payload is left untouched for auditability, but the row stops
        resolving through ``read_for`` so the operator UI can reconnect
        instead of repeatedly using stale tokens.
        """
        self._validate_enums(provider_kind, credential_kind)

        stmt = (
            select(IntegrationCredential)
            .where(IntegrationCredential.tenant_id == tenant_id)
            .where(IntegrationCredential.provider_kind == provider_kind)
            .where(IntegrationCredential.credential_kind == credential_kind)
            .where(IntegrationCredential.status == "active")
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        for cred in rows:
            cred.status = "expired"
            cred.is_default = False

        if rows:
            await self._session.flush()

        await self._audit.record(
            principal=principal,
            action="tenant.credential.expire_active",
            resource="tenant.integration_credential",
            extra={
                "tenant_id": str(tenant_id),
                "provider_kind": provider_kind,
                "credential_kind": credential_kind,
                "expired_count": len(rows),
            },
        )
        return len(rows)

    async def delete(
        self,
        credential_id: UUID,
        *,
        tenant_id: TenantId,
        principal: Principal,
    ) -> None:
        """Soft-delete (status='revoked') unless the row was never active.

        Audit row is always written; the action distinguishes ``revoke``
        from ``delete`` so the operator log retains the difference.
        """
        cred = await self._get_credential_for_tenant(tenant_id, credential_id)
        if cred is None:
            raise NoCredentialError(
                "credential not found",
                details={
                    "credential_id": str(credential_id),
                    "tenant_id": str(tenant_id),
                },
            )

        if cred.status == "active" or cred.last_refreshed_at is not None:
            cred.status = "revoked"
            # Keep the row for historical evidence; clear default so the
            # tenant does not have a revoked credential as its default.
            cred.is_default = False
            action = "tenant.credential.revoke"
        else:
            await self._session.delete(cred)
            action = "tenant.credential.delete"

        await self._audit.record(
            principal=principal,
            action=action,
            resource="tenant.integration_credential",
            extra={
                "tenant_id": str(tenant_id),
                "credential_id": str(credential_id),
                "provider_kind": cred.provider_kind,
                "credential_kind": cred.credential_kind,
            },
        )

    # --- Internals ------------------------------------------------

    async def _get_credential_for_tenant(
        self, tenant_id: TenantId, credential_id: UUID
    ) -> IntegrationCredential | None:
        stmt = (
            select(IntegrationCredential)
            .where(IntegrationCredential.tenant_id == tenant_id)
            .where(IntegrationCredential.id == credential_id)
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _clear_defaults(
        self,
        *,
        tenant_id: TenantId,
        provider_kind: str,
        except_id: UUID | None,
    ) -> None:
        """Clear ``is_default`` on every row in (tenant, provider) except one.

        Single ``UPDATE`` so the flip is atomic w.r.t. the partial unique
        index. Returning the rowcount is not useful here — the audit row
        is written by the caller, with the target credential id.
        """
        stmt = (
            update(IntegrationCredential)
            .where(IntegrationCredential.tenant_id == tenant_id)
            .where(IntegrationCredential.provider_kind == provider_kind)
            .where(IntegrationCredential.is_default.is_(True))
            .values(is_default=False)
        )
        if except_id is not None:
            stmt = stmt.where(IntegrationCredential.id != except_id)
        await self._session.execute(stmt)

    @staticmethod
    def _validate_enums(provider_kind: str, credential_kind: str | None) -> None:
        if provider_kind not in PROVIDER_KINDS:
            raise ValidationError(
                "unknown provider_kind",
                details={
                    "provider_kind": provider_kind,
                    "allowed": list(PROVIDER_KINDS),
                },
            )
        if credential_kind is not None and credential_kind not in CREDENTIAL_KINDS:
            raise ValidationError(
                "unknown credential_kind",
                details={
                    "credential_kind": credential_kind,
                    "allowed": list(CREDENTIAL_KINDS),
                },
            )


__all__ = [
    "IntegrationCredentialService",
    "NoCredentialError",
]
