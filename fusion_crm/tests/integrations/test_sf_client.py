"""Unit tests for ``SfClient`` and the dev-token reader.

External calls are stubbed via ``respx``. No real Salesforce traffic is
generated. The smoke test against prod SF lives in the slice-1 smoke sub-issue
(ENG-105) and runs separately by hand.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import respx
from pydantic import SecretStr

from packages.integrations.salesforce import SfClient, SfNotConnectedError, SfTokens
from packages.integrations.salesforce import client as client_mod
from packages.integrations.salesforce.client import API_VERSION
from packages.integrations.salesforce.exceptions import SfApiError
from packages.integrations.salesforce.tokens import read_dev_tokens

_INSTANCE = "https://example.my.salesforce.com"


def _tokens(access: str = "tok-1", refresh: str | None = "rt-1") -> SfTokens:
    return SfTokens(access_token=access, instance_url=_INSTANCE, refresh_token=refresh)


@pytest.fixture
def soql_url() -> str:
    return f"{_INSTANCE}/services/data/{API_VERSION}/query"


@pytest.fixture
def refresh_url() -> str:
    return f"{_INSTANCE}/services/oauth2/token"


@pytest.fixture
def sf_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub ``get_settings`` so the refresh path sees SF client_id/secret.

    This avoids depending on `.env` loading during the test run — the real
    ``Settings`` requires SECRET_KEY / DATABASE_URL / REDIS_URL which we
    don't want to fake for a unit test of the SF client.
    """
    fake_settings = SimpleNamespace(
        salesforce_client_id="cid",
        salesforce_client_secret=SecretStr("csecret"),
    )
    monkeypatch.setattr(client_mod, "get_settings", lambda: fake_settings)


@pytest.fixture
def no_disk_persist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop ``persist_dev_tokens`` from touching disk during refresh tests."""
    monkeypatch.setattr(client_mod, "persist_dev_tokens", lambda *a, **kw: None)


async def test_soql_200_returns_records(soql_url: str) -> None:
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        rx.get(soql_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "totalSize": 2,
                    "done": True,
                    "records": [{"Id": "00Q1"}, {"Id": "00Q2"}],
                },
            )
        )
        client = SfClient(tokens=_tokens(), http=http)
        result = await client.soql("SELECT Id FROM Lead")
        assert result["totalSize"] == 2
        assert result["records"][0]["Id"] == "00Q1"


async def test_soql_401_then_refresh_then_retry(
    soql_url: str,
    refresh_url: str,
    sf_creds: None,
    no_disk_persist: None,
) -> None:
    """First SOQL → 401, refresh succeeds, retry SOQL → 200."""
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        soql_route = rx.get(soql_url).mock(
            side_effect=[
                httpx.Response(401, json={"error": "expired"}),
                httpx.Response(
                    200,
                    json={"totalSize": 1, "done": True, "records": [{"Id": "00Q9"}]},
                ),
            ]
        )
        rx.post(refresh_url).mock(
            return_value=httpx.Response(
                200,
                json={"access_token": "tok-2", "instance_url": _INSTANCE},
            )
        )
        client = SfClient(tokens=_tokens(), http=http)
        result = await client.soql("SELECT Id FROM Lead")
        assert result["records"][0]["Id"] == "00Q9"
        assert soql_route.call_count == 2


async def test_refresh_access_token_proactively_persists(
    refresh_url: str,
    sf_creds: None,
) -> None:
    persisted: list[SfTokens] = []

    async def _persist(tokens: SfTokens) -> None:
        persisted.append(tokens)

    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        rx.post(refresh_url).mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "tok-2",
                    "instance_url": _INSTANCE,
                    "issued_at": "1710000000000",
                },
            )
        )
        client = SfClient(tokens=_tokens(), http=http, on_refresh=_persist)
        await client.refresh_access_token()

    assert persisted[0].access_token == "tok-2"
    assert persisted[0].refresh_token == "rt-1"
    assert persisted[0].issued_at == "1710000000000"


async def test_soql_401_refresh_also_fails_raises(
    soql_url: str,
    refresh_url: str,
    sf_creds: None,
) -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(soql_url).mock(return_value=httpx.Response(401))
        rx.post(refresh_url).mock(
            return_value=httpx.Response(400, json={"error": "invalid_grant"})
        )
        client = SfClient(tokens=_tokens(), http=http)
        with pytest.raises(SfNotConnectedError):
            await client.soql("SELECT Id FROM Lead")


async def test_soql_401_no_refresh_token_raises(soql_url: str) -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(soql_url).mock(return_value=httpx.Response(401))
        client = SfClient(tokens=_tokens(refresh=None), http=http)
        with pytest.raises(SfNotConnectedError):
            await client.soql("SELECT Id FROM Lead")


async def test_soql_500_raises_api_error(soql_url: str) -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(soql_url).mock(return_value=httpx.Response(500, text="boom"))
        client = SfClient(tokens=_tokens(), http=http)
        with pytest.raises(SfApiError):
            await client.soql("SELECT Id FROM Lead")


# -----------------------------------------------------------------------------
# Refresh failure error envelope — sanitized + user-actionable.
# -----------------------------------------------------------------------------
# These guard the user-facing error message + `details` shape returned
# when Salesforce refuses a refresh. The bug they catch: the prior
# implementation surfaced "salesforce token refresh failed: 400" raw
# to the operator UI, with no Salesforce JSON parsed and no reconnect
# hint. They also assert that the refresh `data` body (which carries
# the refresh_token + client_secret) NEVER appears in the exception
# message or details.


async def test_refresh_400_invalid_grant_returns_reconnect_message(
    soql_url: str,
    refresh_url: str,
    sf_creds: None,
) -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(soql_url).mock(return_value=httpx.Response(401))
        rx.post(refresh_url).mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": "invalid_grant",
                    "error_description": "expired access/refresh token",
                },
            )
        )
        client = SfClient(tokens=_tokens(refresh="rt-doomed"), http=http)
        with pytest.raises(SfNotConnectedError) as ei:
            await client.soql("SELECT Id FROM Lead")
    assert "reconnect Salesforce in Settings → Integrations" in ei.value.message.lower() \
        or "reconnect" in ei.value.message.lower()
    assert "expired" in ei.value.message.lower()
    assert ei.value.details["sf_error"] == "invalid_grant"
    assert ei.value.details["action"] == "reconnect"
    assert ei.value.details["status"] == 400


async def test_refresh_400_other_error_returns_generic_message(
    soql_url: str,
    refresh_url: str,
    sf_creds: None,
) -> None:
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(soql_url).mock(return_value=httpx.Response(401))
        rx.post(refresh_url).mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": "invalid_client_id",
                    "error_description": "client identifier invalid",
                },
            )
        )
        client = SfClient(tokens=_tokens(), http=http)
        with pytest.raises(SfNotConnectedError) as ei:
            await client.soql("SELECT Id FROM Lead")
    assert "reconnect salesforce" in ei.value.message.lower()
    assert ei.value.details["sf_error"] == "invalid_client_id"
    assert ei.value.details.get("action") != "reconnect"  # not invalid_grant


async def test_refresh_failure_never_leaks_token_or_secret(
    soql_url: str,
    refresh_url: str,
    sf_creds: None,
) -> None:
    """The refresh `data` payload (refresh_token + client_secret) MUST
    never appear in the surfaced exception message or details. The
    secret values are stubbed via ``sf_creds`` fixture as
    ``sf-client-id`` / ``sf-client-secret``; the refresh token here is
    ``super-secret-refresh-1234``. None of those strings may leak."""
    async with httpx.AsyncClient() as http, respx.mock() as rx:
        rx.get(soql_url).mock(return_value=httpx.Response(401))
        rx.post(refresh_url).mock(
            return_value=httpx.Response(400, json={"error": "invalid_grant"})
        )
        client = SfClient(
            tokens=_tokens(refresh="super-secret-refresh-1234"), http=http
        )
        with pytest.raises(SfNotConnectedError) as ei:
            await client.soql("SELECT Id FROM Lead")
    serialized = f"{ei.value.message} {ei.value.details}"
    assert "super-secret-refresh-1234" not in serialized
    assert "sf-client-secret" not in serialized
    assert "sf-client-id" not in serialized


def test_read_dev_tokens_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SfNotConnectedError):
        read_dev_tokens(tmp_path / "nope.json")


def test_read_dev_tokens_malformed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not-json", encoding="utf-8")
    with pytest.raises(SfNotConnectedError):
        read_dev_tokens(bad)


def test_read_dev_tokens_missing_required_fields(tmp_path: Path) -> None:
    f = tmp_path / "incomplete.json"
    f.write_text(json.dumps({"access_token": "x"}), encoding="utf-8")
    with pytest.raises(SfNotConnectedError):
        read_dev_tokens(f)


def test_read_dev_tokens_valid(tmp_path: Path) -> None:
    f = tmp_path / "good.json"
    f.write_text(
        json.dumps({"access_token": "x", "instance_url": "https://example.my.salesforce.com"}),
        encoding="utf-8",
    )
    tokens = read_dev_tokens(f)
    assert tokens.access_token == "x"  # noqa: S105 — fixture value, not a real secret
    assert tokens.instance_url == "https://example.my.salesforce.com"
    assert tokens.refresh_token is None


# --- describe + Tooling field listing (ENG-427) ---


def _describe_url() -> str:
    return f"{_INSTANCE}/services/data/{API_VERSION}/sobjects/Lead/describe"


def _tooling_url() -> str:
    return f"{_INSTANCE}/services/data/{API_VERSION}/tooling/query"


async def test_describe_returns_field_metadata() -> None:
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        rx.get(_describe_url()).mock(
            return_value=httpx.Response(
                200,
                json={"name": "Lead", "fields": [{"name": "Id", "type": "id"}]},
            )
        )
        client = SfClient(tokens=_tokens(), http=http)
        described = await client.describe("Lead")
        assert described["fields"][0]["name"] == "Id"


async def test_describe_tooling_fields_follows_pagination() -> None:
    next_path = f"/services/data/{API_VERSION}/tooling/query/01g000"
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        rx.get(_tooling_url()).mock(
            return_value=httpx.Response(
                200,
                json={
                    "records": [{"QualifiedApiName": "Id", "DataType": "Id"}],
                    "done": False,
                    "nextRecordsUrl": next_path,
                },
            )
        )
        rx.get(f"{_INSTANCE}{next_path}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "records": [
                        {"QualifiedApiName": "SSN__c", "DataType": "Text(9)"}
                    ],
                    "done": True,
                },
            )
        )
        client = SfClient(tokens=_tokens(), http=http)
        fields = await client.describe_tooling_fields("Lead")
        names = {f["QualifiedApiName"] for f in fields}
        assert names == {"Id", "SSN__c"}


async def test_describe_401_refreshes_then_retries(
    sf_creds: None, no_disk_persist: None
) -> None:
    """describe shares the refresh-once-on-401 path via _get_json."""
    refresh = f"{_INSTANCE}/services/oauth2/token"
    async with httpx.AsyncClient() as http, respx.mock(assert_all_called=True) as rx:
        rx.get(_describe_url()).mock(
            side_effect=[
                httpx.Response(401, json={"error": "expired"}),
                httpx.Response(200, json={"name": "Lead", "fields": []}),
            ]
        )
        rx.post(refresh).mock(
            return_value=httpx.Response(
                200, json={"access_token": "tok-2", "instance_url": _INSTANCE}
            )
        )
        client = SfClient(tokens=_tokens(), http=http)
        described = await client.describe("Lead")
        assert described["name"] == "Lead"
