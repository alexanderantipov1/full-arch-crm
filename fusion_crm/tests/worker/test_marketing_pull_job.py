"""Unit tests for the ENG-490 per-tenant marketing pull credential path.

These cover credential resolution only — the actual provider HTTP and the
ingest services are mocked. Three behaviours per provider:

  1. A DB credential is preferred over env: when ``read_for`` returns a
     payload, the client is built via ``from_credential`` and ``from_env``
     is NOT called.
  2. No DB credential → env fallback: when ``read_for`` raises
     ``NoCredentialError`` and env vars are present, the client is built via
     ``from_env``.
  3. No DB credential AND no env → graceful skip
     (``{"skipped": "no_credential"}``), never a crash.

The credential service and the per-provider HTTP/ingest layers are fully
mocked; ZERO real network or DB calls.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.worker.jobs import marketing_pull as job
from packages.integrations.google_ads import GoogleAdsNotConnectedError
from packages.integrations.google_analytics import GoogleAnalyticsNotConnectedError
from packages.integrations.google_search_console import (
    GoogleSearchConsoleNotConnectedError,
)
from packages.integrations.meta_ads import MetaAdsNotConnectedError

# ---------------------------------------------------------------- helpers


def _fake_session_cm(session: MagicMock) -> Any:
    @asynccontextmanager
    async def _cm() -> Any:
        yield session

    return _cm


def _ingest_result() -> MagicMock:
    """Stand-in for an ingest *ImportOut — only the fields the log line reads."""
    result = MagicMock()
    result.imported_count = 1
    result.unchanged_count = 0
    result.skipped_count = 0
    result.campaigns_upserted = 1
    result.account_count = 1
    result.model_dump.return_value = {"imported": 1}
    return result


def _cred_svc(*, payload: dict | None, raises: Exception | None = None) -> MagicMock:
    svc = MagicMock()
    if raises is not None:
        svc.read_for = AsyncMock(side_effect=raises)
    else:
        svc.read_for = AsyncMock(return_value=payload)
    return svc


# Per-provider wiring: (pull fn, client attr, ingest svc attr, ingest method,
# provider_kind, not-connected error).
_PROVIDERS = [
    (
        "pull_google_ads_for_tenant",
        "GoogleAdsClient",
        "GoogleAdsCampaignIngestService",
        "import_recent_spend",
        "google_ads",
        GoogleAdsNotConnectedError,
    ),
    (
        "pull_meta_ads_for_tenant",
        "MetaAdsClient",
        "MetaAdsCampaignIngestService",
        "import_recent_spend",
        "meta_ads",
        MetaAdsNotConnectedError,
    ),
    (
        "pull_ga4_for_tenant",
        "GoogleAnalyticsClient",
        "GoogleAnalyticsMetricIngestService",
        "import_recent_metrics",
        "google_analytics",
        GoogleAnalyticsNotConnectedError,
    ),
    (
        "pull_gsc_for_tenant",
        "GoogleSearchConsoleClient",
        "GoogleSearchConsoleQueryIngestService",
        "import_recent_queries",
        "google_search_console",
        GoogleSearchConsoleNotConnectedError,
    ),
]


# ---------------------------------------------------------------- DB-preferred


@pytest.mark.parametrize(
    "pull_fn,client_attr,svc_attr,svc_method,provider,_err",
    _PROVIDERS,
)
@pytest.mark.asyncio
async def test_db_credential_preferred_over_env(
    pull_fn: str,
    client_attr: str,
    svc_attr: str,
    svc_method: str,
    provider: str,
    _err: type[Exception],
) -> None:
    """When a DB credential exists, the client is built via ``from_credential``
    and ``from_env`` is never touched. ``read_for`` is queried for the right
    provider + ``api_key`` kind."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())

    cred_svc = _cred_svc(payload={"client_id": "x"})

    client = MagicMock()
    client.close = AsyncMock()

    svc = MagicMock()
    setattr(svc, svc_method, AsyncMock(return_value=_ingest_result()))
    # GA4 ingest additionally imports channel + page dimensions (ENG-478); the
    # other providers never call these, so mocking them unconditionally is
    # harmless.
    svc.import_recent_channels = AsyncMock(return_value=_ingest_result())
    svc.import_recent_pages = AsyncMock(return_value=_ingest_result())

    with patch.object(job, "async_session", _fake_session_cm(session)), patch.object(
        job, "IntegrationCredentialService", return_value=cred_svc
    ), patch.object(job, client_attr) as client_cls, patch.object(
        job, svc_attr, return_value=svc
    ):
        client_cls.from_credential.return_value = client
        result = await getattr(job, pull_fn)({}, tenant_id)

    assert "skipped" not in result
    client_cls.from_credential.assert_called_once_with({"client_id": "x"})
    client_cls.from_env.assert_not_called()
    cred_svc.read_for.assert_awaited_once_with(tenant_id_arg(cred_svc), provider, "api_key")
    client.close.assert_awaited_once()


def tenant_id_arg(cred_svc: MagicMock) -> Any:
    """Return the tenant_id positional that ``read_for`` was awaited with."""
    return cred_svc.read_for.await_args.args[0]


# ---------------------------------------------------------------- env fallback


@pytest.mark.parametrize(
    "pull_fn,client_attr,svc_attr,svc_method,provider,_err",
    _PROVIDERS,
)
@pytest.mark.asyncio
async def test_env_fallback_when_no_db_credential(
    pull_fn: str,
    client_attr: str,
    svc_attr: str,
    svc_method: str,
    provider: str,
    _err: type[Exception],
) -> None:
    """No DB row (``NoCredentialError``) but env present → ``from_env`` builds
    the client; ``from_credential`` is never called."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())

    cred_svc = _cred_svc(payload=None, raises=job.NoCredentialError("none"))

    client = MagicMock()
    client.close = AsyncMock()

    svc = MagicMock()
    setattr(svc, svc_method, AsyncMock(return_value=_ingest_result()))
    # GA4 ingest additionally imports channel + page dimensions (ENG-478); the
    # other providers never call these, so mocking them unconditionally is
    # harmless.
    svc.import_recent_channels = AsyncMock(return_value=_ingest_result())
    svc.import_recent_pages = AsyncMock(return_value=_ingest_result())

    with patch.object(job, "async_session", _fake_session_cm(session)), patch.object(
        job, "IntegrationCredentialService", return_value=cred_svc
    ), patch.object(job, client_attr) as client_cls, patch.object(
        job, svc_attr, return_value=svc
    ):
        client_cls.from_env.return_value = client
        result = await getattr(job, pull_fn)({}, tenant_id)

    assert "skipped" not in result
    client_cls.from_env.assert_called_once()
    client_cls.from_credential.assert_not_called()


# ---------------------------------------------------------------- graceful skip


@pytest.mark.parametrize(
    "pull_fn,client_attr,svc_attr,svc_method,provider,err",
    _PROVIDERS,
)
@pytest.mark.asyncio
async def test_skip_when_no_db_credential_and_no_env(
    pull_fn: str,
    client_attr: str,
    svc_attr: str,
    svc_method: str,
    provider: str,
    err: type[Exception],
) -> None:
    """No DB row AND no env (``from_env`` raises NotConnected) → graceful skip,
    no ingest service constructed."""
    session = MagicMock()
    tenant_id = str(uuid.uuid4())

    cred_svc = _cred_svc(payload=None, raises=job.NoCredentialError("none"))

    with patch.object(job, "async_session", _fake_session_cm(session)), patch.object(
        job, "IntegrationCredentialService", return_value=cred_svc
    ), patch.object(job, client_attr) as client_cls, patch.object(
        job, svc_attr
    ) as svc_cls:
        client_cls.from_env.side_effect = err("missing env", details={})
        result = await getattr(job, pull_fn)({}, tenant_id)

    assert result == {"skipped": "no_credential"}
    svc_cls.assert_not_called()
