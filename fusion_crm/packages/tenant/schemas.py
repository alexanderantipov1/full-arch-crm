"""Pydantic DTOs for the tenant domain."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

TenantStatus = Literal["active", "paused", "archived"]

# Provider kind literal — must mirror ``packages.tenant.models.PROVIDER_KINDS``
# and the Zod ProviderSchema on the frontend (apps/web/lib/api/schemas).
ProviderKind = Literal[
    "salesforce",
    "hubspot",
    "carestack",
    "open_dental",
    "vapi",
    "twilio",
    "openai",
    "anthropic",
    "elevenlabs",
    "deepgram",
    "google_workspace",
    "microsoft_365",
    "birdeye",
    "podium",
    "google_business",
    "stripe",
    "square",
    "carecredit",
    "sunbit",
    "cherry",
    "google_analytics",
    "meta_pixel",
    "tiktok_pixel",
    "mattermost",
    "google_ads",
    "meta_ads",
    "google_search_console",
    "other",
]
CredentialKind = Literal["oauth_token", "api_key", "password_grant", "webhook_secret"]
CredentialStatus = Literal["active", "expired", "revoked"]
BootstrapProviderKind = Literal[
    "salesforce",
    "carestack",
    "openai",
    # Marketing / SEO providers (ENG-491) — operator-entered bootstrap
    # credentials persisted as ``api_key`` payloads (ENG-489 schemas).
    "google_ads",
    "meta_ads",
    "google_analytics",
    "google_search_console",
]


# --- Tenant ---


class TenantIn(BaseModel):
    """Input for creating / updating a tenant.

    ``slug`` is required and unique. Update flows accept partial input
    via ``model_dump(exclude_unset=True)`` at the service layer.
    """

    slug: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=240)
    primary_email: str | None = Field(default=None, max_length=320)
    timezone: str = Field(default="America/Los_Angeles", max_length=64)
    locale: str = Field(default="en-US", max_length=16)
    status: TenantStatus = Field(default="active")


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    primary_email: str | None
    timezone: str
    locale: str
    status: TenantStatus
    created_at: datetime
    updated_at: datetime


# --- Location ---


class LocationIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=240)
    short_name: str | None = Field(default=None, max_length=64)
    external_ref: dict[str, object] = Field(default_factory=dict)
    address_line1: str | None = Field(default=None, max_length=240)
    address_line2: str | None = Field(default=None, max_length=240)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=64)
    zip: str | None = Field(default=None, max_length=32)
    country: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    timezone_override: str | None = Field(default=None, max_length=64)
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool = True


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    short_name: str | None
    external_ref: dict[str, object]
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    zip: str | None
    country: str | None
    phone: str | None
    timezone_override: str | None
    latitude: float | None
    longitude: float | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- IntegrationCredential ---


class IntegrationCredentialIn(BaseModel):
    """Input for recording a credential.

    ``payload`` MUST already contain Fernet-encrypted values. The service
    refuses to store plaintext — pass ciphertext (e.g. via
    ``packages.integrations.crypto.encrypt_str``).

    Multi-mailbox fields (ENG-125):

    - ``mailbox_email`` — populated by the OAuth callback for
      ``google_workspace`` / ``microsoft_365``; null otherwise.
    - ``location_id`` — pin a credential to a specific office; null = tenant-wide.
    - ``is_default`` — partial-unique within ``(tenant_id, provider_kind)``.
    - ``tags`` — operator-set labels for routing rules.
    """

    provider_kind: ProviderKind
    credential_kind: CredentialKind
    payload: dict[str, object] = Field(default_factory=dict)
    display_name: str | None = Field(default=None, max_length=240)
    status: CredentialStatus = Field(default="active")
    expires_at: datetime | None = None
    last_refreshed_at: datetime | None = None
    mailbox_email: str | None = Field(default=None, max_length=320)
    location_id: UUID | None = None
    is_default: bool = False
    tags: list[str] = Field(default_factory=list)


class IntegrationCredentialUpdate(BaseModel):
    """Patch input for an existing credential.

    Used by routes that update metadata (display_name, tags, location_id,
    is_default) WITHOUT re-encrypting the payload. To rotate the payload
    use ``IntegrationCredentialService.upsert`` instead.
    """

    display_name: str | None = Field(default=None, max_length=240)
    status: CredentialStatus | None = None
    location_id: UUID | None = None
    is_default: bool | None = None
    tags: list[str] | None = None
    expires_at: datetime | None = None
    last_refreshed_at: datetime | None = None


class IntegrationCredentialBootstrapIn(BaseModel):
    """Operator input for provider bootstrap credentials.

    This public API accepts the initial app/API configuration needed to
    bootstrap Salesforce OAuth, CareStack password-grant access, the OpenAI
    API key, and the four marketing / SEO providers (Google Ads, Meta Ads,
    GA4, Search Console — ENG-491). The service converts these fields into
    the encrypted payload; responses still return metadata only via
    ``IntegrationCredentialOut``. The marketing payload shapes mirror the
    ENG-489 ``*CredentialPayload`` models in this module exactly.
    """

    model_config = ConfigDict(extra="forbid")

    provider_kind: BootstrapProviderKind
    credential_kind: CredentialKind | None = None
    display_name: str | None = Field(default=None, max_length=240)
    is_default: bool | None = None

    # Salesforce app config. ``client_secret`` is secret; ``client_id``,
    # ``callback_url`` and ``domain`` are config but remain in the encrypted
    # payload so the UI never has a second read path for stored values.
    client_id: str | None = Field(default=None, min_length=1, max_length=512)
    client_secret: str | None = Field(default=None, min_length=1, max_length=2048)
    callback_url: str | None = Field(default=None, min_length=1, max_length=2048)
    domain: str | None = Field(default=None, min_length=1, max_length=255)

    # CareStack password-grant config.
    vendor_key: str | None = Field(default=None, min_length=1, max_length=1024)
    account_key: str | None = Field(default=None, min_length=1, max_length=1024)
    account_id: str | None = Field(default=None, min_length=1, max_length=255)
    idp_base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_version: str | None = Field(default=None, min_length=1, max_length=64)

    # AI provider API key config.
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)

    # Marketing / SEO config (ENG-491). These mirror the ENG-489 payload
    # models in this module (``GoogleAdsCredentialPayload`` etc.); the OAuth
    # ``client_id`` / ``client_secret`` are reused from the Salesforce block
    # above. Secret-bearing fields stay in the encrypted payload; NEVER log.
    developer_token: str | None = Field(default=None, min_length=1, max_length=2048)
    refresh_token: str | None = Field(default=None, min_length=1, max_length=4096)
    login_customer_id: str | None = Field(default=None, max_length=64)
    customer_ids: list[str] | None = Field(default=None)
    access_token: str | None = Field(default=None, min_length=1, max_length=4096)
    ad_account_ids: list[str] | None = Field(default=None)
    app_id: str | None = Field(default=None, max_length=64)
    app_secret: str | None = Field(default=None, max_length=2048)
    property_id: str | None = Field(default=None, min_length=1, max_length=64)
    site_url: str | None = Field(default=None, min_length=1, max_length=2048)

    @model_validator(mode="after")
    def validate_provider_shape(self) -> Self:
        # All marketing / SEO providers persist as ``api_key`` payloads.
        expected_kind = {
            "salesforce": "api_key",
            "carestack": "password_grant",
            "openai": "api_key",
            "google_ads": "api_key",
            "meta_ads": "api_key",
            "google_analytics": "api_key",
            "google_search_console": "api_key",
        }[self.provider_kind]
        if self.credential_kind is not None and self.credential_kind != expected_kind:
            raise ValueError(
                f"{self.provider_kind} bootstrap credentials must use "
                f"credential_kind={expected_kind}"
            )

        # Every typed field name on this model; ``unsupported`` is computed as
        # "every field NOT in the provider's supported set" so a new provider
        # cannot silently leak a sibling provider's field into the envelope.
        all_fields = {
            "client_id",
            "client_secret",
            "callback_url",
            "domain",
            "vendor_key",
            "account_key",
            "account_id",
            "idp_base_url",
            "api_base_url",
            "api_version",
            "api_key",
            "developer_token",
            "refresh_token",
            "login_customer_id",
            "customer_ids",
            "access_token",
            "ad_account_ids",
            "app_id",
            "app_secret",
            "property_id",
            "site_url",
        }

        # (required, optional) field sets per provider.
        required_by_provider: dict[str, tuple[str, ...]] = {
            "salesforce": ("client_id", "client_secret", "callback_url"),
            "carestack": (
                "client_id",
                "client_secret",
                "vendor_key",
                "account_key",
                "account_id",
                "idp_base_url",
                "api_base_url",
            ),
            "openai": ("api_key",),
            "google_ads": (
                "client_id",
                "client_secret",
                "developer_token",
                "refresh_token",
            ),
            "meta_ads": ("access_token",),
            "google_analytics": (
                "client_id",
                "client_secret",
                "refresh_token",
                "property_id",
            ),
            "google_search_console": (
                "client_id",
                "client_secret",
                "refresh_token",
            ),
        }
        optional_by_provider: dict[str, tuple[str, ...]] = {
            "salesforce": ("domain",),
            "carestack": ("api_version",),
            "openai": (),
            "google_ads": ("login_customer_id", "customer_ids"),
            "meta_ads": ("ad_account_ids", "app_id", "app_secret"),
            "google_analytics": (),
            "google_search_console": ("site_url",),
        }

        supported = set(required_by_provider[self.provider_kind]) | set(
            optional_by_provider[self.provider_kind]
        )
        extra_fields = sorted(
            field
            for field in all_fields - supported
            if getattr(self, field) is not None
        )
        if extra_fields:
            raise ValueError(
                f"unsupported {self.provider_kind} credential fields: "
                + ", ".join(extra_fields)
            )

        missing = [
            field
            for field in required_by_provider[self.provider_kind]
            if getattr(self, field) is None
        ]
        if missing:
            raise ValueError(
                "missing required credential fields: " + ", ".join(missing)
            )
        return self


# --- Marketing / SEO credential payload schemas (ENG-489) ---
#
# These typed models describe the *decrypted* ``payload`` dict stored
# (Fernet-encrypted) in ``tenant.integration_credential.payload`` for each
# marketing / SEO provider. They are the single source the ENG-490
# ``from_credential`` factories consume to build per-tenant ad-spend / SEO
# connectors, replacing the env-var fallback in ``packages.core.config``.
#
# Conventions, in lock-step with the rest of this package:
#
# - Fields are plain JSON-serialisable ``str`` / ``list[str]``. The payload
#   dict is JSON-encoded then Fernet-encrypted by
#   ``IntegrationCredentialService._wrap_envelope`` before it touches the DB,
#   so ``SecretStr`` (which does not round-trip through ``json.dumps``) is
#   deliberately NOT used here — this mirrors ``IntegrationCredentialBootstrapIn``.
#   Secrecy is enforced by the encryption envelope + the "never log payload"
#   rule, NOT by the field type. NEVER log these values; the service logs only
#   ``provider_kind`` + ``credential_kind``.
# - ``credential_kind`` for all four providers is ``"api_key"`` (the bootstrap
#   kind), consistent with how CareStack stores password-grant style payloads.
# - ``extra="forbid"`` so an unexpected key is rejected at the boundary rather
#   than silently encrypted into the envelope.


class GoogleAdsCredentialPayload(BaseModel):
    """Decrypted credential payload for ``provider_kind = "google_ads"``.

    OAuth refresh-token + developer-token grant for the Google Ads API
    (mirrors the ``GOOGLE_ADS_*`` env fields in ``packages.core.config``).
    ``login_customer_id`` is the manager (MCC) account used as the login
    context; ``customer_ids`` are the child accounts to pull.
    """

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(..., min_length=1, max_length=512)
    client_secret: str = Field(..., min_length=1, max_length=2048)
    developer_token: str = Field(..., min_length=1, max_length=2048)
    refresh_token: str = Field(..., min_length=1, max_length=4096)
    login_customer_id: str | None = Field(default=None, max_length=64)
    customer_ids: list[str] = Field(default_factory=list)


class MetaAdsCredentialPayload(BaseModel):
    """Decrypted credential payload for ``provider_kind = "meta_ads"``.

    Long-lived access token for the Meta Graph API (mirrors the
    ``META_ADS_*`` env fields). ``app_id`` / ``app_secret`` back the
    optional token auto-refresh path; ``ad_account_ids`` are the
    ``act_<id>`` accounts to pull.
    """

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(..., min_length=1, max_length=4096)
    ad_account_ids: list[str] = Field(default_factory=list)
    app_id: str | None = Field(default=None, max_length=64)
    app_secret: str | None = Field(default=None, max_length=2048)


class GoogleAnalyticsCredentialPayload(BaseModel):
    """Decrypted credential payload for ``provider_kind = "google_analytics"``.

    GA4 Data API grant. Reuses the Google Ads OAuth client
    (``client_id`` / ``client_secret``) with its own ``refresh_token`` — the
    OAuth client is duplicated into each provider's payload for now so each
    connector is self-contained (a shared-OAuth-app store is a later
    refactor). ``property_id`` is the GA4 property to query.
    """

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(..., min_length=1, max_length=512)
    client_secret: str = Field(..., min_length=1, max_length=2048)
    refresh_token: str = Field(..., min_length=1, max_length=4096)
    property_id: str = Field(..., min_length=1, max_length=64)


class GoogleSearchConsoleCredentialPayload(BaseModel):
    """Decrypted credential payload for ``provider_kind = "google_search_console"``.

    Search Console (Webmasters v3) grant. Like GA4, reuses the Google Ads
    OAuth client (``client_id`` / ``client_secret``) with its own
    ``refresh_token`` — duplicated per provider for now (see
    ``GoogleAnalyticsCredentialPayload``). ``site_url`` is optional; when
    unset the connector auto-discovers the verified property via
    ``sites.list``.
    """

    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(..., min_length=1, max_length=512)
    client_secret: str = Field(..., min_length=1, max_length=2048)
    refresh_token: str = Field(..., min_length=1, max_length=4096)
    site_url: str | None = Field(default=None, max_length=2048)


MarketingCredentialPayload = (
    GoogleAdsCredentialPayload
    | MetaAdsCredentialPayload
    | GoogleAnalyticsCredentialPayload
    | GoogleSearchConsoleCredentialPayload
)
"""Union of the four ENG-489 marketing / SEO credential payload shapes."""


class IntegrationCredentialOut(BaseModel):
    """Output: ``payload`` is intentionally elided — secrets do NOT cross
    the service boundary in plaintext, and even encrypted blobs do not
    leak through DTOs by default.

    Multi-mailbox fields (ENG-125): ``mailbox_email``, ``location_id``,
    ``is_default``, ``tags``. Operators see these in the integrations
    settings UI; the ``payload`` itself never crosses the service.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    provider_kind: ProviderKind
    credential_kind: CredentialKind
    display_name: str | None
    status: CredentialStatus
    expires_at: datetime | None
    last_refreshed_at: datetime | None
    mailbox_email: str | None
    location_id: UUID | None
    is_default: bool
    tags: list[str]
    created_at: datetime
    updated_at: datetime


# --- Setting ---


class SettingIn(BaseModel):
    key: str = Field(..., min_length=1, max_length=160)
    value: dict[str, object] = Field(..., description="Free-form JSON value")


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    key: str
    value: dict[str, object]
    updated_at: datetime


# --- Current tenant aggregate (ENG-124 GET /tenant/current) ---


class CurrentTenantOut(BaseModel):
    """Tenant view for ``GET /tenant/current``.

    Mirrors the Zod ``TenantSchema`` on the frontend: includes the
    organisation-profile fields that the UI surfaces today as
    nullable placeholders (``primary_phone``, ``website``,
    ``logo_url``, ``billing_email``, ``industry``, ``tax_id``,
    ``subscription_status``) so the schema can grow without breaking
    the contract. DB columns for those land in a later migration —
    for now they always emit ``None``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    primary_email: str | None = None
    primary_phone: str | None = None
    website: str | None = None
    logo_url: str | None = None
    billing_email: str | None = None
    industry: str | None = None
    tax_id: str | None = None
    timezone: str
    locale: str
    status: TenantStatus
    subscription_status: str | None = None
    created_at: datetime


class TenantWithRelationsOut(BaseModel):
    """Aggregate response for ``GET /tenant/current``.

    Composes the current tenant with its locations, integration
    credentials (metadata only — payloads stay server-side), and
    settings (free-form JSON value). Field shapes match the Zod
    ``TenantWithRelationsSchema``.
    """

    tenant: CurrentTenantOut
    locations: list[LocationOut]
    integrations: list[IntegrationCredentialOut]
    settings: list[SettingOut]


# --- Import summaries ---


class ImportSummary(BaseModel):
    """Result of an idempotent import job (e.g. CareStack location sync).

    All counters are non-negative. ``total_seen`` is the number of
    rows the upstream provider returned; ``created + updated`` may be
    less than that when nothing changed (the row already exists with
    identical fields). ``deactivated`` counts local rows that no
    longer appear upstream and were marked ``is_active = false``.
    """

    created: int = Field(default=0, ge=0)
    updated: int = Field(default=0, ge=0)
    deactivated: int = Field(default=0, ge=0)
    total_seen: int = Field(default=0, ge=0)
