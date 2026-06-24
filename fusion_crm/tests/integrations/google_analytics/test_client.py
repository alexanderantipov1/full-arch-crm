"""Unit tests for the GA4 Data API client. External calls stubbed via respx."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx

from packages.integrations.google_analytics import (
    GoogleAnalyticsApiError,
    GoogleAnalyticsClient,
    GoogleAnalyticsNotConnectedError,
    GoogleToken,
)

_PROP = "510182665"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REPORT_URL = (
    f"https://analyticsdata.googleapis.com/v1beta/properties/{_PROP}:runReport"
)


def _client(http: httpx.AsyncClient, *, token: GoogleToken | None = None) -> GoogleAnalyticsClient:
    return GoogleAnalyticsClient(
        client_id="cid",
        client_secret="csec",  # noqa: S106 — fixture value
        refresh_token="refresh",  # noqa: S106 — fixture value
        property_id=_PROP,
        http=http,
        token=token,
    )


def _fresh_token() -> GoogleToken:
    return GoogleToken(
        access_token="cached",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _report() -> dict:
    return {
        "dimensionHeaders": [{"name": "date"}],
        "metricHeaders": [
            {"name": "sessions", "type": "TYPE_INTEGER"},
            {"name": "totalUsers", "type": "TYPE_INTEGER"},
            {"name": "conversions", "type": "TYPE_FLOAT"},
        ],
        "rows": [
            {
                "dimensionValues": [{"value": "20260614"}],
                "metricValues": [{"value": "123"}, {"value": "100"}, {"value": "4"}],
            },
            {
                "dimensionValues": [{"value": "20260615"}],
                "metricValues": [{"value": "150"}, {"value": "120"}, {"value": "5"}],
            },
        ],
    }


@pytest.mark.asyncio
async def test_get_daily_metrics_refreshes_and_flattens() -> None:
    async with respx.mock:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "at", "expires_in": 3600})
        )
        respx.post(_REPORT_URL).mock(return_value=httpx.Response(200, json=_report()))
        async with httpx.AsyncClient() as http:
            rows = await _client(http).get_daily_metrics(
                start_date=date(2026, 6, 14), end_date=date(2026, 6, 15)
            )
    assert len(rows) == 2
    assert rows[0] == {"date": "20260614", "sessions": "123", "totalUsers": "100", "conversions": "4"}
    assert rows[1]["date"] == "20260615"


@pytest.mark.asyncio
async def test_401_then_refresh_then_retry() -> None:
    async with respx.mock:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "at2", "expires_in": 3600})
        )
        respx.post(_REPORT_URL).mock(
            side_effect=[
                httpx.Response(401, json={}),
                httpx.Response(200, json=_report()),
            ]
        )
        async with httpx.AsyncClient() as http:
            rows = await _client(http, token=_fresh_token()).get_daily_metrics(
                start_date=date(2026, 6, 14), end_date=date(2026, 6, 15)
            )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_401_after_refresh_raises_not_connected() -> None:
    async with respx.mock:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "at2", "expires_in": 3600})
        )
        respx.post(_REPORT_URL).mock(return_value=httpx.Response(401, json={}))
        async with httpx.AsyncClient() as http:
            with pytest.raises(GoogleAnalyticsNotConnectedError):
                await _client(http, token=_fresh_token()).get_daily_metrics(
                    start_date=date(2026, 6, 14), end_date=date(2026, 6, 15)
                )


@pytest.mark.asyncio
async def test_5xx_raises_api_error() -> None:
    async with respx.mock:
        respx.post(_REPORT_URL).mock(return_value=httpx.Response(500, text="boom"))
        async with httpx.AsyncClient() as http:
            with pytest.raises(GoogleAnalyticsApiError):
                await _client(http, token=_fresh_token()).get_daily_metrics(
                    start_date=date(2026, 6, 14), end_date=date(2026, 6, 15)
                )


# ---------------------------------------------------------------- from_credential (ENG-490)


def _ga4_payload(**overrides: object) -> dict:
    base = {
        "client_id": "cid",
        "client_secret": "csec",
        "refresh_token": "refresh",
        "property_id": "510182665",
    }
    base.update(overrides)
    return base


def test_from_credential_builds_client_from_db_payload() -> None:
    client = GoogleAnalyticsClient.from_credential(_ga4_payload())
    assert client.property_id == "510182665"


def test_from_credential_rejects_missing_property_id() -> None:
    payload = _ga4_payload()
    del payload["property_id"]
    with pytest.raises(GoogleAnalyticsNotConnectedError):
        GoogleAnalyticsClient.from_credential(payload)


def test_from_credential_rejects_unexpected_key() -> None:
    with pytest.raises(GoogleAnalyticsNotConnectedError):
        GoogleAnalyticsClient.from_credential(_ga4_payload(developer_token="oops"))
