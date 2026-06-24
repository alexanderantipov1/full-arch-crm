"""Unit tests for the ENG-134 bounce poller worker.

The full provider call paths (Gmail / Graph HTTP) are exercised by
the integration suite; here we test the deterministic helpers and the
match-and-record path, mocking the repositories + services.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("INTERNAL_CREDENTIAL_TOKEN", "test-token-eng-134-bounce")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:5432/test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql+psycopg://test:test@127.0.0.1:5432/test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")

from packages.core.config import get_settings  # noqa: E402
from packages.core.types import TenantId  # noqa: E402
from packages.outreach.models import SendStatus  # noqa: E402

get_settings.cache_clear()


# --- Deterministic helpers --------------------------------------------------


def test_normalise_message_id_strips_brackets() -> None:
    """``<id@host>`` → ``id@host`` (the form stored on send.message_id)."""
    from apps.worker.jobs.bounce_poll import _normalise_message_id

    assert _normalise_message_id("<abc@x.example>") == "abc@x.example"
    # References chain — first id wins.
    assert _normalise_message_id("<first@x.example> <second@x.example>") == "first@x.example"
    # Already bare → returned as-is.
    assert _normalise_message_id("abc@x.example") == "abc@x.example"
    assert _normalise_message_id("") == ""


def test_gmail_headers_flattens_payload() -> None:
    """``payload.headers`` becomes a lowercased name → value map."""
    from apps.worker.jobs.bounce_poll import _gmail_headers

    metadata = {
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Delivery Failed"},
                {"name": "In-Reply-To", "value": "<abc@x.example>"},
                {"name": "X-Failed-Recipients", "value": "bad@x.example"},
            ]
        }
    }
    headers = _gmail_headers(metadata)
    assert headers["subject"] == "Delivery Failed"
    assert headers["in-reply-to"] == "<abc@x.example>"
    assert headers["x-failed-recipients"] == "bad@x.example"


def test_extract_failed_recipients_splits_csv() -> None:
    """``X-Failed-Recipients`` is comma-separated."""
    from apps.worker.jobs.bounce_poll import _extract_failed_recipients_gmail

    headers = {"x-failed-recipients": "a@x.example, b@x.example , c@x.example"}
    out = _extract_failed_recipients_gmail(headers)
    assert out == ["a@x.example", "b@x.example", "c@x.example"]


def test_graph_headers_flattens_internet_headers() -> None:
    """``internetMessageHeaders`` list flattens to a lower-cased map."""
    from apps.worker.jobs.bounce_poll import _graph_headers

    message = {
        "internetMessageHeaders": [
            {"name": "In-Reply-To", "value": "<original@x.example>"},
            {"name": "Subject", "value": "Undeliverable"},
        ]
    }
    headers = _graph_headers(message)
    assert headers["in-reply-to"] == "<original@x.example>"
    assert headers["subject"] == "Undeliverable"


def test_extract_in_reply_to_falls_back_to_references() -> None:
    """When ``In-Reply-To`` is absent, ``References`` is the fallback."""
    from apps.worker.jobs.bounce_poll import _extract_in_reply_to_gmail

    headers = {"references": "<original@x.example>"}
    assert _extract_in_reply_to_gmail(headers) == "<original@x.example>"


# --- Match + record path ----------------------------------------------------


@pytest.mark.asyncio
async def test_match_and_record_writes_bounce_audit_and_suppression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A matched In-Reply-To flips status, suppresses, and audits."""
    from apps.worker.jobs import bounce_poll
    from apps.worker.jobs.bounce_poll import _try_match_and_record

    tenant_id = TenantId(uuid.uuid4())
    credential_id = uuid.uuid4()
    send_id = uuid.uuid4()
    send = MagicMock()
    send.id = send_id
    send.tenant_id = tenant_id
    send.recipient_email = "patient@example.com"
    send.message_id = "abc@x.example"
    send.status = SendStatus.SENT.value
    send.error_text = None

    session = MagicMock()

    send_repo = MagicMock()
    send_repo.find_by_message_id = AsyncMock(return_value=send)
    send_repo.find_by_message_id_global = AsyncMock(return_value=None)
    suppression = MagicMock()
    suppression.add_suppression = AsyncMock()
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(bounce_poll, "SendRepository", lambda _s: send_repo)
    monkeypatch.setattr(bounce_poll, "SuppressionService", lambda _s: suppression)
    monkeypatch.setattr(bounce_poll, "AuditService", lambda _s: audit)

    principal = bounce_poll._system_principal(tenant_id)
    matched = await _try_match_and_record(
        session=session,
        tenant_id=tenant_id,
        credential_id=credential_id,
        principal=principal,
        in_reply_to="<abc@x.example>",
        failed_recipients=["patient@example.com"],
    )

    assert matched is True
    assert send.status == SendStatus.BOUNCED.value
    assert send.error_text == "bounce_hard"
    suppression.add_suppression.assert_awaited_once()
    add_args = suppression.add_suppression.await_args
    # tenant_id and email are positional; reason and audit context are
    # explicit keyword arguments.
    assert add_args.args[0] == tenant_id
    assert add_args.args[1] == "patient@example.com"
    assert add_args.kwargs["reason"] == "bounce_hard"
    assert add_args.kwargs["source_send_id"] == send_id
    audit.record.assert_awaited_once()
    audit_extra = audit.record.await_args.kwargs["extra"]
    assert audit_extra["send_id"] == str(send_id)
    assert audit_extra["match_strategy"] == "failed_recipients"
    # No raw recipient in audit extra.
    assert "recipient_email" not in audit_extra
    # Hash is present for correlation.
    assert "recipient_hash" in audit_extra


@pytest.mark.asyncio
async def test_match_no_match_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no send row matches the In-Reply-To, nothing is recorded."""
    from apps.worker.jobs import bounce_poll
    from apps.worker.jobs.bounce_poll import _try_match_and_record

    session = MagicMock()
    send_repo = MagicMock()
    send_repo.find_by_message_id = AsyncMock(return_value=None)
    send_repo.find_by_message_id_global = AsyncMock(return_value=None)
    suppression = MagicMock()
    suppression.add_suppression = AsyncMock()
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(bounce_poll, "SendRepository", lambda _s: send_repo)
    monkeypatch.setattr(bounce_poll, "SuppressionService", lambda _s: suppression)
    monkeypatch.setattr(bounce_poll, "AuditService", lambda _s: audit)

    tenant_id = TenantId(uuid.uuid4())
    principal = bounce_poll._system_principal(tenant_id)

    matched = await _try_match_and_record(
        session=session,
        tenant_id=tenant_id,
        credential_id=uuid.uuid4(),
        principal=principal,
        in_reply_to="<missing@x.example>",
        failed_recipients=[],
    )
    assert matched is False
    suppression.add_suppression.assert_not_awaited()
    audit.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_match_no_in_reply_to_returns_false() -> None:
    """An NDR without an In-Reply-To header is not matchable."""
    from apps.worker.jobs import bounce_poll
    from apps.worker.jobs.bounce_poll import _try_match_and_record

    session = MagicMock()
    tenant_id = TenantId(uuid.uuid4())
    principal = bounce_poll._system_principal(tenant_id)

    matched = await _try_match_and_record(
        session=session,
        tenant_id=tenant_id,
        credential_id=uuid.uuid4(),
        principal=principal,
        in_reply_to=None,
        failed_recipients=[],
    )
    assert matched is False


@pytest.mark.asyncio
async def test_match_idempotent_on_already_bounced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second match for an already-bounced send still adds suppression."""
    from apps.worker.jobs import bounce_poll
    from apps.worker.jobs.bounce_poll import _try_match_and_record

    tenant_id = TenantId(uuid.uuid4())
    send = MagicMock()
    send.id = uuid.uuid4()
    send.tenant_id = tenant_id
    send.recipient_email = "patient@example.com"
    send.message_id = "abc@x.example"
    send.status = SendStatus.BOUNCED.value  # already bounced
    send.error_text = "bounce_hard"

    send_repo = MagicMock()
    send_repo.find_by_message_id = AsyncMock(return_value=send)
    send_repo.find_by_message_id_global = AsyncMock(return_value=None)
    suppression = MagicMock()
    suppression.add_suppression = AsyncMock()
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(bounce_poll, "SendRepository", lambda _s: send_repo)
    monkeypatch.setattr(bounce_poll, "SuppressionService", lambda _s: suppression)
    monkeypatch.setattr(bounce_poll, "AuditService", lambda _s: audit)

    principal = bounce_poll._system_principal(tenant_id)
    matched = await _try_match_and_record(
        session=MagicMock(),
        tenant_id=tenant_id,
        credential_id=uuid.uuid4(),
        principal=principal,
        in_reply_to="<abc@x.example>",
        failed_recipients=[],
    )

    assert matched is True
    # Status stays bounced (no re-flip).
    assert send.status == SendStatus.BOUNCED.value
    # Suppression service is idempotent at the service layer; we still
    # call it (the service short-circuits if the row exists).
    suppression.add_suppression.assert_awaited_once()
    audit.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_match_uses_send_recipient_when_no_failed_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``X-Failed-Recipients`` is absent, we suppress the send's address."""
    from apps.worker.jobs import bounce_poll
    from apps.worker.jobs.bounce_poll import _try_match_and_record

    tenant_id = TenantId(uuid.uuid4())
    send = MagicMock()
    send.id = uuid.uuid4()
    send.tenant_id = tenant_id
    send.recipient_email = "patient@example.com"
    send.message_id = "abc@x.example"
    send.status = SendStatus.SENT.value
    send.error_text = None

    send_repo = MagicMock()
    send_repo.find_by_message_id = AsyncMock(return_value=send)
    send_repo.find_by_message_id_global = AsyncMock(return_value=None)
    suppression = MagicMock()
    suppression.add_suppression = AsyncMock()
    audit = MagicMock()
    audit.record = AsyncMock()

    monkeypatch.setattr(bounce_poll, "SendRepository", lambda _s: send_repo)
    monkeypatch.setattr(bounce_poll, "SuppressionService", lambda _s: suppression)
    monkeypatch.setattr(bounce_poll, "AuditService", lambda _s: audit)

    principal = bounce_poll._system_principal(tenant_id)
    await _try_match_and_record(
        session=MagicMock(),
        tenant_id=tenant_id,
        credential_id=uuid.uuid4(),
        principal=principal,
        in_reply_to="<abc@x.example>",
        failed_recipients=[],
    )
    add_args = suppression.add_suppression.await_args
    # Fell back to the send row's recipient.
    assert add_args.args[1] == "patient@example.com"
    audit_extra = audit.record.await_args.kwargs["extra"]
    assert audit_extra["match_strategy"] == "in_reply_to"
