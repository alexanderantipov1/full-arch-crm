"""ENG-125 (2/2): seed bootstrap-only credentials into ``tenant.integration_credential``.

Revision ID: a8c5e7d2f4b9
Revises: b7c3e9f1a2d4
Create Date: 2026-05-09 13:00:00.000000+00:00

Reads the current process environment via ``packages.core.config.Settings``
(the only allowed env-read surface) and copies any populated Salesforce /
CareStack values into encrypted rows on ``tenant.integration_credential``
under the bootstrap tenant id.

Encryption envelope per row payload::

    {"ciphertext": "<fernet-base64>", "alg": "fernet"}

The plaintext is a JSON object whose schema depends on the credential
tuple (see ENG-125 spec):

  - (salesforce, oauth_token)
        ``{access_token, refresh_token, instance_url, issued_at}`` —
        copied from the Phase 1 dev token file
        ``apps/web/.sf-tokens.json`` when present.
  - (salesforce, api_key)
        ``{client_id, client_secret, callback_url, domain}`` from env.
  - (carestack, password_grant)
        ``{client_id, client_secret, vendor_key, account_key, account_id,
        idp_base_url, api_base_url, api_version}`` from env.

Bootstrap rows land with ``is_default = true`` because they are the
single instance of each provider for the seed tenant; later operator
upserts can flip the default via
``IntegrationCredentialService.set_default``.

Rules:

* Idempotent. If a row with ``(tenant_id, provider_kind, credential_kind)``
  and ``status='active'`` already exists, this migration leaves it alone.
  The runtime ``IntegrationCredentialService.upsert`` is the rotation
  path; the bootstrap migration only writes when the table is empty for
  that tuple.
* Plaintext payload values are NEVER printed / logged. The summary log
  emits counts only ("seeded N rows for provider=X").
* Skipped silently when the corresponding env / file source is missing —
  fresh dev environments without integrations stay bootable.

After this migration, ``.env`` ``SALESFORCE_*`` and ``CARESTACK_*`` keys
become **bootstrap-only**: runtime callers prefer DB credentials and
fall back to env via the resolver helpers (see
``packages.tenant.credential_service.IntegrationCredentialService``).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

# NB: this is the ONLY place a migration is allowed to touch ``Settings``.
# Per ``packages/core/CLAUDE.md`` env reads MUST go through Settings; the
# migration reads via the same accessor as application code.
from packages.core.config import get_settings

# Use stdlib logging here (not the platform's structlog) because alembic
# manages its own logger config and migrations run in a non-app context.
log = logging.getLogger("alembic.tenant_credentials_seed")


revision: str = "a8c5e7d2f4b9"
down_revision: str | None = "b7c3e9f1a2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Bootstrap tenant id, kept self-contained per the alembic discipline rule
# that revision files do not import each other.
BOOTSTRAP_TENANT_ID = "11111111-1111-4111-8111-111111111111"

_ALG_FERNET = "fernet"


def _wrap_envelope(payload: dict[str, object], fernet: Fernet) -> dict[str, str]:
    """Return ``{"ciphertext": ..., "alg": "fernet"}`` for a JSON payload."""
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    ciphertext = fernet.encrypt(plaintext.encode("utf-8"))
    return {"ciphertext": ciphertext.decode("ascii"), "alg": _ALG_FERNET}


def _row_exists(
    bind: sa.engine.Connection,
    *,
    tenant_id: str,
    provider_kind: str,
    credential_kind: str,
) -> bool:
    """Return True if an active row already exists for the tuple."""
    stmt = sa.text(
        """
        SELECT 1 FROM tenant.integration_credential
        WHERE tenant_id = :tenant_id
          AND provider_kind = :provider_kind
          AND credential_kind = :credential_kind
          AND status = 'active'
        LIMIT 1
        """
    )
    result = bind.execute(
        stmt,
        {
            "tenant_id": tenant_id,
            "provider_kind": provider_kind,
            "credential_kind": credential_kind,
        },
    ).first()
    return result is not None


def _insert(
    bind: sa.engine.Connection,
    *,
    tenant_id: str,
    provider_kind: str,
    credential_kind: str,
    payload_envelope: dict[str, str],
    display_name: str,
    is_default: bool = True,
) -> None:
    """Insert one credential row.

    Bootstrap rows are the only instance of their provider tuple at
    install-time, so they take ``is_default = true`` by default. The
    partial unique index (`uq_integration_credential_default`) tolerates
    re-runs because ``_row_exists`` short-circuits before we get here.
    """
    bind.execute(
        sa.text(
            """
            INSERT INTO tenant.integration_credential
                (id, tenant_id, provider_kind, credential_kind, payload,
                 display_name, status, is_default, tags,
                 created_at, updated_at)
            VALUES
                (gen_random_uuid(), :tenant_id, :provider_kind,
                 :credential_kind, CAST(:payload AS jsonb),
                 :display_name, 'active', :is_default,
                 CAST('[]' AS jsonb), now(), now())
            """
        ),
        {
            "tenant_id": tenant_id,
            "provider_kind": provider_kind,
            "credential_kind": credential_kind,
            "payload": json.dumps(payload_envelope),
            "display_name": display_name,
            "is_default": is_default,
        },
    )


def _read_sf_dev_token_file(settings: object) -> dict[str, object] | None:
    """Read the Phase 1 SF dev token file via the same path resolver
    used by ``packages.integrations.salesforce.tokens``.

    Returns the raw dict on success or None when missing / malformed —
    callers log a "skipped" line and move on.
    """
    configured = getattr(settings, "sf_dev_token_file", None)
    # packages/db/alembic/versions/<rev>.py → parents[3] = repo root.
    repo_root = Path(__file__).resolve().parents[3]
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = repo_root / path
    else:
        path = repo_root / "apps" / "web" / ".sf-tokens.json"

    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("access_token") or not data.get(
        "instance_url"
    ):
        return None
    return data


def _secret(settings: object, attr: str) -> str | None:
    """Pull a possibly ``SecretStr`` field off the settings object as plaintext."""
    value = getattr(settings, attr, None)
    if value is None:
        return None
    # SecretStr exposes get_secret_value(); plain str attributes pass through.
    get = getattr(value, "get_secret_value", None)
    if callable(get):
        return get()
    return str(value)


def upgrade() -> None:
    settings = get_settings()
    encryption_key = _secret(settings, "encryption_key")
    if not encryption_key:
        # Without a Fernet key we cannot encrypt; that is a hard error
        # only when the operator has populated some integration env. If
        # all integration env is empty too, the migration is effectively
        # a no-op so we can leave it as a warning + skip.
        log.warning(
            "tenant_credentials_seed: ENCRYPTION_KEY not set — "
            "cannot seed credentials. If you have SALESFORCE_* / "
            "CARESTACK_* values populated, generate a Fernet key, set "
            "ENCRYPTION_KEY, and re-run alembic.",
        )
        return

    fernet = Fernet(encryption_key.encode("utf-8"))
    bind = op.get_bind()

    seeded: dict[str, list[str]] = {"salesforce": [], "carestack": []}
    skipped: dict[str, list[str]] = {"salesforce": [], "carestack": []}

    # --- Salesforce: api_key (client config) ---
    sf_client_id = getattr(settings, "salesforce_client_id", None)
    sf_client_secret = _secret(settings, "salesforce_client_secret")
    sf_callback_url = getattr(settings, "salesforce_callback_url", None)
    sf_domain = getattr(settings, "salesforce_domain", None)
    if sf_client_id and sf_client_secret:
        if _row_exists(
            bind,
            tenant_id=BOOTSTRAP_TENANT_ID,
            provider_kind="salesforce",
            credential_kind="api_key",
        ):
            skipped["salesforce"].append("api_key (already present)")
        else:
            payload: dict[str, object] = {
                "client_id": sf_client_id,
                "client_secret": sf_client_secret,
                "callback_url": sf_callback_url or "",
                "domain": sf_domain or "login.salesforce.com",
            }
            _insert(
                bind,
                tenant_id=BOOTSTRAP_TENANT_ID,
                provider_kind="salesforce",
                credential_kind="api_key",
                payload_envelope=_wrap_envelope(payload, fernet),
                display_name="Salesforce production org (bootstrap)",
                is_default=True,
            )
            seeded["salesforce"].append("api_key")
    else:
        skipped["salesforce"].append("api_key (env empty)")

    # --- Salesforce: oauth_token (from dev token file when present) ---
    sf_tokens = _read_sf_dev_token_file(settings)
    if sf_tokens is not None:
        if _row_exists(
            bind,
            tenant_id=BOOTSTRAP_TENANT_ID,
            provider_kind="salesforce",
            credential_kind="oauth_token",
        ):
            skipped["salesforce"].append("oauth_token (already present)")
        else:
            # NB: the partial unique on (tenant_id, provider_kind) WHERE
            # is_default = true would conflict if both api_key and
            # oauth_token tried to be default for ``salesforce``. Keep
            # api_key as default (it's the rotation root); oauth_token
            # is non-default here.
            payload = {
                "access_token": sf_tokens.get("access_token"),
                "refresh_token": sf_tokens.get("refresh_token"),
                "instance_url": sf_tokens.get("instance_url"),
                "issued_at": sf_tokens.get("issued_at"),
            }
            _insert(
                bind,
                tenant_id=BOOTSTRAP_TENANT_ID,
                provider_kind="salesforce",
                credential_kind="oauth_token",
                payload_envelope=_wrap_envelope(payload, fernet),
                display_name="Salesforce OAuth tokens (bootstrap from dev file)",
                is_default=False,
            )
            seeded["salesforce"].append("oauth_token")
    else:
        skipped["salesforce"].append(
            "oauth_token (no .sf-tokens.json — run OAuth flow first)"
        )

    # --- CareStack: password_grant ---
    cs_client_id = getattr(settings, "carestack_client_id", None)
    cs_client_secret = _secret(settings, "carestack_client_secret")
    cs_vendor_key = _secret(settings, "carestack_vendor_key")
    cs_account_key = _secret(settings, "carestack_account_key")
    cs_account_id = getattr(settings, "carestack_account_id", None)
    cs_idp_base_url = getattr(settings, "carestack_idp_base_url", None)
    cs_api_base_url = getattr(settings, "carestack_api_base_url", None)
    cs_api_version = getattr(settings, "carestack_api_version", None)

    cs_complete = all(
        [
            cs_client_id,
            cs_client_secret,
            cs_vendor_key,
            cs_account_key,
            cs_account_id,
            cs_idp_base_url,
            cs_api_base_url,
        ]
    )
    if cs_complete:
        if _row_exists(
            bind,
            tenant_id=BOOTSTRAP_TENANT_ID,
            provider_kind="carestack",
            credential_kind="password_grant",
        ):
            skipped["carestack"].append("password_grant (already present)")
        else:
            payload = {
                "client_id": cs_client_id,
                "client_secret": cs_client_secret,
                "vendor_key": cs_vendor_key,
                "account_key": cs_account_key,
                "account_id": cs_account_id,
                "idp_base_url": cs_idp_base_url,
                "api_base_url": cs_api_base_url,
                "api_version": cs_api_version or "v1.0",
            }
            _insert(
                bind,
                tenant_id=BOOTSTRAP_TENANT_ID,
                provider_kind="carestack",
                credential_kind="password_grant",
                payload_envelope=_wrap_envelope(payload, fernet),
                display_name="CareStack — Antipov account (bootstrap)",
                is_default=True,
            )
            seeded["carestack"].append("password_grant")
    else:
        skipped["carestack"].append("password_grant (env incomplete)")

    # Counts only — never the payload.
    total = sum(len(v) for v in seeded.values())
    log.info(
        "tenant_credentials_seed: completed; seeded=%d "
        "(salesforce=%d, carestack=%d); skipped=%s",
        total,
        len(seeded["salesforce"]),
        len(seeded["carestack"]),
        {k: len(v) for k, v in skipped.items()},
    )


def downgrade() -> None:
    """Remove every active credential under the bootstrap tenant.

    Conservative scope: only deletes ``status='active'`` rows for the
    bootstrap tenant id, because re-running the bootstrap should yield
    the same result. Revoked / expired rows are left in place as
    historical evidence.
    """
    op.execute(
        sa.text(
            """
            DELETE FROM tenant.integration_credential
            WHERE tenant_id = :tenant_id
              AND status = 'active'
              AND provider_kind IN ('salesforce', 'carestack')
            """
        ).bindparams(tenant_id=BOOTSTRAP_TENANT_ID)
    )
