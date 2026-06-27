"""ENG-502 — a Meta Ads pull must not leak the access token into any log.

The Meta Graph client sends ``access_token`` in the query string (and follows
``paging.next`` cursor URLs with the token baked in). httpx logs an INFO
``HTTP Request: GET <full-url> ...`` line that would carry that token. This
test makes a real (transport-mocked) request whose URL holds a known token and
asserts the token value appears in NO emitted stdlib log record — message,
formatted message, or args — after ``configure_logging`` has run.
"""

from __future__ import annotations

import logging
from datetime import date

import httpx
import pytest
import respx

from packages.core.logging import configure_logging
from packages.integrations.meta_ads import MetaAdsClient

_TOKEN = "EAAsecretTOKEN0xDEADBEEF"
_ACCT = "938570599860690"
_INSIGHTS_URL = f"https://graph.facebook.com/v21.0/act_{_ACCT}/insights"


class _CapturingHandler(logging.Handler):
    """Capture every record emitted anywhere in the stdlib tree."""

    def __init__(self) -> None:
        super().__init__(level=logging.NOTSET)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _leaks_token(record: logging.LogRecord) -> bool:
    haystacks: list[str] = []
    try:
        haystacks.append(record.getMessage())
    except Exception:  # pragma: no cover — defensive
        haystacks.append(str(record.msg))
    haystacks.append(str(record.msg))
    if record.args:
        haystacks.append(str(record.args))
    return any(_TOKEN in h for h in haystacks)


@pytest.mark.asyncio
async def test_meta_request_does_not_log_access_token() -> None:
    # Apply the production logging config (this is the fix under test).
    configure_logging()

    handler = _CapturingHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    # Force the root threshold open so that, absent the per-logger clamp, an
    # httpx INFO line WOULD be captured — i.e. the test fails loudly if the fix
    # regresses, rather than passing because the root level hid the record.
    prev_root_level = root.level
    root.setLevel(logging.DEBUG)
    try:
        next_url = f"{_INSIGHTS_URL}?after=CURSOR2&access_token={_TOKEN}"
        async with respx.mock:
            respx.get(_INSIGHTS_URL).mock(
                side_effect=[
                    httpx.Response(
                        200,
                        json={
                            "data": [{"campaign_id": "1", "spend": "1.00"}],
                            "paging": {"next": next_url},
                        },
                    ),
                    httpx.Response(
                        200, json={"data": [{"campaign_id": "2", "spend": "2.00"}]}
                    ),
                ]
            )
            async with httpx.AsyncClient() as http:
                client = MetaAdsClient(
                    access_token=_TOKEN,  # noqa: S106 — test fixture
                    ad_account_ids=[_ACCT],
                    http=http,
                )
                rows = await client.get_campaign_insights(
                    _ACCT, start_date=date(2026, 6, 8), end_date=date(2026, 6, 14)
                )
        # Sanity: the request actually ran and paginated (so a leak was possible).
        assert [r["campaign_id"] for r in rows] == ["1", "2"]

        leaking = [r for r in handler.records if _leaks_token(r)]
        assert not leaking, (
            "access token leaked into log records: "
            + repr([(r.name, r.levelname, r.getMessage()) for r in leaking])
        )
    finally:
        root.removeHandler(handler)
        root.setLevel(prev_root_level)
