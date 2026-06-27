"""FastAPI dependencies — database session, principal, services.

Routers should depend on services, not repositories. Services should depend
on AsyncSession + Principal. This file is the wiring.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, Any, cast
from uuid import NAMESPACE_DNS, uuid5

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from packages.actor.service import ActorService
from packages.analytics.enrichment_service import FactEnrichmentService
from packages.analytics.export_service import AnalyticsExportService
from packages.analytics.fact_repository import FactPatientJourneyRepository
from packages.analytics.full_funnel import FullFunnelService
from packages.analytics.metrics_service import (
    AnalyticsMetricsService,
    AnalyticsPagesService,
)
from packages.analytics.queries import FactAnalyticsQueries
from packages.analytics.service import AnalyticsCatalogReviewService
from packages.attribution.service import AttributionService
from packages.audit.service import AuditService
from packages.core.config import get_settings
from packages.core.exceptions import PlatformError
from packages.core.logging import get_logger
from packages.core.security import ANONYMOUS, Principal, Role
from packages.core.types import TenantId
from packages.db.session import SessionFactory
from packages.enrichment.service import EnrichmentService
from packages.identity.service import IdentityService
from packages.ingest.carestack_accounting_transaction_service import (
    CareStackAccountingTransactionClientProtocol,
    CareStackAccountingTransactionIngestService,
)
from packages.ingest.carestack_appointment_service import (
    CareStackAppointmentClientProtocol,
    CareStackAppointmentIngestService,
)
from packages.ingest.carestack_patient_service import (
    CareStackPatientClientProtocol,
    CareStackPatientIngestService,
)
from packages.ingest.carestack_payment_summary_service import (
    CareStackPaymentSummaryClientProtocol,
    CareStackPaymentSummaryIngestService,
)
from packages.ingest.responsibility_resolver import (
    ActorResolverProtocol,
    FunnelResponsibilityResolver,
)
from packages.ingest.service import IngestService
from packages.ingest.sf_event_service import (
    SfEventClientProtocol,
    SfEventIngestService,
)
from packages.ingest.sf_lead_service import SfClientProtocol, SfLeadIngestService
from packages.ingest.sf_task_service import (
    SfTaskClientProtocol,
    SfTaskIngestService,
)
from packages.insight.service import InsightCatalogService
from packages.integrations.carestack.exceptions import CareStackNotConnectedError
from packages.integrations.chat.base import ChatProvider
from packages.integrations.chat.directory_service import (
    MessengerDirectoryService,
)
from packages.integrations.chat.event_service import NotificationEventService
from packages.integrations.chat.resolver import resolve_chat_provider
from packages.integrations.notification_schemas import NotificationProviderKind
from packages.integrations.notification_service import NotificationService
from packages.integrations.salesforce import SfClient
from packages.integrations.salesforce.exceptions import SfNotConnectedError
from packages.integrations.salesforce.tokens import SfTokens
from packages.integrations.service import IntegrationService
from packages.interaction.service import InteractionService
from packages.marketing.service import MarketingService
from packages.ops.service import OpsService
from packages.outreach.service import (
    CampaignService,
    SuppressionService,
    TemplateService,
)
from packages.phi.service import PhiService
from packages.tenant.credential_service import (
    IntegrationCredentialService,
    NoCredentialError,
)
from packages.tenant.service import (
    CareStackLocationsClientProtocol,
    LocationService,
    TenantService,
)

_dep_log = get_logger("api.dependencies")

_LOCAL_STAFF_SESSION_COOKIE = "staff_session"
_LOCAL_DEV_PRINCIPAL_EMAIL = "demo@fusion-dental.local"
_IAP_AUTHENTICATED_USER_EMAIL_HEADER = "x-goog-authenticated-user-email"
_IAP_EMAIL_PREFIX = "accounts.google.com:"


class _UnavailableSfClient:
    def __init__(self, exc: SfNotConnectedError) -> None:
        self._exc = exc

    async def soql(self, _query: str) -> dict[str, Any]:
        raise self._exc


class _UnavailableCareStackClient:
    def __init__(self, exc: CareStackNotConnectedError) -> None:
        self._exc = exc

    async def list_patients_modified_since(
        self,
        _modified_since: object,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        _ = page_size, continue_token
        raise self._exc

    async def list_appointments_modified_since(
        self,
        _modified_since: object,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        _ = page_size, continue_token
        raise self._exc

    async def list_accounting_transactions_modified_since(
        self,
        _modified_since: object,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        _ = page_size, continue_token
        raise self._exc

    async def get_payment_summary(self, _patient_id: object) -> dict[str, Any]:
        raise self._exc


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a session that commits on success and rolls back on error."""
    session = SessionFactory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_tenant_id(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantId:
    """Resolve the request tenant from ``Settings.tenant_default_slug``.

    Phase 1 single-tenant: every request resolves to the same tenant
    looked up by the configured slug. Phase 2 (real multi-tenant)
    replaces this with a subdomain / path resolver — the call sites
    (``Depends(get_tenant_id)``) stay the same.

    Raises ``NotFoundError`` if the slug does not exist in
    ``tenant.tenant`` — the bootstrap migration must have run.
    """
    settings = get_settings()
    tenant = await TenantService(db).resolve_default(settings.tenant_default_slug)
    return TenantId(tenant.id)


def _get_local_dev_principal(request: Request) -> Principal | None:
    """Bridge the local staff cookie into FastAPI's principal contract.

    The Next.js local sign-in flow uses a lightweight ``staff_session`` cookie
    so operators can exercise the real FastAPI backend without IAP. Production
    auth still comes from middleware/IAP and must set ``request.state.principal``.
    """
    settings = get_settings()
    if settings.is_production:
        return None

    session_id = request.cookies.get(_LOCAL_STAFF_SESSION_COOKIE)
    if session_id is None:
        return None

    return Principal(
        id=uuid5(NAMESPACE_DNS, f"fusion-crm-local-dev:{session_id}"),
        email=_LOCAL_DEV_PRINCIPAL_EMAIL,
        roles=frozenset({Role.ADMIN}),
        context={"auth_source": "local_dev_staff_session"},
    )


def _get_iap_principal(request: Request) -> Principal | None:
    """Bridge Google IAP identity into the shared principal contract.

    Production staff access is currently enforced by Google IAP in front of the
    web/API surfaces. Until `auth.staff` lands, IAP-authenticated users are
    treated as staff admins for internal control-plane workbench access.
    """
    raw_email = request.headers.get(_IAP_AUTHENTICATED_USER_EMAIL_HEADER)
    if not raw_email:
        return None

    email = raw_email.removeprefix(_IAP_EMAIL_PREFIX)
    if not email:
        return None

    return Principal(
        id=uuid5(NAMESPACE_DNS, f"fusion-crm-iap:{email}"),
        email=email,
        roles=frozenset({Role.ADMIN}),
        context={"auth_source": "google_iap"},
    )


def get_principal(request: Request) -> Principal:
    """Return the authenticated principal for this request.

    Today this returns ANONYMOUS unless an upstream middleware/auth dependency
    has set ``request.state.principal``. The shape is what real auth (OIDC,
    JWT) will populate later.

    Note: ``Principal.tenant_id`` is set by ``get_principal_with_tenant``
    on routes that need tenant context. Routes that do NOT need tenant
    context (health, readiness) keep ``ANONYMOUS`` (whose ``tenant_id``
    is ``None``).
    """
    state_principal = getattr(request.state, "principal", None)
    if isinstance(state_principal, Principal):
        return state_principal

    iap_principal = _get_iap_principal(request)
    if iap_principal is not None:
        return iap_principal

    local_dev_principal = _get_local_dev_principal(request)
    if local_dev_principal is not None:
        return local_dev_principal

    return ANONYMOUS


async def get_principal_with_tenant(
    principal: Annotated[Principal, Depends(get_principal)],
    tenant_id: Annotated[TenantId, Depends(get_tenant_id)],
) -> Principal:
    """Return the principal with ``tenant_id`` populated.

    Use this on every per-tenant route. Routes that do not need a tenant
    (health checks, the `tenant.create` admin path) depend on
    ``get_principal`` directly.
    """
    return Principal(
        id=principal.id,
        email=principal.email,
        tenant_id=tenant_id,
        roles=principal.roles,
        context=principal.context,
    )


def get_identity_service(db: AsyncSession = Depends(get_db)) -> IdentityService:
    return IdentityService(db)


def get_ops_service(db: AsyncSession = Depends(get_db)) -> OpsService:
    return OpsService(db)


def get_attribution_service(
    db: AsyncSession = Depends(get_db),
) -> AttributionService:
    return AttributionService(db)


def get_actor_service(db: AsyncSession = Depends(get_db)) -> ActorService:
    """Build the unified-actor service.

    ENG-418: the persons-timeline route uses this to attach actor display
    names to the per-event responsibility rows that
    ``InteractionService.list_operational_timeline`` emits.
    """
    return ActorService(db)


def get_messenger_directory_service(
    db: AsyncSession = Depends(get_db),
) -> MessengerDirectoryService:
    """Build the read-only Mattermost directory service (ENG-564).

    Backs the staff "Messenger" settings tab. The service resolves the tenant's
    Mattermost adapter per request via ``resolve_chat_provider``.
    """
    return MessengerDirectoryService(db)


def _build_responsibility_resolver(db: AsyncSession) -> FunnelResponsibilityResolver:
    """Construct the funnel-responsibility resolver at the app boundary.

    ``packages/ingest`` cannot import ``packages/actor`` directly (matrix rule
    in ``packages/CLAUDE.md``), so the concrete ``ActorService`` is wired in
    here and passed to the resolver via :class:`ActorResolverProtocol`.
    """
    return FunnelResponsibilityResolver(
        OpsService(db),
        cast(ActorResolverProtocol, ActorService(db)),
    )


class _ActorNameResolverAdapter:
    """App-boundary adapter: external party id → ``actor.actor`` name (ENG-465).

    Lets the manual CareStack appointment ``/pull`` resolve the DOCTOR (and TC
    owner) name the same way the scheduled worker does. ``packages/ingest`` may
    not import ``packages/actor``; this adapter satisfies the ingest-side
    ``ActorNameResolver`` Protocol by delegating to
    ``ActorService.find_by_identifier``.
    """

    def __init__(self, actors: ActorService) -> None:
        self._actors = actors

    async def resolve_actor_name(
        self, tenant_id: TenantId, kind: str, value: str
    ) -> str | None:
        actor = await self._actors.find_by_identifier(tenant_id, kind, value)
        return actor.name if actor is not None else None


def _build_actor_name_resolver(db: AsyncSession) -> _ActorNameResolverAdapter:
    """ENG-465: actor-name resolver for the manual CareStack appointment pull."""
    return _ActorNameResolverAdapter(ActorService(db))


def get_phi_service(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> PhiService:
    return PhiService(db, principal)


def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    return AuditService(db)


def get_ingest_service(db: AsyncSession = Depends(get_db)) -> IngestService:
    return IngestService(db)


def get_enrichment_service(db: AsyncSession = Depends(get_db)) -> EnrichmentService:
    """Build the manual-enrichment service (ENG-439, Block F).

    Used by the staff-UI annotation write/read routes; the chat / agent
    action paths (Block G) will reuse the same service through their own
    boundaries.
    """
    return EnrichmentService(db)


def get_fact_enrichment_service(
    db: AsyncSession = Depends(get_db),
) -> FactEnrichmentService:
    """Compose the analytics manual-enrichment service (ENG-513).

    Wires the shared ``EnrichmentService`` write path (annotation + audit) to
    the ``fact_patient_journey`` repository so an operator override lands as
    both a durable annotation and a manual-provenance fact value in one unit of
    work.
    """
    return FactEnrichmentService(
        enrichment=EnrichmentService(db),
        repo=FactPatientJourneyRepository(db),
    )


def get_marketing_service(db: AsyncSession = Depends(get_db)) -> MarketingService:
    return MarketingService(db)


def get_interaction_service(db: AsyncSession = Depends(get_db)) -> InteractionService:
    return InteractionService(
        db,
        operational_projection_reader=OpsService(db),
    )


def get_full_funnel_service(db: AsyncSession = Depends(get_db)) -> FullFunnelService:
    """Compose the person-anchored Full Funnel v2 read model (ENG-481).

    A read-only composition over OpsService + IdentityService +
    InteractionService + MarketingService. Wiring the four domain services at
    the app boundary keeps the cross-domain crossings service-only (per
    ``packages/CLAUDE.md``) and the route a thin caller.
    """
    return FullFunnelService(
        ops=OpsService(db),
        identity=IdentityService(db),
        interaction=InteractionService(db, operational_projection_reader=OpsService(db)),
        marketing=MarketingService(db),
    )


def get_analytics_metrics_service(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsMetricsService:
    """Compose the shared analytics filter + derived-metric layer (ENG-507).

    Reads ``fact_patient_journey`` (own schema) + ``MarketingService`` spend and
    resolves the per-location timezone via ``TenantService``. The 14 pages
    compose onto this; the journey-metrics smoke endpoint proves the contract.
    """
    return AnalyticsMetricsService(
        fact_repo=FactPatientJourneyRepository(db),
        marketing=MarketingService(db),
        tenant=TenantService(db),
        location=LocationService(db),
    )


def get_analytics_pages_service(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsPagesService:
    """Compose the B2 data-ready page service (ENG-514…523).

    Read-only aggregates over ``fact_patient_journey`` (``FactAnalyticsQueries``)
    + ``MarketingService`` spend + per-location timezone via ``TenantService``.
    Separate from ``AnalyticsMetricsService`` so the five new pages add no
    regression surface to the foundation contract.
    """
    return AnalyticsPagesService(
        queries=FactAnalyticsQueries(db),
        marketing=MarketingService(db),
        tenant=TenantService(db),
        location=LocationService(db),
    )


def get_analytics_export_service(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsExportService:
    """Compose the analytics CSV/XLSX export service (ENG-508).

    Wraps ``AnalyticsPagesService`` so an export is byte-for-byte the on-screen
    page's numbers for the same filters; the serializers add no logic and no
    independent query. Marketing-page export is a documented gap until its page
    (ENG-516) exists.
    """
    return AnalyticsExportService(pages=get_analytics_pages_service(db))


def get_integration_service(db: AsyncSession = Depends(get_db)) -> IntegrationService:
    return IntegrationService(db)


def get_notification_event_service(
    db: AsyncSession = Depends(get_db),
) -> NotificationEventService:
    return NotificationEventService(db)


def get_notification_service(
    db: AsyncSession = Depends(get_db),
) -> NotificationService:
    """Build the notification-rule admin service (ENG-458).

    Routers depend on this for the rule CRUD surface; the service owns
    persistence + audit and never commits (the ``get_db`` boundary does).
    """
    return NotificationService(db)


async def get_chat_provider(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
) -> ChatProvider:
    """Resolve the tenant's chat provider for channel-name resolution (ENG-458).

    Builds a :class:`ChatProvider` (today the Mattermost adapter) from the
    tenant's stored credential so the rule admin route can map a channel
    NAME to a provider channel id before persisting. ``provider_kind`` is
    fixed to the default for now — the admin surface manages Mattermost
    routes; a multi-provider selector is a later change.
    """
    provider_kind: NotificationProviderKind = "mattermost"
    tenant_id = principal.require_tenant()
    return await resolve_chat_provider(tenant_id, provider_kind, db)


def get_tenant_service(db: AsyncSession = Depends(get_db)) -> TenantService:
    return TenantService(db)


def get_location_service(db: AsyncSession = Depends(get_db)) -> LocationService:
    return LocationService(db)


def get_template_service(db: AsyncSession = Depends(get_db)) -> TemplateService:
    return TemplateService(db)


def get_campaign_service(db: AsyncSession = Depends(get_db)) -> CampaignService:
    return CampaignService(db)


def get_suppression_service(db: AsyncSession = Depends(get_db)) -> SuppressionService:
    return SuppressionService(db)


def get_analytics_catalog_review_service(
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> AnalyticsCatalogReviewService:
    """Return the semantic catalog review service backed by durable insight storage."""
    return AnalyticsCatalogReviewService(
        audit=audit,
        insight=InsightCatalogService(db),
    )


async def _build_salesforce_client(
    db: AsyncSession,
    principal: Principal,
) -> SfClient:
    """Build a Salesforce client from tenant credentials."""
    tenant_id = principal.require_tenant()
    cred_svc = IntegrationCredentialService(db)

    try:
        payload = await cred_svc.read_for(tenant_id, "salesforce", "oauth_token")
    except NoCredentialError as exc:
        raise SfNotConnectedError(
            "Salesforce not connected — run the OAuth flow first.",
            details=exc.details,
        ) from exc
    except PlatformError:
        _dep_log.warning("sf.cred.resolver_failed")
        raise

    # Fetch the companion ``(salesforce, api_key)`` row so the SF
    # client has client_id/client_secret for its 401-refresh path
    # without depending on bootstrap-only env vars (ENG-153). The
    # api_key row is always present after the seed migration; this
    # is best-effort to keep local dev (no api_key seeded) working.
    api_key_payload: dict[str, object] | None
    try:
        api_key_payload = await cred_svc.read_for(tenant_id, "salesforce", "api_key")
    except NoCredentialError:
        api_key_payload = None
    except PlatformError:
        _dep_log.warning("sf.cred.api_key_resolver_failed")
        api_key_payload = None

    async def _persist_to_db(tokens: SfTokens) -> None:
        new_payload: dict[str, object] = {
            "access_token": tokens.access_token,
            "instance_url": tokens.instance_url,
        }
        if tokens.refresh_token:
            new_payload["refresh_token"] = tokens.refresh_token
        if tokens.issued_at:
            new_payload["issued_at"] = tokens.issued_at
        await cred_svc.upsert(
            tenant_id,
            "salesforce",
            "oauth_token",
            new_payload,
            principal=principal,
            display_name="Salesforce OAuth tokens (rotated by SfClient)",
        )

    return SfClient.from_credential(
        payload,
        on_refresh=_persist_to_db,
        api_key_payload=api_key_payload,
    )


async def get_salesforce_client(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
) -> AsyncIterator[SfClient]:
    """Yield a Salesforce client built from the current tenant context."""
    sf_client = await _build_salesforce_client(db, principal)
    try:
        yield sf_client
    finally:
        await sf_client.close()


async def get_sf_lead_ingest_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
) -> AsyncIterator[SfLeadIngestService]:
    """Build the W1 SF Lead ingest service with DB-backed credentials.

    The active ``salesforce / oauth_token`` row in
    ``tenant.integration_credential`` is the only runtime token source.
    Local dev token files are intentionally ignored here so the staff UI
    cannot report "connected" from stale file state while API calls use
    tenant-scoped DB credentials.

    Note: the underlying ``httpx.AsyncClient`` is created per request and
    closed when the request ends. Connection reuse can be added later by
    moving the client to app lifespan if call volume justifies it.

    cast is honest about structural typing here: SfClient.soql returns the
    ``SoqlResult`` TypedDict (a dict[str, Any] at runtime), and the protocol
    in ``packages.ingest`` is intentionally typed as ``dict[str, Any]`` to
    avoid an ``ingest → integrations`` import (forbidden by
    ``packages/CLAUDE.md``).
    """
    resolver = _build_responsibility_resolver(db)
    try:
        sf_client = await _build_salesforce_client(db, principal)
    except SfNotConnectedError as exc:
        yield SfLeadIngestService(
            session=db,
            sf_client=cast(SfClientProtocol, _UnavailableSfClient(exc)),
            responsibility_resolver=resolver,
        )
        return
    try:
        yield SfLeadIngestService(
            session=db,
            sf_client=cast(SfClientProtocol, sf_client),
            responsibility_resolver=resolver,
        )
    finally:
        await sf_client.close()


async def get_sf_event_ingest_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
) -> AsyncIterator[SfEventIngestService]:
    """Build the SF Event ingest service with the same DB-backed creds
    used by the Lead service (ENG-220). The Event service consumes only
    ``SfClient.soql`` so the real client satisfies the local Protocol
    structurally — same import-isolation rule as the Lead service.
    """
    try:
        sf_client = await _build_salesforce_client(db, principal)
    except SfNotConnectedError as exc:
        yield SfEventIngestService(
            session=db,
            sf_client=cast(SfEventClientProtocol, _UnavailableSfClient(exc)),
        )
        return
    try:
        yield SfEventIngestService(
            session=db,
            sf_client=cast(SfEventClientProtocol, sf_client),
        )
    finally:
        await sf_client.close()


async def get_sf_task_ingest_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
) -> AsyncIterator[SfTaskIngestService]:
    """Build the SF Task ingest service with DB-backed Salesforce creds."""
    resolver = _build_responsibility_resolver(db)
    try:
        sf_client = await _build_salesforce_client(db, principal)
    except SfNotConnectedError as exc:
        yield SfTaskIngestService(
            session=db,
            sf_client=cast(SfTaskClientProtocol, _UnavailableSfClient(exc)),
            responsibility_resolver=resolver,
        )
        return
    try:
        yield SfTaskIngestService(
            session=db,
            sf_client=cast(SfTaskClientProtocol, sf_client),
            responsibility_resolver=resolver,
        )
    finally:
        await sf_client.close()


# ----------------------------------------------------------------- CareStack

# Type alias for the lazy-build callable handed to routes. The factory is
# a Callable[[], Awaitable[client]] rather than the client itself so that
# the underlying ``httpx.AsyncClient`` only opens when a route actually
# invokes it. Routes are responsible for ``await client.close()`` after
# use — see the ``finally`` block in ``apps/api/routers/tenant.py``.
CareStackClientFactory = Callable[[], Awaitable[CareStackLocationsClientProtocol]]


def get_carestack_client_factory(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_principal_with_tenant)],
) -> CareStackClientFactory:
    """Hand the route a callable that builds a CareStack client.

    Per ENG-125: credential resolution prefers
    ``tenant.integration_credential`` (DB-backed, encrypted), falling
    back to env vars only when no active credential row exists. The
    factory is closure-captured: the underlying ``httpx.AsyncClient``
    is created on first invocation, and the route is responsible for
    calling ``await client.close()`` (see the ``finally`` blocks in
    ``apps/api/routers/{tenant,carestack}.py``).

    Returns a callable typed as the narrow locations protocol; routes
    that need the full ``CareStackClient`` surface (sync feeds, patient
    fetch) cast at the call site. The runtime object is always the
    real ``CareStackClient``.
    """
    from packages.integrations.carestack import CareStackClient

    cred_svc = IntegrationCredentialService(db)
    tenant_id = principal.require_tenant()

    async def _build() -> CareStackLocationsClientProtocol:
        try:
            payload = await cred_svc.read_for(tenant_id, "carestack", "password_grant")
        except NoCredentialError as exc:
            raise CareStackNotConnectedError(
                "CareStack not connected — configure tenant credentials first.",
                details=exc.details,
            ) from exc
        except PlatformError:
            _dep_log.warning("carestack.cred.resolver_failed")
            raise

        client = CareStackClient.from_credential(payload)
        return cast(CareStackLocationsClientProtocol, client)

    return _build


async def get_carestack_patient_ingest_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    factory: Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)],
) -> AsyncIterator[CareStackPatientIngestService]:
    """Build the CareStack Patient ingest service with tenant credentials."""
    try:
        client = await factory()
    except CareStackNotConnectedError as exc:
        yield CareStackPatientIngestService(
            session=db,
            carestack_client=cast(CareStackPatientClientProtocol, _UnavailableCareStackClient(exc)),
        )
        return
    try:
        yield CareStackPatientIngestService(
            session=db,
            carestack_client=cast(CareStackPatientClientProtocol, client),
        )
    finally:
        await cast(Any, client).close()


async def get_carestack_appointment_ingest_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    factory: Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)],
) -> AsyncIterator[CareStackAppointmentIngestService]:
    """Build the CareStack Appointment ingest service with tenant credentials.

    The same factory builds the client; the appointment service consumes
    only the ``list_appointments_modified_since`` surface so the real
    ``CareStackClient`` satisfies the Protocol structurally (ENG-219).
    """
    resolver = _build_responsibility_resolver(db)
    actor_names = _build_actor_name_resolver(db)
    try:
        client = await factory()
    except CareStackNotConnectedError as exc:
        yield CareStackAppointmentIngestService(
            session=db,
            carestack_client=cast(
                CareStackAppointmentClientProtocol, _UnavailableCareStackClient(exc)
            ),
            responsibility_resolver=resolver,
            actor_name_resolver=actor_names,
        )
        return
    try:
        yield CareStackAppointmentIngestService(
            session=db,
            carestack_client=cast(CareStackAppointmentClientProtocol, client),
            responsibility_resolver=resolver,
            actor_name_resolver=actor_names,
        )
    finally:
        await cast(Any, client).close()


async def get_carestack_accounting_transaction_ingest_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    factory: Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)],
) -> AsyncIterator[CareStackAccountingTransactionIngestService]:
    """Build the CareStack Accounting Transaction ingest service (ENG-285).

    Used by the throttled historical backfill at
    ``POST /backfill/run`` (scope ``carestack_accounting_transactions``).
    """
    try:
        client = await factory()
    except CareStackNotConnectedError as exc:
        yield CareStackAccountingTransactionIngestService(
            session=db,
            carestack_client=cast(
                CareStackAccountingTransactionClientProtocol,
                _UnavailableCareStackClient(exc),
            ),
        )
        return
    try:
        yield CareStackAccountingTransactionIngestService(
            session=db,
            carestack_client=cast(CareStackAccountingTransactionClientProtocol, client),
        )
    finally:
        await cast(Any, client).close()


async def get_carestack_payment_summary_ingest_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    factory: Annotated[CareStackClientFactory, Depends(get_carestack_client_factory)],
) -> AsyncIterator[CareStackPaymentSummaryIngestService]:
    """Build the CareStack Payment Summary ingest service (ENG-285).

    Used by the throttled historical backfill at
    ``POST /backfill/run`` (scope ``carestack_payment_summary``).
    """
    try:
        client = await factory()
    except CareStackNotConnectedError as exc:
        yield CareStackPaymentSummaryIngestService(
            session=db,
            carestack_client=cast(
                CareStackPaymentSummaryClientProtocol,
                _UnavailableCareStackClient(exc),
            ),
        )
        return
    try:
        yield CareStackPaymentSummaryIngestService(
            session=db,
            carestack_client=cast(CareStackPaymentSummaryClientProtocol, client),
        )
    finally:
        await cast(Any, client).close()
