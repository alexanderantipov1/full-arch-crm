"""Unit tests for ``IngestService.latest_payment_summary_balances`` (ENG-257 / ENG-266).

Verifies the service-level coercion, outstanding_total math, and the
AR-risk count surfacing given a synthetic repository row. Real-DB
integration (latest-per-patient aggregation against live Postgres) is
covered by the broader test suite once a Postgres fixture is available;
here we lock in the contract.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.core.types import TenantId
from packages.ingest.service import AR_RISK_BALANCE_THRESHOLD, IngestService

_TENANT_ID: TenantId = TenantId(uuid.uuid4())


def _make_service() -> tuple[IngestService, MagicMock]:
    session = MagicMock()
    service = IngestService(session)
    service._repo = MagicMock(  # type: ignore[attr-defined]
        spec=["sum_latest_payment_summary_balances"]
    )
    return service, service._repo  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_outstanding_total_sums_patient_and_insurance() -> None:
    service, repo = _make_service()
    repo.sum_latest_payment_summary_balances = AsyncMock(
        return_value={
            "balance_due_patient": "1200.75",
            "balance_due_insurance": "300.25",
            "patient_count": 5,
            "ar_risk_count": 2,
        }
    )

    result = await service.latest_payment_summary_balances(_TENANT_ID)

    assert result.balance_due_patient == 1200.75
    assert result.balance_due_insurance == 300.25
    assert result.outstanding_total == pytest.approx(1501.0)
    assert result.patient_count == 5
    assert result.ar_risk_count == 2
    assert result.ar_risk_threshold == AR_RISK_BALANCE_THRESHOLD
    repo.sum_latest_payment_summary_balances.assert_awaited_once_with(
        _TENANT_ID, ar_risk_threshold=AR_RISK_BALANCE_THRESHOLD
    )


@pytest.mark.asyncio
async def test_zero_snapshots_returns_safe_defaults() -> None:
    service, repo = _make_service()
    repo.sum_latest_payment_summary_balances = AsyncMock(
        return_value={
            "balance_due_patient": 0,
            "balance_due_insurance": 0,
            "patient_count": 0,
            "ar_risk_count": 0,
        }
    )

    result = await service.latest_payment_summary_balances(_TENANT_ID)

    assert result.balance_due_patient == 0.0
    assert result.balance_due_insurance == 0.0
    assert result.outstanding_total == 0.0
    assert result.patient_count == 0
    assert result.ar_risk_count == 0
    assert result.ar_risk_threshold == AR_RISK_BALANCE_THRESHOLD


@pytest.mark.asyncio
async def test_missing_fields_coerce_to_zero() -> None:
    service, repo = _make_service()
    repo.sum_latest_payment_summary_balances = AsyncMock(return_value={})

    result = await service.latest_payment_summary_balances(_TENANT_ID)

    assert result.balance_due_patient == 0.0
    assert result.balance_due_insurance == 0.0
    assert result.outstanding_total == 0.0
    assert result.patient_count == 0
    assert result.ar_risk_count == 0
    assert result.ar_risk_threshold == AR_RISK_BALANCE_THRESHOLD


@pytest.mark.asyncio
async def test_ar_risk_count_surfaces_from_repo() -> None:
    """The service passes the module-constant threshold to the repo and
    surfaces the count it returns. Above/below threshold filtering and
    latest-snapshot-per-patient aggregation are SQL-side concerns; the
    repo unit tests cover that. Here we lock in the wiring.
    """
    service, repo = _make_service()
    repo.sum_latest_payment_summary_balances = AsyncMock(
        return_value={
            "balance_due_patient": "9000.00",
            "balance_due_insurance": 0,
            "patient_count": 12,
            "ar_risk_count": 7,
        }
    )

    result = await service.latest_payment_summary_balances(_TENANT_ID)

    assert result.ar_risk_count == 7
    assert result.ar_risk_threshold == AR_RISK_BALANCE_THRESHOLD
    repo.sum_latest_payment_summary_balances.assert_awaited_once_with(
        _TENANT_ID, ar_risk_threshold=AR_RISK_BALANCE_THRESHOLD
    )


def test_ar_risk_threshold_is_positive_dollar_amount() -> None:
    """A non-positive threshold would count every patient with any
    outstanding balance as 'at risk' and dilute the signal. Anchor the
    default so an accidental zero/negative tune is a test failure.
    """
    assert AR_RISK_BALANCE_THRESHOLD > 0.0
