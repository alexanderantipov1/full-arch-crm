"""Unit tests for the ENG-498 messenger Cloud Run Job entrypoints.

Prod has no always-on arq worker (ENG-172), so the notification-outbox
drain and the consultation-reminder scan run as scheduled Cloud Run Jobs.
These tests prove the thin ``run()`` wrappers funnel into the underlying
cron with an empty ctx and surface its summary unchanged. The crons
themselves (locking, dedupe, posting) are tested elsewhere and fully
mocked here — ZERO real DB or network.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from apps.worker.jobs import consult_reminder_scan as reminder_job
from apps.worker.jobs import notification_drain as drain_job


@pytest.mark.asyncio
async def test_notification_drain_run_invokes_cron_and_returns_summary() -> None:
    summary = {"sent": 3, "failed": 0, "skipped": 1}
    cron = AsyncMock(return_value=summary)

    with patch.object(drain_job, "drain_notification_outbox", cron):
        result = await drain_job.run()

    assert result == summary
    cron.assert_awaited_once_with({})


@pytest.mark.asyncio
async def test_notification_drain_alias_funnels_into_run() -> None:
    summary = {"sent": 0, "failed": 0, "skipped": 0}
    cron = AsyncMock(return_value=summary)

    with patch.object(drain_job, "drain_notification_outbox", cron):
        result = await drain_job.drain_notification_outbox_job({"redis": object()})

    assert result == summary
    cron.assert_awaited_once_with({})


@pytest.mark.asyncio
async def test_consult_reminder_run_invokes_cron_and_returns_summary() -> None:
    summary = {"tenants": 2, "emitted": 1, "failed": 0}
    cron = AsyncMock(return_value=summary)

    with patch.object(reminder_job, "scan_consultation_reminders", cron):
        result = await reminder_job.run()

    assert result == summary
    cron.assert_awaited_once_with({})


@pytest.mark.asyncio
async def test_consult_reminder_alias_funnels_into_run() -> None:
    summary = {"tenants": 0, "emitted": 0, "failed": 0}
    cron = AsyncMock(return_value=summary)

    with patch.object(reminder_job, "scan_consultation_reminders", cron):
        result = await reminder_job.scan_consultation_reminders_job({"x": 1})

    assert result == summary
    cron.assert_awaited_once_with({})
