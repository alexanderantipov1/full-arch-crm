"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from packages.core.config import get_settings
from packages.core.exceptions import PlatformError
from packages.core.logging import configure_logging, get_logger

from .middleware import (
    RequestContextMiddleware,
    platform_error_handler,
    request_validation_error_handler,
)
from .routers import (
    agent_runtime,
    attribution,
    auth,
    backfill,
    carestack,
    chat_inbound,
    dashboard,
    dev,
    enrichment,
    funnel,
    health,
    identity,
    ingest,
    integrations,
    integrations_list,
    integrations_oauth,
    internal_credentials,
    messenger,
    notification_rules,
    ops,
    outreach,
    outreach_tracking,
    persons,
    phi,
    provider_messenger_mappings,
    semantic_catalog,
    tenant,
    tools,
)

log = get_logger("api")


def _safe_host(url: object) -> str | None:
    """Return the hostname of a DSN-shaped value without leaking the DSN.

    Pydantic v2 represents ``PostgresDsn`` as ``MultiHostUrl``, which has
    no ``.host`` attribute (`.hosts()` returns a list of dicts). Falling
    back to ``urlsplit(str(url)).hostname`` works for single-host DSNs
    (Cloud SQL Private IP) and degrades gracefully for any value the
    URL types accept. Wrapped in try/except so a malformed DSN never
    kills container boot — the lifespan log is diagnostics, not a gate.
    """
    if url is None:
        return None
    try:
        return urlsplit(str(url)).hostname
    except Exception:
        return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    settings = get_settings()
    log.info("api.start", env=settings.app_env, name=settings.app_name)
    # Sanitized prod-URL contract dump. Catches the 127.0.0.1 / localhost
    # leak at container boot — Cloud Run logs show the values in the first
    # second of every revision so an operator can spot a missing env var
    # without waiting for an OAuth callback to fail. No secrets, no PHI,
    # no full DSNs — only hostnames and public URLs. See
    # docs/DEPLOYMENT_RULES.md §4.
    log.info(
        "startup.config",
        env=settings.app_env,
        oauth_redirect_base_url=settings.oauth_redirect_base_url,
        web_app_base_url=settings.web_app_base_url,
        tracking_base_url=settings.effective_tracking_base_url,
        api_cors_origins=settings.api_cors_origins,
        web_cors_origins=settings.web_cors_origins,
        database_host=_safe_host(settings.database_url),
        redis_host=_safe_host(settings.redis_url),
    )
    yield
    log.info("api.stop")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Fusion CRM API",
        version="0.1.0",
        lifespan=lifespan,
        # Disable docs in production unless an internal reverse proxy gates them.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    if settings.api_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(PlatformError, platform_error_handler)
    app.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    # Funnel analytics (ENG-419): per-stage × actor × role aggregates +
    # drop-off attribution + revenue slices. Reads
    # interaction.event_responsibility joined to actor.actor.
    app.include_router(funnel.router)
    app.include_router(attribution.router)
    app.include_router(identity.router)
    # Flat /persons list — staff UI cross-domain composer. Sits at the
    # top-level path the frontend hook expects (api.get("/persons")),
    # parallel to dashboard.summary. Per-person reads still live under
    # /identity, /ops, /phi prefixes.
    app.include_router(persons.router)
    app.include_router(ops.router)
    app.include_router(phi.router)
    # Messenger settings (ENG-546): map each CareStack provider (doctor) to a
    # Mattermost username so the consult-reminder can @mention them (ENG-543).
    app.include_router(provider_messenger_mappings.router)
    # Messenger directory (ENG-564): read-only mirror of the Mattermost server's
    # teams + channels for the staff "Messenger" settings tab.
    app.include_router(messenger.router)
    app.include_router(semantic_catalog.router)
    app.include_router(ingest.router)
    # Manual-enrichment store (ENG-439, Block F). Staff-UI write/read path
    # for our own fields layered over canonical entities, all through one
    # service. Chat / agent action paths (Block G) reuse the same service.
    app.include_router(enrichment.router)
    app.include_router(integrations.router)
    # General /integrations list — staff UI provider cards. Reads
    # ``tenant.integration_credential`` and projects to the Zod
    # ``IntegrationAccountSchema`` (connected / disconnected). Mounted
    # before the SF / OAuth surfaces so the bare ``GET /integrations``
    # route resolves to this aggregation, not to a sub-prefix 404.
    app.include_router(integrations_list.router)
    # CareStack inspector surface (ENG-145 PR-2): sync/patients +
    # sync/appointments feeds and per-id RAW lookups. Mounted before the
    # OAuth router so its concrete prefix wins over the
    # ``/{provider}/...`` patterns there.
    app.include_router(carestack.router)
    # Operator-account email outreach OAuth (ENG-131): Google Workspace +
    # Microsoft 365 connect / callback / refresh routes. Lives next to the
    # existing integrations router but is its own module so the SF /
    # CareStack pull surface stays untouched.
    app.include_router(integrations_oauth.router)
    app.include_router(tenant.router)
    app.include_router(agent_runtime.router)
    app.include_router(tools.router)
    # Internal credential resolver (ENG-125) — Next.js → FastAPI bridge.
    # Mounted last so the prefix (``/_internal``) is unambiguous; gated
    # by a shared ``X-Internal-Token`` header on every route.
    app.include_router(internal_credentials.router)
    # Outreach tracking (ENG-134) — recipient-facing tracking pixel +
    # RFC 8058 one-click unsubscribe + manual unsubscribe form. The
    # routes are unauthenticated; the HMAC tokens embedded in the
    # outbound mail are the only auth. See
    # ``apps/api/routers/outreach_tracking.py``.
    app.include_router(outreach.router)
    app.include_router(outreach_tracking.router)
    # Signed inbound Mattermost callbacks (ENG-438, Block E). PUBLIC /
    # unauthenticated — the Mattermost shared token IS the auth (verified
    # constant-time, resolves the tenant). See
    # ``apps/api/routers/chat_inbound.py``.
    app.include_router(chat_inbound.router)
    # Notification-rule admin API (ENG-458, Block D). Operator-facing CRUD
    # for "route event X → channel Y" so routes are a configurable SETTING
    # (channel by NAME, resolved to a Mattermost channel id before storage)
    # instead of seed code / raw SQL. Staff-only; tenant-scoped. See
    # ``apps/api/routers/notification_rules.py``.
    app.include_router(notification_rules.router)
    # Operator-triggered historical backfill (ENG-246, Phase 1). Sits at
    # the top-level path; not on the scheduled job path. See router
    # docstring for the phasing and the relationship with mission
    # ENG-235 (workflow-ready ingest foundation).
    app.include_router(backfill.router)
    # Local-dev-only "Sync data now" drain (ENG-330). Every route raises
    # NotFoundError (404) when APP_ENV=production, so the surface is
    # invisible in prod. The drain runs in the API process; no worker
    # dependency. See apps/api/routers/dev.py.
    app.include_router(dev.router)
    return app


app = create_app()
