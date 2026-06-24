"""HTTP-level tests for the signed Mattermost inbound routes (ENG-438).

The routes are PUBLIC (no principal). The Mattermost shared token is the
auth: it is constant-time-compared against the tenant's stored
``mattermost`` / ``webhook_secret`` credential, and the match yields the
tenant. These tests assert fail-closed behaviour on missing / wrong tokens
(401, nothing captured) and a verbatim capture on the correct token.

No real DB: ``get_db`` is overridden with a MagicMock session,
``IntegrationCredentialService.list_active_payloads_across_tenants`` is
patched to return the seeded tenant token, and ``IngestService.capture`` is
patched to record what (if anything) was captured.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db
from apps.api.middleware import RequestContextMiddleware, platform_error_handler
from apps.api.routers import chat_inbound as chat_inbound_router
from packages.core.exceptions import PlatformError
from packages.core.types import TenantId


def _build_app(db_session: Any) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(PlatformError, platform_error_handler)  # type: ignore[arg-type]
    app.include_router(chat_inbound_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return app


def _patch_credentials(monkeypatch, rows: list[tuple[TenantId, dict[str, object]]]) -> None:
    async def _fake_list(self, provider_kind, credential_kind):  # noqa: ANN001
        assert provider_kind == "mattermost"
        assert credential_kind == "webhook_secret"
        return rows

    monkeypatch.setattr(
        chat_inbound_router.IntegrationCredentialService,
        "list_active_payloads_across_tenants",
        _fake_list,
    )


def _patch_capture(monkeypatch, captured: list[dict[str, Any]]) -> None:
    async def _fake_capture(self, tenant_id, payload):  # noqa: ANN001
        captured.append(
            {
                "tenant_id": tenant_id,
                "source": payload.source,
                "event_type": payload.event_type,
                "external_id": payload.external_id,
                "payload": payload.payload,
            }
        )
        return MagicMock()

    monkeypatch.setattr(
        chat_inbound_router.IngestService, "capture", _fake_capture
    )


def test_webhook_missing_token_is_rejected_and_not_captured(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    captured: list[dict[str, Any]] = []
    _patch_credentials(monkeypatch, [(tenant_id, {"token": "right"})])
    _patch_capture(monkeypatch, captured)

    client = TestClient(_build_app(MagicMock()))
    # Body carries identifying ids but NO token → not a health check → 401.
    res = client.post(
        "/integrations/chat/mattermost/webhook",
        data={"post_id": "p1", "user_id": "u1", "text": "hi"},
    )

    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"
    assert captured == []


def test_webhook_wrong_token_is_rejected_and_not_captured(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    captured: list[dict[str, Any]] = []
    _patch_credentials(monkeypatch, [(tenant_id, {"token": "right"})])
    _patch_capture(monkeypatch, captured)

    client = TestClient(_build_app(MagicMock()))
    res = client.post(
        "/integrations/chat/mattermost/webhook",
        data={"token": "WRONG", "post_id": "p1", "user_id": "u1", "text": "hi"},
    )

    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"
    assert captured == []
    # The presented token must not leak into the response body.
    assert "WRONG" not in res.text


def test_webhook_correct_token_captures_verbatim(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    captured: list[dict[str, Any]] = []
    _patch_credentials(monkeypatch, [(tenant_id, {"token": "right-secret"})])
    _patch_capture(monkeypatch, captured)

    client = TestClient(_build_app(MagicMock()))
    res = client.post(
        "/integrations/chat/mattermost/webhook",
        data={
            "token": "right-secret",
            "channel_id": "chan1",
            "user_id": "user1",
            "post_id": "post1",
            "text": "reply text",
        },
    )

    assert res.status_code == 200
    assert len(captured) == 1
    row = captured[0]
    assert row["tenant_id"] == tenant_id
    assert row["source"] == "mattermost"
    assert row["event_type"] == "mattermost.webhook"
    assert row["external_id"] == "post1"
    # Verbatim for everything EXCEPT the live auth token: the forensic copy
    # keeps the full inbound body but the top-level ``token`` is redacted
    # (N3) so the live secret is never persisted.
    assert row["payload"]["text"] == "reply text"
    assert row["payload"]["channel_id"] == "chan1"
    assert row["payload"]["token"] == "[redacted]"
    # The raw secret must not survive anywhere in the captured payload.
    assert "right-secret" not in str(row["payload"])


def test_action_context_token_is_redacted_in_capture(monkeypatch) -> None:
    """N3: the action ``context.token`` is redacted before raw_event capture."""
    tenant_id = TenantId(uuid.uuid4())
    captured: list[dict[str, Any]] = []
    _patch_credentials(monkeypatch, [(tenant_id, {"token": "ctx-secret"})])
    _patch_capture(monkeypatch, captured)

    client = TestClient(_build_app(MagicMock()))
    res = client.post(
        "/integrations/chat/mattermost/action",
        json={
            "trigger_id": "trig9",
            "user_id": "user9",
            "context": {
                "token": "ctx-secret",
                "proposal_ref": "ref-9",
                "decision": "approve",
            },
        },
    )

    assert res.status_code == 200
    assert len(captured) == 1
    payload = captured[0]["payload"]
    # The secret is redacted, but the rest of the context is preserved verbatim.
    assert payload["context"]["token"] == "[redacted]"
    assert payload["context"]["proposal_ref"] == "ref-9"
    assert payload["context"]["decision"] == "approve"
    assert "ctx-secret" not in str(payload)


def test_action_correct_token_in_context_captures(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    captured: list[dict[str, Any]] = []
    _patch_credentials(monkeypatch, [(tenant_id, {"token": "act-secret"})])
    _patch_capture(monkeypatch, captured)

    client = TestClient(_build_app(MagicMock()))
    res = client.post(
        "/integrations/chat/mattermost/action",
        json={
            "trigger_id": "trig1",
            "user_id": "user2",
            "context": {"token": "act-secret", "action": "approve"},
        },
    )

    assert res.status_code == 200
    assert len(captured) == 1
    row = captured[0]
    assert row["tenant_id"] == tenant_id
    assert row["event_type"] == "mattermost.action"
    assert row["external_id"] == "trig1"
    assert row["payload"]["context"]["action"] == "approve"


def test_action_wrong_token_rejected(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    captured: list[dict[str, Any]] = []
    _patch_credentials(monkeypatch, [(tenant_id, {"token": "act-secret"})])
    _patch_capture(monkeypatch, captured)

    client = TestClient(_build_app(MagicMock()))
    res = client.post(
        "/integrations/chat/mattermost/action",
        json={"trigger_id": "t", "context": {"token": "bad"}},
    )

    assert res.status_code == 401
    assert captured == []


def test_empty_body_is_health_check_no_capture(monkeypatch) -> None:
    tenant_id = TenantId(uuid.uuid4())
    captured: list[dict[str, Any]] = []
    _patch_credentials(monkeypatch, [(tenant_id, {"token": "right"})])
    _patch_capture(monkeypatch, captured)

    client = TestClient(_build_app(MagicMock()))
    res = client.post(
        "/integrations/chat/mattermost/webhook",
        content=b"",
        headers={"content-type": "application/json"},
    )

    assert res.status_code == 200
    assert captured == []
