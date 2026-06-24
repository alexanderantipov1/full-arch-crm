"""Unit tests for the ENG-312 backfill_person_dob_ssn.py script.

The script populates ``identity.person.dob`` / ``identity.person.ssn``
from the latest ``carestack.patient.upsert`` payload per linked
patient_id. This activates the ENG-309 hard veto on the existing
population -- the veto only fires when the candidate Person row has
a value, and today it has none.

Hard rules these tests pin:

* Write-once: an existing non-null ``dob`` / ``ssn`` is NEVER
  overwritten (mirrors :func:`IdentityService._maybe_backfill_demographic`).
* Multi-pid AGREE → set once.
* Multi-pid DISAGREE → SKIP the person, increment
  ``needs_manual_review`` (the ENG-311 split should have driven this
  near-zero; surfacing it is the point).
* Placeholder ``1900-01-01`` (CareStack "unknown DOB" sentinel) is
  never written to ``person.dob``; the person is counted under
  ``skipped_placeholder_dob`` and ``dob`` stays NULL.
* SF-only persons (no CareStack source_link) are never selected --
  the SELECT joins ``identity.source_link``, so the test fixture
  models that by simply not yielding a row for SF-only persons.
* ``--dry-run`` (the default) is a strict no-op: no UPDATE, no
  AccessLog insert. Only a stdout plan line.
* ``--apply`` is the only path that mutates.
* ``--max-persons`` caps how many candidates are processed.
* ``--person-uid`` filters selection to a single target.
* Idempotent: a second run sees no candidates → 0 writes.
* The ``audit.access_log`` row's ``extra`` carries ONLY booleans +
  the ``source_pid_count`` integer. No dob / ssn / name VALUES.
* The database is fully mocked; ZERO real Postgres calls and ZERO
  CareStack API calls.
"""

from __future__ import annotations

import importlib.util
import io
import pathlib
import sys
import uuid
from argparse import Namespace
from contextlib import asynccontextmanager, redirect_stdout
from datetime import date
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "backfill_person_dob_ssn.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "infra_backfill_person_dob_ssn", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backfill = _load_script()

_TENANT_UUID = uuid.uuid4()


def _args(**overrides: object) -> Namespace:
    base: dict[str, object] = {
        "tenant_id": str(_TENANT_UUID),
        "dry_run": True,
        "apply": False,
        "max_persons": 200,
        "commit_every": 50,
        "person_uid": None,
    }
    base.update(overrides)
    return Namespace(**base)


def _row(
    person_uid: uuid.UUID,
    patient_ids: list[str],
    dobs: list[str | None],
    ssns: list[str | None],
    *,
    person_dob: date | None = None,
    person_ssn: str | None = None,
) -> SimpleNamespace:
    mapping = {
        "person_uid": person_uid,
        "person_dob": person_dob,
        "person_ssn": person_ssn,
        "patient_ids": patient_ids,
        "dobs": dobs,
        "ssns": ssns,
    }
    return SimpleNamespace(_mapping=mapping)


def _make_session_recorder() -> Any:
    """Build a MagicMock session that records add() / execute() / commit() calls.

    The session yields a different mock return per ``execute`` call based
    on SQL identity:

    * the SELECT (WITH latest_payload) returns the ``.all()`` rows the
      caller wired via ``all_rows``;
    * UPDATE identity.person returns a result with ``.rowcount``.
    """
    session = MagicMock()
    session.added = []
    session.executed_sql = []
    session.executed_params = []

    def _add(obj: Any) -> None:
        session.added.append(obj)

    async def _commit() -> None:
        session.commits = getattr(session, "commits", 0) + 1  # type: ignore[attr-defined]

    def _execute_side(query: Any, params: dict[str, Any] | None = None) -> Any:
        sql_text = str(query)
        session.executed_sql.append(sql_text)
        session.executed_params.append(params or {})
        result = MagicMock()
        result.rowcount = 1
        result.all.return_value = session.all_for(sql_text)  # type: ignore[attr-defined]
        return result

    # ``session.begin_nested()`` returns an async context manager that
    # records its enter/exit lifecycle so tests can assert per-person
    # SAVEPOINT scoping. Real SQLAlchemy auto-rolls-back on exception;
    # the mock just records the outcome and does NOT swallow.
    session.savepoints = []  # type: ignore[attr-defined]

    class _NestedTx:
        async def __aenter__(self) -> Any:
            session.savepoints.append({"status": "open"})  # type: ignore[attr-defined]
            return self

        async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            session.savepoints[-1]["status"] = (  # type: ignore[attr-defined]
                "rolled_back" if exc_type is not None else "released"
            )
            return False  # never swallow

    session.add = MagicMock(side_effect=_add)
    session.flush = AsyncMock()
    session.commit = AsyncMock(side_effect=_commit)
    session.execute = AsyncMock(side_effect=_execute_side)
    session.begin_nested = MagicMock(side_effect=lambda: _NestedTx())
    session.commits = 0  # type: ignore[attr-defined]

    session.all_rows = []

    def _all_for(sql: str) -> list[Any]:
        if "WITH latest_payload" in sql:
            return list(session.all_rows)  # type: ignore[attr-defined]
        return []

    session.all_for = _all_for  # type: ignore[attr-defined]
    return session


def _fake_session_cm(session: Any) -> Any:
    @asynccontextmanager
    async def _cm() -> Any:
        yield session

    return _cm()


# ----------------------------------------------------------------- argparse


def test_parse_args_defaults_match_spec() -> None:
    args = backfill.parse_args(["--tenant-id", str(_TENANT_UUID)])
    assert args.tenant_id == str(_TENANT_UUID)
    assert args.dry_run is True
    assert args.apply is False
    assert args.max_persons == 200
    assert args.commit_every == 50
    assert args.person_uid is None


def test_parse_args_apply_flag_opts_in() -> None:
    args = backfill.parse_args(["--tenant-id", str(_TENANT_UUID), "--apply"])
    assert args.apply is True


def test_parse_args_person_uid_and_max_persons() -> None:
    target = str(uuid.uuid4())
    args = backfill.parse_args(
        [
            "--tenant-id",
            str(_TENANT_UUID),
            "--max-persons",
            "5",
            "--person-uid",
            target,
        ]
    )
    assert args.max_persons == 5
    assert args.person_uid == target


def test_bad_tenant_id_returns_exit_code_2() -> None:
    import asyncio

    session = _make_session_recorder()
    cm = _fake_session_cm(session)
    rc = asyncio.run(
        backfill.main(
            _args(tenant_id="not-a-uuid"),
            session_factory=lambda: cm,
        )
    )
    assert rc == 2


def test_bad_person_uid_returns_exit_code_2() -> None:
    import asyncio

    session = _make_session_recorder()
    cm = _fake_session_cm(session)
    rc = asyncio.run(
        backfill.main(
            _args(person_uid="not-a-uuid"),
            session_factory=lambda: cm,
        )
    )
    assert rc == 2


# ------------------------------------------------------ plan computation


def test_compute_plan_single_pid_sets_dob_and_ssn() -> None:
    person_uid = uuid.uuid4()
    cand = backfill._Candidate(
        person_uid=person_uid,
        person_dob=None,
        person_ssn=None,
        patient_ids=["1234"],
        dob_strings=["1968-04-19"],
        ssn_strings=["623-35-9385"],
    )
    plan = backfill._compute_plan(cand)
    assert plan.set_dob == date(1968, 4, 19)
    assert plan.set_ssn == "623359385"  # dashes stripped
    assert plan.skip_reason is None
    assert plan.placeholder_dob is False


def test_compute_plan_multi_pid_agree_sets_once() -> None:
    cand = backfill._Candidate(
        person_uid=uuid.uuid4(),
        person_dob=None,
        person_ssn=None,
        patient_ids=["1", "2"],
        dob_strings=["1972-08-20", "1972-08-20"],
        ssn_strings=["602378893", "602378893"],
    )
    plan = backfill._compute_plan(cand)
    assert plan.set_dob == date(1972, 8, 20)
    assert plan.set_ssn == "602378893"
    assert plan.skip_reason is None


def test_compute_plan_multi_pid_disagree_dob_skips() -> None:
    cand = backfill._Candidate(
        person_uid=uuid.uuid4(),
        person_dob=None,
        person_ssn=None,
        patient_ids=["1", "2"],
        dob_strings=["1968-04-19", "1972-08-20"],
        ssn_strings=["623359385", "623359385"],
    )
    plan = backfill._compute_plan(cand)
    assert plan.skip_reason == "mismatch_dob"
    assert plan.set_dob is None
    assert plan.set_ssn is None


def test_compute_plan_multi_pid_disagree_ssn_skips() -> None:
    cand = backfill._Candidate(
        person_uid=uuid.uuid4(),
        person_dob=None,
        person_ssn=None,
        patient_ids=["1", "2"],
        dob_strings=["1968-04-19", "1968-04-19"],
        ssn_strings=["623359385", "111223333"],
    )
    plan = backfill._compute_plan(cand)
    assert plan.skip_reason == "mismatch_ssn"


def test_compute_plan_write_once_existing_dob_not_overwritten() -> None:
    """If person.dob is already set, plan.set_dob is None even when a value is
    available (write-once)."""
    cand = backfill._Candidate(
        person_uid=uuid.uuid4(),
        person_dob=date(1900, 1, 2),  # arbitrary existing real value
        person_ssn=None,
        patient_ids=["1"],
        dob_strings=["1968-04-19"],
        ssn_strings=["623359385"],
    )
    plan = backfill._compute_plan(cand)
    assert plan.set_dob is None  # write-once
    assert plan.set_ssn == "623359385"


def test_compute_plan_write_once_existing_ssn_not_overwritten() -> None:
    cand = backfill._Candidate(
        person_uid=uuid.uuid4(),
        person_dob=None,
        person_ssn="999999999",
        patient_ids=["1"],
        dob_strings=["1968-04-19"],
        ssn_strings=["623359385"],
    )
    plan = backfill._compute_plan(cand)
    assert plan.set_dob == date(1968, 4, 19)
    assert plan.set_ssn is None  # write-once


def test_compute_plan_placeholder_dob_only_skipped() -> None:
    """The placeholder ``1900-01-01`` is never written; person counted in
    ``skipped_placeholder_dob``. SSN is still settable."""
    cand = backfill._Candidate(
        person_uid=uuid.uuid4(),
        person_dob=None,
        person_ssn=None,
        patient_ids=["1"],
        dob_strings=["1900-01-01"],
        ssn_strings=["623359385"],
    )
    plan = backfill._compute_plan(cand)
    assert plan.placeholder_dob is True
    assert plan.set_dob is None  # placeholder not written
    assert plan.set_ssn == "623359385"  # ssn still goes through


def test_compute_plan_iso_timestamp_dob_parsed() -> None:
    """CareStack sometimes emits dob as an ISO timestamp; both formats parse."""
    cand = backfill._Candidate(
        person_uid=uuid.uuid4(),
        person_dob=None,
        person_ssn=None,
        patient_ids=["1"],
        dob_strings=["1968-04-19T00:00:00"],
        ssn_strings=["623359385"],
    )
    plan = backfill._compute_plan(cand)
    assert plan.set_dob == date(1968, 4, 19)


# ----------------------------------------------------------- dry-run


@pytest.mark.asyncio
async def test_dry_run_writes_nothing_only_prints_plan() -> None:
    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(person_uid, ["1"], ["1968-04-19"], ["623359385"])
    ]
    cm = _fake_session_cm(session)

    captured = io.StringIO()
    with redirect_stdout(captured):
        rc = await backfill.main(_args(), session_factory=lambda: cm)

    assert rc == 0
    # No session.add() at all (no AccessLog), and only one execute (the SELECT).
    assert session.added == []
    assert len(session.executed_sql) == 1
    assert "WITH latest_payload" in session.executed_sql[0]
    # No commits in dry-run.
    assert session.commits == 0
    # Plan was printed.
    out = captured.getvalue()
    assert str(person_uid) in out
    assert "would_set_dob=True" in out
    assert "would_set_ssn=True" in out


@pytest.mark.asyncio
async def test_dry_run_plan_line_carries_no_phi_values() -> None:
    """Dry-run plan must show booleans / counts only -- never the parsed
    dob / ssn VALUES."""
    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1460847"],
            ["1968-04-19"],
            ["623359385"],
        )
    ]
    cm = _fake_session_cm(session)

    captured = io.StringIO()
    with redirect_stdout(captured):
        await backfill.main(_args(), session_factory=lambda: cm)

    out = captured.getvalue()
    assert "1968-04-19" not in out
    assert "623359385" not in out


# ----------------------------------------------------------- apply path


@pytest.mark.asyncio
async def test_apply_single_pid_writes_update_and_audit() -> None:
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(person_uid, ["1"], ["1968-04-19"], ["623359385"])
    ]
    cm = _fake_session_cm(session)

    rc = await backfill.main(_args(apply=True), session_factory=lambda: cm)
    assert rc == 0

    # One UPDATE issued; one AccessLog added.
    updates = [sql for sql in session.executed_sql if "UPDATE identity.person" in sql]
    assert len(updates) == 1
    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 1
    assert audits[0].action == "identity.person.demographic_backfill"
    # UPDATE bound the parsed values, not raw strings.
    update_params = next(
        params
        for sql, params in zip(
            session.executed_sql, session.executed_params, strict=False
        )
        if "UPDATE identity.person" in sql
    )
    assert update_params["dob"] == date(1968, 4, 19)
    assert update_params["ssn"] == "623359385"
    assert update_params["person_uid"] == str(person_uid)


@pytest.mark.asyncio
async def test_apply_multi_pid_agree_sets_once() -> None:
    """Multi-pid AGREE → exactly one UPDATE; same dob/ssn bound."""
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1", "2", "3"],
            ["1972-08-20", "1972-08-20", "1972-08-20"],
            ["602378893", "602378893", "602378893"],
        )
    ]
    cm = _fake_session_cm(session)

    await backfill.main(_args(apply=True), session_factory=lambda: cm)
    updates = [
        params
        for sql, params in zip(
            session.executed_sql, session.executed_params, strict=False
        )
        if "UPDATE identity.person" in sql
    ]
    assert len(updates) == 1
    assert updates[0]["dob"] == date(1972, 8, 20)
    assert updates[0]["ssn"] == "602378893"

    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 1
    assert audits[0].extra["source_pid_count"] == 3


@pytest.mark.asyncio
async def test_apply_multi_pid_disagree_skips_and_counts_manual_review() -> None:
    """Disagreement → NO UPDATE, NO AccessLog. needs_manual_review bumped."""
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1", "2"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "602378893"],
        )
    ]
    cm = _fake_session_cm(session)

    rc = await backfill.main(_args(apply=True), session_factory=lambda: cm)
    assert rc == 0
    assert not any("UPDATE identity.person" in sql for sql in session.executed_sql)
    assert [o for o in session.added if isinstance(o, AccessLog)] == []


# ----------------------------------------------------------- write-once


@pytest.mark.asyncio
async def test_existing_non_null_dob_is_not_overwritten() -> None:
    """A person whose ``dob`` is already set must not have it overwritten,
    even if a different value is available in the payload."""
    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1"],
            ["1972-08-20"],  # different dob from existing
            ["602378893"],
            person_dob=date(1968, 4, 19),  # existing value
            person_ssn=None,
        )
    ]
    cm = _fake_session_cm(session)

    await backfill.main(_args(apply=True), session_factory=lambda: cm)

    # UPDATE issued (for ssn) but dob bound is None → SQL COALESCE
    # preserves the existing value.
    update_params = next(
        params
        for sql, params in zip(
            session.executed_sql, session.executed_params, strict=False
        )
        if "UPDATE identity.person" in sql
    )
    assert update_params["dob"] is None
    assert update_params["ssn"] == "602378893"


@pytest.mark.asyncio
async def test_already_fully_populated_person_is_a_noop() -> None:
    """Idempotent re-run shape: a person whose dob+ssn are both already set
    yields no UPDATE and no AccessLog."""
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1"],
            ["1968-04-19"],
            ["623359385"],
            person_dob=date(1968, 4, 19),
            person_ssn="623359385",
        )
    ]
    cm = _fake_session_cm(session)

    rc = await backfill.main(_args(apply=True), session_factory=lambda: cm)
    assert rc == 0
    assert not any("UPDATE identity.person" in sql for sql in session.executed_sql)
    assert [o for o in session.added if isinstance(o, AccessLog)] == []


# ----------------------------------------------------------- placeholder


@pytest.mark.asyncio
async def test_placeholder_dob_only_leaves_dob_null_but_still_sets_ssn() -> None:
    """Person whose only dob signal is the 1900-01-01 placeholder still gets
    ssn written, but dob stays NULL. UPDATE binds dob=None."""
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(person_uid, ["1"], ["1900-01-01"], ["623359385"])
    ]
    cm = _fake_session_cm(session)

    await backfill.main(_args(apply=True), session_factory=lambda: cm)

    update_params = next(
        params
        for sql, params in zip(
            session.executed_sql, session.executed_params, strict=False
        )
        if "UPDATE identity.person" in sql
    )
    assert update_params["dob"] is None  # placeholder NOT written
    assert update_params["ssn"] == "623359385"

    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 1
    assert audits[0].extra["set_dob"] is False
    assert audits[0].extra["set_ssn"] is True


@pytest.mark.asyncio
async def test_placeholder_dob_only_no_ssn_is_full_noop() -> None:
    """Placeholder dob + no ssn → nothing to set → no UPDATE, no AccessLog."""
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(person_uid, ["1"], ["1900-01-01"], [None])
    ]
    cm = _fake_session_cm(session)

    await backfill.main(_args(apply=True), session_factory=lambda: cm)

    assert not any("UPDATE identity.person" in sql for sql in session.executed_sql)
    assert [o for o in session.added if isinstance(o, AccessLog)] == []


# --------------------------------------------- SF-only person untouched


@pytest.mark.asyncio
async def test_sf_only_person_not_selected() -> None:
    """SF-only persons have NO ``carestack/patient`` source_link, so the
    SELECT (which joins source_link) never yields them. With no rows
    returned, no UPDATE / no AccessLog is written -- a strict no-op."""
    from packages.audit.models import AccessLog

    session = _make_session_recorder()
    session.all_rows = []  # SF-only → not selected by the JOIN
    cm = _fake_session_cm(session)

    rc = await backfill.main(_args(apply=True), session_factory=lambda: cm)
    assert rc == 0
    assert not any("UPDATE identity.person" in sql for sql in session.executed_sql)
    assert [o for o in session.added if isinstance(o, AccessLog)] == []


# ----------------------------------------------------------- audit shape


@pytest.mark.asyncio
async def test_audit_row_extra_carries_only_booleans_counts_no_phi() -> None:
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1460847", "1461274"],
            ["1968-04-19", "1968-04-19"],
            ["623359385", "623359385"],
        )
    ]
    cm = _fake_session_cm(session)

    await backfill.main(_args(apply=True), session_factory=lambda: cm)

    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "identity.person.demographic_backfill"
    extra = audit.extra
    assert set(extra.keys()) == {"set_dob", "set_ssn", "source_pid_count"}
    assert extra["source_pid_count"] == 2
    assert extra["set_dob"] is True
    assert extra["set_ssn"] is True
    # No PHI values in the serialised extra.
    serialised = str(extra)
    assert "1968-04-19" not in serialised
    assert "623359385" not in serialised
    assert "1460847" not in serialised


# ----------------------------------------------------------- caps + filter


@pytest.mark.asyncio
async def test_max_persons_caps_processing() -> None:
    from packages.audit.models import AccessLog

    session = _make_session_recorder()
    session.all_rows = [
        _row(uuid.uuid4(), [str(i)], ["1968-04-19"], ["623359385"])
        for i in range(10)
    ]
    cm = _fake_session_cm(session)

    await backfill.main(
        _args(apply=True, max_persons=3), session_factory=lambda: cm
    )

    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 3


@pytest.mark.asyncio
async def test_person_uid_filter_processes_only_target() -> None:
    from packages.audit.models import AccessLog

    target = uuid.uuid4()
    other_a = uuid.uuid4()
    other_b = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(other_a, ["1"], ["1968-04-19"], ["111111111"]),
        _row(target, ["2"], ["1972-08-20"], ["222222222"]),
        _row(other_b, ["3"], ["1980-01-01"], ["333333333"]),
    ]
    cm = _fake_session_cm(session)

    await backfill.main(
        _args(apply=True, person_uid=str(target)),
        session_factory=lambda: cm,
    )

    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 1
    assert audits[0].person_uid == target


# ----------------------------------------------------------- idempotency


@pytest.mark.asyncio
async def test_idempotent_when_no_candidates() -> None:
    """No candidate rows → no writes, no errors. This is the steady-state
    of the second run after the first has written everything settable."""
    session = _make_session_recorder()
    session.all_rows = []
    cm = _fake_session_cm(session)

    rc = await backfill.main(_args(apply=True), session_factory=lambda: cm)
    assert rc == 0
    assert session.added == []
    # Still commits once at the end of the apply path -- harmless empty
    # transaction; matches the split-script shape.
    assert session.commits == 1


# ----------------------------------------------------------- savepoint


@pytest.mark.asyncio
async def test_per_person_savepoint_isolates_failure() -> None:
    """A single failing person rolls back via SAVEPOINT; the batch survives.

    Persons A and C succeed; person B's UPDATE raises. The per-person
    ``session.begin_nested()`` rolls B back; A and C's audit rows still
    land; ``main`` returns 0; the savepoint lifecycle records
    released/rolled_back/released."""
    from packages.audit.models import AccessLog

    uid_a, uid_b, uid_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(uid_a, ["1"], ["1968-04-19"], ["111111111"]),
        _row(uid_b, ["2"], ["1972-08-20"], ["222222222"]),
        _row(uid_c, ["3"], ["1980-01-01"], ["333333333"]),
    ]

    # Patch execute() so the 2nd UPDATE raises. The SELECT is execute #1;
    # then UPDATE/UPDATE/UPDATE are execute #2/3/4. We want execute #3
    # (B's UPDATE) to raise.
    original_side = session.execute.side_effect
    update_calls = {"n": 0}

    async def _execute_with_b_failure(query: Any, params: dict[str, Any] | None = None) -> Any:
        sql_text = str(query)
        if "UPDATE identity.person" in sql_text:
            update_calls["n"] += 1
            if update_calls["n"] == 2:
                # Record the attempted SQL/params before raising so the
                # recorder accounting matches a real execute.
                session.executed_sql.append(sql_text)
                session.executed_params.append(params or {})
                raise RuntimeError("simulated transient DB hiccup")
        return original_side(query, params)

    session.execute = AsyncMock(side_effect=_execute_with_b_failure)
    cm = _fake_session_cm(session)

    rc = await backfill.main(_args(apply=True), session_factory=lambda: cm)
    assert rc == 0  # batch survived

    audits = [o for o in session.added if isinstance(o, AccessLog)]
    audit_uids = {a.person_uid for a in audits}
    # A and C survive; B never reaches _write_audit_row.
    assert uid_a in audit_uids
    assert uid_c in audit_uids
    assert uid_b not in audit_uids

    # Savepoint lifecycle: 3 begin_nested entries; B is rolled_back.
    assert len(session.savepoints) == 3
    assert session.savepoints[0]["status"] == "released"
    assert session.savepoints[1]["status"] == "rolled_back"
    assert session.savepoints[2]["status"] == "released"


# ----------------------------------------------------------- batching


@pytest.mark.asyncio
async def test_commit_every_boundary_arithmetic_is_off_by_one_safe() -> None:
    """6 updatable persons with ``commit_every=2`` must issue exactly
    4 commits: 3 intermediate flushes at updated=2/4/6 plus one final
    end-of-apply commit. The intermediate-flush trigger is
    ``updated % commit_every == 0`` -- a classic off-by-one site if the
    counter is bumped before or after the modulo check shifts. Pinning
    the exact count catches accidental reorderings."""
    from packages.audit.models import AccessLog

    session = _make_session_recorder()
    session.all_rows = [
        _row(uuid.uuid4(), [str(i)], ["1968-04-19"], [f"60237889{i}"])
        for i in range(6)
    ]
    cm = _fake_session_cm(session)

    rc = await backfill.main(
        _args(apply=True, commit_every=2), session_factory=lambda: cm
    )
    assert rc == 0

    # All 6 persons updated → 6 UPDATEs + 6 AccessLog rows.
    updates = [sql for sql in session.executed_sql if "UPDATE identity.person" in sql]
    assert len(updates) == 6
    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 6

    # Boundary arithmetic: intermediate at 2 / 4 / 6 plus the final
    # post-loop commit. 6 // 2 + 1 = 4.
    assert session.commits == 4


@pytest.mark.asyncio
async def test_commit_every_zero_only_commits_at_end() -> None:
    """``--commit-every 0`` (or any non-positive) MUST disable intermediate
    flushes. The ``args.commit_every > 0`` guard exists precisely so
    operators can opt into a single end-of-run commit; pin the contract."""
    session = _make_session_recorder()
    session.all_rows = [
        _row(uuid.uuid4(), [str(i)], ["1968-04-19"], [f"60237889{i}"])
        for i in range(5)
    ]
    cm = _fake_session_cm(session)

    rc = await backfill.main(
        _args(apply=True, commit_every=0), session_factory=lambda: cm
    )
    assert rc == 0
    # Exactly the single end-of-apply commit.
    assert session.commits == 1


# --------------------------------------------------- manual-review counter


@pytest.mark.asyncio
async def test_disagree_dob_apply_increments_needs_manual_review_counter() -> None:
    """The summary log line must surface ``needs_manual_review`` so
    operators can spot the leftover wrong-merges post-ENG-311. The
    counter is otherwise invisible (no UPDATE, no AccessLog, no dry-run
    stdout when apply is on). Capture the structlog kwargs directly via
    ``patch.object(backfill, "log")`` (the same pattern
    ``test_backfill_payment_summary.py`` uses to sidestep structlog's
    cache_logger_on_first_use ambiguity)."""
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1", "2"],
            ["1968-04-19", "1972-08-20"],  # disagree on dob
            ["623359385", "623359385"],
        )
    ]
    cm = _fake_session_cm(session)

    with patch.object(backfill, "log") as mocked_log:
        rc = await backfill.main(_args(apply=True), session_factory=lambda: cm)

    assert rc == 0

    # No write side-effects for the skipped person.
    assert not any("UPDATE identity.person" in sql for sql in session.executed_sql)
    assert [o for o in session.added if isinstance(o, AccessLog)] == []

    # Counter surfaced in the summary log call.
    summary_calls = [
        call
        for call in mocked_log.info.call_args_list
        if call.args and call.args[0] == "backfill.person_dob_ssn.summary"
    ]
    assert len(summary_calls) == 1, (
        f"expected exactly one summary log call; got {mocked_log.info.call_args_list}"
    )
    summary = summary_calls[0]
    assert summary.kwargs["needs_manual_review"] == 1
    assert summary.kwargs["updated"] == 0
    assert summary.kwargs["scanned"] == 1


# ----------------------------------------------------- ssn-disagree path


@pytest.mark.asyncio
async def test_disagree_ssn_only_apply_path_skips_and_counts() -> None:
    """Pids AGREE on dob but DISAGREE on ssn → the skip fires
    specifically on ``mismatch_ssn`` (not the dob branch the existing
    multi-pid-disagree test trips on). This pins that the ssn-disagreement
    code path is exercised end-to-end through ``main`` -- not just at the
    ``_compute_plan`` unit level -- so a future refactor that drops the
    ssn check from the apply loop is caught."""
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1", "2"],
            ["1968-04-19", "1968-04-19"],  # AGREE on dob
            ["623359385", "111223333"],     # DISAGREE on ssn
        )
    ]
    cm = _fake_session_cm(session)

    with patch.object(backfill, "log") as mocked_log:
        rc = await backfill.main(_args(apply=True), session_factory=lambda: cm)

    assert rc == 0
    # No UPDATE; no AccessLog.
    assert not any("UPDATE identity.person" in sql for sql in session.executed_sql)
    assert [o for o in session.added if isinstance(o, AccessLog)] == []
    # The skip branch bumped manual_review (not error_count, not nothing_to_do).
    summary_calls = [
        call
        for call in mocked_log.info.call_args_list
        if call.args and call.args[0] == "backfill.person_dob_ssn.summary"
    ]
    assert len(summary_calls) == 1
    summary = summary_calls[0]
    assert summary.kwargs["needs_manual_review"] == 1
    assert summary.kwargs["updated"] == 0
    assert summary.kwargs["error_count"] == 0
    assert summary.kwargs["nothing_to_do"] == 0


# ----------------------------------------------------- dry-run formatter


@pytest.mark.asyncio
async def test_dry_run_line_placeholder_dob_carries_marker_no_phi() -> None:
    """A placeholder-1900-01-01 row in dry-run renders ``placeholder_dob=true``
    so the operator can see how many persons still need a real DOB pulled.
    The literal ``1900-01-01`` and any ssn digits MUST NOT leak into stdout
    (the dry-run formatter is the most likely PHI leak site since it
    consumes parsed values)."""
    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(person_uid, ["1"], ["1900-01-01"], ["623359385"])
    ]
    cm = _fake_session_cm(session)

    captured = io.StringIO()
    with redirect_stdout(captured):
        rc = await backfill.main(_args(), session_factory=lambda: cm)

    assert rc == 0
    out = captured.getvalue()
    # The single plan line carries the marker.
    assert "placeholder_dob=true" in out
    assert str(person_uid) in out
    # would_set_dob is False (placeholder is never written); would_set_ssn
    # is True (placeholder is dob-only; ssn still goes through).
    assert "would_set_dob=False" in out
    assert "would_set_ssn=True" in out
    # PHI gate: no raw values surface even though the parser saw them.
    # (Don't assert against bare "1900" -- that 4-char hex substring is
    # plausible inside a random uuid4 string. The full placeholder date
    # is the actual PHI shape we're guarding against.)
    assert "1900-01-01" not in out
    assert "623359385" not in out
    assert "623-35-9385" not in out


@pytest.mark.asyncio
async def test_dry_run_line_mismatch_row_renders_skip_reason_no_phi() -> None:
    """A disagree row in dry-run renders ``skip_reason=mismatch_dob`` so
    the operator can triage. As with every dry-run line, the parsed dob /
    ssn VALUES must NOT appear."""
    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1", "2"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "111223333"],
        )
    ]
    cm = _fake_session_cm(session)

    captured = io.StringIO()
    with redirect_stdout(captured):
        rc = await backfill.main(_args(), session_factory=lambda: cm)

    assert rc == 0
    out = captured.getvalue()
    assert "skip_reason=mismatch_dob" in out
    assert str(person_uid) in out
    assert "source_pid_count=2" in out
    # PHI gate.
    assert "1968-04-19" not in out
    assert "1972-08-20" not in out
    assert "623359385" not in out
    assert "111223333" not in out


# ---------------------------------------------- person-uid filter SQL shape


@pytest.mark.asyncio
async def test_person_uid_filter_is_python_side_not_in_select_params() -> None:
    """The ``--person-uid`` filter is applied in Python (post-fetch) --
    NOT pushed into the SELECT WHERE clause. Pin the SQL param shape so a
    future bad refactor that smuggles ``person_uid`` into the bound params
    (and presumably the SQL text) is caught: a SQL-level filter would
    silently skip the matching person if the tenant binding is wrong AND
    would hide the count of total scanned persons the operator relies on
    for canary verification."""
    target = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(target, ["1"], ["1968-04-19"], ["623359385"]),
    ]
    cm = _fake_session_cm(session)

    await backfill.main(
        _args(apply=True, person_uid=str(target)),
        session_factory=lambda: cm,
    )

    # First execute is the SELECT (WITH latest_payload). Its params
    # dict must NOT carry person_uid.
    select_idx = next(
        i
        for i, sql in enumerate(session.executed_sql)
        if "WITH latest_payload" in sql
    )
    select_params = session.executed_params[select_idx]
    assert "person_uid" not in select_params, (
        f"--person-uid must filter in Python, not SQL; got SELECT params: "
        f"{select_params}"
    )
    assert set(select_params.keys()) == {"tenant_id"}
