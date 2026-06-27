"""Centralised, env-driven configuration.

All runtime configuration MUST go through this module. Never read os.environ
directly elsewhere — that ensures we have a single source of truth and a single
audit point for what the platform reads from the environment.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.core.secrets import resolve_mapping

Env = Literal["development", "production", "test"]


class Settings(BaseSettings):
    """Application settings, loaded once from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: Env = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="fusion-crm", alias="APP_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(..., alias="SECRET_KEY")

    # --- DB ---
    database_url: PostgresDsn = Field(..., alias="DATABASE_URL")
    database_url_sync: PostgresDsn | None = Field(default=None, alias="DATABASE_URL_SYNC")

    # --- Redis ---
    redis_url: RedisDsn = Field(..., alias="REDIS_URL")

    # --- Scheduled ingestion (ENG-222) ---
    # Cadence for the cron-driven SF + CareStack pull per tenant. Default
    # 24h; operator can tune via env. Per-tenant override (tenant.setting)
    # ships in a follow-up.
    ingest_interval_hours: int = Field(default=24, alias="INGEST_INTERVAL_HOURS")

    # --- Backups ---
    gcs_bucket: str | None = Field(default=None, alias="GCS_BUCKET")
    google_application_credentials: str | None = Field(
        default=None, alias="GOOGLE_APPLICATION_CREDENTIALS"
    )
    backup_retention_days: int = Field(default=30, alias="BACKUP_RETENTION_DAYS")
    backup_local_dir: str = Field(default="/var/backups/fusion", alias="BACKUP_LOCAL_DIR")

    # --- API ---
    # 0.0.0.0 is intentional: API binds inside a container; reverse proxy
    # terminates TLS and gates the network. infra/docker/docker-compose.yml
    # binds the published port to 127.0.0.1 only, never the LAN.
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")  # noqa: S104
    api_port: int = Field(default=8000, alias="API_PORT")
    # Cloud Run env vars are strings. `pydantic-settings` v2 tries
    # `json.loads()` on `list[str]` fields before any validator runs,
    # so a CSV like `https://a.com,https://b.com` raises SettingsError.
    # Store the raw string and expose a list via `api_cors_origins`.
    # See `docs/DEPLOYMENT_RULES.md` §3.
    api_cors_origins_raw: str = Field(default="", alias="API_CORS_ORIGINS")

    # --- Worker ---
    worker_concurrency: int = Field(default=4, alias="WORKER_CONCURRENCY")

    # --- Tenant resolution (added 2026-05-09 with ENG-123 / ADR-0003) ---
    # Phase 1 single-tenant resolver. The API dependency that builds
    # ``Principal.tenant_id`` looks up this slug in ``tenant.tenant`` at
    # request time. Phase 2 (real multi-tenant) replaces this with a
    # subdomain / path-prefix resolver — the field stays as a fallback for
    # workers and CLI scripts.
    tenant_default_slug: str = Field(
        default="fusion-dental-implants", alias="TENANT_DEFAULT_SLUG"
    )

    # --- Internal credential resolver (ENG-125, 2026-05-09) ---
    # Shared secret between the Next.js server-side route handlers and
    # the FastAPI ``/_internal/credentials/...`` endpoint. The Next.js
    # SF / CareStack clients fetch decrypted credentials via this
    # endpoint and fall back to env on any failure (404, network, etc.).
    # The token MUST live in a server-only env on the Next.js side
    # (``INTERNAL_CREDENTIAL_TOKEN``) — never the public bundle.
    # Generate with:
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Optional at startup so dev environments without the resolver can
    # boot; the route returns 503 ``not_configured`` until set.
    #
    # ENG-131 (2026-05-10): the same secret is reused as the HMAC key
    # for the Google / Microsoft OAuth ``state`` parameter (see
    # packages/integrations/_oauth_state.py). The OAuth flow refuses
    # to mint state without it, so this field becomes effectively
    # required for the email-outreach feature.
    #
    # ENG-134 (2026-05-11): the same secret keys the open-tracking +
    # one-click unsubscribe HMAC tokens (namespaced by ``"open:"`` /
    # ``"unsubscribe:"``). See ``packages.outreach.tracking_tokens``.
    internal_credential_token: SecretStr | None = Field(
        default=None, alias="INTERNAL_CREDENTIAL_TOKEN"
    )

    # --- M1 vertical-slice fields (added 2026-05-01) ---

    # Fernet key for encrypted columns (e.g. integration OAuth tokens).
    # Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Optional at startup so dev environments without integrations can boot;
    # consumers (packages.integrations.crypto) raise if missing at use-time.
    encryption_key: SecretStr | None = Field(default=None, alias="ENCRYPTION_KEY")

    # Salesforce OAuth (M1 — Lead pull). All optional so dev can boot without
    # creds; integration code fails closed when a credential is missing.
    # NOTE (ENG-125): these env values are BOOTSTRAP-ONLY after this PR.
    # The ``tenant_credentials_seed`` migration copies them into
    # ``tenant.integration_credential`` once; runtime callers prefer DB
    # credentials and fall back to env via the Next.js resolver path.
    salesforce_client_id: str | None = Field(default=None, alias="SALESFORCE_CLIENT_ID")
    salesforce_client_secret: SecretStr | None = Field(
        default=None, alias="SALESFORCE_CLIENT_SECRET"
    )
    salesforce_callback_url: str | None = Field(default=None, alias="SALESFORCE_CALLBACK_URL")
    salesforce_domain: str | None = Field(default=None, alias="SALESFORCE_DOMAIN")
    # Phase 1 dev-only override for the Salesforce token JSON file path.
    # Defaults to ``<repo_root>/apps/web/.sf-tokens.json`` (the same file the
    # Next.js OAuth flow writes). Production replaces this with a DB-backed
    # reader (FUS-22) and this field becomes unused.
    sf_dev_token_file: str | None = Field(default=None, alias="SF_DEV_TOKEN_FILE")

    # CareStack (M1 — appointment / case-acceptance metadata, narrow non-PHI scope).
    # NOTE (ENG-125): bootstrap-only, see SALESFORCE_* note above.
    carestack_idp_base_url: str | None = Field(default=None, alias="CARESTACK_IDP_BASE_URL")
    carestack_api_base_url: str | None = Field(default=None, alias="CARESTACK_API_BASE_URL")
    carestack_api_version: str | None = Field(default=None, alias="CARESTACK_API_VERSION")
    carestack_client_id: str | None = Field(default=None, alias="CARESTACK_CLIENT_ID")
    carestack_client_secret: SecretStr | None = Field(
        default=None, alias="CARESTACK_CLIENT_SECRET"
    )
    carestack_vendor_key: SecretStr | None = Field(default=None, alias="CARESTACK_VENDOR_KEY")
    carestack_account_key: SecretStr | None = Field(default=None, alias="CARESTACK_ACCOUNT_KEY")
    carestack_account_id: str | None = Field(default=None, alias="CARESTACK_ACCOUNT_ID")

    # --- Marketing / ad-spend connectors (Phase 1 — read-only pull) ---
    # Each provider follows the CareStack bootstrap pattern: env vars now,
    # ``tenant.integration_credential`` later. The ingest connectors read
    # these via ``Settings`` through their ``from_env()`` factories.
    #
    # Google Ads (Google Ads API v23, OAuth refresh + developer token).
    # ``GOOGLE_ADS_CUSTOMER_ID`` / ``GOOGLE_ADS_LOGIN_CUSTOMER_ID`` accept a
    # single id or a comma-separated list (the Replit account spans multiple
    # child accounts under one manager); dashes are tolerated and stripped
    # at use site.
    google_ads_client_id: str | None = Field(default=None, alias="GOOGLE_ADS_CLIENT_ID")
    google_ads_client_secret: SecretStr | None = Field(
        default=None, alias="GOOGLE_ADS_CLIENT_SECRET"
    )
    google_ads_developer_token: SecretStr | None = Field(
        default=None, alias="GOOGLE_ADS_DEVELOPER_TOKEN"
    )
    google_ads_refresh_token: SecretStr | None = Field(
        default=None, alias="GOOGLE_ADS_REFRESH_TOKEN"
    )
    google_ads_login_customer_id: str | None = Field(
        default=None, alias="GOOGLE_ADS_LOGIN_CUSTOMER_ID"
    )
    google_ads_customer_id: str | None = Field(
        default=None, alias="GOOGLE_ADS_CUSTOMER_ID"
    )

    # Meta Ads (Graph API v21, long-lived access token). App id/secret back
    # the auto-refresh path; the access token is what the insights pull uses.
    # ``META_ADS_AD_ACCOUNT_ID`` accepts a comma-separated list of ``act=<id>``
    # entries (parsed at use site).
    meta_ads_app_id: str | None = Field(default=None, alias="META_ADS_APP_ID")
    meta_ads_app_secret: SecretStr | None = Field(
        default=None, alias="META_ADS_APP_SECRET"
    )
    meta_ads_access_token: SecretStr | None = Field(
        default=None, alias="META_ADS_ACCESS_TOKEN"
    )
    meta_ads_ad_account_id: str | None = Field(
        default=None, alias="META_ADS_AD_ACCOUNT_ID"
    )

    # TikTok Ads (Business API v1.3, access token + advertiser id).
    tiktok_ads_access_token: SecretStr | None = Field(
        default=None, alias="TIKTOK_ADS_ACCESS_TOKEN"
    )
    tiktok_ads_advertiser_id: str | None = Field(
        default=None, alias="TIKTOK_ADS_ADVERTISER_ID"
    )

    # --- Web analytics connectors (Phase 2 — read-only pull) ---
    # GA4 (Data API v1beta) + Search Console (Webmasters v3). Both reuse the
    # Google Ads OAuth client (client_id/secret) with their own refresh tokens,
    # mirroring the Replit fallback. ``GSC_SITE_URL`` is optional — the GSC
    # connector auto-discovers the verified property via ``sites.list`` when
    # unset.
    ga_property_id: str | None = Field(default=None, alias="GA_PROPERTY_ID")
    ga_refresh_token: SecretStr | None = Field(default=None, alias="GA_REFRESH_TOKEN")
    gsc_refresh_token: SecretStr | None = Field(default=None, alias="GSC_REFRESH_TOKEN")
    gsc_site_url: str | None = Field(default=None, alias="GSC_SITE_URL")

    # --- Operator-account email outreach OAuth (ENG-131 / ADR-0004) ---
    # Google Workspace + Microsoft 365 OAuth foundation. Both providers
    # follow the same pattern: client_id (public), client_secret (Secret),
    # and a single ``OAUTH_REDIRECT_BASE_URL`` shared between them. The
    # callback path is appended at use site
    # (``/integrations/<provider>/callback``).
    #
    # Provisioning steps live in the per-provider CLAUDE.md files
    # (``packages/integrations/google_workspace/CLAUDE.md`` and
    # ``packages/integrations/microsoft_365/CLAUDE.md``).
    google_oauth_client_id: str | None = Field(
        default=None, alias="GOOGLE_OAUTH_CLIENT_ID"
    )
    google_oauth_client_secret: SecretStr | None = Field(
        default=None, alias="GOOGLE_OAUTH_CLIENT_SECRET"
    )
    microsoft_oauth_client_id: str | None = Field(
        default=None, alias="MICROSOFT_OAUTH_CLIENT_ID"
    )
    microsoft_oauth_client_secret: SecretStr | None = Field(
        default=None, alias="MICROSOFT_OAUTH_CLIENT_SECRET"
    )
    # Base URL the OAuth providers will redirect operators back to. Dev:
    # ``http://127.0.0.1:8001``. Prod: ``https://app.fusioncrm.example``.
    # The full callback URI is ``<base>/integrations/<provider>/callback``;
    # both must match the redirect URIs registered with the OAuth client.
    oauth_redirect_base_url: str = Field(
        default="http://127.0.0.1:8001", alias="OAUTH_REDIRECT_BASE_URL"
    )

    # --- Outreach tracking (ENG-134 / ADR-0004 §"Tracking") ---
    # Base URL the tracking pixel + one-click unsubscribe links resolve
    # to. Embedded in every outbound email at send time. MUST be HTTPS
    # in production (Gmail / Outlook reject http:// references in the
    # ``List-Unsubscribe`` header on some clients).
    #
    # The recipient-facing routes mounted under this base URL are:
    #   - ``GET  /outreach/track/open/{token}`` — 1x1 pixel
    #   - ``POST /outreach/unsubscribe/{token}`` — RFC 8058 one-click
    #   - ``GET  /u/{token}``                   — manual unsubscribe form
    #
    # When unset we fall back to ``OAUTH_REDIRECT_BASE_URL`` so dev
    # environments do not have to set two values for the same host.
    tracking_base_url: str | None = Field(
        default=None, alias="TRACKING_BASE_URL"
    )

    # Web frontend CORS (the staff dashboard origin will hit /api/...).
    # Same string-not-list rationale as `api_cors_origins_raw` above.
    web_cors_origins_raw: str = Field(default="", alias="WEB_CORS_ORIGINS")

    # Base URL of the Next.js staff frontend. Used by server-side OAuth
    # callback redirects to send the operator back to the settings UI
    # (which lives on the web app, not on the API). Dev:
    # ``http://127.0.0.1:3000``. Prod: ``https://app.fusioncrm.example``.
    web_app_base_url: str = Field(
        default="http://127.0.0.1:3000", alias="WEB_APP_BASE_URL"
    )

    # --- Messenger notifications (ENG-455, dedupe core) ---
    # Master enablement gate for the messenger rule→outbox engine
    # (``NotificationEventService.emit``). Default OFF so the dedupe +
    # enablement wiring lands DARK: emit becomes a no-op until an operator
    # flips this on (production rollout is deferred). When False, emit
    # enqueues NOTHING regardless of rules, dedupe key, or cutoff.
    notifications_enabled: bool = Field(
        default=False, alias="NOTIFICATIONS_ENABLED"
    )
    # Historical-entity cutoff: only entities whose ``source_created_at`` is
    # at or after this instant may notify. An entity created before the
    # cutoff (e.g. a CareStack/SF backfill of pre-existing leads) is
    # suppressed even when notifications are enabled. ``None`` = no cutoff
    # (rely on the enablement flag + per-entity dedupe key instead). Set as
    # an ISO-8601 timestamp; a timezone-aware value is recommended so the
    # comparison against provider ``source_created_at`` is unambiguous.
    notifications_cutoff_at: datetime | None = Field(
        default=None, alias="NOTIFICATIONS_CUTOFF_AT"
    )
    # ENG-460: the corporate messenger is an AUTHORIZED PHI surface — only
    # staff with PHI access read the Mattermost team — so notification cards
    # carry the patient's REAL name / phone / provider, not a de-identified
    # ``person_uid`` stub. When True the renderer runs in ``phi_mode="full"``
    # and substitutes any context variable verbatim (the de-identification
    # allowlist is bypassed); when False it falls back to the historical
    # ``deidentified`` behaviour (allowlist only, everything else redacted).
    # Default True per the operator decision (ADR-0006). SECURITY: with this
    # on, PHI lands in the Mattermost store — the prod Mattermost server
    # (ENG-442) MUST be treated as a PHI system (access control, TLS,
    # encrypted backup, retention). Application logs stay PHI-free regardless.
    messenger_phi_full: bool = Field(
        default=True, alias="MESSENGER_PHI_FULL"
    )

    @model_validator(mode="before")
    @classmethod
    def _resolve_secret_urls(cls, values: Any) -> Any:
        """Replace ``gcp-secret://...`` env values with their payloads.

        Runs before per-field parsing so DSN-typed and SecretStr fields
        receive the materialised value, not the URL. No-op for any value
        that is not a Secret Manager URL — dev `.env` files are unaffected.
        """
        if isinstance(values, dict):
            return resolve_mapping(values)
        return values

    @property
    def api_cors_origins(self) -> list[str]:
        return [v.strip() for v in self.api_cors_origins_raw.split(",") if v.strip()]

    @property
    def web_cors_origins(self) -> list[str]:
        return [v.strip() for v in self.web_cors_origins_raw.split(",") if v.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def effective_tracking_base_url(self) -> str:
        """Resolved tracking base URL with the OAuth fallback applied.

        ENG-134: the tracking pixel + unsubscribe routes are mounted on
        the same FastAPI surface as the OAuth callbacks today, so dev
        environments do not need a second host. Production deployments
        should set ``TRACKING_BASE_URL`` to a stable HTTPS host that is
        not coupled to the OAuth callback domain.
        """
        if self.tracking_base_url:
            return self.tracking_base_url.rstrip("/")
        return self.oauth_redirect_base_url.rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Use this everywhere instead of instantiating Settings()."""
    return Settings()
