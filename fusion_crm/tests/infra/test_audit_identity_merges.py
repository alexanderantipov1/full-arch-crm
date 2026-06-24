"""Unit tests for the ENG-309 audit_identity_merges.py script.

The audit script reads ``identity.source_link`` joined to the latest
``ingest.raw_event`` of type ``carestack.patient.upsert`` and counts
``identity.person`` rows where the linked patient_ids disagree on DOB or
SSN. These tests verify:

* Argparse defaults match the spec.
* The audit identifies Torosyan-shape (one person, two patient_ids with
  different DOB) as wrong-merged.
* Persons with consistent DOB/SSN across linked patient_ids are NOT
  flagged.
* SSN normalisation (dashes stripped) is applied before comparison so
  '623-35-9385' and '623359385' do NOT count as a mismatch.
* CareStack and the database are fully mocked; ZERO real network or
  Postgres calls.
"""

from __future__ import annotations

import importlib.util
import io
import pathlib
import sys
import uuid
from argparse import Namespace
from contextlib import asynccontextmanager, redirect_stdout
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "audit_identity_merges.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "infra_audit_identity_merges", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit_identity_merges = _load_script()

_TENANT_UUID = uuid.uuid4()


def _args(**overrides: object) -> Namespace:
    base: dict[str, object] = {
        "tenant_id": str(_TENANT_UUID),
        "sample_size": 20,
        "dry_run": True,
    }
    base.update(overrides)
    return Namespace(**base)


def _row(
    person_uid: uuid.UUID,
    patient_ids: list[str],
    dobs: list[str | None],
    ssns: list[str | None],
) -> SimpleNamespace:
    mapping = {
        "person_uid": person_uid,
        "patient_ids": patient_ids,
        "dobs": dobs,
        "ssns": ssns,
    }
    return SimpleNamespace(_mapping=mapping)


def _fake_session_cm(rows: list[SimpleNamespace]) -> Any:
    session = MagicMock()
    execute_result = MagicMock()
    execute_result.all.return_value = rows
    session.execute = AsyncMock(return_value=execute_result)

    @asynccontextmanager
    async def _cm() -> Any:
        yield session

    cm = _cm()
    cm.session = session  # type: ignore[attr-defined]
    return cm


# --------------------------------------------------------------- argparse


def test_parse_args_defaults_match_spec() -> None:
    args = audit_identity_merges.parse_args(["--tenant-id", str(_TENANT_UUID)])
    assert args.tenant_id == str(_TENANT_UUID)
    assert args.sample_size == 20
    assert args.dry_run is True


def test_parse_args_supports_sample_size_override() -> None:
    args = audit_identity_merges.parse_args(
        ["--tenant-id", str(_TENANT_UUID), "--sample-size", "5"]
    )
    assert args.sample_size == 5


# ------------------------------------------------ flagging behaviour


@pytest.mark.asyncio
async def test_audit_flags_torosyan_shape_dob_mismatch() -> None:
    eduard_gaiane_uid = uuid.uuid4()
    cm = _fake_session_cm(
        [
            _row(
                eduard_gaiane_uid,
                ["1460847", "1461274"],
                ["1968-04-19", "1972-08-20"],
                ["623359385", "602378893"],
            )
        ]
    )

    captured_stdout = io.StringIO()
    with redirect_stdout(captured_stdout):
        exit_code = await audit_identity_merges.main(
            _args(), session_factory=lambda: cm
        )

    assert exit_code == 0
    output = captured_stdout.getvalue()
    assert str(eduard_gaiane_uid) in output
    assert "1460847" in output and "1461274" in output


@pytest.mark.asyncio
async def test_audit_does_not_flag_consistent_dob_and_ssn() -> None:
    """Legitimate same-person multi-registration: same DOB + SSN across
    linked patient_ids (e.g. Gaiane registered at two locations). NOT
    wrong-merged."""
    consistent_uid = uuid.uuid4()
    cm = _fake_session_cm(
        [
            _row(
                consistent_uid,
                ["1461274", "1462000"],
                ["1972-08-20", "1972-08-20"],
                ["602378893", "602378893"],
            )
        ]
    )

    captured_stdout = io.StringIO()
    with redirect_stdout(captured_stdout):
        exit_code = await audit_identity_merges.main(
            _args(), session_factory=lambda: cm
        )

    assert exit_code == 0
    # No sample lines emitted (the structured log line may leak from
    # configure_logging() in a sibling test; assert only on the
    # script-owned stdout prefix).
    assert "person_uid=" not in captured_stdout.getvalue()


@pytest.mark.asyncio
async def test_audit_treats_dashed_and_digit_ssn_as_equal() -> None:
    """The two payloads were captured at different times -- one with a
    dashed SSN, one without. The resolver normalises both to digits-only
    before compare; the audit must do the same to avoid false positives.
    """
    uid = uuid.uuid4()
    cm = _fake_session_cm(
        [
            _row(
                uid,
                ["1500000", "1500001"],
                ["1968-04-19", "1968-04-19"],
                ["623-35-9385", "623359385"],
            )
        ]
    )

    captured_stdout = io.StringIO()
    with redirect_stdout(captured_stdout):
        exit_code = await audit_identity_merges.main(
            _args(), session_factory=lambda: cm
        )

    assert exit_code == 0
    assert "person_uid=" not in captured_stdout.getvalue()


@pytest.mark.asyncio
async def test_audit_does_not_flag_missing_value_on_one_side() -> None:
    """One linked patient_id has DOB, the other doesn't. The veto only
    fires when BOTH sides have a value; the audit follows the same
    semantic (distinct-non-null > 1)."""
    uid = uuid.uuid4()
    cm = _fake_session_cm(
        [
            _row(
                uid,
                ["1500000", "1500001"],
                ["1968-04-19", None],
                [None, None],
            )
        ]
    )

    captured_stdout = io.StringIO()
    with redirect_stdout(captured_stdout):
        exit_code = await audit_identity_merges.main(
            _args(), session_factory=lambda: cm
        )

    assert exit_code == 0
    assert "person_uid=" not in captured_stdout.getvalue()


@pytest.mark.asyncio
async def test_audit_sample_size_caps_stdout_output() -> None:
    rows = [
        _row(
            uuid.uuid4(),
            [f"{i}000", f"{i}001"],
            ["1968-04-19", "1972-08-20"],
            [None, None],
        )
        for i in range(5)
    ]
    cm = _fake_session_cm(rows)

    captured_stdout = io.StringIO()
    with redirect_stdout(captured_stdout):
        exit_code = await audit_identity_merges.main(
            _args(sample_size=2), session_factory=lambda: cm
        )

    assert exit_code == 0
    # 2 sample lines emitted (sample-size 2), even though 5 rows are
    # wrong-merged. The structured log carries the real total. Count
    # the script-owned "person_uid=" prefix rather than total newlines
    # because configure_logging() may have emitted a leading log line
    # via a sibling test.
    assert captured_stdout.getvalue().count("person_uid=") == 2


@pytest.mark.asyncio
async def test_audit_returns_zero_when_no_persons_at_all() -> None:
    cm = _fake_session_cm([])
    exit_code = await audit_identity_merges.main(_args(), session_factory=lambda: cm)
    assert exit_code == 0


# ----------------------------------------------------- normalise_ssn helper


def test_normalise_ssn_strips_dashes_and_whitespace() -> None:
    assert audit_identity_merges._normalise_ssn("  623-35-9385  ") == "623359385"
    assert audit_identity_merges._normalise_ssn("623359385") == "623359385"
    assert audit_identity_merges._normalise_ssn(None) is None
    assert audit_identity_merges._normalise_ssn("   ") is None
    assert audit_identity_merges._normalise_ssn(123) is None  # type: ignore[arg-type]
