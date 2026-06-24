"""Unit tests for the Search Console client. External calls stubbed via respx."""

from __future__ import annotations

import urllib.parse
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx

from packages.integrations.google_search_console import (
    GoogleSearchConsoleApiError,
    GoogleSearchConsoleClient,
    GoogleSearchConsoleNotConnectedError,
    GoogleToken,
)

_SITE = "sc-domain:fusiondentalimplants.com"
_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
_QUERY_URL = (
    "https://www.googleapis.com/webmasters/v3/sites/"
    f"{urllib.parse.quote(_SITE, safe='')}/searchAnalytics/query"
)


def _client(
    http: httpx.AsyncClient, *, site_url: str | None = None, token: GoogleToken | None = None
) -> GoogleSearchConsoleClient:
    return GoogleSearchConsoleClient(
        client_id="cid",
        client_secret="csec",  # noqa: S106 — fixture value
        refresh_token="refresh",  # noqa: S106 — fixture value
        site_url=site_url,
        http=http,
        token=token or _fresh_token(),
    )


def _fresh_token() -> GoogleToken:
    return GoogleToken(
        access_token="cached",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_resolve_site_url_prefers_sc_domain() -> None:
    async with respx.mock:
        respx.get(_SITES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "siteEntry": [
                        {"siteUrl": "https://www.fusiondentalimplants.com/", "permissionLevel": "siteOwner"},
                        {"siteUrl": _SITE, "permissionLevel": "siteOwner"},
                        {"siteUrl": "https://other.com/", "permissionLevel": "siteUnverifiedUser"},
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            resolved = await _client(http).resolve_site_url()
    assert resolved == _SITE


@pytest.mark.asyncio
async def test_resolve_site_url_uses_configured() -> None:
    async with httpx.AsyncClient() as http:
        # No HTTP call needed when site_url is configured.
        resolved = await _client(http, site_url=_SITE).resolve_site_url()
    assert resolved == _SITE


@pytest.mark.asyncio
async def test_resolve_site_url_raises_when_none_verified() -> None:
    async with respx.mock:
        respx.get(_SITES_URL).mock(
            return_value=httpx.Response(
                200,
                json={"siteEntry": [{"siteUrl": "https://x.com/", "permissionLevel": "siteUnverifiedUser"}]},
            )
        )
        async with httpx.AsyncClient() as http:
            with pytest.raises(GoogleSearchConsoleNotConnectedError):
                await _client(http).resolve_site_url()


@pytest.mark.asyncio
async def test_get_query_metrics_flattens_keys() -> None:
    async with respx.mock:
        respx.post(_QUERY_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "rows": [
                        {
                            "keys": ["2026-06-14", "dental implants roseville"],
                            "clicks": 5,
                            "impressions": 120,
                            "ctr": 0.0416,
                            "position": 3.2,
                        }
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            rows = await _client(http, site_url=_SITE).get_query_metrics(
                _SITE, start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
            )
    assert rows == [
        {
            "date": "2026-06-14",
            "query": "dental implants roseville",
            "clicks": 5,
            "impressions": 120,
            "ctr": 0.0416,
            "position": 3.2,
        }
    ]


@pytest.mark.asyncio
async def test_query_5xx_raises_api_error() -> None:
    async with respx.mock:
        respx.post(_QUERY_URL).mock(return_value=httpx.Response(503, text="busy"))
        async with httpx.AsyncClient() as http:
            with pytest.raises(GoogleSearchConsoleApiError):
                await _client(http, site_url=_SITE).get_query_metrics(
                    _SITE, start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
                )


# ---------------------------------------------------------------- from_credential (ENG-490)


def _gsc_payload(**overrides: object) -> dict:
    base = {
        "client_id": "cid",
        "client_secret": "csec",
        "refresh_token": "refresh",
        "site_url": "sc-domain:fusiondentalimplants.com",
    }
    base.update(overrides)
    return base


def test_from_credential_builds_client_from_db_payload() -> None:
    client = GoogleSearchConsoleClient.from_credential(_gsc_payload())
    assert client._resolved_site_url == "sc-domain:fusiondentalimplants.com"


def test_from_credential_allows_absent_site_url() -> None:
    """``site_url`` is optional — the client auto-discovers it later."""
    payload = _gsc_payload()
    del payload["site_url"]
    client = GoogleSearchConsoleClient.from_credential(payload)
    assert client._resolved_site_url is None


def test_from_credential_rejects_missing_refresh_token() -> None:
    payload = _gsc_payload()
    del payload["refresh_token"]
    with pytest.raises(GoogleSearchConsoleNotConnectedError):
        GoogleSearchConsoleClient.from_credential(payload)


def test_from_credential_rejects_unexpected_key() -> None:
    with pytest.raises(GoogleSearchConsoleNotConnectedError):
        GoogleSearchConsoleClient.from_credential(_gsc_payload(property_id="oops"))
