"""SQL-shape + behaviour tests for the household resolver (ENG-310).

``IngestRepository.person_household_members`` is what powers the
"Household / shared contact" section on the staff person card. The
contract we lock in:

* Tenant scoping is in the SQL.
* The household key is normalised phone OR email — **NEVER**
  ``accountId``. A test grep-asserts the compiled SQL string does not
  reference ``accountId``.
* The resolver reads the verbatim ``carestack.patient.upsert`` payload,
  not ``identity.person_identifier`` (PersonIdentifier has a global
  ``UNIQUE(kind, value)`` constraint that puts a shared phone on a
  single Person row after ENG-311).
* Self person is excluded; results are deduped by sibling person_uid.
* Empty input (no CareStack pids on this person) short-circuits.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from packages.core.types import TenantId
from packages.ingest.repository import IngestRepository


def _compile_sql(stmt: Any) -> str:
    compiled = stmt.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    return str(compiled)


def _session_recording(plan: list[Any]) -> tuple[MagicMock, list[Any]]:
    """Return a MagicMock session that returns rows from ``plan`` in order.

    Each item in ``plan`` is the iterable of "rows" that the next
    ``await session.execute(stmt)`` call should return via ``.all()``.
    """
    captured: list[Any] = []
    queue: list[Any] = list(plan)

    async def fake_execute(stmt: Any) -> Any:
        captured.append(stmt)
        rows = queue.pop(0) if queue else []
        result = MagicMock()
        result.all.return_value = list(rows)
        result.scalars.return_value = MagicMock()
        result.scalars.return_value.all.return_value = list(rows)
        return result

    session = MagicMock()
    session.execute = fake_execute
    return session, captured


@pytest.mark.asyncio
async def test_household_members_short_circuits_when_person_has_no_cs_links() -> None:
    """No CareStack source_links on this person → empty list, ONE SELECT
    against ``source_link`` and nothing else.
    """
    session, captured = _session_recording([[]])  # source_link returns no pids
    repo = IngestRepository(session)
    out = await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())
    assert out == []
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_household_query_never_uses_accountid() -> None:
    """Hard constraint: the household key is phone/email; ``accountId``
    is forbidden because it is a clinic-level default value worth
    ~55K patients. Test asserts the compiled SQL across every
    statement issued by the resolver never references the column.
    """
    plan: list[Any] = [
        # 1. self source_link → pids
        [("PT-1",)],
        # 2. self latest patient.upsert payload → phones+email
        [
            SimpleNamespace(
                mobile="(916) 215-4258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email="self@example.com",
            )
        ],
        # 3. candidate patient.upsert rows
        [
            SimpleNamespace(
                patient_id="PT-2",
                mobile="916-215-4258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
                first_name="Aram",
                last_name="Torosyan",
            )
        ],
        # 4. sibling source_link → person_uid
        [SimpleNamespace(source_id="PT-2", person_uid=uuid.uuid4())],
        # 5. identity.person name lookup
        [],
    ]
    session, captured = _session_recording(plan)
    repo = IngestRepository(session)
    await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())

    compiled = "\n".join(_compile_sql(stmt).lower() for stmt in captured)
    # The household key NEVER comes from accountId.
    assert "accountid" not in compiled, (
        "household resolver must not reference accountId — "
        "value 10762 is a clinic-level default with ~55K rows"
    )


@pytest.mark.asyncio
async def test_household_query_reads_phone_and_email_payload_paths() -> None:
    """SQL must read mobile / phoneWithExt / workPhoneWithExt + email
    from the latest patient.upsert payload. That's where the household
    signal lives.
    """
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile="(916) 215-4258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email="self@example.com",
            )
        ],
        [],
        [],
        [],
    ]
    session, captured = _session_recording(plan)
    repo = IngestRepository(session)
    await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())

    compiled = "\n".join(_compile_sql(stmt).lower() for stmt in captured)
    # The candidate query references the four payload fields by name.
    assert "'mobile'" in compiled
    assert "'phonewithext'" in compiled
    assert "'workphonewithext'" in compiled
    assert "'email'" in compiled
    # And the patient.upsert event type.
    assert "patient.upsert" in compiled
    # The phone pre-filter MUST strip non-digits from the payload before
    # the LIKE — CareStack stores formatted phones like "(916) 215-4258",
    # so a digit-only last-7 ("2154258") would otherwise never match.
    # Regression guard for the household-link-empty bug found on real data.
    assert "regexp_replace" in compiled


@pytest.mark.asyncio
async def test_household_query_is_tenant_scoped_in_sql() -> None:
    """Every SELECT must filter ``raw_event.tenant_id`` AND
    ``source_link.tenant_id`` — household lookups must NEVER cross
    tenants.
    """
    tenant_id = TenantId(uuid.uuid4())
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
            )
        ],
        [],
        [],
        [],
    ]
    session, captured = _session_recording(plan)
    repo = IngestRepository(session)
    await repo.person_household_members(tenant_id, uuid.uuid4())

    for stmt in captured:
        compiled = _compile_sql(stmt).lower()
        assert "tenant_id" in compiled


@pytest.mark.asyncio
async def test_household_excludes_self_person_uid() -> None:
    """The sibling-link query must filter out the input person_uid so
    the requester never appears in their own household list.
    """
    self_uid = uuid.uuid4()
    sibling_uid = uuid.uuid4()
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
            )
        ],
        [
            SimpleNamespace(
                patient_id="PT-2",
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
                first_name="Aram",
                last_name="Torosyan",
            )
        ],
        [SimpleNamespace(source_id="PT-2", person_uid=sibling_uid)],
        [],
    ]
    session, captured = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members(TenantId(uuid.uuid4()), self_uid)

    # Result contains the sibling, not self.
    assert len(out) == 1
    assert out[0]["person_uid"] == str(sibling_uid)
    assert out[0]["person_uid"] != str(self_uid)

    # The sibling-link SELECT must also explicitly filter ``person_uid !=
    # :self_uid``. We grep the SQL string for the self UID literal.
    sibling_stmt_sql = _compile_sql(captured[3])
    assert str(self_uid) in sibling_stmt_sql


@pytest.mark.asyncio
async def test_household_phone_match_returns_masked_last4() -> None:
    """Phone-shared sibling: ``shared_via='phone'`` and
    ``shared_value_masked='···4258'``.
    """
    sibling_uid = uuid.uuid4()
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile="(916) 215-4258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
            )
        ],
        [
            SimpleNamespace(
                patient_id="PT-2",
                mobile="916-215-4258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
                first_name="Aram",
                last_name="Torosyan",
            )
        ],
        [SimpleNamespace(source_id="PT-2", person_uid=sibling_uid)],
        [],
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())

    assert len(out) == 1
    assert out[0]["shared_via"] == "phone"
    assert out[0]["shared_value_masked"] == "···4258"
    assert out[0]["display_name"] == "Aram Torosyan"


@pytest.mark.asyncio
async def test_household_email_match_returns_masked_local_part() -> None:
    """Email-shared sibling: ``shared_via='email'`` and
    ``shared_value_masked='g···@gmail.com'`` (first char + ``···`` +
    domain). Phones with fewer than 7 digits would be invalid so we
    only seed email here.
    """
    sibling_uid = uuid.uuid4()
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile=None,
                phone_with_ext=None,
                work_phone_with_ext=None,
                email="gaiane@gmail.com",
            )
        ],
        [
            SimpleNamespace(
                patient_id="PT-2",
                mobile=None,
                phone_with_ext=None,
                work_phone_with_ext=None,
                email="Gaiane@Gmail.com",
                first_name=None,
                last_name=None,
            )
        ],
        [SimpleNamespace(source_id="PT-2", person_uid=sibling_uid)],
        [],
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())

    assert len(out) == 1
    assert out[0]["shared_via"] == "email"
    assert out[0]["shared_value_masked"] == "g···@gmail.com"


@pytest.mark.asyncio
async def test_household_both_phone_and_email_match_returns_both() -> None:
    """When BOTH a phone and an email match, ``shared_via='both'``."""
    sibling_uid = uuid.uuid4()
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email="self@example.com",
            )
        ],
        [
            SimpleNamespace(
                patient_id="PT-2",
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email="self@example.com",
                first_name="Aram",
                last_name="Torosyan",
            )
        ],
        [SimpleNamespace(source_id="PT-2", person_uid=sibling_uid)],
        [],
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())

    assert len(out) == 1
    assert out[0]["shared_via"] == "both"


@pytest.mark.asyncio
async def test_household_dedup_by_sibling_person_uid() -> None:
    """A sibling person with multiple matching pids must surface ONCE,
    not once per pid.
    """
    sibling_uid = uuid.uuid4()
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
            )
        ],
        [
            SimpleNamespace(
                patient_id="PT-2",
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
                first_name="Aram",
                last_name="Torosyan",
            ),
            SimpleNamespace(
                patient_id="PT-3",
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
                first_name="Aram",
                last_name="Torosyan",
            ),
        ],
        [
            SimpleNamespace(source_id="PT-2", person_uid=sibling_uid),
            SimpleNamespace(source_id="PT-3", person_uid=sibling_uid),
        ],
        [],
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())

    assert len(out) == 1
    assert out[0]["person_uid"] == str(sibling_uid)


@pytest.mark.asyncio
async def test_household_uses_identity_person_name_when_present() -> None:
    """When ``identity.person`` has a given/family name for the
    sibling, prefer that over the CareStack payload firstName/lastName.
    """
    sibling_uid = uuid.uuid4()
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
            )
        ],
        [
            SimpleNamespace(
                patient_id="PT-2",
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
                first_name="OldFirst",
                last_name="OldLast",
            )
        ],
        [SimpleNamespace(source_id="PT-2", person_uid=sibling_uid)],
        [
            SimpleNamespace(
                id=sibling_uid,
                given_name="Gaiane",
                family_name="Torosyan",
                display_name=None,
            )
        ],
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())

    assert len(out) == 1
    assert out[0]["display_name"] == "Gaiane Torosyan"


@pytest.mark.asyncio
async def test_household_no_self_phones_or_emails_returns_empty() -> None:
    """If THIS person's latest patient.upsert payload has no usable
    phone and no usable email, there's nothing to match against → ``[]``.
    """
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile=None,
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
            )
        ],
    ]
    session, captured = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())
    assert out == []
    # No candidate query was issued (only the two pre-flight SELECTs).
    assert len(captured) == 2


@pytest.mark.asyncio
async def test_household_payload_name_fallback_when_identity_has_none() -> None:
    """If identity.person has no name for the sibling, fall back to the
    CareStack payload ``firstName + lastName``.
    """
    sibling_uid = uuid.uuid4()
    plan: list[Any] = [
        [("PT-1",)],
        [
            SimpleNamespace(
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
            )
        ],
        [
            SimpleNamespace(
                patient_id="PT-2",
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
                first_name="Eduard",
                last_name="Karionov",
            )
        ],
        [SimpleNamespace(source_id="PT-2", person_uid=sibling_uid)],
        [],  # identity.person returns nothing
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())

    assert len(out) == 1
    assert out[0]["display_name"] == "Eduard Karionov"


# --- Symmetry: A-shows-B implies B-shows-A. The resolver is symmetric
#     by construction (both sides read the same normalised phone/email
#     sets from the same payload field), but we still exercise the
#     pair to lock in the invariant.

@pytest.mark.asyncio
async def test_household_symmetry_a_to_b_and_b_to_a() -> None:
    """If A sees B in its household, then running the resolver from B's
    side surfaces A. Each call returns exactly the other party (not
    self).
    """
    uid_a = uuid.uuid4()
    uid_b = uuid.uuid4()
    # A → B
    plan_a_to_b: list[Any] = [
        [("PT-A",)],
        [
            SimpleNamespace(
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
            )
        ],
        [
            SimpleNamespace(
                patient_id="PT-B",
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
                first_name="B",
                last_name="One",
            )
        ],
        [SimpleNamespace(source_id="PT-B", person_uid=uid_b)],
        [],
    ]
    session_a, _ = _session_recording(plan_a_to_b)
    repo_a = IngestRepository(session_a)
    out_a = await repo_a.person_household_members(TenantId(uuid.uuid4()), uid_a)
    assert [m["person_uid"] for m in out_a] == [str(uid_b)]

    # B → A (mirror)
    plan_b_to_a: list[Any] = [
        [("PT-B",)],
        [
            SimpleNamespace(
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
            )
        ],
        [
            SimpleNamespace(
                patient_id="PT-A",
                mobile="9162154258",
                phone_with_ext=None,
                work_phone_with_ext=None,
                email=None,
                first_name="A",
                last_name="One",
            )
        ],
        [SimpleNamespace(source_id="PT-A", person_uid=uid_a)],
        [],
    ]
    session_b, _ = _session_recording(plan_b_to_a)
    repo_b = IngestRepository(session_b)
    out_b = await repo_b.person_household_members(TenantId(uuid.uuid4()), uid_b)
    assert [m["person_uid"] for m in out_b] == [str(uid_a)]


@pytest.mark.asyncio
async def test_origin_aggregator_returns_first_last_name_per_pid() -> None:
    """ENG-310 A: the per-pid CareStack origin rows must surface
    ``first_name`` / ``last_name`` from the latest patient.upsert
    payload — the multi-link expander label depends on them.
    """
    session, _ = _session_recording(
        [
            [],
            [],
            [
                SimpleNamespace(
                    patient_id="1461274",
                    default_location_id=None,
                    default_provider_id=None,
                    city=None,
                    state=None,
                    first_name="Gaiane",
                    last_name="Torosyan",
                    dob=None,
                    gender=None,
                    marital_status=None,
                    mobile=None,
                    phone_with_ext=None,
                    work_phone_with_ext=None,
                    email=None,
                    address_line1=None,
                    address_line2=None,
                    address_zip=None,
                    patient_identifier=None,
                    account_id=None,
                )
            ],
        ]
    )
    repo = IngestRepository(session)
    out = await repo.person_carestack_origin_context(
        TenantId(uuid.uuid4()), ["1461274"]
    )
    assert out["1461274"]["first_name"] == "Gaiane"
    assert out["1461274"]["last_name"] == "Torosyan"


@pytest.mark.asyncio
async def test_origin_aggregator_returns_patient_details_fields() -> None:
    """ENG-310 B: the per-pid origin rows must surface DOB / gender /
    phones / email / full address / patientIdentifier / accountId.
    The Patient details click-to-reveal panel reads them.
    """
    session, _ = _session_recording(
        [
            [],
            [],
            [
                SimpleNamespace(
                    patient_id="1461274",
                    default_location_id=None,
                    default_provider_id=None,
                    city="El Dorado Hills",
                    state="CA",
                    first_name="Gaiane",
                    last_name="Torosyan",
                    dob="1980-03-12",
                    gender="Female",
                    marital_status="Married",
                    mobile="(916) 215-4258",
                    phone_with_ext="(916) 555-0123 x42",
                    work_phone_with_ext=None,
                    email="gaiane@gmail.com",
                    address_line1="123 Oak St",
                    address_line2="Apt 4",
                    address_zip="95762",
                    patient_identifier="MRN-12345",
                    account_id="10762",
                )
            ],
        ]
    )
    repo = IngestRepository(session)
    out = await repo.person_carestack_origin_context(
        TenantId(uuid.uuid4()), ["1461274"]
    )
    row = out["1461274"]
    assert row["dob"] == "1980-03-12"
    assert row["gender"] == "Female"
    assert row["marital_status"] == "Married"
    assert row["mobile"] == "(916) 215-4258"
    assert row["phone_with_ext"] == "(916) 555-0123 x42"
    assert row["email"] == "gaiane@gmail.com"
    assert row["address_line1"] == "123 Oak St"
    assert row["address_line2"] == "Apt 4"
    assert row["address_zip"] == "95762"
    assert row["patient_identifier"] == "MRN-12345"
    assert row["account_id"] == "10762"


def test_module_unused() -> None:
    """Force the datetime import to register so static analysers do not
    strip it; we use it in fixture seeds elsewhere in this suite."""
    assert datetime(2026, 1, 1, tzinfo=UTC) is not None


@pytest.mark.asyncio
async def test_household_by_identifier_links_cross_form_phone_siblings() -> None:
    """ENG-463: the identity.person_identifier resolver links two persons
    sharing a number stored in different forms (10-digit vs 11-digit) via
    a last-7-digit match — the Salesforce-lead household case the
    CareStack-payload resolver misses."""
    sibling = uuid.uuid4()
    plan: list[Any] = [
        # 1. self identifiers (kind, value)
        [("phone", "9258125438"), ("email", "self@example.com")],
        # 2. candidate person_identifier rows (person_id, kind, value)
        [(sibling, "phone", "19258125438")],
        # 3. sibling identity.person names
        [
            SimpleNamespace(
                id=sibling,
                given_name="Fredrick",
                family_name="Dixon",
                display_name=None,
            )
        ],
    ]
    session, _captured = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members_by_identifier(
        TenantId(uuid.uuid4()), uuid.uuid4()
    )
    assert out == [
        {
            "person_uid": str(sibling),
            "display_name": "Fredrick Dixon",
            "shared_via": "phone",
            "shared_value_masked": "···5438",
        }
    ]


# --- ENG-542: hint-based household resolver (Salesforce-lead siblings whose
#     shared phone was never persisted as an identifier). ---


@pytest.mark.asyncio
async def test_household_by_hint_short_circuits_without_self_values() -> None:
    """No phone/email in either person_identifier or hints → empty, exactly
    the two pre-flight SELECTs (self identifiers + self hints)."""
    session, captured = _session_recording([[], []])
    repo = IngestRepository(session)
    out = await repo.person_household_members_by_hint(
        TenantId(uuid.uuid4()), uuid.uuid4()
    )
    assert out == []
    assert len(captured) == 2


@pytest.mark.asyncio
async def test_household_by_hint_surfaces_lead_only_sibling() -> None:
    """The Patrick↔duplicate case: self holds the phone as an IDENTIFIER, the
    non-merged sibling holds the byte-identical phone only in a hint. The
    sibling surfaces with a masked last-4 and its identity.person name."""
    sibling = uuid.uuid4()
    plan: list[Any] = [
        # 1. self person_identifier (kind, value)
        [("phone", "+19167307719")],
        # 2. self hints (phone_normalized, email_normalized)
        [],
        # 3. hint-side siblings (person_uid, phone_normalized, email_normalized)
        [(sibling, "+19167307719", None)],
        # 4. identifier-side siblings (person_id, kind, value)
        [],
        # 5. identity.person name lookup
        [
            SimpleNamespace(
                id=sibling,
                given_name="Lead",
                family_name="Duplicate",
                display_name=None,
            )
        ],
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members_by_hint(
        TenantId(uuid.uuid4()), uuid.uuid4()
    )
    assert out == [
        {
            "person_uid": str(sibling),
            "display_name": "Lead Duplicate",
            "shared_via": "phone",
            "shared_value_masked": "···7719",
        }
    ]


@pytest.mark.asyncio
async def test_household_by_hint_excludes_self_and_is_tenant_scoped() -> None:
    """The sibling search filters ``person_uid != self`` and every statement
    is tenant-scoped in the compiled SQL."""
    self_uid = uuid.uuid4()
    sibling = uuid.uuid4()
    plan: list[Any] = [
        [("phone", "+19167307719")],
        [],
        [(sibling, "+19167307719", None)],
        [],
        [SimpleNamespace(id=sibling, given_name="A", family_name="B", display_name=None)],
    ]
    session, captured = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members_by_hint(
        TenantId(uuid.uuid4()), self_uid
    )
    assert [m["person_uid"] for m in out] == [str(sibling)]
    for stmt in captured:
        assert "tenant_id" in _compile_sql(stmt).lower()
    # The hint sibling SELECT references the hint table + the self uid filter.
    hint_sib_sql = _compile_sql(captured[2]).lower()
    assert "normalized_person_hint" in hint_sib_sql
    assert "source_link" in hint_sib_sql
    assert str(self_uid) in _compile_sql(captured[2])


@pytest.mark.asyncio
async def test_household_by_hint_email_match_masks_local_part() -> None:
    """Email-only shared sibling: ``shared_via='email'`` with masked local."""
    sibling = uuid.uuid4()
    plan: list[Any] = [
        [],  # no self identifiers
        [(None, "shared@gmail.com")],  # self hint carries the email
        [(sibling, None, "Shared@Gmail.com")],  # sibling hint (mixed case)
        [],
        [SimpleNamespace(id=sibling, given_name=None, family_name=None, display_name=None)],
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members_by_hint(
        TenantId(uuid.uuid4()), uuid.uuid4()
    )
    assert len(out) == 1
    assert out[0]["shared_via"] == "email"
    assert out[0]["shared_value_masked"] == "s···@gmail.com"


@pytest.mark.asyncio
async def test_household_by_hint_phone_wins_over_email_for_same_sibling() -> None:
    """When a sibling matches on both an email (hint) and a phone (identifier),
    the phone label wins."""
    sibling = uuid.uuid4()
    plan: list[Any] = [
        [("phone", "+19167307719"), ("email", "shared@x.com")],
        [],
        [(sibling, None, "shared@x.com")],  # hint side: email match
        [(sibling, "phone", "+19167307719")],  # identifier side: phone match
        [SimpleNamespace(id=sibling, given_name="P", family_name="W", display_name=None)],
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members_by_hint(
        TenantId(uuid.uuid4()), uuid.uuid4()
    )
    assert len(out) == 1
    assert out[0]["shared_via"] == "phone"
    assert out[0]["shared_value_masked"] == "···7719"


@pytest.mark.asyncio
async def test_household_by_identifier_short_circuits_without_identifiers() -> None:
    """Person with no phone/email identifiers → no candidate query."""
    session, captured = _session_recording([[]])  # self identifiers empty
    repo = IngestRepository(session)
    out = await repo.person_household_members_by_identifier(
        TenantId(uuid.uuid4()), uuid.uuid4()
    )
    assert out == []
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_household_by_identifier_drops_last7_false_positive() -> None:
    """Two unrelated numbers sharing the last 7 digits must NOT link: the
    last-7 SQL filter is confirmed in Python by full E.164 equality."""
    sibling = uuid.uuid4()
    plan: list[Any] = [
        [("phone", "415-555-1234")],  # self → +14155551234
        [(sibling, "phone", "212-555-1234")],  # same last-7, different number
    ]
    session, _ = _session_recording(plan)
    repo = IngestRepository(session)
    out = await repo.person_household_members_by_identifier(
        TenantId(uuid.uuid4()), uuid.uuid4()
    )
    assert out == []


@pytest.mark.asyncio
async def test_household_by_identifier_candidate_sql_shape() -> None:
    """Candidate query is tenant-scoped and matches on right(regexp_replace
    (value),7) — the last-7-digit pre-filter."""
    sibling = uuid.uuid4()
    plan: list[Any] = [
        [("phone", "9258125438")],
        [(sibling, "phone", "19258125438")],
        [SimpleNamespace(id=sibling, given_name="A", family_name="B", display_name=None)],
    ]
    session, captured = _session_recording(plan)
    repo = IngestRepository(session)
    await repo.person_household_members_by_identifier(
        TenantId(uuid.uuid4()), uuid.uuid4()
    )
    candidate_sql = _compile_sql(captured[1]).lower()
    assert "regexp_replace" in candidate_sql
    assert "right(" in candidate_sql
    assert "tenant_id" in candidate_sql
    assert "person_identifier" in candidate_sql


@pytest.mark.asyncio
async def test_service_household_unions_and_dedups_carestack_wins() -> None:
    """Service unions the CareStack-payload + identifier resolvers, deduped
    by sibling person_uid with the CareStack row winning on conflict."""
    from unittest.mock import AsyncMock

    from packages.ingest.service import IngestService

    shared = str(uuid.uuid4())
    other = str(uuid.uuid4())
    svc = IngestService(MagicMock())
    svc._repo = MagicMock()  # type: ignore[attr-defined]
    svc._repo.person_household_members = AsyncMock(
        return_value=[
            {
                "person_uid": shared,
                "display_name": "CareStack Name",
                "shared_via": "phone",
                "shared_value_masked": "···1111",
            }
        ]
    )
    svc._repo.person_household_members_by_identifier = AsyncMock(
        return_value=[
            {
                "person_uid": shared,  # duplicate → CareStack wins
                "display_name": "Identifier Name",
                "shared_via": "email",
                "shared_value_masked": "i···@x.com",
            },
            {
                "person_uid": other,
                "display_name": "SF Lead Sibling",
                "shared_via": "phone",
                "shared_value_masked": "···5438",
            },
        ]
    )
    svc._repo.person_household_members_by_hint = AsyncMock(return_value=[])
    out = await svc.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())
    by_uid = {o.person_uid: o for o in out}
    assert set(by_uid) == {shared, other}
    assert by_uid[shared].display_name == "CareStack Name"  # CareStack won
    assert by_uid[other].display_name == "SF Lead Sibling"


@pytest.mark.asyncio
async def test_service_household_includes_hint_only_siblings() -> None:
    """ENG-542: a Salesforce-lead sibling surfaced ONLY by the hint resolver
    (no identifier row, never merged) still appears in the unioned result."""
    from unittest.mock import AsyncMock

    from packages.ingest.service import IngestService

    hint_sibling = str(uuid.uuid4())
    svc = IngestService(MagicMock())
    svc._repo = MagicMock()  # type: ignore[attr-defined]
    svc._repo.person_household_members = AsyncMock(return_value=[])
    svc._repo.person_household_members_by_identifier = AsyncMock(return_value=[])
    svc._repo.person_household_members_by_hint = AsyncMock(
        return_value=[
            {
                "person_uid": hint_sibling,
                "display_name": "Lead Duplicate",
                "shared_via": "phone",
                "shared_value_masked": "···7719",
            }
        ]
    )
    out = await svc.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())
    assert [o.person_uid for o in out] == [hint_sibling]
    assert out[0].shared_via == "phone"
    assert out[0].shared_value_masked == "···7719"


@pytest.mark.asyncio
async def test_service_household_hint_loses_to_identifier_on_conflict() -> None:
    """When the SAME sibling is surfaced by both the identifier and hint
    resolvers, the identifier row (listed first) wins — first-write-wins
    precedence: CareStack > identifier > hint."""
    from unittest.mock import AsyncMock

    from packages.ingest.service import IngestService

    shared = str(uuid.uuid4())
    svc = IngestService(MagicMock())
    svc._repo = MagicMock()  # type: ignore[attr-defined]
    svc._repo.person_household_members = AsyncMock(return_value=[])
    svc._repo.person_household_members_by_identifier = AsyncMock(
        return_value=[
            {
                "person_uid": shared,
                "display_name": "Identifier Name",
                "shared_via": "phone",
                "shared_value_masked": "···5438",
            }
        ]
    )
    svc._repo.person_household_members_by_hint = AsyncMock(
        return_value=[
            {
                "person_uid": shared,
                "display_name": "Hint Name",
                "shared_via": "email",
                "shared_value_masked": "h···@x.com",
            }
        ]
    )
    out = await svc.person_household_members(TenantId(uuid.uuid4()), uuid.uuid4())
    assert len(out) == 1
    assert out[0].display_name == "Identifier Name"  # identifier won
