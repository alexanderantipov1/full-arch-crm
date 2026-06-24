"""Idempotent interaction.event emission — dedupe + cross-pull partial UNIQUE.

ENG-269. Re-pulls were duplicating timeline events x N (measured x5 against
the local CareStack ingest), because every pull captures a new
``ingest.raw_event`` (and therefore a new ``source_event_id``) so the
legacy partial UNIQUE on ``(source_provider, source_event_id)`` could
never catch the duplicate. This revision fixes the event layer:

1. ``upgrade()`` deletes existing duplicate ``interaction.event`` rows,
   keeping the earliest row per
   ``(tenant_id, source_provider, source_kind, source_external_id,
   kind)`` where ``source_external_id`` AND ``source_kind`` are both
   NOT NULL (earliest by ``created_at`` ASC, tie-broken by ``id`` ASC).
   The DELETE runs server-side via a single window-function statement so
   no Python iteration is needed.

2. ``upgrade()`` adds a partial UNIQUE INDEX
   ``uq_event_provider_source_kind`` on the same key, scoped
   ``WHERE source_external_id IS NOT NULL``. Future re-pulls hit
   ``ON CONFLICT DO NOTHING`` (via ``InteractionService.create_event_idempotent``
   running inside a SAVEPOINT) and become no-ops; the ``ingest.raw_event``
   capture from the same pull survives the savepoint rollback.

3. ``downgrade()`` drops the index. It does NOT resurrect deleted rows
   — the data fix is permanent. If anyone needs the duplicates back,
   replay from ``ingest.raw_event`` (the forensic record is intact).

The DELETE is a one-time migration-level data fix. The runtime
``InteractionService`` stays append-only — no update/delete methods are
exposed on the service layer. This exception is logged in
``.agents/orchestration/interaction-event-idempotency-v1/decision-log.md``.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-05-30 06:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX_NAME = "uq_event_provider_source_kind"

# Single statement, server-side dedup. ``row_number()`` partitions by the
# dedup key (only over rows the new index would actually enforce — i.e.
# rows where both ``source_external_id`` and ``source_kind`` are NOT
# NULL) and orders by oldest-first with id as the tie-breaker. Every row
# beyond rn=1 is deleted.
_DEDUPE_SQL = """
DELETE FROM interaction.event AS dup
USING (
    SELECT id
    FROM (
        SELECT
            id,
            row_number() OVER (
                PARTITION BY tenant_id,
                             source_provider,
                             source_kind,
                             source_external_id,
                             kind
                ORDER BY created_at ASC, id ASC
            ) AS rn
        FROM interaction.event
        WHERE source_external_id IS NOT NULL
          AND source_kind IS NOT NULL
    ) ranked
    WHERE ranked.rn > 1
) AS losers
WHERE dup.id = losers.id;
"""


def upgrade() -> None:
    op.execute(_DEDUPE_SQL)
    op.create_index(
        _INDEX_NAME,
        "event",
        [
            "tenant_id",
            "source_provider",
            "source_kind",
            "source_external_id",
            "kind",
        ],
        unique=True,
        schema="interaction",
        postgresql_where="source_external_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="event", schema="interaction")
