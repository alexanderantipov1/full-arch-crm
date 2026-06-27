"""Unit tests for the Meta Ads Graph client. External calls stubbed via respx."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from packages.integrations.meta_ads import (
    MetaAdsApiError,
    MetaAdsClient,
    MetaAdsNotConnectedError,
)
from packages.integrations.meta_ads.client import _parse_account_ids

_ACCT = "938570599860690"
_INSIGHTS_URL = f"https://graph.facebook.com/v21.0/act_{_ACCT}/insights"
_CAMPAIGNS_URL = f"https://graph.facebook.com/v21.0/act_{_ACCT}/campaigns"


def _client(http: httpx.AsyncClient) -> MetaAdsClient:
    return MetaAdsClient(
        access_token="EAAtest",  # noqa: S106 — fixture value
        ad_account_ids=[_ACCT],
        app_id="941342815084196",
        app_secret="appsecret",  # noqa: S106 — fixture value
        http=http,
    )


def _insight(cid: str = "111", day: str = "2026-06-14") -> dict:
    return {
        "campaign_id": cid,
        "campaign_name": "Implants - Roseville",
        "spend": "123.45",
        "impressions": "1000",
        "clicks": "30",
        "actions": [
            {"action_type": "lead", "value": "3"},
            {"action_type": "link_click", "value": "30"},
        ],
        "date_start": day,
        "date_stop": day,
    }


def test_parse_account_ids_strips_act_prefix() -> None:
    parsed = _parse_account_ids("act=938570599860690,act=1175596492910619")
    assert parsed == ["938570599860690", "1175596492910619"]


@pytest.mark.asyncio
async def test_get_campaign_insights_happy_path() -> None:
    async with respx.mock:
        respx.get(_INSIGHTS_URL).mock(
            return_value=httpx.Response(200, json={"data": [_insight()]})
        )
        async with httpx.AsyncClient() as http:
            rows = await _client(http).get_campaign_insights(
                _ACCT, start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
            )
    assert len(rows) == 1
    assert rows[0]["campaign_id"] == "111"


@pytest.mark.asyncio
async def test_insights_follow_paging_next() -> None:
    next_url = f"{_INSIGHTS_URL}?after=CURSOR2&access_token=EAAtest"
    async with respx.mock:
        respx.get(_INSIGHTS_URL).mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={"data": [_insight("1")], "paging": {"next": next_url}},
                ),
                httpx.Response(200, json={"data": [_insight("2")]}),
            ]
        )
        async with httpx.AsyncClient() as http:
            rows = await _client(http).get_campaign_insights(
                _ACCT, start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
            )
    assert [r["campaign_id"] for r in rows] == ["1", "2"]


@pytest.mark.asyncio
async def test_list_campaigns() -> None:
    async with respx.mock:
        respx.get(_CAMPAIGNS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "111", "name": "C1", "status": "ACTIVE", "objective": "OUTCOME_LEADS"}
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as http:
            campaigns = await _client(http).list_campaigns(_ACCT)
    assert campaigns[0]["objective"] == "OUTCOME_LEADS"


@pytest.mark.asyncio
async def test_auth_failure_raises_not_connected() -> None:
    async with respx.mock:
        respx.get(_INSIGHTS_URL).mock(
            return_value=httpx.Response(401, json={"error": {"message": "bad token"}})
        )
        async with httpx.AsyncClient() as http:
            with pytest.raises(MetaAdsNotConnectedError):
                await _client(http).get_campaign_insights(
                    _ACCT, start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
                )


@pytest.mark.asyncio
async def test_error_envelope_raises_api_error() -> None:
    async with respx.mock:
        respx.get(_INSIGHTS_URL).mock(
            return_value=httpx.Response(
                200, json={"error": {"message": "rate limit", "code": 17}}
            )
        )
        async with httpx.AsyncClient() as http:
            with pytest.raises(MetaAdsApiError):
                await _client(http).get_campaign_insights(
                    _ACCT, start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
                )


@pytest.mark.asyncio
async def test_5xx_raises_api_error() -> None:
    async with respx.mock:
        respx.get(_INSIGHTS_URL).mock(return_value=httpx.Response(500, text="boom"))
        async with httpx.AsyncClient() as http:
            with pytest.raises(MetaAdsApiError):
                await _client(http).get_campaign_insights(
                    _ACCT, start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
                )


# ---------------------------------------------------------------- from_credential (ENG-490)


def _meta_payload(**overrides: object) -> dict:
    base = {
        "access_token": "tok",
        "ad_account_ids": ["act_938570599860690"],
        "app_id": "appid",
        "app_secret": "appsecret",
    }
    base.update(overrides)
    return base


def test_from_credential_builds_client_from_db_payload() -> None:
    client = MetaAdsClient.from_credential(_meta_payload())
    # ``act_`` prefix is digit-stripped (matches the env factory).
    assert client.ad_account_ids == ["938570599860690"]


def test_from_credential_rejects_empty_account_ids() -> None:
    with pytest.raises(MetaAdsNotConnectedError):
        MetaAdsClient.from_credential(_meta_payload(ad_account_ids=[]))


def test_from_credential_rejects_missing_access_token() -> None:
    payload = _meta_payload()
    del payload["access_token"]
    with pytest.raises(MetaAdsNotConnectedError):
        MetaAdsClient.from_credential(payload)


def test_from_credential_rejects_unexpected_key() -> None:
    with pytest.raises(MetaAdsNotConnectedError):
        MetaAdsClient.from_credential(_meta_payload(refresh_token="oops"))
