"""Tests for the open-tracking pixel route (ENG-134).

Coverage:

- Invalid token still returns the 1x1 pixel (privacy: never reveal
  whether tracking is active).
- Valid token + ``template.tracking_enabled = true`` flips
  ``send.status='opened'`` and ticks the campaign counter.
- Valid token + ``template.tracking_enabled = false`` (e.g.
  clinical category) is a no-op on state but still returns the pixel.
- A second open is idempotent — the status stays ``opened`` and the
  counter does not double-tick.

The route depends on a DB session, the outreach repositories, and
the audit service. We mock the session-bound collaborators so the
tests can run without a live Postgres — the privacy contract is
deterministic regardless of the DB layer.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

# A short, deterministic key so ``mint_open_token`` works without a
# real environment. Setting this before importing the tracking module
# is the simplest way to satisfy ``get_settings().internal_credential_token``.
os.environ.setdefault("INTERNAL_CREDENTIAL_TOKEN", "test-token-eng-134-open")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:5432/test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg://test:test@127.0.0.1:5432/test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")

from packages.core.config import get_settings  # noqa: E402
from packages.outreach.models import SendStatus  # noqa: E402
from packages.outreach.tracking_tokens import mint_open_token  # noqa: E402

# Force a fresh settings instance after env mutation — the lru_cache
# from a previous test module otherwise sticks.
get_settings.cache_clear()


_PIXEL_PREFIX = bytes([0x47, 0x49, 0x46, 0x38, 0x39, 0x61])  # GIF89a


def _make_send(
    *,
    send_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    status: str = SendStatus.SENT.value,
    campaign_id: uuid.UUID | None = None,
    person_uid: uuid.UUID | None = None,
) -> MagicMock:
    """Stand-in for an ORM ``Send`` row."""
    obj = MagicMock()
    obj.id = send_id or uuid.uuid4()
    obj.tenant_id = tenant_id or uuid.uuid4()
    obj.campaign_id = campaign_id
    obj.person_uid = person_uid
    obj.recipient_email = "patient@example.com"
    obj.status = status
    obj.mailbox_credential_id = uuid.uuid4()
    obj.sent_at = datetime.now(UTC)
    return obj


def _make_campaign(*, tenant_id: uuid.UUID, template_id: uuid.UUID) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.tenant_id = tenant_id
    obj.template_id = template_id
    obj.opened_count = 0
    return obj


def _make_template(*, tenant_id: uuid.UUID, tracking_enabled: bool) -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.tenant_id = tenant_id
    obj.tracking_enabled = tracking_enabled
    obj.category = "marketing" if tracking_enabled else "clinical"
    return obj


# --- Tests ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_pixel_returned_for_invalid_token() -> None:
    """An invalid token still returns a 200 + GIF — no information leaked."""
    from apps.api.routers.outreach_tracking import track_open

    db = MagicMock()
    response = await track_open(token="garbage", db=db)  # noqa: S106 — not a secret

    assert response.status_code == 200
    body = response.body
    assert isinstance(body, bytes)
    assert body.startswith(_PIXEL_PREFIX)
    assert response.headers["Cache-Control"].startswith("no-store")


@pytest.mark.asyncio
async def test_open_recorded_when_tracking_enabled(monkeypatch) -> None:
    """A valid token + marketing template flips the send status."""
    from apps.api.routers import outreach_tracking
    from apps.api.routers.outreach_tracking import track_open

    tenant_id = uuid.uuid4()
    send_id = uuid.uuid4()
    campaign = _make_campaign(tenant_id=tenant_id, template_id=uuid.uuid4())
    template = _make_template(tenant_id=tenant_id, tracking_enabled=True)
    campaign.template_id = template.id
    send = _make_send(send_id=send_id, tenant_id=tenant_id, campaign_id=campaign.id)

    send_repo = MagicMock()
    send_repo.get_global = AsyncMock(return_value=send)
    campaign_repo = MagicMock()
    campaign_repo.get_for_tenant = AsyncMock(return_value=campaign)
    template_repo = MagicMock()
    template_repo.get_for_tenant = AsyncMock(return_value=template)
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(outreach_tracking, "SendRepository", lambda _db: send_repo)
    monkeypatch.setattr(outreach_tracking, "CampaignRepository", lambda _db: campaign_repo)
    monkeypatch.setattr(outreach_tracking, "TemplateRepository", lambda _db: template_repo)
    monkeypatch.setattr(outreach_tracking, "AuditService", lambda _db: audit)

    token = mint_open_token(send_id=send_id)
    response = await track_open(token=token, db=MagicMock())

    assert response.status_code == 200
    assert bytes(response.body).startswith(_PIXEL_PREFIX)
    assert send.status == SendStatus.OPENED.value
    assert campaign.opened_count == 1
    audit.record.assert_awaited_once()
    call_kwargs = audit.record.await_args.kwargs
    assert call_kwargs["action"] == "outreach.email.opened"
    extra = call_kwargs["extra"]
    assert extra["send_id"] == str(send_id)
    assert extra["campaign_id"] == str(campaign.id)
    # No PII in audit extra — only ids.
    assert "recipient_email" not in extra


@pytest.mark.asyncio
async def test_open_ignored_when_tracking_disabled(monkeypatch) -> None:
    """A clinical-category template never records opens, even on a valid token."""
    from apps.api.routers import outreach_tracking
    from apps.api.routers.outreach_tracking import track_open

    tenant_id = uuid.uuid4()
    send_id = uuid.uuid4()
    template = _make_template(tenant_id=tenant_id, tracking_enabled=False)
    campaign = _make_campaign(tenant_id=tenant_id, template_id=template.id)
    send = _make_send(send_id=send_id, tenant_id=tenant_id, campaign_id=campaign.id)

    send_repo = MagicMock()
    send_repo.get_global = AsyncMock(return_value=send)
    campaign_repo = MagicMock()
    campaign_repo.get_for_tenant = AsyncMock(return_value=campaign)
    template_repo = MagicMock()
    template_repo.get_for_tenant = AsyncMock(return_value=template)
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(outreach_tracking, "SendRepository", lambda _db: send_repo)
    monkeypatch.setattr(outreach_tracking, "CampaignRepository", lambda _db: campaign_repo)
    monkeypatch.setattr(outreach_tracking, "TemplateRepository", lambda _db: template_repo)
    monkeypatch.setattr(outreach_tracking, "AuditService", lambda _db: audit)

    token = mint_open_token(send_id=send_id)
    response = await track_open(token=token, db=MagicMock())

    # Still returns the pixel — privacy contract.
    assert response.status_code == 200
    assert bytes(response.body).startswith(_PIXEL_PREFIX)
    # State unchanged because template.tracking_enabled is false.
    assert send.status == SendStatus.SENT.value
    assert campaign.opened_count == 0
    audit.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_double_open_is_idempotent(monkeypatch) -> None:
    """Calling the pixel route twice does not double-tick the counter."""
    from apps.api.routers import outreach_tracking
    from apps.api.routers.outreach_tracking import track_open

    tenant_id = uuid.uuid4()
    send_id = uuid.uuid4()
    template = _make_template(tenant_id=tenant_id, tracking_enabled=True)
    campaign = _make_campaign(tenant_id=tenant_id, template_id=template.id)
    send = _make_send(send_id=send_id, tenant_id=tenant_id, campaign_id=campaign.id)

    send_repo = MagicMock()
    send_repo.get_global = AsyncMock(return_value=send)
    campaign_repo = MagicMock()
    campaign_repo.get_for_tenant = AsyncMock(return_value=campaign)
    template_repo = MagicMock()
    template_repo.get_for_tenant = AsyncMock(return_value=template)
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(outreach_tracking, "SendRepository", lambda _db: send_repo)
    monkeypatch.setattr(outreach_tracking, "CampaignRepository", lambda _db: campaign_repo)
    monkeypatch.setattr(outreach_tracking, "TemplateRepository", lambda _db: template_repo)
    monkeypatch.setattr(outreach_tracking, "AuditService", lambda _db: audit)

    token = mint_open_token(send_id=send_id)
    await track_open(token=token, db=MagicMock())
    # Second call should see status='opened' and short-circuit.
    await track_open(token=token, db=MagicMock())

    assert send.status == SendStatus.OPENED.value
    assert campaign.opened_count == 1  # not 2
    # Only the first call wrote an audit row.
    assert audit.record.await_count == 1


@pytest.mark.asyncio
async def test_pixel_response_headers_are_no_store() -> None:
    """Every pixel response carries no-store + nosniff headers."""
    from apps.api.routers.outreach_tracking import _pixel_response

    response = _pixel_response()
    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.media_type == "image/gif"


@pytest.mark.asyncio
async def test_pixel_response_byte_length_constant() -> None:
    """The pixel is a fixed 43-byte transparent GIF89a."""
    from apps.api.routers.outreach_tracking import _TRANSPARENT_GIF

    assert len(_TRANSPARENT_GIF) == 43
    assert _TRANSPARENT_GIF.startswith(_PIXEL_PREFIX)
    # Final byte is the GIF terminator 0x3B.
    assert _TRANSPARENT_GIF.endswith(b"\x3b")
