"""Unit tests for the CareStack password-grant client.

External calls are stubbed via ``respx``. No real CareStack traffic is
generated. Real-CareStack smoke tests live with the manual sync-script
runbook, not in CI.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from packages.integrations.carestack import (
    CareStackApiError,
    CareStackClient,
    CareStackNotConnectedError,
    CareStackTokens,
)

_IDP = "https://identity.example-cs.com"
_API = "https://api.example-cs.com"
_TOKEN_URL = f"{_IDP}/connect/token"


def _client(http: httpx.AsyncClient, *, tokens: CareStackTokens | None = None) -> CareStackClient:
    return CareStackClient(
        idp_base_url=_IDP,
        api_base_url=_API,
        client_id="cid",
        client_secret="csec",  # noqa: S106 — fixture value, not a real secret
        vendor_key="vendor",
        account_key="account",
        account_id="acct-1",
        http=http,
        tokens=tokens,
    )


def _live_tokens(access: str = "tok-1") -> CareStackTokens:
    return CareStackTokens(
        access_token=access,
        token_type="Bearer",  # noqa: S106 — OAuth scheme name, not a credential
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        account_id="acct-1",
    )


# ----------------------------------------------------------------- happy path


async def test_get_returns_json_when_token_cached() -> None:
    """A pre-cached, unexpired token short-circuits the password grant."""
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        rx.get(f"{_API}/api/v1.0/locations").mock(
            return_value=httpx.Response(200, json=[{"id": 1, "name": "FUSION-EDH"}]),
        )
        # Token endpoint NOT mocked — assert it isn't called when cache is hot.
        client = _client(http, tokens=_live_tokens())
        body = await client.get("api/v1.0/locations")

        assert isinstance(body, list)
        assert body[0]["id"] == 1


async def test_list_locations_asserts_array_shape() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(f"{_API}/api/v1.0/locations").mock(
            return_value=httpx.Response(200, json={"locations": []}),
        )
        client = _client(http, tokens=_live_tokens())
        with pytest.raises(CareStackApiError):
            await client.list_locations()


# ----------------------------------------------------------------- token issuance


async def test_get_issues_token_when_missing() -> None:
    """No cached token → POST password grant → use returned access_token."""
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        token_route = rx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "tok-fresh",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            ),
        )
        api_route = rx.get(f"{_API}/api/v1.0/locations").mock(
            return_value=httpx.Response(200, json=[]),
        )

        client = _client(http)
        await client.get("api/v1.0/locations")

        assert token_route.call_count == 1
        assert api_route.call_count == 1
        # And the bearer header carries the freshly issued token.
        request = api_route.calls[0].request
        assert request.headers["Authorization"] == "Bearer tok-fresh"


async def test_token_request_4xx_raises_not_connected() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(400, json={"error": "invalid_client"}),
        )
        client = _client(http)
        with pytest.raises(CareStackNotConnectedError):
            await client.get("api/v1.0/locations")


async def test_token_response_missing_access_token_raises() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"token_type": "Bearer", "expires_in": 60}),
        )
        client = _client(http)
        with pytest.raises(CareStackNotConnectedError):
            await client.get("api/v1.0/locations")


# ----------------------------------------------------------------- 401 handling


async def test_401_then_regrant_then_retry_returns_200() -> None:
    """First call → 401, re-grant succeeds, retry → 200."""
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        api_route = rx.get(f"{_API}/api/v1.0/locations").mock(
            side_effect=[
                httpx.Response(401, json={"error": "expired"}),
                httpx.Response(200, json=[{"id": 8027, "name": "FUSION-ROS"}]),
            ],
        )
        rx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "tok-new",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            ),
        )

        client = _client(http, tokens=_live_tokens(access="tok-stale"))
        body = await client.get("api/v1.0/locations")

        assert body[0]["id"] == 8027
        assert api_route.call_count == 2
        # Second call carries the new token.
        retry_request = api_route.calls[1].request
        assert retry_request.headers["Authorization"] == "Bearer tok-new"


async def test_401_after_regrant_raises_not_connected() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(f"{_API}/api/v1.0/locations").mock(
            return_value=httpx.Response(401, json={"error": "expired"}),
        )
        rx.post(_TOKEN_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "tok-new",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            ),
        )
        client = _client(http, tokens=_live_tokens())
        with pytest.raises(CareStackNotConnectedError):
            await client.get("api/v1.0/locations")


# ----------------------------------------------------------------- 5xx


async def test_500_raises_api_error() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(f"{_API}/api/v1.0/locations").mock(
            return_value=httpx.Response(500, text="boom"),
        )
        client = _client(http, tokens=_live_tokens())
        with pytest.raises(CareStackApiError):
            await client.get("api/v1.0/locations")


# --------------------------------- ENG-257: accounting transactions + payment summary


async def test_list_accounting_transactions_sends_modified_since_initially() -> None:
    """Initial call: modifiedSince + pageSize, no continueToken."""
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        route = rx.get(
            f"{_API}/api/v1.0/sync/accounting-transactions"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "accountingTransactions": [{"id": 1, "lastUpdatedOn": "X"}],
                    "continueToken": "next-page",
                },
            )
        )
        client = _client(http, tokens=_live_tokens())
        modified_since = datetime(2026, 5, 1, tzinfo=UTC)

        body = await client.list_accounting_transactions_modified_since(
            modified_since, page_size=50
        )

        assert body["continueToken"] == "next-page"
        request = route.calls[0].request
        assert "modifiedSince=2026-05-01T00%3A00%3A00Z" in str(request.url)
        assert "pageSize=50" in str(request.url)
        assert "continueToken" not in str(request.url)


async def test_list_accounting_transactions_forwards_continue_token() -> None:
    """Continuation call: continueToken + pageSize, no modifiedSince."""
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        route = rx.get(
            f"{_API}/api/v1.0/sync/accounting-transactions"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"accountingTransactions": [], "continueToken": None},
            )
        )
        client = _client(http, tokens=_live_tokens())

        await client.list_accounting_transactions_modified_since(
            datetime.now(UTC),
            page_size=25,
            continue_token="cursor-abc",
        )

        request = route.calls[0].request
        assert "continueToken=cursor-abc" in str(request.url)
        assert "modifiedSince" not in str(request.url)


async def test_list_accounting_transactions_rejects_non_object_body() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(
            f"{_API}/api/v1.0/sync/accounting-transactions"
        ).mock(return_value=httpx.Response(200, json=[]))
        client = _client(http, tokens=_live_tokens())
        with pytest.raises(CareStackApiError):
            await client.list_accounting_transactions_modified_since(
                datetime.now(UTC)
            )


async def test_get_payment_summary_uses_billing_path() -> None:
    """Per spec: GET /api/v1.0/billing/payment-summary/{patientId}."""
    payload = {
        "patientId": 9985,
        "appliedPatientPayment": 200.0,
        "appliedInsPayments": 100.0,
        "balanceDuePatient": 50.0,
        "balanceDueInsurance": 25.0,
        "patientUnappliedCredits": 10.0,
    }
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        rx.get(
            f"{_API}/api/v1.0/billing/payment-summary/9985"
        ).mock(return_value=httpx.Response(200, json=payload))
        client = _client(http, tokens=_live_tokens())

        body = await client.get_payment_summary(9985)

        assert body["balanceDuePatient"] == 50.0
        assert body["patientId"] == 9985


async def test_get_payment_summary_rejects_non_object_body() -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(
            f"{_API}/api/v1.0/billing/payment-summary/1"
        ).mock(return_value=httpx.Response(200, json=[]))
        client = _client(http, tokens=_live_tokens())
        with pytest.raises(CareStackApiError):
            await client.get_payment_summary(1)
