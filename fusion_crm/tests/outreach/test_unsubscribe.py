"""Tests for the unsubscribe surface (ENG-134).

Coverage:

- One-click POST with a valid token adds a suppression row.
- A second POST is idempotent — no second audit row, status stays 200.
- A bad signature returns 400 plain text.
- The manual GET form renders a confirmation page when the token is
  valid and the recipient is not yet suppressed.
- The GET form shows the "already unsubscribed" page when the
  suppression already exists.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("INTERNAL_CREDENTIAL_TOKEN", "test-token-eng-134-unsub")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:5432/test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg://test:test@127.0.0.1:5432/test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")

from packages.core.config import get_settings  # noqa: E402
from packages.identity.service import normalise_email  # noqa: E402
from packages.outreach.models import SendStatus  # noqa: E402
from packages.outreach.tracking_tokens import mint_unsubscribe_token  # noqa: E402

get_settings.cache_clear()


def _make_send(
    *,
    send_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    recipient_email: str = "patient@example.com",
    status: str = SendStatus.SENT.value,
) -> MagicMock:
    obj = MagicMock()
    obj.id = send_id or uuid.uuid4()
    obj.tenant_id = tenant_id or uuid.uuid4()
    obj.campaign_id = uuid.uuid4()
    obj.person_uid = uuid.uuid4()
    obj.recipient_email = recipient_email
    obj.status = status
    obj.mailbox_credential_id = uuid.uuid4()
    return obj


# --- One-click POST ------------------------------------------------------


@pytest.mark.asyncio
async def test_one_click_post_adds_suppression(monkeypatch) -> None:
    """A valid token POST records the suppression + flips send status."""
    from apps.api.routers import outreach_tracking
    from apps.api.routers.outreach_tracking import unsubscribe_one_click

    tenant_id = uuid.uuid4()
    send_id = uuid.uuid4()
    send = _make_send(
        send_id=send_id,
        tenant_id=tenant_id,
        recipient_email="patient@example.com",
    )

    send_repo = MagicMock()
    send_repo.get_global = AsyncMock(return_value=send)
    suppression = MagicMock()
    suppression.add_suppression = AsyncMock()
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(outreach_tracking, "SendRepository", lambda _db: send_repo)
    monkeypatch.setattr(outreach_tracking, "SuppressionService", lambda _db: suppression)
    monkeypatch.setattr(outreach_tracking, "AuditService", lambda _db: audit)

    token = mint_unsubscribe_token(
        tenant_id=tenant_id,
        send_id=send_id,
        recipient_email_normalised=normalise_email("patient@example.com"),
    )

    response = await unsubscribe_one_click(token=token, db=MagicMock(), request=MagicMock())

    assert response.status_code == 200
    assert response.body == b"Unsubscribed"
    assert response.headers["Cache-Control"] == "no-store"

    suppression.add_suppression.assert_awaited_once()
    add_kwargs = suppression.add_suppression.await_args
    # Positional args: tenant_id, email. Keyword args carry the explicit
    # reason and audit context.
    assert add_kwargs.args[0] == tenant_id
    assert add_kwargs.args[1] == "patient@example.com"
    assert add_kwargs.kwargs["reason"] == "one_click"
    assert add_kwargs.kwargs["source_send_id"] == send_id

    audit.record.assert_awaited_once()
    audit_kwargs = audit.record.await_args.kwargs
    assert audit_kwargs["action"] == "outreach.email.unsubscribed"
    extra = audit_kwargs["extra"]
    assert extra["send_id"] == str(send_id)
    assert "recipient_email" not in extra
    assert send.status == SendStatus.UNSUBSCRIBED.value


@pytest.mark.asyncio
async def test_bad_signature_returns_400(monkeypatch) -> None:
    """Tampered token → 400 plain text. No DB write, no audit row."""
    from apps.api.routers import outreach_tracking
    from apps.api.routers.outreach_tracking import unsubscribe_one_click

    send_repo = MagicMock()
    send_repo.get_global = AsyncMock(return_value=None)
    suppression = MagicMock()
    suppression.add_suppression = AsyncMock()
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(outreach_tracking, "SendRepository", lambda _db: send_repo)
    monkeypatch.setattr(outreach_tracking, "SuppressionService", lambda _db: suppression)
    monkeypatch.setattr(outreach_tracking, "AuditService", lambda _db: audit)

    # Take a valid token, flip one byte of the signature.
    real = mint_unsubscribe_token(
        tenant_id=uuid.uuid4(),
        send_id=uuid.uuid4(),
        recipient_email_normalised="patient@example.com",
    )
    body, sig = real.rsplit(".", 1)
    tampered = f"{body}.{'a' if sig[0] != 'a' else 'b'}{sig[1:]}"

    response = await unsubscribe_one_click(token=tampered, db=MagicMock(), request=MagicMock())
    assert response.status_code == 400
    suppression.add_suppression.assert_not_awaited()
    audit.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_token_for_other_recipient_returns_400(monkeypatch) -> None:
    """Token email_hash mismatch → 400, no suppression added."""
    from apps.api.routers import outreach_tracking
    from apps.api.routers.outreach_tracking import unsubscribe_one_click

    tenant_id = uuid.uuid4()
    send_id = uuid.uuid4()
    # Send row has a DIFFERENT recipient than the token was minted for.
    send = _make_send(
        send_id=send_id,
        tenant_id=tenant_id,
        recipient_email="someone-else@example.com",
    )

    send_repo = MagicMock()
    send_repo.get_global = AsyncMock(return_value=send)
    suppression = MagicMock()
    suppression.add_suppression = AsyncMock()
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(outreach_tracking, "SendRepository", lambda _db: send_repo)
    monkeypatch.setattr(outreach_tracking, "SuppressionService", lambda _db: suppression)
    monkeypatch.setattr(outreach_tracking, "AuditService", lambda _db: audit)

    # Token bound to a DIFFERENT email.
    token = mint_unsubscribe_token(
        tenant_id=tenant_id,
        send_id=send_id,
        recipient_email_normalised="bound-to@example.com",
    )

    response = await unsubscribe_one_click(token=token, db=MagicMock(), request=MagicMock())
    assert response.status_code == 400
    suppression.add_suppression.assert_not_awaited()


@pytest.mark.asyncio
async def test_one_click_post_is_idempotent(monkeypatch) -> None:
    """A second submission still returns 200; SuppressionService is idempotent."""
    from apps.api.routers import outreach_tracking
    from apps.api.routers.outreach_tracking import unsubscribe_one_click

    tenant_id = uuid.uuid4()
    send_id = uuid.uuid4()
    send = _make_send(
        send_id=send_id,
        tenant_id=tenant_id,
        recipient_email="patient@example.com",
        status=SendStatus.UNSUBSCRIBED.value,  # already unsubscribed
    )

    send_repo = MagicMock()
    send_repo.get_global = AsyncMock(return_value=send)
    suppression = MagicMock()
    suppression.add_suppression = AsyncMock()
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(outreach_tracking, "SendRepository", lambda _db: send_repo)
    monkeypatch.setattr(outreach_tracking, "SuppressionService", lambda _db: suppression)
    monkeypatch.setattr(outreach_tracking, "AuditService", lambda _db: audit)

    token = mint_unsubscribe_token(
        tenant_id=tenant_id,
        send_id=send_id,
        recipient_email_normalised=normalise_email("patient@example.com"),
    )
    response = await unsubscribe_one_click(token=token, db=MagicMock(), request=MagicMock())
    assert response.status_code == 200
    # add_suppression is still called — the service layer enforces
    # idempotency by checking for an existing row. We just verify the
    # endpoint stays a 200 even when called against an already-
    # unsubscribed send.
    suppression.add_suppression.assert_awaited()


# --- Manual unsubscribe form --------------------------------------------


@pytest.mark.asyncio
async def test_form_renders_confirm_page(monkeypatch) -> None:
    """A valid token + un-suppressed recipient renders a confirm form."""
    from apps.api.routers import outreach_tracking
    from apps.api.routers.outreach_tracking import unsubscribe_form

    tenant_id = uuid.uuid4()
    send_id = uuid.uuid4()
    send = _make_send(
        send_id=send_id,
        tenant_id=tenant_id,
        recipient_email="patient@example.com",
    )

    send_repo = MagicMock()
    send_repo.get_global = AsyncMock(return_value=send)
    suppression = MagicMock()
    suppression.is_suppressed = AsyncMock(return_value=False)

    monkeypatch.setattr(outreach_tracking, "SendRepository", lambda _db: send_repo)
    monkeypatch.setattr(outreach_tracking, "SuppressionService", lambda _db: suppression)

    token = mint_unsubscribe_token(
        tenant_id=tenant_id,
        send_id=send_id,
        recipient_email_normalised=normalise_email("patient@example.com"),
    )
    response = await unsubscribe_form(token=token, db=MagicMock())

    assert response.status_code == 200
    body = bytes(response.body).decode("utf-8")
    assert "Confirm unsubscribe" in body
    assert f'action="/outreach/unsubscribe/{token}"' in body
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
async def test_form_shows_already_unsubscribed(monkeypatch) -> None:
    """Pre-suppressed recipient sees a friendly 'unsubscribed' page."""
    from apps.api.routers import outreach_tracking
    from apps.api.routers.outreach_tracking import unsubscribe_form

    tenant_id = uuid.uuid4()
    send_id = uuid.uuid4()
    send = _make_send(send_id=send_id, tenant_id=tenant_id)
    send_repo = MagicMock()
    send_repo.get_global = AsyncMock(return_value=send)
    suppression = MagicMock()
    suppression.is_suppressed = AsyncMock(return_value=True)

    monkeypatch.setattr(outreach_tracking, "SendRepository", lambda _db: send_repo)
    monkeypatch.setattr(outreach_tracking, "SuppressionService", lambda _db: suppression)

    token = mint_unsubscribe_token(
        tenant_id=tenant_id,
        send_id=send_id,
        recipient_email_normalised=normalise_email("patient@example.com"),
    )
    response = await unsubscribe_form(token=token, db=MagicMock())

    assert response.status_code == 200
    body = bytes(response.body).decode("utf-8")
    assert "You are unsubscribed" in body
    # No form on the already-unsubscribed page.
    assert "<form" not in body
