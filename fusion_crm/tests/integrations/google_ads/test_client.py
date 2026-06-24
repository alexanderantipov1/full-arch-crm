"""Unit tests for the Google Ads REST client.

External calls (OAuth token + ``:search``) are stubbed via ``respx``. No real
Google traffic. Real-account smoke tests live with the manual sync runbook.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx

from packages.integrations.google_ads import (
    GoogleAdsApiError,
    GoogleAdsClient,
    GoogleAdsNotConnectedError,
    GoogleAdsToken,
)

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SEARCH_URL = (
    "https://googleads.googleapis.com/v23/customers/8185418623/googleAds:search"
)


def _client(
    http: httpx.AsyncClient, *, token: GoogleAdsToken | None = None
) -> GoogleAdsClient:
    return GoogleAdsClient(
        client_id="cid",
        client_secret="csec",  # noqa: S106 — fixture value
        developer_token="devtoken",  # noqa: S106 — fixture value
        refresh_token="refresh",  # noqa: S106 — fixture value
        login_customer_id="445-464-2405",
        customer_ids=["8185418623"],
        http=http,
        token=token,
    )


def _fresh_token() -> GoogleAdsToken:
    return GoogleAdsToken(
        access_token="cached",  # noqa: S106
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _row(campaign_id: str = "111", day: str = "2026-06-14") -> dict:
    return {
        "campaign": {
            "id": campaign_id,
            "name": "Implants - Search",
            "status": "ENABLED",
            "advertisingChannelType": "SEARCH",
        },
        "metrics": {
            "costMicros": "12340000",
            "impressions": "100",
            "clicks": "5",
            "conversions": 2.0,
        },
        "segments": {"date": day},
    }


@pytest.mark.asyncio
async def test_search_refreshes_token_then_returns_rows() -> None:
    async with respx.mock:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200, json={"access_token": "at", "expires_in": 3600}
            )
        )
        respx.post(_SEARCH_URL).mock(
            return_value=httpx.Response(200, json={"results": [_row()]})
        )
        async with httpx.AsyncClient() as http:
            client = _client(http)
            rows = await client.search_campaign_metrics(
                "8185418623", start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
            )
    assert len(rows) == 1
    assert rows[0]["campaign"]["id"] == "111"


@pytest.mark.asyncio
async def test_search_paginates_via_next_page_token() -> None:
    async with respx.mock:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200, json={"access_token": "at", "expires_in": 3600}
            )
        )
        respx.post(_SEARCH_URL).mock(
            side_effect=[
                httpx.Response(
                    200, json={"results": [_row("1")], "nextPageToken": "p2"}
                ),
                httpx.Response(200, json={"results": [_row("2")]}),
            ]
        )
        async with httpx.AsyncClient() as http:
            rows = await _client(http, token=_fresh_token()).search(
                "8185418623", "SELECT campaign.id FROM campaign"
            )
    assert [r["campaign"]["id"] for r in rows] == ["1", "2"]


@pytest.mark.asyncio
async def test_search_includes_login_customer_id_header_and_query() -> None:
    captured: dict = {}

    def _record(request: httpx.Request) -> httpx.Response:
        captured["login"] = request.headers.get("login-customer-id")
        captured["devtoken"] = request.headers.get("developer-token")
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"results": []})

    async with respx.mock:
        respx.post(_SEARCH_URL).mock(side_effect=_record)
        async with httpx.AsyncClient() as http:
            await _client(http, token=_fresh_token()).search_campaign_metrics(
                "8185418623", start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
            )
    assert captured["login"] == "4454642405"  # dashes stripped
    assert captured["devtoken"] == "devtoken"
    assert "2026-06-08" in captured["body"] and "2026-06-14" in captured["body"]


@pytest.mark.asyncio
async def test_401_then_refresh_then_retry_succeeds() -> None:
    async with respx.mock:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200, json={"access_token": "at2", "expires_in": 3600}
            )
        )
        respx.post(_SEARCH_URL).mock(
            side_effect=[
                httpx.Response(401, json={"error": "expired"}),
                httpx.Response(200, json={"results": [_row()]}),
            ]
        )
        async with httpx.AsyncClient() as http:
            rows = await _client(http, token=_fresh_token()).search(
                "8185418623", "SELECT campaign.id FROM campaign"
            )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_401_after_refresh_raises_not_connected() -> None:
    async with respx.mock:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200, json={"access_token": "at2", "expires_in": 3600}
            )
        )
        respx.post(_SEARCH_URL).mock(return_value=httpx.Response(401, json={}))
        async with httpx.AsyncClient() as http:
            with pytest.raises(GoogleAdsNotConnectedError):
                await _client(http, token=_fresh_token()).search(
                    "8185418623", "SELECT campaign.id FROM campaign"
                )


@pytest.mark.asyncio
async def test_5xx_raises_api_error() -> None:
    async with respx.mock:
        respx.post(_SEARCH_URL).mock(return_value=httpx.Response(500, text="boom"))
        async with httpx.AsyncClient() as http:
            with pytest.raises(GoogleAdsApiError):
                await _client(http, token=_fresh_token()).search(
                    "8185418623", "SELECT campaign.id FROM campaign"
                )


@pytest.mark.asyncio
async def test_token_endpoint_4xx_raises_not_connected() -> None:
    async with respx.mock:
        respx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(400, text="invalid_grant")
        )
        respx.post(_SEARCH_URL).mock(return_value=httpx.Response(200, json={}))
        async with httpx.AsyncClient() as http:
            with pytest.raises(GoogleAdsNotConnectedError):
                await _client(http).search(
                    "8185418623", "SELECT campaign.id FROM campaign"
                )


# ---------------------------------------------------------------- from_credential (ENG-490)


def _ga_payload(**overrides: object) -> dict:
    base = {
        "client_id": "cid",
        "client_secret": "csec",
        "developer_token": "devtoken",
        "refresh_token": "refresh",
        "login_customer_id": "445-464-2405",
        "customer_ids": ["818-541-8623"],
    }
    base.update(overrides)
    return base


def test_from_credential_builds_client_from_db_payload() -> None:
    """Happy path: a valid decrypted payload yields a client with the
    digit-stripped customer + login ids (mirrors the env factory)."""
    client = GoogleAdsClient.from_credential(_ga_payload())
    assert client.customer_ids == ["8185418623"]
    # login_customer_id is digit-stripped in __init__; reach the private
    # field since there is no public getter.
    assert client._login_customer_id == "4454642405"


def test_from_credential_rejects_empty_customer_ids() -> None:
    with pytest.raises(GoogleAdsNotConnectedError):
        GoogleAdsClient.from_credential(_ga_payload(customer_ids=[]))


def test_from_credential_rejects_missing_required_field() -> None:
    payload = _ga_payload()
    del payload["developer_token"]
    with pytest.raises(GoogleAdsNotConnectedError):
        GoogleAdsClient.from_credential(payload)


def test_from_credential_rejects_unexpected_key() -> None:
    """The payload schema is ``extra='forbid'`` — a stray key (e.g. a leaked
    env name) must be rejected at the boundary, not silently ignored."""
    with pytest.raises(GoogleAdsNotConnectedError):
        GoogleAdsClient.from_credential(_ga_payload(api_key="oops"))
