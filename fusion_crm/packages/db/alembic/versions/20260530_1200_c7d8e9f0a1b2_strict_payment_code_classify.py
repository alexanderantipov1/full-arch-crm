"""Strict payment-code classification — delete spurious payment events
and reclassify mislabeled ones (ENG-284).

ENG-283 introduced an ``isReversed`` override that flipped EVERY
``isReversed=true`` accounting-transaction row to ``payment_reversed``,
regardless of the row's ``transactionCode``. Reversed CHARGES
(``PROCEDURECOMPLETED``) and reversed ADJUSTMENTS
(``PATIENTADJUSTMENT``) therefore landed in ``interaction.event`` as
``payment_reversed``. The dashboard's Collected aggregate is
``sum(payment_recorded) − sum(payment_refunded + payment_reversed)``,
so those ~$110k of reversed non-payments were SUBTRACTED from
Collected and the local Project Manager Payments page Collected total
went NEGATIVE (−$71,934 vs the real ~+$11,538).

The runtime emit was tightened to a strict allow-list in the same
mission (see
``packages/ingest/carestack_accounting_transaction_service.py``). This
migration fixes the in-flight data the old emit wrote in three
ordered server-side passes:

1. ``DELETE`` every payment-kind ``interaction.event`` whose linked
   ``ingest.raw_event`` carries a ``transactionCode`` that is NOT in
   the payment allow-list. These are spurious — they should never
   have been emitted in the first place
   (``PROCEDURECOMPLETED`` / ``PATIENTADJUSTMENT`` / ``FEEUPDATION``,
   unknown codes, or rows with no ``transactionCode`` at all).
2. ``DELETE`` payment-kind events whose ``kind`` is wrong AND a
   correctly-classified sibling already exists at the same
   ``(tenant_id, source_provider, source_kind, source_external_id)``
   under the correct ``kind``. These show up in local dev where the
   ENG-283 emit wrote one row and a later re-pull (after the
   ENG-283 reclassify migration) wrote the correct sibling. The
   ENG-269 cross-pull partial UNIQUE on
   ``(tenant_id, source_provider, source_kind, source_external_id,
   kind)`` would block the step-3 UPDATE from converging them
   otherwise; this pass clears the duplicates first.
3. ``UPDATE`` every remaining payment-kind event so its ``kind``
   matches the allow-list mapping for its actual ``transactionCode``.
   The ``isReversed`` override applies ONLY to cash codes
   (``PATIENTPAYMENTS`` / ``INSURANCEPAYMENTS`` / refund codes) —
   allocation reversals (``PATPAYMENTAPPLIED`` / ``INSPAYMENTAPPLIED``)
   stay at ``payment_applied``, because their cash counterpart is
   the paired ``PATIENTPAYMENTSDELETE`` row. This corrects ENG-283
   mislabels, the local re-pollution where ``PATPAYMENTAPPLIED``
   rows landed in ``payment_recorded``, and the 70 reversed
   ``PATPAYMENTAPPLIED`` rows that ENG-283 wrote as
   ``payment_reversed`` (and that would otherwise pull Collected
   negative by ~$40k via the double-entry allocation leg).

Idempotency:

* All three statements are naturally idempotent — re-running this
  migration on the same data is a no-op.
* The DELETE in step 1 only matches rows whose linked raw still has
  a non-payment code; once the row is gone, the next run finds
  nothing to delete.
* The DELETE in step 2 only matches a row that still has a wrong
  kind AND still has a correctly-classified sibling; step 3 then
  removes the wrong kind so the row no longer qualifies on the
  next pass.
* The UPDATE in step 3 only flips ``kind`` when the current value
  differs from the target derived from the joined raw.

Downgrade:

``downgrade()`` is a documented no-op. The DELETE side cannot be
reversed — the rows it removes are spurious copies of forensic data
that still lives intact in ``ingest.raw_event``. An operator who needs
the pre-strict shape can replay from ``ingest.raw_event`` (the
forensic record is untouched). Reversing the UPDATE side would
re-introduce the known-wrong ENG-283 classifications and is not
useful. The append-only exception is recorded in the mission
``decision-log.md`` — same precedent as ENG-269's dedup DELETE,
ENG-270's location backfill UPDATE, and ENG-283's reclassify UPDATE.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-05-30 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "b6c7d8e9f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# These constants mirror ``_PAYMENT_CODE_TO_KIND`` /
# ``_REFUND_TRANSACTION_CODES`` in
# ``packages/ingest/carestack_accounting_transaction_service.py``.
# They are duplicated here intentionally so the migration is
# self-contained and stable against future runtime refactors.
_RECORDED_CODES: tuple[str, ...] = ("PATIENTPAYMENTS", "INSURANCEPAYMENTS")
_APPLIED_CODES: tuple[str, ...] = ("PATPAYMENTAPPLIED", "INSPAYMENTAPPLIED")
_DELETE_CODES: tuple[str, ...] = ("PATIENTPAYMENTSDELETE",)
_REFUND_CODES: tuple[str, ...] = ("REFUND", "PATIENTREFUND", "INSURANCEREFUND")
# ENG-284: ``isReversed=true`` only flips CASH codes (recorded /
# refund) to ``payment_reversed``. Allocation reversals stay as
# ``payment_applied``; PATIENTPAYMENTSDELETE stays as
# ``payment_reversed`` via its own code mapping.
_CASH_REVERSAL_CODES: tuple[str, ...] = _RECORDED_CODES + _REFUND_CODES

PAYMENT_KINDS: tuple[str, ...] = (
    "payment_recorded",
    "payment_applied",
    "payment_refunded",
    "payment_reversed",
)

# Code-set used by the SQL IN clauses below.
_ALL_PAYMENT_CODES: tuple[str, ...] = (
    _RECORDED_CODES + _APPLIED_CODES + _DELETE_CODES + _REFUND_CODES
)


def _sql_in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# Reused CASE that derives the strict-allow-list target kind from a
# raw event's payload. ``r_alias`` is the SQL alias of the
# ``ingest.raw_event`` row in the surrounding query.
#
# Cash codes (PATIENTPAYMENTS / INSURANCEPAYMENTS / refund codes)
# flip to ``payment_reversed`` when ``isReversed=true``. Allocation
# codes (PATPAYMENTAPPLIED / INSPAYMENTAPPLIED) keep their mapped
# kind regardless of the flag (a reversed allocation is still an
# allocation; the paired PATIENTPAYMENTSDELETE row carries the cash
# reversal). PATIENTPAYMENTSDELETE always maps to ``payment_reversed``
# from its own code.
def _target_kind_case(r_alias: str) -> str:
    is_reversed = (
        f"COALESCE(NULLIF(lower({r_alias}.payload->>'isReversed'), ''), 'false') = 'true'"
    )
    code = f"upper({r_alias}.payload->>'transactionCode')"
    return f"""
        CASE
            WHEN {code} IN ({_sql_in(_RECORDED_CODES)}) AND {is_reversed}
                THEN 'payment_reversed'
            WHEN {code} IN ({_sql_in(_REFUND_CODES)}) AND {is_reversed}
                THEN 'payment_reversed'
            WHEN {code} IN ({_sql_in(_RECORDED_CODES)})
                THEN 'payment_recorded'
            WHEN {code} IN ({_sql_in(_APPLIED_CODES)})
                THEN 'payment_applied'
            WHEN {code} IN ({_sql_in(_REFUND_CODES)})
                THEN 'payment_refunded'
            WHEN {code} IN ({_sql_in(_DELETE_CODES)})
                THEN 'payment_reversed'
        END
    """.strip()


# 1. DELETE spurious payment events — payment-kind rows whose joined
#    raw_event has a transactionCode that is NOT in the payment
#    allow-list. The exclusion also catches missing / NULL codes
#    (``r.payload->>'transactionCode'`` is NULL when the key is absent
#    or the value is JSON null), so reversed rows without a code are
#    deleted too. We restrict to the CareStack accounting-transaction
#    source so the DELETE never touches payment events from any other
#    future source.
DELETE_SPURIOUS_PAYMENT_EVENTS_SQL = f"""
DELETE FROM interaction.event AS e
USING ingest.raw_event AS r
WHERE e.source_event_id = r.id
  AND r.tenant_id = e.tenant_id
  AND e.source_provider = 'carestack'
  AND e.source_kind = 'carestack_accounting_transaction'
  AND e.kind IN ({_sql_in(PAYMENT_KINDS)})
  AND (
        r.payload->>'transactionCode' IS NULL
        OR upper(r.payload->>'transactionCode') NOT IN ({_sql_in(_ALL_PAYMENT_CODES)})
      );
"""

# 2. DELETE wrong-kind duplicates whose correctly-classified sibling
#    already exists. ENG-269's cross-pull partial UNIQUE on
#    ``(tenant_id, source_provider, source_kind, source_external_id,
#    kind)`` allows the SAME accounting-transaction id to hold rows
#    under multiple kinds (because ``kind`` is part of the key); when
#    the old emit wrote a wrong-kind row AND a later re-pull added
#    the correct-kind one, both survive that UNIQUE. The step-3
#    UPDATE would collide trying to converge them, so this pass drops
#    the legacy wrong-kind row first. The keeper is the row whose
#    ``kind`` already matches the allow-list mapping for its raw.
DELETE_DUPLICATE_MISCLASSIFIED_EVENTS_SQL = f"""
DELETE FROM interaction.event AS e
USING ingest.raw_event AS r
WHERE e.source_event_id = r.id
  AND r.tenant_id = e.tenant_id
  AND e.source_provider = 'carestack'
  AND e.source_kind = 'carestack_accounting_transaction'
  AND e.kind IN ({_sql_in(PAYMENT_KINDS)})
  AND upper(r.payload->>'transactionCode') IN ({_sql_in(_ALL_PAYMENT_CODES)})
  AND e.kind <> ({_target_kind_case("r")})
  AND EXISTS (
        SELECT 1
        FROM interaction.event AS sibling
        WHERE sibling.tenant_id = e.tenant_id
          AND sibling.source_provider = e.source_provider
          AND sibling.source_kind = e.source_kind
          AND sibling.source_external_id = e.source_external_id
          AND sibling.kind = ({_target_kind_case("r")})
          AND sibling.id <> e.id
      );
"""

# 3. UPDATE remaining payment events so ``kind`` matches the allow-list
#    mapping for the joined raw's ``transactionCode``. Reversed rows
#    are mapped to ``payment_reversed`` — but only because step 1
#    already deleted reversed non-payment rows, so a survivor with
#    ``isReversed=true`` is guaranteed to be a real reversed payment.
#
#    The CASE collapses (code, isReversed) into one of the four
#    payment kinds. The outer ``WHERE e.kind <> target`` makes the
#    UPDATE idempotent: a row that already carries the correct kind
#    is filtered out and not rewritten. The two outer guards
#    (``upper(...) IN (...)`` and ``e.kind IN (...)``) keep the row
#    set tight and let PostgreSQL prune the join.
RECLASSIFY_PAYMENT_EVENTS_SQL = f"""
UPDATE interaction.event AS e
SET kind = sub.target_kind
FROM (
    SELECT
        e2.id AS event_id,
        ({_target_kind_case("r2")}) AS target_kind
    FROM interaction.event AS e2
    JOIN ingest.raw_event AS r2
      ON r2.id = e2.source_event_id
     AND r2.tenant_id = e2.tenant_id
    WHERE e2.source_provider = 'carestack'
      AND e2.source_kind = 'carestack_accounting_transaction'
      AND e2.kind IN ({_sql_in(PAYMENT_KINDS)})
      AND upper(r2.payload->>'transactionCode') IN ({_sql_in(_ALL_PAYMENT_CODES)})
) AS sub
WHERE e.id = sub.event_id
  AND sub.target_kind IS NOT NULL
  AND e.kind <> sub.target_kind;
"""


def upgrade() -> None:
    # Order matters: delete the spurious rows first, then drop any
    # wrong-kind duplicates of an already-correct sibling, THEN
    # UPDATE survivors — so the UPDATE never has to fight the
    # cross-pull UNIQUE on (tenant_id, source_provider, source_kind,
    # source_external_id, kind).
    op.execute(DELETE_SPURIOUS_PAYMENT_EVENTS_SQL)
    op.execute(DELETE_DUPLICATE_MISCLASSIFIED_EVENTS_SQL)
    op.execute(RECLASSIFY_PAYMENT_EVENTS_SQL)


def downgrade() -> None:
    # Intentional no-op. The DELETE side removes spurious payment
    # events whose forensic record still lives in ``ingest.raw_event``;
    # we cannot fabricate the original ``interaction.event`` UUIDs,
    # source_event_id links, occurred_at, or payloads on downgrade
    # without corrupting cross-references. The UPDATE side cannot
    # meaningfully be reversed either — restoring it would reinstate
    # the known-wrong ENG-283 classifications. See the module
    # docstring for the replay path via ``ingest.raw_event``.
    pass
