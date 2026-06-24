"""Read-only diagnostic: do leads and consultations share persons? (ENG-402)

The lead-sources explorer joins ``ops.consultation`` / payment events to
``ops.lead`` via ``person_uid``. If provider ingests created SEPARATE
identity.person rows for the same human (lead-person vs patient-person),
every funnel join silently returns ~nothing. This script measures that
linkage so the fix (identity merge backfill / projection replay) is chosen
on facts, not guesses.

Usage (local or via the Cloud Run job image):

    python3 infra/scripts/diagnose_funnel_linkage.py

Prints aggregate counts only — no PHI beyond normalized-identifier overlap
counts, no row dumps.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from packages.db.session import SessionFactory

_QUERIES: list[tuple[str, str]] = [
    ("persons total", "SELECT count(*) FROM identity.person"),
    ("persons with >=1 lead", "SELECT count(DISTINCT person_uid) FROM ops.lead"),
    (
        "persons with >=1 consultation",
        "SELECT count(DISTINCT person_uid) FROM ops.consultation",
    ),
    (
        "persons with lead AND consultation",
        """
        SELECT count(*) FROM (
            SELECT person_uid FROM ops.lead
            INTERSECT
            SELECT person_uid FROM ops.consultation
        ) AS joined
        """,
    ),
    ("consultations total", "SELECT count(*) FROM ops.consultation"),
    (
        "consultations by status",
        """
        SELECT string_agg(status || '=' || cnt::text, ', ' ORDER BY status)
        FROM (
            SELECT status, count(*) AS cnt FROM ops.consultation GROUP BY status
        ) AS s
        """,
    ),
    (
        "consultations with location_id",
        "SELECT count(*) FROM ops.consultation WHERE location_id IS NOT NULL",
    ),
    (
        "persons with payment events",
        """
        SELECT count(DISTINCT person_uid) FROM interaction.event
        WHERE kind IN ('payment_recorded', 'payment_refunded', 'payment_reversed')
          AND data_class = 'billing'
        """,
    ),
    (
        "payment persons that also have a lead",
        """
        SELECT count(*) FROM (
            SELECT DISTINCT person_uid FROM interaction.event
            WHERE kind IN ('payment_recorded', 'payment_refunded', 'payment_reversed')
              AND data_class = 'billing'
            INTERSECT
            SELECT person_uid FROM ops.lead
        ) AS joined
        """,
    ),
    (
        # The identity-split detector: one normalized identifier value owned
        # by TWO different persons, one carrying a lead and one carrying a
        # consultation. Non-zero here = merge backfill needed.
        "split identities (same identifier, lead-person != patient-person)",
        """
        SELECT count(*) FROM (
            SELECT pi.value
            FROM identity.person_identifier pi
            JOIN ops.lead l ON l.person_uid = pi.person_id
            INTERSECT
            SELECT pi2.value
            FROM identity.person_identifier pi2
            JOIN ops.consultation c ON c.person_uid = pi2.person_id
            EXCEPT
            SELECT pi3.value
            FROM identity.person_identifier pi3
            WHERE EXISTS (SELECT 1 FROM ops.lead l3 WHERE l3.person_uid = pi3.person_id)
              AND EXISTS (
                SELECT 1 FROM ops.consultation c3 WHERE c3.person_uid = pi3.person_id
              )
        ) AS split_values
        """,
    ),
]


async def main() -> None:
    async with SessionFactory() as session:
        for label, sql in _QUERIES:
            value = (await session.execute(text(sql))).scalar()
            print(f"{label}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
