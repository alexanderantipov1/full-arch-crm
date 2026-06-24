"""Unit tests for the ENG-311 split_wrong_merged_persons.py script.

The split script reads ``identity.source_link`` joined to the latest
``ingest.raw_event`` of type ``carestack.patient.upsert`` (same selection
as ``audit_identity_merges.py``) and, for every ``identity.person`` row
that has multiple linked patient_ids disagreeing on DOB or SSN, splits
the merged person into N new persons -- one per ``(dob, ssn)`` bucket.

Hard rules these tests pin:

* Largest bucket stays on the original ``person.id``; tie-break is the
  bucket containing the lexicographically smallest patient_id.
* Legitimate same-person multi-registration (same DOB + SSN) is NEVER
  split.
* ``--dry-run`` is the default and writes nothing.
* ``--apply`` is the only path that mutates the database.
* ``--max-splits`` caps how many candidate persons are processed.
* ``--person-uid`` filters selection to a single target.
* Idempotent: re-running on a clean person produces no splits.
* One ``audit.access_log`` row per split (``action='identity.person.split'``)
  with ONLY uuids + counts in ``extra`` -- NO PHI values.
* CareStack-traced downstream rows repoint to the new person; rows with
  no provider trace stay on surviving + bump ``needs_manual_review``.
* The database is fully mocked; ZERO real Postgres calls.
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
    / "split_wrong_merged_persons.py"
)


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "infra_split_wrong_merged_persons", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


split_module = _load_script()

_TENANT_UUID = uuid.uuid4()


def _args(**overrides: object) -> Namespace:
    base: dict[str, object] = {
        "tenant_id": str(_TENANT_UUID),
        "dry_run": True,
        "apply": False,
        "max_splits": 100,
        "person_uid": None,
        "commit_every": 50,
    }
    base.update(overrides)
    return Namespace(**base)


def _row(
    person_uid: uuid.UUID,
    patient_ids: list[str],
    dobs: list[str | None],
    ssns: list[str | None],
    first_names: list[str | None] | None = None,
    last_names: list[str | None] | None = None,
) -> SimpleNamespace:
    n = len(patient_ids)
    if first_names is None:
        first_names = [None] * n
    if last_names is None:
        last_names = [None] * n
    mapping = {
        "person_uid": person_uid,
        "patient_ids": patient_ids,
        "dobs": dobs,
        "ssns": ssns,
        "first_names": first_names,
        "last_names": last_names,
    }
    return SimpleNamespace(_mapping=mapping)


def _make_session_recorder() -> Any:
    """Build a MagicMock session that records add() / execute() / commit() calls.

    The session yields a different mock return for each ``execute`` call
    based on the SQL identity: the first ``execute`` (the audit selection)
    returns the ``.all()`` rows the caller wired; subsequent ``execute``
    calls (per-bucket UPDATEs and the needs-manual-review SELECT) return
    a mock with ``.rowcount`` and ``.first()``.
    """
    session = MagicMock()
    session.added = []
    session.executed_sql = []
    session.executed_params = []

    def _add(obj: Any) -> None:
        session.added.append(obj)

    async def _flush() -> None:
        # Assign a fake UUID to any Person without an id (so the script
        # can read .id back after flush, like real SQLAlchemy would).
        from packages.identity.models import Person as _Person

        for obj in session.added:
            if isinstance(obj, _Person) and getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()  # type: ignore[attr-defined]

    async def _commit() -> None:
        session.commits = getattr(session, "commits", 0) + 1  # type: ignore[attr-defined]

    def _execute_side(query: Any, params: dict[str, Any] | None = None) -> Any:
        sql_text = str(query)
        session.executed_sql.append(sql_text)
        session.executed_params.append(params or {})
        result = MagicMock()
        # Default rowcount + first() for UPDATEs + scalar queries
        result.rowcount = session.rowcount_for(sql_text)  # type: ignore[attr-defined]
        first_value = session.first_for(sql_text)  # type: ignore[attr-defined]
        first_row = MagicMock()
        first_row.__getitem__.side_effect = lambda i: first_value
        first_row._mapping = {"total": first_value}
        result.first.return_value = first_row
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
    session.flush = AsyncMock(side_effect=_flush)
    session.commit = AsyncMock(side_effect=_commit)
    session.execute = AsyncMock(side_effect=_execute_side)
    session.begin_nested = MagicMock(side_effect=lambda: _NestedTx())
    session.commits = 0  # type: ignore[attr-defined]

    # Defaults — overridden per test via .all_rows / .rowcounts / .firsts
    session.all_rows = []
    session.rowcounts = {}
    session.firsts = {}
    session.default_rowcount = 0
    session.default_first = 0

    def _all_for(sql: str) -> list[Any]:
        if "FROM latest_payload" in sql or "WITH latest_payload" in sql:
            return list(session.all_rows)  # type: ignore[attr-defined]
        return []

    def _rowcount_for(sql: str) -> int:
        for fragment, rc in session.rowcounts.items():  # type: ignore[attr-defined]
            if fragment in sql:
                return rc
        return session.default_rowcount  # type: ignore[attr-defined]

    def _first_for(sql: str) -> int:
        for fragment, val in session.firsts.items():  # type: ignore[attr-defined]
            if fragment in sql:
                return val
        return session.default_first  # type: ignore[attr-defined]

    session.all_for = _all_for  # type: ignore[attr-defined]
    session.rowcount_for = _rowcount_for  # type: ignore[attr-defined]
    session.first_for = _first_for  # type: ignore[attr-defined]
    return session


def _fake_session_cm(session: Any) -> Any:
    @asynccontextmanager
    async def _cm() -> Any:
        yield session

    cm = _cm()
    cm.session = session  # type: ignore[attr-defined]
    return cm


# ----------------------------------------------------------------- argparse


def test_parse_args_defaults_match_spec() -> None:
    args = split_module.parse_args(["--tenant-id", str(_TENANT_UUID)])
    assert args.tenant_id == str(_TENANT_UUID)
    assert args.dry_run is True
    assert args.apply is False
    assert args.max_splits == 100
    assert args.person_uid is None


def test_parse_args_apply_flag_opts_in() -> None:
    args = split_module.parse_args(["--tenant-id", str(_TENANT_UUID), "--apply"])
    assert args.apply is True


def test_parse_args_person_uid_filter() -> None:
    target = str(uuid.uuid4())
    args = split_module.parse_args(
        ["--tenant-id", str(_TENANT_UUID), "--person-uid", target]
    )
    assert args.person_uid == target


def test_parse_args_max_splits_override() -> None:
    args = split_module.parse_args(
        ["--tenant-id", str(_TENANT_UUID), "--max-splits", "5"]
    )
    assert args.max_splits == 5


# ----------------------------------------------------------- bucketing


def test_bucket_pids_groups_same_dob_ssn_together() -> None:
    """Legitimate same-person multi-registration: same DOB + SSN across pids
    must collapse into ONE bucket."""
    pids = [
        split_module._PidInfo(
            patient_id="1461274",
            dob="1972-08-20",
            ssn="602378893",
            given_name="Gaiane",
            family_name="X",
        ),
        split_module._PidInfo(
            patient_id="1462000",
            dob="1972-08-20",
            ssn="602378893",
            given_name="Gaiane",
            family_name="X",
        ),
    ]
    buckets = split_module._bucket_pids(pids)
    assert len(buckets) == 1


def test_bucket_pids_torosyan_shape_two_buckets() -> None:
    """1 Eduard pid (dob 1968, ssn A) + 1 Gaiane pid (dob 1972, ssn B) →
    two buckets."""
    pids = [
        split_module._PidInfo("1460847", "1968-04-19", "623359385", "Eduard", "T"),
        split_module._PidInfo("1461274", "1972-08-20", "602378893", "Gaiane", "T"),
    ]
    buckets = split_module._bucket_pids(pids)
    assert len(buckets) == 2


def test_bucket_pids_perevertov_shape_five_buckets() -> None:
    """5 pids with 5 distinct (dob, ssn) → 5 buckets."""
    pids = [
        split_module._PidInfo(f"100{i}", f"19{50 + i}-01-01", f"111{i}{i}{i}{i}{i}{i}", None, None)
        for i in range(5)
    ]
    buckets = split_module._bucket_pids(pids)
    assert len(buckets) == 5


def test_pick_surviving_prefers_largest_bucket() -> None:
    bucket_a = split_module._Bucket(
        key=("1972-08-20", "602378893"),
        pids=[
            split_module._PidInfo("1461274", "1972-08-20", "602378893", None, None),
            split_module._PidInfo("1462000", "1972-08-20", "602378893", None, None),
        ],
    )
    bucket_b = split_module._Bucket(
        key=("1968-04-19", "623359385"),
        pids=[
            split_module._PidInfo("1460847", "1968-04-19", "623359385", None, None),
        ],
    )
    surviving = split_module._pick_surviving([bucket_a, bucket_b])
    assert surviving.key == bucket_a.key


def test_pick_surviving_tie_break_smallest_patient_id() -> None:
    """Buckets of equal size: the one containing the lexicographically
    smallest patient_id wins."""
    bucket_a = split_module._Bucket(
        key=("1972-08-20", "602378893"),
        pids=[split_module._PidInfo("1003", "1972-08-20", "602378893", None, None)],
    )
    bucket_b = split_module._Bucket(
        key=("1968-04-19", "623359385"),
        pids=[split_module._PidInfo("1001", "1968-04-19", "623359385", None, None)],
    )
    bucket_c = split_module._Bucket(
        key=("1980-01-01", "111111111"),
        pids=[split_module._PidInfo("1002", "1980-01-01", "111111111", None, None)],
    )
    surviving = split_module._pick_surviving([bucket_a, bucket_b, bucket_c])
    # Smallest patient_id is "1001" → bucket_b survives.
    assert surviving.key == bucket_b.key


def test_bucket_pids_partial_null_ssn_joins_unique_matching_dob() -> None:
    """A pid with dob set but ssn null joins a bucket sharing that dob iff
    exactly one such bucket has a non-null ssn for that dob."""
    pids = [
        split_module._PidInfo("100", "1972-08-20", "602378893", None, None),
        split_module._PidInfo("101", "1972-08-20", None, None, None),
    ]
    buckets = split_module._bucket_pids(pids)
    assert len(buckets) == 1


def test_bucket_pids_never_merges_two_different_non_null_dobs() -> None:
    pids = [
        split_module._PidInfo("100", "1972-08-20", "602378893", None, None),
        split_module._PidInfo("101", "1968-04-19", "602378893", None, None),
    ]
    buckets = split_module._bucket_pids(pids)
    assert len(buckets) == 2


# ----------------------------------------------------------- dry-run


@pytest.mark.asyncio
async def test_dry_run_writes_nothing() -> None:
    """--dry-run is the default; no INSERT / UPDATE happens."""
    eduard_gaiane_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            eduard_gaiane_uid,
            ["1460847", "1461274"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "602378893"],
            first_names=["Eduard", "Gaiane"],
            last_names=["T", "T"],
        )
    ]
    cm = _fake_session_cm(session)

    captured_stdout = io.StringIO()
    with redirect_stdout(captured_stdout):
        exit_code = await split_module.main(_args(), session_factory=lambda: cm)

    assert exit_code == 0
    # No session.add() at all -- no new Person, no AccessLog.
    assert session.added == []
    # Only one execute call: the SELECT for candidates. No UPDATEs.
    assert len(session.executed_sql) == 1
    # Plan was printed.
    output = captured_stdout.getvalue()
    assert str(eduard_gaiane_uid) in output


# ----------------------------------------------------------- apply path


@pytest.mark.asyncio
async def test_apply_torosyan_shape_creates_one_new_person_and_audit_row() -> None:
    """1 Gaiane bucket (2 pids) survives; 1 Eduard bucket (1 pid) → 1 new
    person + 1 audit row."""
    from packages.audit.models import AccessLog
    from packages.identity.models import Person

    eduard_gaiane_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            eduard_gaiane_uid,
            ["1460847", "1461274", "1462000"],
            ["1968-04-19", "1972-08-20", "1972-08-20"],
            ["623359385", "602378893", "602378893"],
            first_names=["Eduard", "Gaiane", "Gaiane"],
            last_names=["T", "T", "T"],
        )
    ]
    session.rowcounts = {"UPDATE identity.source_link": 1}
    cm = _fake_session_cm(session)

    exit_code = await split_module.main(_args(apply=True), session_factory=lambda: cm)
    assert exit_code == 0

    new_persons = [o for o in session.added if isinstance(o, Person)]
    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(new_persons) == 1
    assert len(audits) == 1
    # New person carries Eduard's dob+ssn (the non-surviving bucket).
    new_person = new_persons[0]
    assert str(new_person.dob) == "1968-04-19"
    assert new_person.ssn == "623359385"


@pytest.mark.asyncio
async def test_apply_perevertov_shape_creates_four_new_persons() -> None:
    """5 distinct (dob, ssn) buckets, all size 1 → 4 new persons (the
    bucket with the smallest patient_id survives)."""
    from packages.audit.models import AccessLog
    from packages.identity.models import Person

    person_uid = uuid.uuid4()
    pids = [f"100{i}" for i in range(5)]
    dobs: list[str | None] = [f"19{60 + i}-01-01" for i in range(5)]
    ssns: list[str | None] = [f"1{i}{i}{i}{i}{i}{i}{i}{i}" for i in range(5)]

    session = _make_session_recorder()
    session.all_rows = [_row(person_uid, pids, dobs, ssns)]
    session.rowcounts = {"UPDATE identity.source_link": 1}
    cm = _fake_session_cm(session)

    exit_code = await split_module.main(_args(apply=True), session_factory=lambda: cm)
    assert exit_code == 0

    assert len([o for o in session.added if isinstance(o, Person)]) == 4
    assert len([o for o in session.added if isinstance(o, AccessLog)]) == 1


# ------------------------------------------------------- skip / idempotent


@pytest.mark.asyncio
async def test_legitimate_same_person_is_skipped() -> None:
    """Same dob + ssn across pids → 1 bucket → skip."""
    from packages.audit.models import AccessLog
    from packages.identity.models import Person

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1461274", "1462000"],
            ["1972-08-20", "1972-08-20"],
            ["602378893", "602378893"],
        )
    ]
    cm = _fake_session_cm(session)

    exit_code = await split_module.main(_args(apply=True), session_factory=lambda: cm)
    assert exit_code == 0
    # Multi-pid but DOB+SSN consistent → ``_is_mismatch`` returns False, so
    # this person never enters the bucketing/split path. No writes.
    assert [o for o in session.added if isinstance(o, Person)] == []
    assert [o for o in session.added if isinstance(o, AccessLog)] == []


@pytest.mark.asyncio
async def test_idempotent_on_clean_persons() -> None:
    """No multi-link persons in audit → no writes."""
    session = _make_session_recorder()
    session.all_rows = []  # audit query returns nothing
    cm = _fake_session_cm(session)

    exit_code = await split_module.main(_args(apply=True), session_factory=lambda: cm)
    assert exit_code == 0
    assert session.added == []


# ----------------------------------------------------------- caps + filter


@pytest.mark.asyncio
async def test_max_splits_caps_processing() -> None:
    from packages.identity.models import Person

    rows = []
    for _ in range(10):
        pid_base = uuid.uuid4().int % 1000
        rows.append(
            _row(
                uuid.uuid4(),
                [f"{pid_base}0", f"{pid_base}1"],
                ["1968-04-19", "1972-08-20"],
                ["623359385", "602378893"],
            )
        )
    session = _make_session_recorder()
    session.all_rows = rows
    session.rowcounts = {"UPDATE identity.source_link": 1}
    cm = _fake_session_cm(session)

    exit_code = await split_module.main(
        _args(apply=True, max_splits=3), session_factory=lambda: cm
    )
    assert exit_code == 0
    # 3 wrong-merged persons processed → exactly 3 new persons created.
    assert len([o for o in session.added if isinstance(o, Person)]) == 3


@pytest.mark.asyncio
async def test_person_uid_filter_processes_only_target() -> None:
    from packages.identity.models import Person

    target = uuid.uuid4()
    other_a = uuid.uuid4()
    other_b = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(other_a, ["1", "2"], ["1968-04-19", "1972-08-20"], ["A", "B"]),
        _row(target, ["3", "4"], ["1968-04-19", "1972-08-20"], ["A", "B"]),
        _row(other_b, ["5", "6"], ["1968-04-19", "1972-08-20"], ["A", "B"]),
    ]
    session.rowcounts = {"UPDATE identity.source_link": 1}
    cm = _fake_session_cm(session)

    exit_code = await split_module.main(
        _args(apply=True, person_uid=str(target)),
        session_factory=lambda: cm,
    )
    assert exit_code == 0
    # Only the target gets split → exactly 1 new Person.
    assert len([o for o in session.added if isinstance(o, Person)]) == 1


# ----------------------------------------------------------- audit row shape


@pytest.mark.asyncio
async def test_audit_row_contains_only_uuids_and_counts_no_phi() -> None:
    """The audit row's ``extra`` carries surviving + new uuids + counts ONLY.
    No dob, no ssn, no name, no patient_id values."""
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1460847", "1461274"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "602378893"],
            first_names=["Eduard", "Gaiane"],
            last_names=["T", "T"],
        )
    ]
    session.rowcounts = {"UPDATE identity.source_link": 1}
    cm = _fake_session_cm(session)

    await split_module.main(_args(apply=True), session_factory=lambda: cm)
    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 1
    audit = audits[0]
    assert audit.action == "identity.person.split"
    extra = audit.extra
    assert "surviving_person_uid" in extra
    assert "new_person_uids" in extra
    assert "bucket_count" in extra
    assert "source_links_moved" in extra
    # The extra serialised as a string must NOT contain any PHI values.
    serialised = str(extra)
    assert "1968-04-19" not in serialised
    assert "1972-08-20" not in serialised
    assert "623359385" not in serialised
    assert "602378893" not in serialised
    assert "Eduard" not in serialised
    assert "Gaiane" not in serialised
    # patient_ids are CareStack non-PII references, but the spec says
    # "uuids + counts only" -- they must not appear either.
    assert "1460847" not in serialised
    assert "1461274" not in serialised


# ---------------------------------------------- downstream repoint


@pytest.mark.asyncio
async def test_interaction_event_repoint_issued_per_bucket() -> None:
    """For each non-surviving bucket, an UPDATE against
    ``interaction.event`` is issued so CS-traceable timeline rows follow
    the patient_ids that left. Round 2: also asserts the NEW person's
    UUID is bound into the executed statement's params (not just the
    SQL text)."""
    from packages.identity.models import Person

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1460847", "1461274"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "602378893"],
        )
    ]
    session.rowcounts = {
        "UPDATE identity.source_link": 1,
        "UPDATE interaction.event": 2,
    }
    cm = _fake_session_cm(session)

    await split_module.main(_args(apply=True), session_factory=lambda: cm)

    # 1. One UPDATE per non-surviving bucket (Torosyan shape → 1 bucket).
    update_calls = [
        (sql, params)
        for sql, params in zip(session.executed_sql, session.executed_params, strict=False)
        if "UPDATE interaction.event" in sql
    ]
    assert len(update_calls) == 1

    # 2. The NEW person's UUID was bound into the executed params, not
    #    just present in the SQL text. Round 2 fix: previous assertion
    #    only checked the SQL string and would have passed even if the
    #    UUID never actually reached the database.
    new_persons = [o for o in session.added if isinstance(o, Person)]
    assert len(new_persons) == 1
    new_uid = str(new_persons[0].id)
    _, params = update_calls[0]
    assert params.get("new_person_uid") == new_uid

    # 3. The non-surviving bucket's patient_id is bound into the params.
    #    Both buckets are size 1 → lexicographic tie-break: "1460847"
    #    survives; "1461274" moves to the new person.
    assert "1461274" in params.get("patient_ids", [])
    assert "1460847" not in params.get("patient_ids", [])


@pytest.mark.asyncio
async def test_ops_consultation_repoint_issued_per_bucket() -> None:
    """``ops.consultation`` has a clean patient_id trace via
    ``raw_event_id → ingest.raw_event.payload->>'patientId'``. For each
    non-surviving bucket, an UPDATE against ``ops.consultation`` is
    issued; the NEW person's UUID and the bucket's patient_ids are bound
    into the executed params."""
    from packages.identity.models import Person

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1460847", "1461274"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "602378893"],
        )
    ]
    session.rowcounts = {
        "UPDATE identity.source_link": 1,
        "UPDATE interaction.event": 0,
        "UPDATE ops.consultation": 3,
    }
    cm = _fake_session_cm(session)

    await split_module.main(_args(apply=True), session_factory=lambda: cm)

    update_calls = [
        (sql, params)
        for sql, params in zip(session.executed_sql, session.executed_params, strict=False)
        if "UPDATE ops.consultation" in sql
    ]
    assert len(update_calls) == 1

    new_persons = [o for o in session.added if isinstance(o, Person)]
    assert len(new_persons) == 1
    new_uid = str(new_persons[0].id)

    sql, params = update_calls[0]
    # Joined through raw_event payload's patientId (camelCase) with a
    # PascalCase fallback for either form CareStack sends.
    assert "payload->>'patientId'" in sql
    assert "PatientId" in sql
    assert "carestack.appointment.upsert" in sql
    assert params.get("new_person_uid") == new_uid
    assert params.get("surviving_person_uid") == str(person_uid)
    # Lexicographic tie-break: "1460847" survives → "1461274" moves.
    assert "1461274" in params.get("patient_ids", [])
    assert "1460847" not in params.get("patient_ids", [])


@pytest.mark.asyncio
async def test_ops_consultation_repoint_counts_into_audit_row() -> None:
    """The audit row's ``extra`` carries the consultations_moved count
    surfaced by ``_repoint_ops_consultations``. Counts only -- no PHI."""
    from packages.audit.models import AccessLog

    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1460847", "1461274"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "602378893"],
        )
    ]
    session.rowcounts = {
        "UPDATE identity.source_link": 1,
        "UPDATE interaction.event": 2,
        "UPDATE ops.consultation": 5,
    }
    cm = _fake_session_cm(session)

    await split_module.main(_args(apply=True), session_factory=lambda: cm)

    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 1
    audit = audits[0]
    extra = audit.extra
    # Both downstream-repoint counts are surfaced in the audit row.
    assert extra["interaction_events_moved"] == 2
    assert extra["consultations_moved"] == 5


@pytest.mark.asyncio
async def test_followup_task_and_location_profile_kept_in_manual_review() -> None:
    """``ops.followup_task`` and ``ops.person_location_profile`` STAY on
    the surviving person -- they have no clean patient_id trace
    (followup_task has no source columns; person_location_profile is an
    aggregate row whose move would orphan the surviving person's
    profile at that location). They are counted by the manual-review
    SELECT and NEVER mutated by an UPDATE from this script."""
    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1460847", "1461274"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "602378893"],
        )
    ]
    session.rowcounts = {"UPDATE identity.source_link": 1}
    cm = _fake_session_cm(session)

    await split_module.main(_args(apply=True), session_factory=lambda: cm)

    # No UPDATE against followup_task or person_location_profile.
    assert not any("UPDATE ops.followup_task" in sql for sql in session.executed_sql)
    assert not any(
        "UPDATE ops.person_location_profile" in sql for sql in session.executed_sql
    )
    # Both tables ARE referenced from the manual-review COUNT SELECT.
    nm_select = [s for s in session.executed_sql if "needs_manual_review" in s]
    assert len(nm_select) == 1
    assert "ops.followup_task" in nm_select[0]
    assert "ops.person_location_profile" in nm_select[0]


@pytest.mark.asyncio
async def test_ops_lead_not_repointed_kept_in_manual_review() -> None:
    """``ops.lead`` is Salesforce-origin and predates any CareStack
    patient. It STAYS on the surviving person. The script must NEVER
    issue an UPDATE against ``ops.lead`` and must count it in the
    manual-review SELECT."""
    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1460847", "1461274"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "602378893"],
        )
    ]
    session.rowcounts = {"UPDATE identity.source_link": 1}
    cm = _fake_session_cm(session)

    await split_module.main(_args(apply=True), session_factory=lambda: cm)

    assert not any("UPDATE ops.lead" in sql for sql in session.executed_sql)
    nm_select = [s for s in session.executed_sql if "needs_manual_review" in s]
    assert len(nm_select) == 1
    assert "ops.lead" in nm_select[0]


# ----------------------------------------------------------- savepoint isolation


@pytest.mark.asyncio
async def test_per_person_savepoint_isolates_failure() -> None:
    """A single failing person does NOT abort the batch.

    Persons A and C split successfully; person B's flush raises during
    ``_create_new_person`` (simulating a transient DB hiccup). The
    per-person ``session.begin_nested()`` SAVEPOINT rolls B back; the
    outer batch continues. Verified by:

    1. ``main`` returns exit_code 0 (the batch survived).
    2. Two audit rows exist (one each for A and C); none for B
       (B's ``_write_audit_row`` call is never reached because flush
       raised earlier in ``_apply_split``).
    3. ``begin_nested`` was entered 3 times; B's savepoint was
       ``rolled_back``; A and C's were ``released``.
    """
    from packages.audit.models import AccessLog

    uid_a, uid_b, uid_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(uid_a, ["1", "2"], ["1968-04-19", "1972-08-20"], ["A1", "B1"]),
        _row(uid_b, ["3", "4"], ["1968-04-19", "1972-08-20"], ["A2", "B2"]),
        _row(uid_c, ["5", "6"], ["1968-04-19", "1972-08-20"], ["A3", "B3"]),
    ]
    session.rowcounts = {"UPDATE identity.source_link": 1}

    # Patch flush to raise on the 2nd call (B's _create_new_person flush).
    # Torosyan-shape: each candidate has 1 non-surviving bucket → 1 flush.
    original_flush_side = session.flush.side_effect
    flush_call_count = {"n": 0}

    async def _flush_with_b_failure() -> None:
        flush_call_count["n"] += 1
        if flush_call_count["n"] == 2:
            raise RuntimeError("simulated transient DB hiccup")
        await original_flush_side()

    session.flush = AsyncMock(side_effect=_flush_with_b_failure)
    cm = _fake_session_cm(session)

    exit_code = await split_module.main(_args(apply=True), session_factory=lambda: cm)
    assert exit_code == 0  # batch survived

    # 2 audit rows -- A and C succeeded; B never reached _write_audit_row.
    audits = [o for o in session.added if isinstance(o, AccessLog)]
    assert len(audits) == 2
    audit_uids = {str(a.person_uid) for a in audits}
    assert str(uid_a) in audit_uids
    assert str(uid_c) in audit_uids
    assert str(uid_b) not in audit_uids

    # Savepoint lifecycle: 3 begin_nested entries; the middle one rolled
    # back; the other two were released.
    assert len(session.savepoints) == 3
    assert session.savepoints[0]["status"] == "released"
    assert session.savepoints[1]["status"] == "rolled_back"
    assert session.savepoints[2]["status"] == "released"


@pytest.mark.asyncio
async def test_needs_manual_review_counted_per_split() -> None:
    """A non-zero needs_manual_review count from the surviving person's
    downstream rows is surfaced in the run summary (no PHI in logs)."""
    person_uid = uuid.uuid4()
    session = _make_session_recorder()
    session.all_rows = [
        _row(
            person_uid,
            ["1460847", "1461274"],
            ["1968-04-19", "1972-08-20"],
            ["623359385", "602378893"],
        )
    ]
    session.rowcounts = {"UPDATE identity.source_link": 1}
    session.firsts = {"needs_manual_review": 7}
    cm = _fake_session_cm(session)

    exit_code = await split_module.main(_args(apply=True), session_factory=lambda: cm)
    assert exit_code == 0
    # The needs-manual-review SELECT was issued.
    nm_calls = [s for s in session.executed_sql if "needs_manual_review" in s]
    assert len(nm_calls) == 1
